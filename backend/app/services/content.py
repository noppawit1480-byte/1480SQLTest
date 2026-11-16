"""Content validation shared by the seeder and the Admin Panel.

A lesson example's "result" and an exercise's "expected" are always produced by executing SQL on the
sandbox — so neither the seed files nor an admin can publish an exercise whose solution does not run.
"""
from __future__ import annotations

from dataclasses import asdict

from app.services.sandbox.base import ExecutionResult
from app.services.sandbox.postgres import SYSTEM_USER_ID, get_sandbox

PREVIEW_ROWS = 10


class ContentError(ValueError):
    pass


def preview(r: ExecutionResult) -> dict:
    last = r.last_rows
    out = {"ok": r.ok, "exec_ms": r.exec_ms, "commands": [rs.command for rs in r.result_sets]}
    if last:
        out.update(columns=[asdict(c) for c in last.columns], rows=last.rows[:PREVIEW_ROWS],
                   row_count=last.row_count, truncated=last.truncated or last.row_count > PREVIEW_ROWS)
    if r.error:
        out["error"] = {"message": r.error.message, "detail": r.error.detail, "sqlstate": r.error.sqlstate}
    return out


def run_example(db_key: str, sql: str, writable: bool) -> dict:
    """Execute a lesson example. Errors in the SQL itself are allowed (some examples demonstrate an
    error on purpose); infrastructure/limit errors are not."""
    sb = get_sandbox()
    res = sb.execute_on_fresh_copy(SYSTEM_USER_ID, db_key, sql) if writable else sb.execute(sb.readonly_target(db_key), sql)
    if not res.ok and res.error and res.error.kind in ("internal", "limit"):
        raise ContentError(f"ตัวอย่างรันไม่ได้: {res.error.message}")
    return preview(res)


def compute_expected(db_key: str, check_type: str, solution: str, check_sql: str | None) -> dict:
    sb = get_sandbox()
    if check_type == "dml":
        if not check_sql:
            raise ContentError("โจทย์ DML/DDL ต้องมี check_sql")
        sb.ensure_role(SYSTEM_USER_ID)
        res = sb.execute_on_fresh_copy(SYSTEM_USER_ID, db_key, solution, check_sql)
    else:
        res = sb.execute(sb.readonly_target(db_key), solution)
    last = res.last_rows
    if not res.ok:
        raise ContentError(f"เฉลยรันไม่ผ่าน: {res.error.message if res.error else 'unknown error'}")
    if last is None or not last.columns:
        raise ContentError("เฉลยต้องคืนผลลัพธ์เป็นตาราง (SELECT หรือ check_sql)")
    if last.truncated:
        raise ContentError("ผลลัพธ์ของเฉลยเกินขีดจำกัดจำนวนแถว")
    return {"columns": [asdict(c) for c in last.columns], "rows": last.rows}
