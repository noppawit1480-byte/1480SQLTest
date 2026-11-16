from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bookmark, Course, Exercise, Lesson, LessonProgress, Note, User
from app.schemas import LessonProgressIn, NoteIn
from app.security import get_current_user, get_optional_user
from app.services import progress

router = APIRouter(prefix="/api", tags=["learning"])


def _progress_map(db: Session, user: User | None) -> dict[int, str]:
    if user is None:
        return {}
    return dict(db.execute(select(LessonProgress.lesson_id, LessonProgress.status)
                           .where(LessonProgress.user_id == user.id)).all())


@router.get("/courses")
def list_courses(db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    pm = _progress_map(db, user)
    out = []
    for c in db.scalars(select(Course).order_by(Course.position)):
        lessons = c.lessons
        done = sum(1 for lesson in lessons if pm.get(lesson.id) == "completed")
        out.append({"slug": c.slug, "title": c.title, "level": c.level, "description": c.description,
                    "lesson_count": len(lessons), "completed": done,
                    "percent": round(100 * done / len(lessons)) if lessons else 0,
                    "first_lesson": lessons[0].slug if lessons else None})
    return out


@router.get("/courses/{slug}")
def get_course(slug: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    c = db.scalar(select(Course).where(Course.slug == slug))
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบหลักสูตร")
    pm = _progress_map(db, user)
    ex_counts = dict(db.execute(select(Exercise.lesson_id, Exercise.id).where(
        Exercise.lesson_id.in_([lesson.id for lesson in c.lessons]))).all())
    lessons = [{"slug": lesson.slug, "title": lesson.title, "summary": lesson.summary, "position": lesson.position,
                "status": pm.get(lesson.id, "not_started"), "has_exercise": lesson.id in ex_counts}
               for lesson in c.lessons]
    done = sum(1 for x in lessons if x["status"] == "completed")
    return {"slug": c.slug, "title": c.title, "level": c.level, "description": c.description, "lessons": lessons,
            "completed": done, "percent": round(100 * done / len(lessons)) if lessons else 0}


def _lesson_or_404(db: Session, slug: str) -> Lesson:
    lesson = db.scalar(select(Lesson).where(Lesson.slug == slug))
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบบทเรียน")
    return lesson


@router.get("/lessons/{slug}")
def get_lesson(slug: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    lesson = _lesson_or_404(db, slug)
    course = lesson.course
    ordered = db.execute(select(Lesson.slug, Lesson.title, Course.slug).join(Course)
                         .order_by(Course.position, Lesson.position)).all()
    idx = next(i for i, r in enumerate(ordered) if r[0] == slug)
    nav = lambda r: {"slug": r[0], "title": r[1], "course_slug": r[2]} if r else None  # noqa: E731
    related = db.execute(select(Lesson.slug, Lesson.title, Course.slug).join(Course)
                         .where(Lesson.slug.in_(lesson.related_slugs or []))).all()
    exercises = db.execute(select(Exercise.code, Exercise.title, Exercise.difficulty).where(
        Exercise.lesson_id == lesson.id).order_by(Exercise.position)).all()
    status_, bookmarked, note = "not_started", False, ""
    if user is not None:
        lp = db.get(LessonProgress, (user.id, lesson.id))
        status_ = lp.status if lp else "not_started"
        bookmarked = db.get(Bookmark, (user.id, lesson.id)) is not None
        n = db.get(Note, (user.id, lesson.id))
        note = n.body if n else ""
    return {
        "slug": lesson.slug, "title": lesson.title, "summary": lesson.summary, "objectives": lesson.objectives,
        "content_md": lesson.content_md, "examples": lesson.examples, "common_mistakes": lesson.common_mistakes,
        "sample_db": lesson.sample_db, "position": lesson.position,
        "course": {"slug": course.slug, "title": course.title, "level": course.level,
                   "lessons": [{"slug": x.slug, "title": x.title} for x in course.lessons]},
        "prev": nav(ordered[idx - 1]) if idx > 0 else None,
        "next": nav(ordered[idx + 1]) if idx + 1 < len(ordered) else None,
        "related": [nav(r) for r in related],
        "exercises": [{"code": c, "title": t, "difficulty": d} for c, t, d in exercises],
        "status": status_, "bookmarked": bookmarked, "note": note,
    }


@router.post("/lessons/{slug}/progress")
def set_progress(slug: str, body: LessonProgressIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    lesson = _lesson_or_404(db, slug)
    now = datetime.now(UTC)
    lp = db.get(LessonProgress, (user.id, lesson.id))
    if lp is None:
        lp = LessonProgress(user_id=user.id, lesson_id=lesson.id, status=body.status, started_at=now, updated_at=now)
        db.add(lp)
    elif not (lp.status == "completed" and body.status == "in_progress"):  # never downgrade
        lp.status = body.status
    lp.updated_at = now
    if body.status == "completed" and lp.completed_at is None:
        lp.completed_at = now
    progress.record_activity(db, user.id)
    db.flush()
    new = progress.evaluate_achievements(db, user.id)
    db.commit()
    return {"status": lp.status, "new_achievements": new}


@router.put("/lessons/{slug}/bookmark", status_code=204)
def add_bookmark(slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = _lesson_or_404(db, slug)
    db.execute(pg_insert(Bookmark).values(user_id=user.id, lesson_id=lesson.id).on_conflict_do_nothing())
    db.commit()


@router.delete("/lessons/{slug}/bookmark", status_code=204)
def remove_bookmark(slug: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = _lesson_or_404(db, slug)
    b = db.get(Bookmark, (user.id, lesson.id))
    if b:
        db.delete(b)
        db.commit()


@router.put("/lessons/{slug}/note")
def save_note(slug: str, body: NoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lesson = _lesson_or_404(db, slug)
    n = db.get(Note, (user.id, lesson.id))
    if not body.body.strip():
        if n:
            db.delete(n)
            db.commit()
        return {"body": ""}
    if n is None:
        n = Note(user_id=user.id, lesson_id=lesson.id, body=body.body)
        db.add(n)
    n.body, n.updated_at = body.body, datetime.now(UTC)
    db.commit()
    return {"body": n.body, "updated_at": n.updated_at.isoformat()}
