"""Admin Panel API — every route requires role=admin (RBAC dependency on the router).

Content saved here is validated by executing it on the sandbox (same code path as the seeder) and is
marked `admin_edited`/`is_custom` so a later re-seed never overwrites or deletes it.
"""
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

from app.content.model import POINTS
from app.db import get_db
from app.models import (Achievement, ActivityDay, AssistantLog, Course, Exercise, Lesson, LessonProgress, Project,
                        SampleDatabase, Submission, User, UserAchievement, UserSession)
from app.routers.playground import readonly_schema
from app.security import require_role
from app.services import progress
from app.services.content import ContentError, compute_expected, run_example
from app.services.sandbox.postgres import get_sandbox

log = logging.getLogger("admin")
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])
admin_user = require_role("admin")
SLUG = r"^[a-z0-9][a-z0-9-]{1,78}$"
DBKEY = r"^[a-z][a-z0-9_]{1,30}$"


def audit(request: Request, admin: User, action: str, target: str) -> None:
    log.info("event=admin_action admin=%s action=%s target=%s rid=%s", admin.id, action, target,
             request.headers.get("x-request-id", "-"))


def _known_db(db: Session, key: str) -> None:
    if db.get(SampleDatabase, key) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"ไม่พบฐานข้อมูล {key}")


# ------------------------------------------------------------------ statistics
@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    today = progress.today_local()
    week = datetime.now(UTC) - timedelta(days=7)
    users = db.scalar(select(func.count()).select_from(User)) or 0
    new_users = db.scalar(select(func.count()).select_from(User).where(User.created_at >= week)) or 0
    active_today = db.scalar(select(func.count()).select_from(ActivityDay).where(ActivityDay.day == today)) or 0
    active_7d = db.scalar(select(func.count(distinct(ActivityDay.user_id))).where(ActivityDay.day >= today - timedelta(days=6))) or 0
    subs, correct = db.execute(select(func.count(), func.count().filter(Submission.is_correct))).one()
    lessons_done = db.scalar(select(func.count()).select_from(LessonProgress).where(LessonProgress.status == "completed")) or 0
    hardest = db.execute(
        select(Exercise.code, Exercise.title, func.count(), func.count().filter(Submission.is_correct),
               func.count(distinct(Submission.user_id)))
        .join(Submission, Submission.exercise_id == Exercise.id).group_by(Exercise.id)
        .having(func.count() >= 3).order_by((func.count().filter(Submission.is_correct) * 1.0 / func.count()).asc()).limit(8)).all()
    start = today - timedelta(days=13)
    day = func.date(func.timezone("Asia/Bangkok", Submission.created_at))
    per_day = dict((d, n) for d, n in db.execute(select(day, func.count()).where(day >= start).group_by(day)).all())
    signup_day = func.date(func.timezone("Asia/Bangkok", User.created_at))
    signups = dict((d, n) for d, n in db.execute(select(signup_day, func.count()).where(signup_day >= start).group_by(signup_day)).all())
    ai = db.execute(select(AssistantLog.provider, func.count(), func.coalesce(func.sum(AssistantLog.input_tokens), 0),
                           func.coalesce(func.sum(AssistantLog.output_tokens), 0))
                    .where(AssistantLog.created_at >= week).group_by(AssistantLog.provider)).all()
    return {
        "users": {"total": users, "new_7d": new_users, "active_today": active_today, "active_7d": active_7d},
        "submissions": {"total": subs, "correct": correct, "accuracy": round(100 * correct / subs, 1) if subs else None},
        "lessons_completed": lessons_done,
        "content": {"lessons": db.scalar(select(func.count()).select_from(Lesson)),
                    "exercises": db.scalar(select(func.count()).select_from(Exercise).where(Exercise.project_id.is_(None))),
                    "projects": db.scalar(select(func.count()).select_from(Project)),
                    "custom": db.scalar(select(func.count()).select_from(Exercise).where(Exercise.is_custom))},
        "hardest_exercises": [{"code": c, "title": t, "attempts": n, "correct": k, "learners": u,
                               "success_rate": round(100 * k / n, 1)} for c, t, n, k, u in hardest],
        "daily": [{"date": (start + timedelta(days=i)).isoformat(), "submissions": per_day.get(start + timedelta(days=i), 0),
                   "signups": signups.get(start + timedelta(days=i), 0)} for i in range(14)],
        "assistant_7d": [{"provider": p, "requests": n, "input_tokens": int(ti), "output_tokens": int(to)} for p, n, ti, to in ai],
    }


