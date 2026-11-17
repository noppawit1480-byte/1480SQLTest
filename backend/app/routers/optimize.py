"""Query Execution Plan visualizer + Index Lab (Phase 3)."""
import logging
from typing import Literal

import pglast
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pglast import ast
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import SampleDatabase, User
from app.ratelimit import check_rate
from app.routers.playground import readonly_schema
from app.security import get_current_user, get_optional_user
from app.services import plans
from app.services.sandbox.postgres import get_sandbox
from app.services.sandbox.sqlite_engine import get_engine

log = logging.getLogger("optimize")
router = APIRouter(prefix="/api/plans", tags=["plans"])
DBKEY = r"^[a-z][a-z0-9_]{1,30}$"


class ExplainIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)
    db_key: str = Field(default="ecommerce", pattern=DBKEY)
    engine: Literal["postgresql", "sqlite"] = "postgresql"
    mode: Literal["readonly", "writable"] = "readonly"
    analyze: bool = False


class IndexLabIn(BaseModel):
    sql: str = Field(min_length=1, max_length=20000)
    index_sql: str = Field(min_length=1, max_length=5000)
    db_key: str = Field(default="ecommerce", pattern=DBKEY)


def _known(db: Session, key: str):
    if db.get(SampleDatabase, key) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ไม่พบฐานข้อมูลนี้")


def _rows(db_key: str, engine: str) -> dict[str, int]:
    return {t["name"]: t["row_estimate"] for t in readonly_schema(db_key, engine)}


@router.post("/explain")
def explain(body: ExplainIn, request: Request, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    check_rate(request, "execute", get_settings().rate_execute_per_min)
    _known(db, body.db_key)
    eng = get_engine(body.engine)
    if body.mode == "writable":
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "โหมด Writable ต้องเข้าสู่ระบบ")
        target = eng.ensure_user_db(user.id, body.db_key)
    else:
        target = eng.readonly_target(body.db_key)
    try:
        if body.engine == "sqlite":
            stmt = body.sql.strip().rstrip(";")
            res = eng.execute(target, f"EXPLAIN QUERY PLAN {stmt}")
        else:
            allowed = (ast.SelectStmt, ast.InsertStmt, ast.UpdateStmt, ast.DeleteStmt)
            stmt = plans.single_statement(body.sql, allowed)
            opts = "FORMAT JSON, ANALYZE, BUFFERS" if body.analyze else "FORMAT JSON"
            # ANALYZE really executes the statement: always inside a transaction that is rolled back
            script = f"BEGIN; EXPLAIN ({opts}) {stmt}; ROLLBACK" if body.analyze and target.mode == "writable" \
                else f"EXPLAIN ({opts}) {stmt}"
            res = eng.execute(target, script)
    except plans.PlanError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    rs = next((r for r in res.result_sets if r.columns), None)
    if not res.ok or rs is None:
        return {"ok": False, "error": res.error.message if res.error else "EXPLAIN failed", "sqlstate": res.error.sqlstate if res.error else None}
    plan = plans.normalize_sqlite(rs.rows) if body.engine == "sqlite" else plans.normalize_pg(rs.rows[0][0])
    return {"ok": True, "plan": plan, "summary": plans.summarize(plan),
            "findings": plans.plan_findings(body.sql, plan, _rows(body.db_key, body.engine))}


@router.post("/index-lab")
def index_lab(body: IndexLabIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Measure a query, add the proposed index(es), measure again — on a throwaway copy, so nothing persists."""
    check_rate(request, "index_lab", 10)
    _known(db, body.db_key)
    try:
        query = plans.single_statement(body.sql, (ast.SelectStmt,))
        idx_tree = pglast.parse_sql(body.index_sql)
    except plans.PlanError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    except Exception as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"คำสั่งสร้าง index มี syntax error: {e}") from None
    if not idx_tree or len(idx_tree) > 3 or not all(isinstance(r.stmt, ast.IndexStmt) for r in idx_tree):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ใส่ได้เฉพาะคำสั่ง CREATE INDEX (สูงสุด 3 คำสั่ง)")
    explain = f"EXPLAIN (FORMAT JSON, ANALYZE, BUFFERS) {query}"
    results = get_sandbox().run_scripts_on_fresh_copy(user.id, body.db_key, [explain, body.index_sql + ";\nANALYZE", explain])
    if not all(r.ok for r in results) or len(results) != 3:
        bad = next(r for r in results if not r.ok)
        step = ["วัดผลก่อนสร้าง index", "สร้าง index", "วัดผลหลังสร้าง index"][results.index(bad)]
        return {"ok": False, "error": f"{step} ไม่สำเร็จ: {bad.error.message if bad.error else ''}"}
    before = plans.normalize_pg(results[0].last_rows.rows[0][0])
    after = plans.normalize_pg(results[2].last_rows.rows[0][0])
    sb, sa = plans.summarize(before), plans.summarize(after)
    used = [i for i in sa["indexes_used"] if i not in sb["indexes_used"]]
    speedup = round(before["execution_ms"] / after["execution_ms"], 1) if after["execution_ms"] else None
    verdict = ("planner เลือกใช้ index ใหม่" + (f" — เร็วขึ้น ~{speedup}×" if speedup and speedup > 1.1 else "")) if used else \
        "planner ไม่เลือกใช้ index ใหม่ — อาจเป็นเพราะตารางเล็ก, เงื่อนไขคัดแถวได้น้อย, หรือคอลัมน์/ลำดับคอลัมน์ไม่ตรงกับ query"
    log.info("event=index_lab user=%s db=%s used=%s speedup=%s", user.id, body.db_key, used, speedup)
    return {"ok": True, "before": before, "after": after, "summary_before": sb, "summary_after": sa,
            "new_indexes_used": used, "speedup": speedup, "verdict": verdict,
            "note": "ทดลองบนสำเนาฐานข้อมูลชั่วคราว — index ไม่ถูกเก็บไว้ในฐานข้อมูลใด ๆ"}
