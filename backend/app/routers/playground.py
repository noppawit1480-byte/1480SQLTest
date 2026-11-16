import logging
from dataclasses import asdict
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import QueryHistory, SampleDatabase, SavedQuery, User
from app.ratelimit import check_rate
from app.schemas import ExecuteIn, ResetIn, SavedQueryIn, ValidateIn
from app.security import get_current_user, get_optional_user
from app.services import progress
from app.services.sandbox.base import ExecutionResult
from app.services.sandbox.postgres import get_sandbox
from app.services.validator import validate_sql

log = logging.getLogger("playground")
router = APIRouter(prefix="/api", tags=["playground"])


def result_out(r: ExecutionResult) -> dict:
    d = asdict(r)
    return d


def _known_db(db: Session, key: str) -> None:
    if not db.get(SampleDatabase, key):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")


@router.post("/playground/execute")
def execute(body: ExecuteIn, request: Request, db: Session = Depends(get_db),
            user: User | None = Depends(get_optional_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    _known_db(db, body.db_key)
    sb = get_sandbox()
    if body.mode == "writable":
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "โหมด Writable sandbox ต้องเข้าสู่ระบบก่อน")
        target = sb.ensure_user_db(user.id, body.db_key)
    else:
        target = sb.readonly_target(body.db_key)
    result = sb.execute(target, body.sql)
    if body.mode == "writable" and user is not None:
        size = sb.user_db_size(user.id, body.db_key)
        if size > get_settings().writable_db_max_bytes:
            sb.reset_user_db(user.id, body.db_key)
            result.notices.append(f"Sandbox มีขนาดเกิน {get_settings().writable_db_max_bytes // 1048576} MB จึงถูกรีเซ็ตอัตโนมัติ")
    last = result.last_rows
    log.info("event=sql_exec user=%s db=%s mode=%s ms=%s status=%s rows=%s", user.id if user else "guest",
             body.db_key, body.mode, result.exec_ms, "ok" if result.ok else (result.error.kind if result.error else "error"),
             last.row_count if last else 0)
    if user is not None:
        db.add(QueryHistory(user_id=user.id, db_key=body.db_key, mode=body.mode, sql=body.sql, success=result.ok,
                            row_count=last.row_count if last else 0, exec_ms=result.exec_ms))
        progress.record_activity(db, user.id)
        new = progress.evaluate_achievements(db, user.id) if result.ok else []
        db.commit()
    else:
        new = []
    out = result_out(result)
    out["new_achievements"] = new
    return out


@router.post("/playground/validate")
def validate(body: ValidateIn):
    return {"issues": [asdict(i) for i in validate_sql(body.sql)]}


@router.post("/playground/reset")
def reset(body: ResetIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_rate(request, "reset", 10)
    _known_db(db, body.db_key)
    get_sandbox().reset_user_db(user.id, body.db_key)
    return {"ok": True, "message": f"รีเซ็ตฐานข้อมูล {body.db_key} (Writable sandbox) กลับเป็นค่าเริ่มต้นแล้ว"}


@router.get("/playground/history")
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user), limit: int = 50):
    rows = db.scalars(select(QueryHistory).where(QueryHistory.user_id == user.id)
                      .order_by(QueryHistory.created_at.desc()).limit(min(limit, 200)))
    return [{"id": h.id, "db_key": h.db_key, "mode": h.mode, "sql": h.sql, "success": h.success,
             "row_count": h.row_count, "exec_ms": h.exec_ms, "created_at": h.created_at.isoformat()} for h in rows]


@router.delete("/playground/history", status_code=204)
def clear_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(delete(QueryHistory).where(QueryHistory.user_id == user.id))
    db.commit()


def _saved_out(q: SavedQuery) -> dict:
    return {"id": q.id, "title": q.title, "db_key": q.db_key, "sql": q.sql, "updated_at": q.updated_at.isoformat()}


