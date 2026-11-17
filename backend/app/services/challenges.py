"""Timed challenges, random challenges and mock interviews (Phase 3).

Rules (all enforced on the server — the client timer is display only):
  * a session has a fixed set of exercises and a deadline; submissions after the deadline are rejected
  * scoring per solved item = points × (1 + 0.5 × remaining-time share) × (0.9 ^ hints used) × max(0.5, 1 − 0.1 × extra attempts)
  * an interview report scores correctness, efficiency (attempts/hints), time management and communication
    (the written explanation of the approach)
"""
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChallengeItem, ChallengeSession, Exercise, User

LIMITS = {"timed": {"count": (3, 10), "minutes": (5, 60)}, "random": {"count": (1, 1), "minutes": (5, 30)},
          "interview": {"count": (2, 5), "minutes": (15, 90)}}
DEFAULTS = {"timed": {"count": 5, "minutes": 20}, "random": {"count": 1, "minutes": 15}, "interview": {"count": 3, "minutes": 45}}
MAX_ACTIVE = 3


class ChallengeError(ValueError):
    pass


def now() -> datetime:
    return datetime.now(UTC)


def _pool(db: Session, kind: str, difficulty: str | None, category: str | None):
    q = select(Exercise).where(Exercise.project_id.is_(None))
    q = q.where(Exercise.is_interview.is_(kind == "interview"))
    if kind != "interview":
        q = q.where(Exercise.check_type == "select")  # keep timed rounds fast: no fresh-copy grading
    if difficulty:
        q = q.where(Exercise.difficulty == difficulty)
    if category:
        q = q.where(Exercise.category == category)
    return list(db.scalars(q))


def start(db: Session, user: User, kind: str, count: int | None, minutes: int | None,
          difficulty: str | None = None, category: str | None = None, seed: int | None = None) -> ChallengeSession:
    expire_overdue(db, user.id)
    active = db.scalar(select(func.count()).select_from(ChallengeSession).where(
        ChallengeSession.user_id == user.id, ChallengeSession.status == "active")) or 0
    if active >= MAX_ACTIVE:
        raise ChallengeError(f"มี challenge ที่ยังไม่จบ {active} รายการ — จบหรือรอให้หมดเวลาก่อน")
    lim, d = LIMITS[kind], DEFAULTS[kind]
    count = min(max(count or d["count"], lim["count"][0]), lim["count"][1])
    minutes = min(max(minutes or d["minutes"], lim["minutes"][0]), lim["minutes"][1])
    pool = _pool(db, kind, difficulty, category)
    if len(pool) < count:
        raise ChallengeError(f"มีโจทย์ตามเงื่อนไขนี้เพียง {len(pool)} ข้อ — ลดจำนวนข้อหรือเปลี่ยนตัวกรอง")
    picks = random.Random(seed).sample(pool, count)
    order = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}
    picks.sort(key=lambda e: (order.get(e.difficulty, 9), e.code))
    s = ChallengeSession(user_id=user.id, kind=kind, config={"count": count, "minutes": minutes, "difficulty": difficulty,
                                                             "category": category},
                         started_at=now(), deadline_at=now() + timedelta(minutes=minutes))
    db.add(s)
    db.flush()
    for i, e in enumerate(picks):
        db.add(ChallengeItem(session_id=s.id, position=i, exercise_id=e.id))
    db.commit()
    return s


def expire_overdue(db: Session, user_id: int) -> None:
    for s in db.scalars(select(ChallengeSession).where(ChallengeSession.user_id == user_id, ChallengeSession.status == "active",
                                                      ChallengeSession.deadline_at < now())):
        _close(db, s, "expired")
    db.commit()


def _close(db: Session, s: ChallengeSession, status: str) -> None:
    s.status = status
    s.finished_at = min(now(), s.deadline_at) if status == "expired" else now()
    s.score = sum(i.points for i in items(db, s))


