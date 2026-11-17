"""Timed / random challenges, mock interviews and the leaderboard (Phase 3)."""
from dataclasses import asdict
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ChallengeItem, ChallengeSession, Exercise, Submission, User, UserAchievement
from app.ratelimit import check_rate
from app.routers.practice import grade
from app.security import get_current_user, get_optional_user
from app.services import challenges as svc
from app.services import progress

router = APIRouter(prefix="/api", tags=["challenges"])


class StartIn(BaseModel):
    kind: Literal["timed", "random", "interview"]
    count: int | None = Field(default=None, ge=1, le=10)
    minutes: int | None = Field(default=None, ge=1, le=90)
    difficulty: Literal["easy", "medium", "hard", "expert"] | None = None
    category: str | None = Field(default=None, max_length=40)


class AnswerIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)
    approach: str | None = Field(default=None, max_length=4000)


def _own(db: Session, user: User, sid: int) -> ChallengeSession:
    s = db.get(ChallengeSession, sid)
    if s is None or s.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบ challenge")
    if s.status == "active" and s.deadline_at < svc.now():
        svc._close(db, s, "expired")
        db.commit()
    return s


def _session_out(db: Session, s: ChallengeSession) -> dict:
    its = svc.items(db, s)
    exs = {e.id: e for e in db.scalars(select(Exercise).where(Exercise.id.in_([i.exercise_id for i in its])))}
    items = []
    for i in its:
        e = exs[i.exercise_id]
        exp = e.expected or {}
        items.append({"position": i.position, "code": e.code, "title": e.title, "description_md": e.description_md,
                      "difficulty": e.difficulty, "category": e.category, "points": e.points, "sample_db": e.sample_db,
                      "order_matters": e.order_matters,
                      "expected": {"columns": exp.get("columns", []), "rows": exp.get("rows", [])[:5], "row_count": len(exp.get("rows", []))},
                      "hints": e.hints[:i.hints_used], "hints_total": len(e.hints), "solved": i.solved_at is not None,
                      "attempts": i.attempts, "points_awarded": i.points, "approach_text": i.approach_text, "last_sql": i.last_sql})
    out = {"id": s.id, "kind": s.kind, "status": s.status, "config": s.config, "score": s.score,
           "started_at": s.started_at.isoformat(), "deadline_at": s.deadline_at.isoformat(),
           "remaining_seconds": svc.remaining_seconds(s), "items": items}
    if s.status != "active":
        out["report"] = svc.report(db, s)
    return out


@router.post("/challenges", status_code=201)
def start(body: StartIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "challenge_start", 10)
    try:
        s = svc.start(db, user, body.kind, body.count, body.minutes, body.difficulty, body.category)
    except svc.ChallengeError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    return _session_out(db, s)


@router.get("/challenges")
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc.expire_overdue(db, user.id)
    rows = db.scalars(select(ChallengeSession).where(ChallengeSession.user_id == user.id)
                      .order_by(ChallengeSession.started_at.desc()).limit(30))
    return [{"id": s.id, "kind": s.kind, "status": s.status, "score": s.score, "config": s.config,
             "started_at": s.started_at.isoformat(), "remaining_seconds": svc.remaining_seconds(s),
             "solved": db.scalar(select(func.count()).select_from(ChallengeItem).where(ChallengeItem.session_id == s.id,
                                                                                      ChallengeItem.solved_at.is_not(None))),
             "total": s.config.get("count")} for s in rows]


@router.get("/challenges/{sid}")
def get_session(sid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _session_out(db, _own(db, user, sid))


def _item(db: Session, s: ChallengeSession, pos: int) -> tuple[ChallengeItem, Exercise]:
    it = db.get(ChallengeItem, (s.id, pos))
    if it is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบข้อนี้")
    return it, db.get(Exercise, it.exercise_id)


def _active(s: ChallengeSession) -> None:
    if s.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "challenge นี้จบแล้ว" if s.status == "finished" else "หมดเวลาแล้ว")


@router.post("/challenges/{sid}/items/{pos}/submit")
def submit(sid: int, pos: int, body: AnswerIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    s = _own(db, user, sid)
    _active(s)
    it, ex = _item(db, s, pos)
    if it.solved_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "ข้อนี้ตอบถูกแล้ว")
    g = grade(db, ex, body.sql, user)
    awarded = svc.record_attempt(db, s, it, ex, body.sql, g["correct"], body.approach)
    special = _session_awards(db, s, user.id) if s.status == "finished" else []
    new = progress.evaluate_achievements(db, user.id)
    db.commit()
    return {"correct": g["correct"], "message": g["message"], "details": g["details"], "points_awarded": awarded,
            "execution": asdict(g["result"]), "session_status": s.status, "new_achievements": new + special}