@router.get("/saved-queries")
def list_saved(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(SavedQuery).where(SavedQuery.user_id == user.id).order_by(SavedQuery.updated_at.desc()))
    return [_saved_out(q) for q in rows]


@router.post("/saved-queries", status_code=201)
def create_saved(body: SavedQueryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _known_db(db, body.db_key)
    q = SavedQuery(user_id=user.id, title=body.title.strip(), db_key=body.db_key, sql=body.sql)
    db.add(q)
    db.commit()
    return _saved_out(q)


def _own_saved(db: Session, user: User, qid: int) -> SavedQuery:
    q = db.get(SavedQuery, qid)
    if q is None or q.user_id != user.id:  # never reveal other users' rows
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบ query ที่บันทึกไว้")
    return q


@router.put("/saved-queries/{qid}")
def update_saved(qid: int, body: SavedQueryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = _own_saved(db, user, qid)
    q.title, q.db_key, q.sql, q.updated_at = body.title.strip(), body.db_key, body.sql, datetime.now(UTC)
    db.commit()
    return _saved_out(q)


@router.delete("/saved-queries/{qid}", status_code=204)
def delete_saved(qid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_own_saved(db, user, qid))
    db.commit()


# ---------------------------------------------------------------- sample databases
@lru_cache(maxsize=16)
def readonly_schema(db_key: str) -> list[dict]:
    sb = get_sandbox()
    return [asdict(t) for t in sb.introspect(sb.readonly_target(db_key))]


@router.get("/databases")
def list_databases(db: Session = Depends(get_db)):
    out = []
    for d in db.scalars(select(SampleDatabase).order_by(SampleDatabase.position)):
        tables = readonly_schema(d.key)
        out.append({"key": d.key, "name": d.name, "engine": d.engine, "description": d.description,
                    "tables": [{"name": t["name"], "rows": t["row_estimate"]} for t in tables]})
    return out


@router.get("/databases/{key}")
def get_database(key: str, mode: str = "readonly", db: Session = Depends(get_db),
                 user: User | None = Depends(get_optional_user)):
    d = db.get(SampleDatabase, key)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")
    if mode == "writable":
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "กรุณาเข้าสู่ระบบ")
        sb = get_sandbox()
        tables = [asdict(t) for t in sb.introspect(sb.ensure_user_db(user.id, key))]
    else:
        tables = readonly_schema(key)
    return {"key": d.key, "name": d.name, "engine": d.engine, "description": d.description, "mode": mode,
            "tables": tables, "er_mermaid": er_mermaid(tables)}


@router.get("/databases/{key}/tables/{table}/preview")
def preview(key: str, table: str, request: Request, mode: str = "readonly", db: Session = Depends(get_db),
            user: User | None = Depends(get_optional_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    if db.get(SampleDatabase, key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")
    sb = get_sandbox()
    if mode == "writable":
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "กรุณาเข้าสู่ระบบ")
        target = sb.ensure_user_db(user.id, key)
    else:
        target = sb.readonly_target(key)
    try:
        return result_out(sb.preview(target, table))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบตารางนี้") from None


def er_mermaid(tables: list[dict]) -> str:
    """Build a Mermaid erDiagram from the real catalog (so the diagram can never drift from the schema)."""
    lines = ["erDiagram"]
    for t in tables:
        for c in t["columns"]:
            if c["fk"]:
                ref_table = c["fk"].split(".")[0]
                card = "|o--o{" if c["nullable"] else "||--o{"
                lines.append(f'  {ref_table} {card} {t["name"]} : "{c["name"]}"')
    for t in tables:
        lines.append(f"  {t['name']} {{")
        for c in t["columns"]:
            typ = (c["type"].split("(")[0].replace("character varying", "varchar")
                   .replace("timestamp without time zone", "timestamp")
                   .replace("timestamp with time zone", "timestamptz").replace(" ", "_"))
            key = " PK" if c["is_pk"] else (" FK" if c["fk"] else "")
            lines.append(f"    {typ} {c['name']}{key}")
        lines.append("  }")
    return "\n".join(lines)


