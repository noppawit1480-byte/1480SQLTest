"""Provision the sandbox and seed platform content.

    python -m app.seed            # idempotent: upserts content, recomputes example & expected results
    python -m app.seed --rebuild  # also rebuilds the sandbox template databases

Example results and exercise expected results are produced by *executing* the SQL on the
sandbox — if any solution fails, seeding aborts with a clear error (content is tested on every seed).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import asdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.content import COURSES, SAMPLE_DATABASES
from app.content.exercises import ALL as EXERCISES
from app.content.model import POINTS
from app.db import SessionLocal
from app.models import Achievement, Course, Exercise, Lesson, SampleDatabase, User
from app.security import hash_password
from app.services.progress import ACHIEVEMENTS
from app.services.sandbox.base import ExecutionResult
from app.services.sandbox.postgres import SYSTEM_USER_ID, get_sandbox

log = logging.getLogger("seed")
PREVIEW_ROWS = 10


class SeedError(RuntimeError):
    pass


def _preview(r: ExecutionResult) -> dict:
    last = r.last_rows
    out = {"ok": r.ok, "exec_ms": r.exec_ms,
           "commands": [rs.command for rs in r.result_sets]}
    if last:
        out.update(columns=[asdict(c) for c in last.columns], rows=last.rows[:PREVIEW_ROWS],
                   row_count=last.row_count, truncated=last.truncated or last.row_count > PREVIEW_ROWS)
    if r.error:
        out["error"] = {"message": r.error.message, "detail": r.error.detail, "sqlstate": r.error.sqlstate}
    return out


def validate_content() -> None:
    slugs = [lesson.slug for c in COURSES for lesson in c.lessons]
    if len(slugs) != len(set(slugs)):
        raise SeedError("duplicate lesson slugs")
    known = set(slugs)
    for c in COURSES:
        for lesson in c.lessons:
            missing = [r for r in lesson.related if r not in known]
            if missing:
                raise SeedError(f"lesson {lesson.slug}: unknown related slugs {missing}")
    codes = [e.code for e in EXERCISES]
    if len(codes) != len(set(codes)):
        raise SeedError("duplicate exercise codes")
    for e in EXERCISES:
        if len(e.hints) != 3:
            raise SeedError(f"{e.code}: must have exactly 3 hints")
        if e.lesson and e.lesson not in known:
            raise SeedError(f"{e.code}: unknown lesson {e.lesson}")
        if e.difficulty not in POINTS:
            raise SeedError(f"{e.code}: bad difficulty")
        if e.check_type == "dml" and not e.check_sql:
            raise SeedError(f"{e.code}: dml exercise needs check_sql")
    without = known - {e.lesson for e in EXERCISES}
    if without:
        raise SeedError(f"lessons without an end-of-lesson exercise: {sorted(without)}")


def seed(db: Session, rebuild: bool = False) -> None:
    validate_content()
    sb = get_sandbox()
    created = sb.provision_templates(force=rebuild)
    log.info("sandbox templates ready (created: %s)", created or "none")
    sb.ensure_role(SYSTEM_USER_ID)

    for i, (key, name, desc) in enumerate(SAMPLE_DATABASES):
        row = db.get(SampleDatabase, key) or SampleDatabase(key=key)
        row.name, row.description, row.position, row.engine = name, desc, i, "postgresql"
        db.merge(row)
    for i, (key, title, desc, icon) in enumerate(ACHIEVEMENTS):
        db.merge(Achievement(key=key, title=title, description=desc, icon=icon, position=i))
    db.flush()

    lesson_ids: dict[str, int] = {}
    for ci, cdef in enumerate(COURSES):
        course = db.scalar(select(Course).where(Course.slug == cdef.slug)) or Course(slug=cdef.slug)
        course.title, course.level, course.description, course.position = cdef.title, cdef.level, cdef.description, ci
        db.add(course)
        db.flush()
        for li, ldef in enumerate(cdef.lessons):
            examples = []
            for ex in ldef.examples:
                db_key = ex.db or ldef.db
                if ex.writable:
                    res = sb.execute_on_fresh_copy(SYSTEM_USER_ID, db_key, ex.sql)
                else:
                    res = sb.execute(sb.readonly_target(db_key), ex.sql)
                if not res.ok and res.error and res.error.kind in ("internal", "limit"):
                    raise SeedError(f"lesson {ldef.slug} example '{ex.title}' failed: {res.error.message}")
                examples.append({"title": ex.title, "sql": ex.sql, "explain": ex.explain, "db": db_key,
                                 "writable": ex.writable, "result": _preview(res)})
            lesson = db.scalar(select(Lesson).where(Lesson.slug == ldef.slug)) or Lesson(slug=ldef.slug)
            lesson.course_id, lesson.title, lesson.summary = course.id, ldef.title, ldef.summary
            lesson.objectives, lesson.content_md = ldef.objectives, ldef.content.strip()
            lesson.examples = examples
            lesson.common_mistakes = [asdict(m) for m in ldef.mistakes]
            lesson.related_slugs, lesson.sample_db, lesson.position = ldef.related, ldef.db, li
            db.add(lesson)
            db.flush()
            lesson_ids[ldef.slug] = lesson.id
        log.info("course %s: %d lessons", cdef.slug, len(cdef.lessons))
    db.execute(delete(Lesson).where(Lesson.slug.not_in(list(lesson_ids))))

    failures = []
    for pos, xdef in enumerate(EXERCISES):
        if xdef.check_type == "dml":
            res = sb.execute_on_fresh_copy(SYSTEM_USER_ID, xdef.db, xdef.solution, xdef.check_sql)
        else:
            res = sb.execute(sb.readonly_target(xdef.db), xdef.solution)
        last = res.last_rows
        if not res.ok or last is None or last.truncated:
            failures.append(f"{xdef.code}: {res.error.message if res.error else 'no result set / truncated'}")
            continue
        ex = db.scalar(select(Exercise).where(Exercise.code == xdef.code)) or Exercise(code=xdef.code)
        ex.title, ex.description_md, ex.difficulty, ex.category = xdef.title, xdef.description.strip(), xdef.difficulty, xdef.category
        ex.points, ex.sample_db, ex.check_type = POINTS[xdef.difficulty], xdef.db, xdef.check_type
        ex.solution_sql, ex.check_sql, ex.order_matters = xdef.solution.strip(), xdef.check_sql, xdef.order_matters
        ex.check_column_names = xdef.check_column_names
        ex.expected = {"columns": [asdict(c) for c in last.columns], "rows": last.rows}
        ex.hints, ex.explanation_md = xdef.hints, xdef.explanation
        ex.lesson_id = lesson_ids.get(xdef.lesson) if xdef.lesson else None
        ex.position = pos
        db.add(ex)
    if failures:
        raise SeedError("exercise solutions failed:\n  " + "\n  ".join(failures))
    db.execute(delete(Exercise).where(Exercise.code.not_in([e.code for e in EXERCISES])))

    admin_email, admin_pw = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_pw:
        u = db.scalar(select(User).where(User.email == admin_email.lower()))
        if u is None:
            db.add(User(email=admin_email.lower(), display_name="Admin", password_hash=hash_password(admin_pw), role="admin"))
            log.info("created admin user %s", admin_email)
    db.commit()
    log.info("seed complete: %d lessons, %d exercises", len(lesson_ids), len(EXERCISES))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--rebuild", action="store_true", help="rebuild sandbox template databases")
    args = p.parse_args()
    with SessionLocal() as db:
        try:
            seed(db, rebuild=args.rebuild)
        except SeedError as e:
            log.error("%s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