def _session_awards(db: Session, s: ChallengeSession, user_id: int) -> list[str]:
    """Achievements earned by finishing a session. Returns the keys that were newly awarded."""
    rep = svc.report(db, s)
    keys = []
    if s.kind == "timed" and rep["solved"] == rep["total"] and s.finished_at and s.finished_at <= s.deadline_at:
        keys.append("beat_the_clock")
    if s.kind == "interview" and rep.get("rubric", {}).get("passed"):
        keys.append("interview_ready")
    new = []
    for key in keys:
        if db.get(UserAchievement, (user_id, key)) is None:
            db.add(UserAchievement(user_id=user_id, achievement_key=key))
            new.append(key)
    return new


@router.post("/challenges/{sid}/items/{pos}/hint")
def hint(sid: int, pos: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _own(db, user, sid)
    _active(s)
    it, ex = _item(db, s, pos)
    if it.hints_used >= len(ex.hints):
        raise HTTPException(status.HTTP_409_CONFLICT, "ใช้ hint ครบแล้ว")
    it.hints_used += 1
    db.commit()
    return {"hint": ex.hints[it.hints_used - 1], "hints_used": it.hints_used, "penalty": "คะแนนข้อนี้ลดลง 10% ต่อ hint"}


@router.post("/challenges/{sid}/items/{pos}/approach")
def save_approach(sid: int, pos: int, body: AnswerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Mock interview: save the written explanation (sql field is ignored)."""
    s = _own(db, user, sid)
    _active(s)
    it, _ = _item(db, s, pos)
    it.approach_text = (body.approach or "")[:4000]
    db.commit()
    return {"ok": True}


@router.post("/challenges/{sid}/finish")
def finish(sid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _own(db, user, sid)
    awards = []
    if s.status == "active":
        svc._close(db, s, "finished")
        awards = _session_awards(db, s, user.id)
        db.commit()
    return _session_out(db, s) | {"new_achievements": awards}


# ------------------------------------------------------------------ leaderboard
class SettingsIn(BaseModel):
    show_on_leaderboard: bool


@router.patch("/me/settings")
def settings(body: SettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.show_on_leaderboard = body.show_on_leaderboard
    db.commit()
    return {"show_on_leaderboard": user.show_on_leaderboard}


@router.get("/leaderboard")
def leaderboard(board: Literal["points", "challenges"] = "points", period: Literal["week", "all"] = "all",
                db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    since = svc.now() - timedelta(days=7) if period == "week" else None
    if board == "points":
        # points of distinct exercises whose FIRST correct submission falls in the period
        first = (select(Submission.user_id, Submission.exercise_id, func.min(Submission.created_at).label("at"))
                 .where(Submission.is_correct).group_by(Submission.user_id, Submission.exercise_id).subquery())
        q = (select(first.c.user_id, func.sum(Exercise.points).label("score"), func.count().label("count"))
             .join(Exercise, Exercise.id == first.c.exercise_id).group_by(first.c.user_id))
        if since:
            q = q.where(first.c.at >= since)
    else:
        q = (select(ChallengeSession.user_id, func.sum(ChallengeSession.score).label("score"), func.count().label("count"))
             .where(ChallengeSession.status != "active").group_by(ChallengeSession.user_id))
        if since:
            q = q.where(ChallengeSession.started_at >= since)
    rows = db.execute(q).all()
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([r[0] for r in rows])))}
    ranked = sorted([r for r in rows if users[r[0]].is_active and users[r[0]].show_on_leaderboard and r[1]],
                    key=lambda r: (-int(r[1]), r[0]))
    entries, rank, prev = [], 0, None
    for i, (uid, score, cnt) in enumerate(ranked):
        if score != prev:
            rank, prev = i + 1, score
        entries.append({"rank": rank, "user_id": uid, "display_name": users[uid].display_name, "score": int(score), "count": int(cnt)})
    me = next((e for e in entries if user and e["user_id"] == user.id), None)
    return {"board": board, "period": period, "entries": entries[:20], "me": me,
            "me_hidden": bool(user and not user.show_on_leaderboard)}
