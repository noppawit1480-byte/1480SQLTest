"""SQLite engine — a second, real database engine behind the same interface as PostgresSandbox.

* Sample databases are exported from the PostgreSQL read-only copies into SQLite files, so both
  engines hold identical data (that is what makes dialect comparison meaningful).
* Every user query runs in a separate worker process (sqlite_worker.py) with OS resource limits.
* Writable sandboxes are per-user copies of the exported file; reset = copy again.
"""
from __future__ import annotations

import json
import logging
import os
import re
import resource
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from psycopg import sql as psql

from app.config import get_settings
from app.services.sandbox.base import ColumnInfo, ExecError, ExecutionResult, ResultSet, TableColumn, TableInfo, Target
from app.services.sandbox.postgres import SAMPLE_DIR, first_keyword, get_sandbox
from app.services.sql_split import offset_to_line_col, split_statements

log = logging.getLogger("sandbox.sqlite")
WORKER = Path(__file__).with_name("sqlite_worker.py")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


def _sqlite_type(pg_type: str) -> str:
    t = pg_type.lower()
    if t.startswith(("integer", "bigint", "smallint")):
        return "INTEGER"
    if t.startswith(("numeric", "double", "real")):
        return "NUMERIC"
    if t.startswith("boolean"):
        return "BOOLEAN"
    if t.startswith(("timestamp", "date", "time")):
        return "TEXT"  # ISO-8601 text — SQLite's date/time functions work on it
    return "TEXT"


def _value(v):
    from datetime import date, datetime, time as dtime
    from decimal import Decimal
    if isinstance(v, Decimal):
        return float(v) if v != v.to_integral_value() else int(v)
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, (date, dtime)):
        return v.isoformat()
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


