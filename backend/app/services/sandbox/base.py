"""Engine-agnostic types for the SQL sandbox (see docs/02-architecture.md §3.3)."""
from __future__ import annotations

import base64
import datetime as dt
import decimal
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Mode = Literal["readonly", "writable"]


@dataclass
class Target:
    """A concrete database inside the sandbox cluster plus the role allowed to use it."""
    db_key: str           # logical sample DB, e.g. "ecommerce"
    database: str         # physical database name, e.g. "ro_ecommerce" or "u_42_ecommerce"
    user: str
    password: str
    mode: Mode


@dataclass
class ColumnInfo:
    name: str
    type: str


@dataclass
class ResultSet:
    statement_index: int
    command: str                       # e.g. "SELECT 12", "INSERT 0 3", "CREATE TABLE"
    columns: list[ColumnInfo] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)   # JSON-safe values
    row_count: int = 0
    truncated: bool = False


@dataclass
class ExecError:
    message: str
    sqlstate: str | None = None
    detail: str | None = None
    hint: str | None = None
    line: int | None = None             # 1-based, relative to the whole submitted text
    column: int | None = None
    statement_index: int | None = None
    kind: str = "sql"                   # sql | timeout | limit | permission | internal


@dataclass
class ExecutionResult:
    ok: bool
    result_sets: list[ResultSet]
    exec_ms: int
    statements: int
    error: ExecError | None = None
    notices: list[str] = field(default_factory=list)

    @property
    def last_rows(self) -> ResultSet | None:
        """The last result set that returned columns (what a user usually wants to see/check)."""
        for rs in reversed(self.result_sets):
            if rs.columns:
                return rs
        return None


@dataclass
class TableColumn:
    name: str
    type: str
    nullable: bool
    default: str | None
    is_pk: bool
    fk: str | None                       # "table.column"
    comment: str | None


@dataclass
class TableInfo:
    name: str
    comment: str | None
    row_estimate: int
    columns: list[TableColumn]


class EngineAdapter(Protocol):
    engine: str

    def execute(self, target: Target, sql: str) -> ExecutionResult: ...
    def execute_on_fresh_copy(self, user_id: int, db_key: str, sql: str, check_sql: str) -> ExecutionResult: ...
    def introspect(self, target: Target) -> list[TableInfo]: ...
    def readonly_target(self, db_key: str) -> Target: ...
    def ensure_user_db(self, user_id: int, db_key: str) -> Target: ...
    def reset_user_db(self, user_id: int, db_key: str) -> None: ...


def to_jsonable(v: Any) -> Any:
    """Convert a DB value into a JSON-safe value. Decimals stay strings to keep exact precision."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            return str(v)
        return v
    if isinstance(v, decimal.Decimal):
        return str(v)
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return "\\x" + bytes(v).hex()
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): to_jsonable(x) for k, x in v.items()}
    try:
        return str(v)
    except Exception:  # pragma: no cover
        return base64.b64encode(repr(v).encode()).decode()
