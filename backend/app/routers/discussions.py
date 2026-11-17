"""Community discussion on exercises and lessons (Phase 3).

* Spoiler gating is enforced by the server: on an exercise, spoiler bodies are only sent to learners who
  have solved it, or who explicitly ask to reveal them.
* A post on an exercise that contains a ```sql block is always marked as a spoiler.
* One level of replies; votes are toggles; reports go to the admin moderation queue.
"""
import logging
import re
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Exercise, Lesson, Post, PostReport, PostVote, User
from app.ratelimit import check_rate
from app.security import get_current_user, get_optional_user, require_role
from app.services import progress

log = logging.getLogger("community")
router = APIRouter(prefix="/api", tags=["community"])
TargetType = Literal["exercise", "lesson"]


class PostIn(BaseModel):
    target_type: TargetType
    target_key: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=2, max_length=5000)
    is_spoiler: bool = False
    parent_id: int | None = None


class PostEdit(BaseModel):
    body: str = Field(min_length=2, max_length=5000)
    is_spoiler: bool | None = None


class ReportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _target_exists(db: Session, ttype: str, key: str) -> Exercise | Lesson:
    obj = (db.scalar(select(Exercise).where(Exercise.code == key.upper())) if ttype == "exercise"
           else db.scalar(select(Lesson).where(Lesson.slug == key)))
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโจทย์/บทเรียนนี้")
    return obj


def _norm_key(ttype: str, key: str) -> str:
    return key.upper() if ttype == "exercise" else key


@router.get("/discussions")
def list_posts(target_type: TargetType, target_key: str, reveal_spoilers: bool = False, db: Session = Depends(get_db),
               user: User | None = Depends(get_optional_user)):
    obj = _target_exists(db, target_type, target_key)
    key = _norm_key(target_type, target_key)
    solved = bool(user) and target_type == "exercise" and obj.id in progress.solved_exercise_ids(db, user.id)
    can_see_spoilers = target_type == "lesson" or solved or reveal_spoilers
    is_admin = bool(user) and user.role == "admin"
    posts = list(db.scalars(select(Post).where(Post.target_type == target_type, Post.target_key == key).order_by(Post.created_at)))
    ids = [p.id for p in posts]
    votes = dict(db.execute(select(PostVote.post_id, func.count()).where(PostVote.post_id.in_(ids)).group_by(PostVote.post_id)).all())
    mine = set(db.scalars(select(PostVote.post_id).where(PostVote.user_id == user.id, PostVote.post_id.in_(ids)))) if user else set()
    authors = {u.id: u.display_name for u in db.scalars(select(User).where(User.id.in_({p.user_id for p in posts})))}

    def out(p: Post) -> dict:
        hidden_body = p.is_hidden and not is_admin
        spoiler_locked = p.is_spoiler and not can_see_spoilers and not (user and p.user_id == user.id)
        return {"id": p.id, "author": authors.get(p.user_id, "?"), "is_mine": bool(user and p.user_id == user.id),
                "body": None if hidden_body or spoiler_locked else p.body, "is_spoiler": p.is_spoiler, "spoiler_locked": spoiler_locked,
                "is_hidden": p.is_hidden, "votes": votes.get(p.id, 0), "voted": p.id in mine,
                "created_at": p.created_at.isoformat(), "edited": p.updated_at > p.created_at, "replies": []}

    by_id, roots = {}, []
    for p in posts:
        by_id[p.id] = out(p)
        (by_id[p.parent_id]["replies"] if p.parent_id in by_id else roots).append(by_id[p.id])
    roots.sort(key=lambda r: (-r["votes"], r["created_at"]))
    return {"target_type": target_type, "target_key": key, "solved": solved, "can_see_spoilers": can_see_spoilers,
            "count": len(posts), "threads": roots}


