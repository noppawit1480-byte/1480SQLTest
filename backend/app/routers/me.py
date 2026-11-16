from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bookmark, Course, Lesson, Note, User
from app.schemas import HeartbeatIn
from app.security import get_current_user
from app.services import progress

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return progress.dashboard(db, user.id)


@router.post("/me/heartbeat")
def heartbeat(body: HeartbeatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Called by the frontend every 60s while a tab is visible — real learning time."""
    progress.record_activity(db, user.id, seconds=body.seconds, events=0)
    db.flush()
    new = progress.evaluate_achievements(db, user.id)
    db.commit()
    return {"ok": True, "new_achievements": new}


@router.get("/me/library")
def library(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    bms = db.execute(select(Lesson.slug, Lesson.title, Course.slug, Bookmark.created_at)
                     .join(Bookmark, Bookmark.lesson_id == Lesson.id).join(Course)
                     .where(Bookmark.user_id == user.id).order_by(Bookmark.created_at.desc())).all()
    notes = db.execute(select(Lesson.slug, Lesson.title, Course.slug, Note.body, Note.updated_at)
                       .join(Note, Note.lesson_id == Lesson.id).join(Course)
                       .where(Note.user_id == user.id).order_by(Note.updated_at.desc())).all()
    return {
        "bookmarks": [{"slug": s, "title": t, "course_slug": c, "created_at": at.isoformat()} for s, t, c, at in bms],
        "notes": [{"slug": s, "title": t, "course_slug": c, "body": b, "updated_at": at.isoformat()}
                  for s, t, c, b, at in notes],
    }
