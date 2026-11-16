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
from app.content.projects import PROJECTS
from app.content.model import POINTS
from app.db import SessionLocal
from app.models import Achievement, Course, Exercise, Lesson, Project, SampleDatabase, User
from app.security import hash_password
from app.services.progress import ACHIEVEMENTS
from app.services.content import ContentError, compute_expected, run_example
from app.services.sandbox.postgres import SYSTEM_USER_ID, get_sandbox

log = logging.getLogger("seed")


class SeedError(RuntimeError):
    pass


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
    all_ex = EXERCISES + [t for p in PROJECTS for t in p.tasks]
    codes = [e.code for e in all_ex]
    if len(codes) != len(set(codes)):
        raise SeedError("duplicate exercise codes")
    for p in PROJECTS:
        if any(t.project != p.slug for t in p.tasks):
            raise SeedError(f"project {p.slug}: every task must set project='{p.slug}'")
    for e in all_ex:
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
                try:
                    result = run_example(db_key, ex.sql, ex.writable)
                except ContentError as e:
                    raise SeedError(f"lesson {ldef.slug} example '{ex.title}': {e}") from None
                examples.append({"title": ex.title, "sql": ex.sql, "explain": ex.explain, "db": db_key,
                                 "writable": ex.writable, "result": result})
            lesson = db.scalar(select(Lesson).where(Lesson.slug == ldef.slug)) or Lesson(slug=ldef.slug)
            if lesson.admin_edited:  # edited in the Admin Panel — the database copy wins
                lesson_ids[ldef.slug] = lesson.id
                continue
            lesson.course_id, lesson.title, lesson.summary = course.id, ldef.title, ldef.summary
            lesson.objectives, lesson.content_md = ldef.objectives, ldef.content.strip()
            lesson.examples = examples
            lesson.common_mistakes = [asdict(m) for m in ldef.mistakes]
            lesson.related_slugs, lesson.sample_db, lesson.position = ldef.related, ldef.db, li
            db.add(lesson)
            db.flush()
            lesson_ids[ldef.slug] = lesson.id
        log.info("course %s: %d lessons", cdef.slug, len(cdef.lessons))
    db.execute(delete(Lesson).where(Lesson.slug.not_in(list(lesson_ids)), Lesson.is_custom.is_(False),
                                    Lesson.admin_edited.is_(False)))

    project_ids: dict[str, int] = {}
    for i, pdef in enumerate(PROJECTS):
        proj = db.scalar(select(Project).where(Project.slug == pdef.slug)) or Project(slug=pdef.slug)
        if not proj.admin_edited:
            proj.title, proj.role, proj.summary, proj.brief_md = pdef.title, pdef.role, pdef.summary, pdef.brief.strip()
            proj.deliverables, proj.sample_db, proj.difficulty, proj.position = pdef.deliverables, pdef.db, pdef.difficulty, i
        db.add(proj)
        db.flush()
        project_ids[pdef.slug] = proj.id
    db.execute(delete(Project).where(Project.slug.not_in(list(project_ids)), Project.is_custom.is_(False),
                                     Project.admin_edited.is_(False)))

    failures = []
    task_pos = {t.code: i for p in PROJECTS for i, t in enumerate(p.tasks)}
    for pos, xdef in enumerate(EXERCISES + [t for p in PROJECTS for t in p.tasks]):
        existing = db.scalar(select(Exercise).where(Exercise.code == xdef.code))
        if existing is not None and existing.admin_edited:
            continue
        try:
            expected = compute_expected(xdef.db, xdef.check_type, xdef.solution, xdef.check_sql)
        except ContentError as e:
            failures.append(f"{xdef.code}: {e}")
            continue
        ex = existing or Exercise(code=xdef.code)
        ex.title, ex.description_md, ex.difficulty, ex.category = xdef.title, xdef.description.strip(), xdef.difficulty, xdef.category
        ex.points, ex.sample_db, ex.check_type = POINTS[xdef.difficulty], xdef.db, xdef.check_type
        ex.solution_sql, ex.check_sql, ex.order_matters = xdef.solution.strip(), xdef.check_sql, xdef.order_matters
        ex.check_column_names = xdef.check_column_names
        ex.expected = expected
        ex.hints, ex.explanation_md = xdef.hints, xdef.explanation
        ex.lesson_id = lesson_ids.get(xdef.lesson) if xdef.lesson else None
        ex.project_id = project_ids.get(xdef.project) if xdef.project else None
        ex.position = task_pos.get(xdef.code, pos)
        db.add(ex)
    if failures:
        raise SeedError("exercise solutions failed:\n  " + "\n  ".join(failures))
    seeded_codes = [e.code for e in EXERCISES] + [t.code for p in PROJECTS for t in p.tasks]
    db.execute(delete(Exercise).where(Exercise.code.not_in(seeded_codes), Exercise.is_custom.is_(False),
                                      Exercise.admin_edited.is_(False)))

    admin_email, admin_pw = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if admin_email and admin_pw:
        u = db.scalar(select(User).where(User.email == admin_email.lower()))
        if u is None:
            db.add(User(email=admin_email.lower(), display_name="Admin", password_hash=hash_password(admin_pw), role="admin"))
            log.info("created admin user %s", admin_email)
    db.commit()
    log.info("seed complete: %d lessons, %d exercises, %d projects (%d tasks)", len(lesson_ids), len(EXERCISES),
             len(PROJECTS), len(task_pos))


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