# ------------------------------------------------------------------ users
class UserPatch(BaseModel):
    role: Literal["learner", "admin"] | None = None
    is_active: bool | None = None


def _user_row(db: Session, u: User) -> dict:
    last = db.scalar(select(func.max(ActivityDay.day)).where(ActivityDay.user_id == u.id))
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role, "is_active": u.is_active,
            "created_at": u.created_at.isoformat(), "last_active": last.isoformat() if last else None,
            "points": progress.user_points(db, u.id), "solved": len(progress.solved_exercise_ids(db, u.id))}


@router.get("/users")
def list_users(q: str = "", page: int = 1, db: Session = Depends(get_db)):
    stmt = select(User)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where((func.lower(User.email).like(like)) | (func.lower(User.display_name).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(User.created_at.desc()).offset((max(page, 1) - 1) * 50).limit(50))
    return {"total": total, "page": page, "items": [_user_row(db, u) for u in rows]}


@router.get("/users/{uid}")
def user_detail(uid: int, db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบผู้ใช้")
    return {"user": _user_row(db, u), "progress": progress.dashboard(db, uid)}


@router.patch("/users/{uid}")
def update_user(uid: int, body: UserPatch, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบผู้ใช้")
    if u.id == admin.id and (body.role == "learner" or body.is_active is False):
        raise HTTPException(status.HTTP_409_CONFLICT, "ลดสิทธิ์หรือระงับบัญชีของตัวเองไม่ได้")
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
        if not body.is_active:  # revoke all sessions immediately
            db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    db.commit()
    audit(request, admin, "update_user", f"user:{uid} role={body.role} active={body.is_active}")
    return _user_row(db, u)


# ------------------------------------------------------------------ courses & lessons
class CoursePatch(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=2000)


class ExampleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    sql: str = Field(min_length=1, max_length=20000)
    explain: list[str] = Field(default_factory=list, max_length=30)
    db: str = Field(pattern=DBKEY)
    writable: bool = False


class MistakeIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    wrong: str = Field(max_length=5000)
    right: str = Field(max_length=5000)
    why: str = Field(max_length=2000)


class LessonIn(BaseModel):
    course_slug: str
    slug: str = Field(pattern=SLUG)
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=2, max_length=1000)
    objectives: list[str] = Field(default_factory=list, max_length=20)
    content_md: str = Field(min_length=1, max_length=100000)
    examples: list[ExampleIn] = Field(default_factory=list, max_length=12)
    common_mistakes: list[MistakeIn] = Field(default_factory=list, max_length=12)
    related_slugs: list[str] = Field(default_factory=list, max_length=12)
    sample_db: str | None = Field(default=None, pattern=DBKEY)
    position: int | None = None


@router.get("/courses")
def admin_courses(db: Session = Depends(get_db)):
    return [{"id": c.id, "slug": c.slug, "title": c.title, "level": c.level, "description": c.description,
             "lessons": [{"id": lsn.id, "slug": lsn.slug, "title": lsn.title, "position": lsn.position,
                          "is_custom": lsn.is_custom, "admin_edited": lsn.admin_edited} for lsn in c.lessons]}
            for c in db.scalars(select(Course).order_by(Course.position))]


@router.put("/courses/{cid}")
def update_course(cid: int, body: CoursePatch, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    c = db.get(Course, cid)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบหลักสูตร")
    c.title, c.description = body.title, body.description
    db.commit()
    audit(request, admin, "update_course", c.slug)
    return {"ok": True}


def _lesson_out(lsn: Lesson) -> dict:
    return {"id": lsn.id, "course_slug": lsn.course.slug, "slug": lsn.slug, "title": lsn.title, "summary": lsn.summary,
            "objectives": lsn.objectives, "content_md": lsn.content_md, "examples": lsn.examples,
            "common_mistakes": lsn.common_mistakes, "related_slugs": lsn.related_slugs, "sample_db": lsn.sample_db,
            "position": lsn.position, "is_custom": lsn.is_custom, "admin_edited": lsn.admin_edited}


@router.get("/lessons/{lid}")
def get_lesson(lid: int, db: Session = Depends(get_db)):
    lsn = db.get(Lesson, lid)
    if lsn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบทเรียน")
    return _lesson_out(lsn)


def _apply_lesson(db: Session, lsn: Lesson, body: LessonIn) -> None:
    course = db.scalar(select(Course).where(Course.slug == body.course_slug))
    if course is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ไม่พบหลักสูตร")
    dup = db.scalar(select(Lesson.id).where(Lesson.slug == body.slug, Lesson.id != (lsn.id or 0)))
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug นี้ถูกใช้แล้ว")
    for key in {e.db for e in body.examples} | ({body.sample_db} if body.sample_db else set()):
        _known_db(db, key)
    known = set(db.scalars(select(Lesson.slug)))
    bad = [r for r in body.related_slugs if r not in known]
    if bad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"ไม่พบบทเรียนที่เกี่ยวข้อง: {', '.join(bad)}")
    examples = []
    for i, ex in enumerate(body.examples, 1):
        try:
            result = run_example(ex.db, ex.sql, ex.writable)
        except ContentError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"ตัวอย่างที่ {i}: {e}") from None
        examples.append(ex.model_dump() | {"result": result})
    lsn.course_id, lsn.slug, lsn.title, lsn.summary = course.id, body.slug, body.title, body.summary
    lsn.objectives, lsn.content_md, lsn.examples = body.objectives, body.content_md, examples
    lsn.common_mistakes = [m.model_dump() for m in body.common_mistakes]
    lsn.related_slugs, lsn.sample_db = body.related_slugs, body.sample_db
    if body.position is not None:
        lsn.position = body.position
    elif lsn.position is None:
        lsn.position = (db.scalar(select(func.max(Lesson.position)).where(Lesson.course_id == course.id)) or 0) + 1
    lsn.admin_edited = True


@router.post("/lessons", status_code=201)
def create_lesson(body: LessonIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    lsn = Lesson(is_custom=True)
    _apply_lesson(db, lsn, body)
    db.add(lsn)
    db.commit()
    audit(request, admin, "create_lesson", lsn.slug)
    return _lesson_out(lsn)


@router.put("/lessons/{lid}")
def update_lesson(lid: int, body: LessonIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    lsn = db.get(Lesson, lid)
    if lsn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบทเรียน")
    _apply_lesson(db, lsn, body)
    db.commit()
    audit(request, admin, "update_lesson", lsn.slug)
    return _lesson_out(lsn)


@router.delete("/lessons/{lid}", status_code=204)
def delete_lesson(lid: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    lsn = db.get(Lesson, lid)
    if lsn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบทเรียน")
    if not lsn.is_custom:
        raise HTTPException(status.HTTP_409_CONFLICT, "บทเรียนหลักลบไม่ได้ (จะถูกสร้างใหม่ตอน seed) — แก้ไขเนื้อหาแทน")
    db.delete(lsn)
    db.commit()
    audit(request, admin, "delete_lesson", lsn.slug)


@router.post("/lessons/{lid}/revert")
def revert_lesson(lid: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    """Hand a seeded lesson back to content-as-code: the next seed restores the version in Git."""
    lsn = db.get(Lesson, lid)
    if lsn is None or lsn.is_custom:
        raise HTTPException(status.HTTP_409_CONFLICT, "ใช้ได้เฉพาะบทเรียนหลัก")
    lsn.admin_edited = False
    db.commit()
    audit(request, admin, "revert_lesson", lsn.slug)
    return {"ok": True, "message": "จะคืนค่าเป็นเวอร์ชันจาก repository เมื่อรัน seed ครั้งถัดไป"}


# ------------------------------------------------------------------ exercises (incl. project tasks)
CODE = r"^[A-Z0-9][A-Z0-9-]{2,19}$"


class ExerciseIn(BaseModel):
    code: str = Field(pattern=CODE)
    title: str = Field(min_length=2, max_length=160)
    description_md: str = Field(min_length=2, max_length=20000)
    difficulty: Literal["easy", "medium", "hard", "expert"]
    category: str = Field(min_length=2, max_length=40)
    points: int | None = Field(default=None, ge=1, le=500)
    sample_db: str = Field(pattern=DBKEY)
    check_type: Literal["select", "dml"] = "select"
    solution_sql: str = Field(min_length=1, max_length=20000)
    check_sql: str | None = Field(default=None, max_length=20000)
    order_matters: bool = False
    check_column_names: bool = True
    hints: list[str] = Field(min_length=3, max_length=3)
    explanation_md: str = Field(min_length=1, max_length=20000)
    lesson_slug: str | None = None
    project_slug: str | None = None

    @field_validator("code", mode="before")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("hints")
    @classmethod
    def _hints(cls, v: list[str]) -> list[str]:
        if any(not h.strip() for h in v):
            raise ValueError("ต้องมี Hint ครบ 3 ระดับ")
        return v


def _exercise_out(db: Session, e: Exercise, full: bool = True) -> dict:
    lesson = db.get(Lesson, e.lesson_id) if e.lesson_id else None
    proj = db.get(Project, e.project_id) if e.project_id else None
    d = {"id": e.id, "code": e.code, "title": e.title, "difficulty": e.difficulty, "category": e.category, "points": e.points,
         "sample_db": e.sample_db, "check_type": e.check_type, "lesson_slug": lesson.slug if lesson else None,
         "project_slug": proj.slug if proj else None, "is_custom": e.is_custom, "admin_edited": e.admin_edited}
    if full:
        d |= {"description_md": e.description_md, "solution_sql": e.solution_sql, "check_sql": e.check_sql,
              "order_matters": e.order_matters, "check_column_names": e.check_column_names, "hints": e.hints,
              "explanation_md": e.explanation_md,
              "expected": {"columns": e.expected.get("columns", []), "rows": e.expected.get("rows", [])[:20],
                           "row_count": len(e.expected.get("rows", []))}}
    return d


@router.get("/exercises")
def admin_exercises(project: str | None = None, db: Session = Depends(get_db)):
    q = select(Exercise).order_by(Exercise.project_id.nulls_first(), Exercise.position)
    if project:
        q = q.join(Project).where(Project.slug == project)
    return [_exercise_out(db, e, full=False) for e in db.scalars(q)]


@router.get("/exercises/{eid}")
def admin_exercise(eid: int, db: Session = Depends(get_db)):
    e = db.get(Exercise, eid)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโจทย์")
    return _exercise_out(db, e)


def _apply_exercise(db: Session, e: Exercise, body: ExerciseIn) -> None:
    _known_db(db, body.sample_db)
    if db.scalar(select(Exercise.id).where(Exercise.code == body.code, Exercise.id != (e.id or 0))):
        raise HTTPException(status.HTTP_409_CONFLICT, "รหัสโจทย์นี้ถูกใช้แล้ว")
    lesson_id = project_id = None
    if body.lesson_slug:
        lesson_id = db.scalar(select(Lesson.id).where(Lesson.slug == body.lesson_slug))
        if lesson_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ไม่พบบทเรียน")
    if body.project_slug:
        project_id = db.scalar(select(Project.id).where(Project.slug == body.project_slug))
        if project_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ไม่พบโปรเจกต์")
    try:
        expected = compute_expected(body.sample_db, body.check_type, body.solution_sql, body.check_sql)
    except ContentError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(err)) from None
    e.code, e.title, e.description_md, e.difficulty, e.category = body.code, body.title, body.description_md, body.difficulty, body.category
    e.points = body.points or POINTS[body.difficulty]
    e.sample_db, e.check_type, e.solution_sql = body.sample_db, body.check_type, body.solution_sql
    e.check_sql = body.check_sql if body.check_type == "dml" else None
    e.order_matters, e.check_column_names, e.hints, e.explanation_md = body.order_matters, body.check_column_names, body.hints, body.explanation_md
    e.lesson_id, e.project_id, e.expected = lesson_id, project_id, expected
    if e.position is None:
        e.position = (db.scalar(select(func.max(Exercise.position)).where(
            Exercise.project_id == project_id if project_id else Exercise.project_id.is_(None))) or 0) + 1
    e.admin_edited = True


@router.post("/exercises", status_code=201)
def create_exercise(body: ExerciseIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    e = Exercise(is_custom=True)
    _apply_exercise(db, e, body)
    db.add(e)
    db.commit()
    audit(request, admin, "create_exercise", e.code)
    return _exercise_out(db, e)


@router.put("/exercises/{eid}")
def update_exercise(eid: int, body: ExerciseIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    e = db.get(Exercise, eid)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโจทย์")
    _apply_exercise(db, e, body)
    db.commit()
    audit(request, admin, "update_exercise", e.code)
    return _exercise_out(db, e)


@router.delete("/exercises/{eid}", status_code=204)
def delete_exercise(eid: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    e = db.get(Exercise, eid)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโจทย์")
    if not e.is_custom:
        raise HTTPException(status.HTTP_409_CONFLICT, "โจทย์หลักลบไม่ได้ (จะถูกสร้างใหม่ตอน seed) — แก้ไขแทน")
    db.delete(e)
    db.commit()
    audit(request, admin, "delete_exercise", e.code)


@router.post("/exercises/validate")
def validate_exercise(body: ExerciseIn):
    """Dry run: execute the solution and return the expected result without saving."""
    try:
        exp = compute_expected(body.sample_db, body.check_type, body.solution_sql, body.check_sql)
    except ContentError as err:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(err)) from None
    return {"columns": exp["columns"], "rows": exp["rows"][:20], "row_count": len(exp["rows"])}


# ------------------------------------------------------------------ projects
class ProjectIn(BaseModel):
    slug: str = Field(pattern=SLUG)
    title: str = Field(min_length=2, max_length=160)
    role: str = Field(min_length=2, max_length=80)
    summary: str = Field(min_length=2, max_length=1000)
    brief_md: str = Field(min_length=2, max_length=50000)
    deliverables: list[str] = Field(default_factory=list, max_length=20)
    sample_db: str = Field(pattern=DBKEY)
    difficulty: Literal["easy", "medium", "hard", "expert"]


def _project_out(db: Session, p: Project) -> dict:
    n = db.scalar(select(func.count()).select_from(Exercise).where(Exercise.project_id == p.id))
    return {"id": p.id, "slug": p.slug, "title": p.title, "role": p.role, "summary": p.summary, "brief_md": p.brief_md,
            "deliverables": p.deliverables, "sample_db": p.sample_db, "difficulty": p.difficulty, "tasks": n,
            "is_custom": p.is_custom, "admin_edited": p.admin_edited}


@router.get("/projects")
def admin_projects(db: Session = Depends(get_db)):
    return [_project_out(db, p) for p in db.scalars(select(Project).order_by(Project.position))]


def _apply_project(db: Session, p: Project, body: ProjectIn) -> None:
    _known_db(db, body.sample_db)
    if db.scalar(select(Project.id).where(Project.slug == body.slug, Project.id != (p.id or 0))):
        raise HTTPException(status.HTTP_409_CONFLICT, "slug นี้ถูกใช้แล้ว")
    for f in ("slug", "title", "role", "summary", "brief_md", "deliverables", "sample_db", "difficulty"):
        setattr(p, f, getattr(body, f))
    if p.position is None:
        p.position = (db.scalar(select(func.max(Project.position))) or 0) + 1
    p.admin_edited = True


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    p = Project(is_custom=True)
    _apply_project(db, p, body)
    db.add(p)
    db.commit()
    audit(request, admin, "create_project", p.slug)
    return _project_out(db, p)


@router.put("/projects/{pid}")
def update_project(pid: int, body: ProjectIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    p = db.get(Project, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโปรเจกต์")
    _apply_project(db, p, body)
    db.commit()
    audit(request, admin, "update_project", p.slug)
    return _project_out(db, p)


@router.delete("/projects/{pid}", status_code=204)
def delete_project(pid: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    p = db.get(Project, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโปรเจกต์")
    if not p.is_custom:
        raise HTTPException(status.HTTP_409_CONFLICT, "โปรเจกต์หลักลบไม่ได้ — แก้ไขแทน")
    db.delete(p)  # tasks cascade (FK ON DELETE CASCADE)
    db.commit()
    audit(request, admin, "delete_project", p.slug)


# ------------------------------------------------------------------ achievements
class AchievementPatch(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=500)
    icon: str = Field(pattern=r"^[a-z][a-z-]{1,39}$")


@router.get("/achievements")
def admin_achievements(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(UserAchievement.achievement_key, func.count())
                             .group_by(UserAchievement.achievement_key)).all())
    return [{"key": a.key, "title": a.title, "description": a.description, "icon": a.icon, "earned_by": counts.get(a.key, 0)}
            for a in db.scalars(select(Achievement).order_by(Achievement.position))]


@router.put("/achievements/{key}")
def update_achievement(key: str, body: AchievementPatch, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    a = db.get(Achievement, key)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบ achievement")
    a.title, a.description, a.icon = body.title, body.description, body.icon
    db.commit()
    audit(request, admin, "update_achievement", key)
    return {"ok": True}


# ------------------------------------------------------------------ sample databases
class DatabasePatch(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=2, max_length=2000)


@router.get("/databases")
def admin_databases(db: Session = Depends(get_db)):
    out = []
    for d in db.scalars(select(SampleDatabase).order_by(SampleDatabase.position)):
        tables = readonly_schema(d.key)
        n_ex = db.scalar(select(func.count()).select_from(Exercise).where(Exercise.sample_db == d.key))
        out.append({"key": d.key, "name": d.name, "description": d.description, "engine": d.engine,
                    "tables": len(tables), "rows": sum(t["row_estimate"] for t in tables), "exercises": n_ex})
    return out


@router.put("/databases/{key}")
def update_database(key: str, body: DatabasePatch, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    d = db.get(SampleDatabase, key)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูล")
    d.name, d.description = body.name, body.description
    db.commit()
    audit(request, admin, "update_database", key)
    return {"ok": True}


@router.post("/databases/{key}/rebuild")
def rebuild_database(key: str, request: Request, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    """Rebuild the template + shared read-only copy, then recompute expected results of every exercise on
    it. Learners' writable sandboxes are not touched."""
    if db.get(SampleDatabase, key) is None or not re.match(DBKEY, key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูล")
    get_sandbox().provision_one(key, force=True)
    from app.services.sandbox.mysql_engine import get_mysql, mysql_enabled
    from app.services.sandbox.sqlite_engine import get_sqlite
    get_sqlite().export(key)
    if mysql_enabled():
        get_mysql().export(key)
    readonly_schema.cache_clear()
    failed = []
    for e in db.scalars(select(Exercise).where(Exercise.sample_db == key)):
        try:
            e.expected = compute_expected(e.sample_db, e.check_type, e.solution_sql, e.check_sql)
        except ContentError as err:
            failed.append({"code": e.code, "error": str(err)})
    db.commit()
    audit(request, admin, "rebuild_database", key)
    return {"ok": not failed, "rebuilt": key, "recomputed_failures": failed, "rebuilt_at": datetime.now(UTC).isoformat()}
