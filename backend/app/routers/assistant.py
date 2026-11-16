from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import GeneratedExercise, SampleDatabase, User
from app.ratelimit import check_rate
from app.security import get_current_user, get_optional_user
from app.services.assistant import service
from app.services.assistant.llm import AssistantUnavailable, get_provider
from app.services.checker import compare_results
from app.services.sandbox.postgres import get_sandbox

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
DbKey = Field(default="ecommerce", pattern=r"^[a-z][a-z0-9_]{1,30}$")


class AnalyzeIn(BaseModel):
    mode: Literal["explain", "review", "explain_error", "fix", "optimize"]
    sql: str = Field(min_length=1, max_length=20000)
    db_key: str = DbKey
    error: dict | None = None
    exercise_code: str | None = Field(default=None, max_length=20)
    use_ai: bool = False


class ChatMsg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class TutorIn(BaseModel):
    messages: list[ChatMsg] = Field(min_length=1, max_length=30)
    db_key: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,30}$")
    exercise_code: str | None = Field(default=None, max_length=20)


class GenerateIn(BaseModel):
    db_key: str = DbKey
    topic: str = Field(min_length=2, max_length=80)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class SqlIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)


def _known_db(db: Session, key: str | None):
    if key and db.get(SampleDatabase, key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")


def _ai_guard(request: Request, db: Session, user: User | None):
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "เข้าสู่ระบบเพื่อใช้ AI")
    p = get_provider()
    if not p.available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ยังไม่ได้ตั้งค่า AI provider บนเซิร์ฟเวอร์ — โหมดวิเคราะห์อัตโนมัติยังใช้ได้ตามปกติ")
    s = get_settings()
    check_rate(request, "assistant_ai", s.rate_assistant_ai_per_min)
    if service.ai_used_today(db, user.id) >= s.assistant_ai_daily_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"ใช้ AI ครบโควตาวันนี้แล้ว ({s.assistant_ai_daily_limit} ครั้ง/วัน) — โหมดวิเคราะห์อัตโนมัติยังใช้ได้")


def _unavailable(e: AssistantUnavailable):
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


@router.get("/status")
def assistant_status():
    p = get_provider()
    return {"ai_available": p.available(), "provider": p.name, "model": getattr(p, "model", "") if p.available() else "",
            "rule_modes": ["explain", "review", "explain_error", "fix", "optimize", "recommendations"],
            "ai_modes": ["tutor", "generate", "use_ai"]}


@router.post("/analyze")
def analyze(body: AnalyzeIn, request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    check_rate(request, "assistant", get_settings().rate_assistant_per_min)
    _known_db(db, body.db_key)
    if body.use_ai:
        _ai_guard(request, db, user)
    try:
        return service.analyze(db, mode=body.mode, sql=body.sql, db_key=body.db_key, user_id=user.id if user else None,
                               error=body.error, exercise_code=body.exercise_code, use_ai=body.use_ai)
    except AssistantUnavailable as e:
        raise _unavailable(e) from None


@router.post("/tutor")
def tutor(body: TutorIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _known_db(db, body.db_key)
    _ai_guard(request, db, user)
    if body.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "ข้อความสุดท้ายต้องเป็นของผู้เรียน")
    try:
        return service.tutor(db, user_id=user.id, messages=[m.model_dump() for m in body.messages],
                             db_key=body.db_key, exercise_code=body.exercise_code)
    except AssistantUnavailable as e:
        raise _unavailable(e) from None


@router.get("/recommendations")
def recommendations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.recommendations(db, user.id)


def _gen_out(g: GeneratedExercise, with_solution: bool = False) -> dict:
    d = {"id": g.id, "db_key": g.db_key, "topic": g.topic, "title": g.title, "description_md": g.description_md,
         "hints": g.hints, "order_matters": g.order_matters, "solved": g.solved_at is not None,
         "expected": {"columns": g.expected.get("columns", []), "rows": g.expected.get("rows", [])[:10],
                      "row_count": len(g.expected.get("rows", []))},
         "created_at": g.created_at.isoformat() if g.created_at else None}
    if with_solution:
        d["solution_sql"] = g.solution_sql
    return d


def _own_gen(db: Session, user: User, gid: int) -> GeneratedExercise:
    g = db.get(GeneratedExercise, gid)
    if g is None or g.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโจทย์")
    return g


@router.post("/generate", status_code=201)
def generate(body: GenerateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _known_db(db, body.db_key)
    _ai_guard(request, db, user)
    try:
        g = service.generate_practice(db, user_id=user.id, db_key=body.db_key, topic=body.topic, difficulty=body.difficulty)
    except AssistantUnavailable as e:
        raise _unavailable(e) from None
    return _gen_out(g)


@router.get("/generated")
def list_generated(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(GeneratedExercise).where(GeneratedExercise.user_id == user.id)
                      .order_by(GeneratedExercise.created_at.desc()).limit(50))
    return [_gen_out(g) for g in rows]


@router.get("/generated/{gid}")
def get_generated(gid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _gen_out(_own_gen(db, user, gid))


@router.get("/generated/{gid}/solution")
def generated_solution(gid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"solution_sql": _own_gen(db, user, gid).solution_sql}


@router.post("/generated/{gid}/run")
def run_generated(gid: int, body: SqlIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    g = _own_gen(db, user, gid)
    from dataclasses import asdict
    sb = get_sandbox()
    return asdict(sb.execute(sb.readonly_target(g.db_key), body.sql))


@router.post("/generated/{gid}/submit")
def submit_generated(gid: int, body: SqlIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Checked exactly like official exercises; generated practice gives no points (it is self-study)."""
    from dataclasses import asdict
    from datetime import UTC, datetime
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    g = _own_gen(db, user, gid)
    sb = get_sandbox()
    res = sb.execute(sb.readonly_target(g.db_key), body.sql)
    if not res.ok:
        return {"correct": False, "reason_code": "SQL_ERROR", "message": "SQL มีข้อผิดพลาด: " + (res.error.message if res.error else ""),
                "details": {}, "execution": asdict(res), "solution_sql": None}
    last = res.last_rows
    actual = {"columns": [asdict(c) for c in last.columns], "rows": last.rows, "truncated": last.truncated} if last else {"columns": [], "rows": []}
    chk = compare_results(actual, g.expected, order_matters=g.order_matters)
    if chk.correct and g.solved_at is None:
        g.solved_at = datetime.now(UTC)
        db.commit()
    return {"correct": chk.correct, "reason_code": chk.reason_code, "message": chk.message, "details": chk.details,
            "execution": asdict(res), "solution_sql": g.solution_sql if chk.correct else None}