class SqliteSandbox:
    engine = "sqlite"

    def __init__(self):
        self.s = get_settings()
        self.dir = Path(self.s.sqlite_dir).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ files
    def _check_key(self, key: str) -> str:
        if not KEY_RE.match(key) or not (SAMPLE_DIR / f"{key}.sql").exists():
            raise ValueError(f"unknown sample database: {key}")
        return key

    def ro_path(self, key: str) -> Path:
        return self.dir / f"ro_{self._check_key(key)}.sqlite"

    def user_path(self, user_id: int, key: str) -> Path:
        return self.dir / "users" / f"u_{int(user_id)}_{self._check_key(key)}.sqlite"

    def readonly_target(self, key: str) -> Target:
        path = self.ro_path(key)
        if not path.exists():
            self.export(key)
        return Target(key, str(path), "", "", "readonly")

    def ensure_user_db(self, user_id: int, key: str) -> Target:
        path = self.user_path(user_id, key)
        if not path.exists():
            self._copy_ro(key, path)
        return Target(key, str(path), "", "", "writable")

    def reset_user_db(self, user_id: int, key: str) -> None:
        self._copy_ro(key, self.user_path(user_id, key))

    def _copy_ro(self, key: str, dest: Path) -> None:
        src = self.readonly_target(key).database
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)

    # ------------------------------------------------------------------ export from PostgreSQL
    def export(self, key: str) -> Path:
        """Build ro_<key>.sqlite from the PostgreSQL read-only copy (same rows, same keys)."""
        self._check_key(key)
        pg = get_sandbox()
        tables = pg.introspect(pg.readonly_target(key))
        names = {t.name for t in tables}
        # parents before children so FOREIGN KEY definitions are satisfied while loading
        order, pending = [], {t.name: t for t in tables}
        while pending:
            progressed = False
            for name, t in list(pending.items()):
                deps = {c.fk.split(".")[0] for c in t.columns if c.fk} - {name}
                if deps <= set(order) or not (deps & names):
                    order.append(name)
                    pending.pop(name)
                    progressed = True
            if not progressed:  # cycle — load remaining in any order (FKs are enforced only at query time)
                order += list(pending)
                break
        by_name = {t.name: t for t in tables}
        with self._lock:
            fd, tmp_name = tempfile.mkstemp(dir=self.dir, suffix=".building")
            os.close(fd)
            out = sqlite3.connect(tmp_name)
            out.execute("PRAGMA foreign_keys = OFF")
            with pg.admin_connect(f"ro_{key}") as conn:
                for name in order:
                    t = by_name[name]
                    pks = [c.name for c in t.columns if c.is_pk]
                    cols = []
                    for c in t.columns:
                        d = f'"{c.name}" {_sqlite_type(c.type)}'
                        if len(pks) == 1 and c.is_pk:
                            d += " PRIMARY KEY"
                        if not c.nullable and not c.is_pk:
                            d += " NOT NULL"
                        if c.fk:
                            rt, rc = c.fk.split(".")
                            d += f' REFERENCES "{rt}"("{rc}")'
                        cols.append(d)
                    if len(pks) > 1:
                        cols.append("PRIMARY KEY (" + ", ".join(f'"{p}"' for p in pks) + ")")
                    out.execute(f'CREATE TABLE "{name}" (\n  ' + ",\n  ".join(cols) + "\n)")
                    col_list = ", ".join(f'"{c.name}"' for c in t.columns)
                    marks = ", ".join("?" for _ in t.columns)
                    q = psql.SQL("SELECT * FROM {} ORDER BY 1").format(psql.Identifier(name))
                    with conn.cursor() as cur:
                        cur.execute(q)
                        while batch := cur.fetchmany(2000):
                            out.executemany(f'INSERT INTO "{name}" ({col_list}) VALUES ({marks})',
                                            [tuple(_value(v) for v in row) for row in batch])
                # secondary indexes so the SQLite query planner has the same access paths
                for idxname, idxdef in conn.execute(
                        "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname NOT LIKE '%_pkey'"
                        " AND indexdef NOT LIKE 'CREATE UNIQUE%'"):
                    m = re.match(r"CREATE INDEX \w+ ON public\.(\w+) USING btree \((.+)\)$", idxdef)
                    if m:
                        out.execute(f'CREATE INDEX "{idxname}" ON "{m.group(1)}" ({m.group(2)})')
            out.commit()
            out.execute("VACUUM")
            out.close()
            dest = self.dir / f"ro_{key}.sqlite"
            os.replace(tmp_name, dest)
            os.chmod(dest, 0o444)
        log.info("exported sample database %s to SQLite", key)
        return dest

    # ------------------------------------------------------------------ execution
    def execute(self, target: Target, sql_text: str) -> ExecutionResult:
        s = self.s
        if not sql_text.strip():
            return ExecutionResult(False, [], 0, 0, ExecError("กรุณาพิมพ์คำสั่ง SQL ก่อนรัน", kind="limit"))
        if len(sql_text) > s.max_sql_length:
            return ExecutionResult(False, [], 0, 0, ExecError(f"SQL ยาวเกินกำหนด ({len(sql_text)} ตัวอักษร)", kind="limit"))
        stmts = split_statements(sql_text)
        if not stmts or len(stmts) > s.max_statements:
            return ExecutionResult(False, [], 0, len(stmts), ExecError("ไม่พบคำสั่ง SQL หรือจำนวนคำสั่งเกินกำหนด", kind="limit"))
        payload = {"db_path": target.database, "readonly": target.mode == "readonly", "max_rows": s.max_result_rows,
                   "max_sets": s.max_result_sets, "timeout_ms": s.query_timeout_ms,
                   "statements": [{"text": st.text, "keyword": first_keyword(st.text),
                                   **dict(zip(("line", "column"), offset_to_line_col(sql_text, st.offset), strict=True))}
                                  for st in stmts]}
        timeout_s = s.query_timeout_ms / 1000

        def limits():  # runs in the child just before exec
            mb = 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (512 * mb, 512 * mb))
            resource.setrlimit(resource.RLIMIT_CPU, (int(timeout_s) + 2, int(timeout_s) + 3))
            resource.setrlimit(resource.RLIMIT_FSIZE, (s.writable_db_max_bytes, s.writable_db_max_bytes))
            resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
            os.setsid()

        try:
            proc = subprocess.run([sys.executable, "-I", str(WORKER)], input=json.dumps(payload), capture_output=True,
                                  text=True, timeout=timeout_s + 3, preexec_fn=limits, env={"PATH": "/usr/bin:/bin"},
                                  cwd=str(self.dir))
        except subprocess.TimeoutExpired:
            return ExecutionResult(False, [], int((timeout_s + 3) * 1000), len(stmts),
                                   ExecError(f"Query ใช้เวลานานเกิน {int(timeout_s)} วินาที จึงถูกยกเลิก", kind="timeout"))
        if proc.returncode != 0 or not proc.stdout:
            log.warning("sqlite worker exited %s: %s", proc.returncode, proc.stderr[-500:])
            msg = "Query ใช้ทรัพยากรเกินขีดจำกัดของ sandbox จึงถูกหยุด" if proc.returncode < 0 or "MemoryError" in proc.stderr \
                else "SQLite sandbox ทำงานผิดพลาด"
            return ExecutionResult(False, [], 0, len(stmts), ExecError(msg, kind="limit"))
        d = json.loads(proc.stdout)
        sets = [ResultSet(r["statement_index"], r["command"], [ColumnInfo(**c) for c in r["columns"]],
                          r["rows"], r["row_count"], r["truncated"]) for r in d["result_sets"]]
        return ExecutionResult(d["ok"], sets, d["exec_ms"], d["statements"],
                               ExecError(**d["error"]) if d["error"] else None, d["notices"])

    # ------------------------------------------------------------------ introspection (trusted, read-only)
    def introspect(self, target: Target) -> list[TableInfo]:
        conn = sqlite3.connect(f"file:{target.database}?mode=ro", uri=True)
        try:
            out = []
            for (name,) in conn.execute("SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
                fks = {r[3]: f"{r[2]}.{r[4]}" for r in conn.execute(f'PRAGMA foreign_key_list("{name}")')}
                cols = [TableColumn(r[1], (r[2] or "").lower() or "any", not r[3] and not r[5], r[4], bool(r[5]), fks.get(r[1]), None)
                        for r in conn.execute(f'PRAGMA table_info("{name}")')]
                n = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                out.append(TableInfo(name, None, n, cols))
            return out
        finally:
            conn.close()

    def preview(self, target: Target, table: str, limit: int = 50) -> ExecutionResult:
        if table not in {t.name for t in self.introspect(target)}:
            raise ValueError("unknown table")
        return self.execute(target, f'SELECT * FROM "{table}" LIMIT {min(limit, 200)}')


_sqlite: SqliteSandbox | None = None


def get_sqlite() -> SqliteSandbox:
    global _sqlite
    if _sqlite is None:
        _sqlite = SqliteSandbox()
    return _sqlite


def get_engine(name: str):
    """Engine registry — the API layer only talks to engines through this."""
    if name == "sqlite":
        return get_sqlite()
    if name in ("postgresql", "postgres", ""):
        return get_sandbox()
    raise ValueError(f"unsupported engine: {name}")
