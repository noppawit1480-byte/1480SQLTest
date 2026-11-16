import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Exercise, Lesson, Submission, User
from app.ratelimit import check_rate
from app.schemas import SqlIn
from app.security import get_current_user, get_optional_user
from app.services import progress
from app.services.checker import compare_results
from app.services.sandbox.base import ExecutionResult
from app.services.sandbox.postgres import get_sandbox

log = logging.getLogger("practice")
router = APIRouter(prefix="/api/exercises", tags=["practice"])
DIFF_ORDER = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}


def _get(db: Session, code: str) -> Exercise:
    ex = db.scalar(select(Exercise).where(Exercise.code == code.upper()))
    if ex is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบโจทย์")
    return ex


def _ordered_codes(db: Session) -> list[str]:
    rows = db.execute(select(Exercise.code, Exercise.difficulty, Exercise.position)).all()
    return [c for c, _, _ in sorted(rows, key=lambda r: (DIFF_ORDER[r[1]], r[2]))]


@router.get("")
def list_exercises(difficulty: str | None = None, category: str | None = None, db: Session = Depends(get_db),
                   user: User | None = Depends(get_optional_user)):
    q = select(Exercise)
    if difficulty:
        q = q.where(Exercise.difficulty == difficulty)
    if category:
        q = q.where(Exercise.category == category)
    solved = progress.solved_exercise_ids(db, user.id) if user else set()
    attempted = progress.attempted_exercise_ids(db, user.id) if user else set()
    items = sorted(db.scalars(q), key=lambda e: (DIFF_ORDER[e.difficulty], e.position))
    cats = sorted(set(db.scalars(select(Exercise.category).distinct())))
    return {
        "categories": cats,
        "items": [{"code": e.code, "title": e.title, "difficulty": e.difficulty, "category": e.category,
                   "points": e.points, "sample_db": e.sample_db, "check_type": e.check_type,
                   "status": "solved" if e.id in solved else "attempted" if e.id in attempted else "new"}
                  for e in items],
    }


@router.get("/{code}")
def get_exercise(code: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    ex = _get(db, code)
    codes = _ordered_codes(db)
    i = codes.index(ex.code)
    lesson = db.get(Lesson, ex.lesson_id) if ex.lesson_id else None
    exp = ex.expected or {}
    status_ = "new"
    attempts = 0
    if user:
        attempts = db.scalar(select(func.count()).select_from(Submission).where(
            Submission.user_id == user.id, Submission.exercise_id == ex.id)) or 0
        if ex.id in progress.solved_exercise_ids(db, user.id):
            status_ = "solved"
        elif attempts:
            status_ = "attempted"
    return {
        "code": ex.code, "title": ex.title, "description_md": ex.description_md, "difficulty": ex.difficulty,
        "category": ex.category, "points": ex.points, "sample_db": ex.sample_db, "check_type": ex.check_type,
        "order_matters": ex.order_matters,
        "expected": {"columns": exp.get("columns", []), "rows": exp.get("rows", [])[:10],
                     "row_count": len(exp.get("rows", []))},
        "hints": ex.hints,
        "lesson": {"slug": lesson.slug, "title": lesson.title, "course_slug": lesson.course.slug} if lesson else None,
        "prev": codes[i - 1] if i > 0 else None, "next": codes[i + 1] if i + 1 < len(codes) else None,
        "status": status_, "attempts": attempts,
    }


def _run_answer(ex: Exercise, sql: str, user: User | None) -> ExecutionResult:
    sb = get_sandbox()
    if ex.check_type == "dml":
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "โจทย์ประเภท DML/DDL ต้องเข้าสู่ระบบก่อนจึงจะรันได้")
        return sb.execute_on_fresh_copy(user.id, ex.sample_db, sql, ex.check_sql or "SELECT 1")
    return sb.execute(sb.readonly_target(ex.sample_db), sql)


@router.post("/{code}/run")
def run(code: str, body: SqlIn, request: Request, db: Session = Depends(get_db),
        user: User | None = Depends(get_optional_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    ex = _get(db, code)
    result = _run_answer(ex, body.sql, user)
    if user:
        progress.record_activity(db, user.id)
        db.commit()
    return asdict(result)


@router.post("/{code}/submit")
def submit(code: str, body: SqlIn, request: Request, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    ex = _get(db, code)
    result = _run_answer(ex, body.sql, user)
    actual = None
    if not result.ok:
        correct, reason, message, details = False, "SQL_ERROR", "SQL มีข้อผิดพลาด: " + (result.error.message if result.error else ""), {}
    else:
        last = result.last_rows
        actual = {"columns": [asdict(c) for c in last.columns], "rows": last.rows, "truncated": last.truncated} if last \
            else {"columns": [], "rows": []}
        chk = compare_results(actual, ex.expected, order_matters=ex.order_matters,
                              check_column_names=ex.check_column_names)
        correct, reason, message, details = chk.correct, chk.reason_code, chk.message, chk.details
    already = ex.id in progress.solved_exercise_ids(db, user.id)
    db.add(Submission(user_id=user.id, exercise_id=ex.id, sql=body.sql, is_correct=correct, reason_code=reason,
                      exec_ms=result.exec_ms))
    progress.record_activity(db, user.id)
    db.flush()
    new = progress.evaluate_achievements(db, user.id)
    db.commit()
    log.info("event=submit user=%s ex=%s correct=%s reason=%s", user.id, ex.code, correct, reason)
    return {
        "correct": correct, "reason_code": reason, "message": message, "details": details,
        "points_awarded": ex.points if correct and not already else 0,
        "execution": asdict(result),
        "actual": {"columns": actual["columns"], "rows": actual["rows"][:200]} if actual else None,
        "expected": {"columns": ex.expected.get("columns", []), "rows": ex.expected.get("rows", [])[:200],
                     "row_count": len(ex.expected.get("rows", []))},
        "explanation_md": ex.explanation_md,
        "solution_sql": ex.solution_sql,
        "new_achievements": new,
    }


@router.get("/{code}/solution")
def solution(code: str, db: Session = Depends(get_db)):
    ex = _get(db, code)
    return {"solution_sql": ex.solution_sql, "explanation_md": ex.explanation_md}