def items(db: Session, s: ChallengeSession) -> list[ChallengeItem]:
    return list(db.scalars(select(ChallengeItem).where(ChallengeItem.session_id == s.id).order_by(ChallengeItem.position)))


def remaining_seconds(s: ChallengeSession) -> int:
    end = s.finished_at if s.status != "active" else now()
    return max(0, int((s.deadline_at - end).total_seconds()))


def item_points(ex: Exercise, item: ChallengeItem, s: ChallengeSession) -> int:
    total = (s.deadline_at - s.started_at).total_seconds()
    share = max(0.0, (s.deadline_at - now()).total_seconds()) / total if total else 0
    mult = (1 + 0.5 * share) * (0.9 ** item.hints_used) * max(0.5, 1 - 0.1 * max(0, item.attempts - 1))
    return int(round(ex.points * mult))


def record_attempt(db: Session, s: ChallengeSession, item: ChallengeItem, ex: Exercise, sql: str, correct: bool,
                   approach: str | None) -> int:
    item.attempts += 1
    item.last_sql = sql
    if approach is not None:
        item.approach_text = approach[:4000]
    awarded = 0
    if correct and item.solved_at is None:
        item.solved_at = now()
        awarded = item.points = item_points(ex, item, s)
    if all(i.solved_at for i in items(db, s)):
        _close(db, s, "finished")
    return awarded


def report(db: Session, s: ChallengeSession) -> dict:
    its = items(db, s)
    exs = {e.id: e for e in db.scalars(select(Exercise).where(Exercise.id.in_([i.exercise_id for i in its])))}
    total_time = (s.deadline_at - s.started_at).total_seconds()
    used = ((s.finished_at or now()) - s.started_at).total_seconds()
    solved = [i for i in its if i.solved_at]
    rows = [{"position": i.position, "code": exs[i.exercise_id].code, "title": exs[i.exercise_id].title,
             "difficulty": exs[i.exercise_id].difficulty, "solved": bool(i.solved_at), "attempts": i.attempts,
             "hints_used": i.hints_used, "points": i.points,
             "seconds_to_solve": int((i.solved_at - s.started_at).total_seconds()) if i.solved_at else None,
             "approach_text": i.approach_text} for i in its]
    out = {"solved": len(solved), "total": len(its), "score": s.score, "max_score": sum(int(exs[i.exercise_id].points * 1.5) for i in its),
           "seconds_used": int(min(used, total_time)), "items": rows}
    if s.kind == "interview":
        correctness = 100 * len(solved) / len(its)
        eff_parts = [max(0, 100 - 15 * (i.attempts - 1) - 20 * i.hints_used) for i in solved]
        efficiency = sum(eff_parts) / len(its) if its else 0
        time_mgmt = 100 * max(0.0, 1 - used / total_time) if solved else 0
        explained = [i for i in its if i.approach_text and len(i.approach_text.strip()) >= 40]
        communication = 100 * len(explained) / len(its)
        overall = round(0.5 * correctness + 0.2 * efficiency + 0.1 * time_mgmt + 0.2 * communication)
        out["rubric"] = {
            "overall": overall, "passed": overall >= 70,
            "criteria": [
                {"name": "ความถูกต้อง", "weight": 50, "score": round(correctness), "note": f"ตอบถูก {len(solved)}/{len(its)} ข้อ"},
                {"name": "ประสิทธิภาพ", "weight": 20, "score": round(efficiency), "note": "หักคะแนนเมื่อส่งหลายครั้งหรือใช้ hint"},
                {"name": "การบริหารเวลา", "weight": 10, "score": round(time_mgmt), "note": f"ใช้เวลา {int(used // 60)} จาก {int(total_time // 60)} นาที"},
                {"name": "การอธิบายแนวคิด", "weight": 20, "score": round(communication),
                 "note": f"อธิบายแนวทาง (≥ 40 ตัวอักษร) {len(explained)}/{len(its)} ข้อ — สัมภาษณ์จริงผู้สัมภาษณ์ให้น้ำหนักกับการสื่อสารมาก"},
            ],
        }
    return out