@router.post("/discussions", status_code=201)
def create_post(body: PostIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "post", 10)
    _target_exists(db, body.target_type, body.target_key)
    key = _norm_key(body.target_type, body.target_key)
    if body.parent_id is not None:
        parent = db.get(Post, body.parent_id)
        if parent is None or parent.target_type != body.target_type or parent.target_key != key or parent.parent_id is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ตอบกลับได้เฉพาะโพสต์หลักในหัวข้อเดียวกัน")
    spoiler = body.is_spoiler or (body.target_type == "exercise" and bool(re.search(r"```\s*sql", body.body, re.I)))
    p = Post(user_id=user.id, target_type=body.target_type, target_key=key, parent_id=body.parent_id, body=body.body.strip(),
             is_spoiler=spoiler)
    db.add(p)
    db.commit()
    return {"id": p.id, "is_spoiler": p.is_spoiler, "auto_spoiler": spoiler and not body.is_spoiler}


def _own_post(db: Session, user: User, pid: int, allow_admin: bool = False) -> Post:
    p = db.get(Post, pid)
    if p is None or (p.user_id != user.id and not (allow_admin and user.role == "admin")):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโพสต์")
    return p


@router.patch("/discussions/{pid}")
def edit_post(pid: int, body: PostEdit, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = _own_post(db, user, pid)
    p.body, p.updated_at = body.body.strip(), datetime.now(UTC)
    if body.is_spoiler is not None:
        p.is_spoiler = body.is_spoiler or (p.target_type == "exercise" and bool(re.search(r"```\s*sql", p.body, re.I)))
    db.commit()
    return {"ok": True, "is_spoiler": p.is_spoiler}


@router.delete("/discussions/{pid}", status_code=204)
def delete_post(pid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = _own_post(db, user, pid, allow_admin=True)
    db.delete(p)  # replies cascade
    db.commit()
    log.info("event=post_deleted post=%s by=%s", pid, user.id)


@router.post("/discussions/{pid}/vote")
def vote(pid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(Post, pid)
    if p is None or p.is_hidden:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโพสต์")
    if p.user_id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "โหวตโพสต์ของตัวเองไม่ได้")
    v = db.get(PostVote, (user.id, pid))
    if v:
        db.delete(v)
    else:
        db.add(PostVote(user_id=user.id, post_id=pid))
    db.commit()
    n = db.scalar(select(func.count()).select_from(PostVote).where(PostVote.post_id == pid))
    return {"voted": v is None, "votes": n}


@router.post("/discussions/{pid}/report", status_code=201)
def report(pid: int, body: ReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "report", 5)
    if db.get(Post, pid) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโพสต์")
    db.add(PostReport(post_id=pid, user_id=user.id, reason=body.reason))
    db.commit()
    return {"ok": True, "message": "ส่งรายงานให้ผู้ดูแลแล้ว ขอบคุณที่ช่วยดูแลชุมชน"}


# ------------------------------------------------------------------ moderation (admin)
admin_only = require_role("admin")


@router.get("/admin/reports")
def list_reports(db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    rows = db.execute(select(PostReport, Post).join(Post, Post.id == PostReport.post_id)
                      .where(PostReport.resolved.is_(False)).order_by(PostReport.created_at)).all()
    return [{"id": r.id, "reason": r.reason, "created_at": r.created_at.isoformat(),
             "post": {"id": p.id, "body": p.body, "target_type": p.target_type, "target_key": p.target_key, "is_hidden": p.is_hidden}}
            for r, p in rows]


class HideIn(BaseModel):
    hidden: bool


@router.post("/admin/posts/{pid}/hide")
def hide_post(pid: int, body: HideIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    p = db.get(Post, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโพสต์")
    p.is_hidden = body.hidden
    if body.hidden:
        for r in db.scalars(select(PostReport).where(PostReport.post_id == pid)):
            r.resolved = True
    db.commit()
    log.info("event=admin_action admin=%s action=hide_post target=post:%s hidden=%s", admin.id, pid, body.hidden)
    return {"ok": True}


@router.post("/admin/reports/{rid}/resolve")
def resolve_report(rid: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    r = db.get(PostReport, rid)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบรายงาน")
    r.resolved = True
    db.commit()
    log.info("event=admin_action admin=%s action=resolve_report target=report:%s", admin.id, rid)
    return {"ok": True}
