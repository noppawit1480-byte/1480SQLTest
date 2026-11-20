"""MySQL engine — a third real database engine behind the same interface as PostgresSandbox / SqliteSandbox.

Security model (see docs/02-architecture.md §3.3):
  * a separate MySQL server (docker: `sandbox-mysql`, internal network only) started with
    local_infile=0 and secure_file_priv=NULL, so no statement can read or write server files
  * read-only sample databases `ro_<key>` are reached by `sbx_reader`, which only has SELECT on them
    (granted per database) and every session is additionally `TRANSACTION READ ONLY`
  * every learner gets an account `sbx_u_<uid>` (password = HMAC of SANDBOX_ROLE_SECRET) with privileges
    only on their own `u_<uid>_<key>` databases — no FILE, SUPER, PROCESS, EVENT or GRANT OPTION
  * MySQL's own max_execution_time only covers SELECT, so a watchdog issues `KILL QUERY` for anything that
    runs longer than QUERY_TIMEOUT_MS; results are streamed (unbuffered) and cut at MAX_RESULT_ROWS
  * sample data is exported from the PostgreSQL read-only copies, so all three engines hold identical rows

The engine is optional: it is enabled only when MYSQL_HOST is configured.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import threading
import time
from contextlib import contextmanager

import pymysql
import pymysql.cursors
from pymysql.constants import FIELD_TYPE

from app.config import get_settings
from app.services.sandbox.base import (ColumnInfo, ExecError, ExecutionResult, ResultSet, TableColumn, TableInfo, Target,
                                       to_jsonable)
from app.services.sandbox.postgres import SAMPLE_DIR, first_keyword, get_sandbox
from app.services.sql_split import offset_to_line_col, split_statements

log = logging.getLogger("sandbox.mysql")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
READER = "sbx_reader"
# privileges a learner has on *their own* databases (deliberately no EVENT, FILE, GRANT OPTION or admin privileges)
USER_PRIVS = ("SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX, REFERENCES, CREATE TEMPORARY TABLES, "
              "CREATE VIEW, SHOW VIEW, TRIGGER, CREATE ROUTINE, ALTER ROUTINE, EXECUTE, LOCK TABLES")
TYPE_NAMES = {v: k.lower() for k, v in vars(FIELD_TYPE).items() if k.isupper()}
TIMEOUT_CODES = {1317, 3024}           # query interrupted (KILL QUERY) / max_execution_time exceeded
PERMISSION_CODES = {1044, 1045, 1142, 1143, 1148, 1227, 1290, 1370, 1410, 1792, 3948}
READONLY_HINT = "โหมด Read-only แก้ไขข้อมูลไม่ได้ (ถ้าต้องการฝึก INSERT/UPDATE/DDL ให้สลับเป็นโหมด Writable sandbox)"


class MySQLUnavailable(RuntimeError):
    pass


def mysql_type(pg_type: str, indexed: bool) -> str:
    """PostgreSQL column type (format_type) -> MySQL column type."""
    t = pg_type.lower()
    if t == "integer":
        return "INT"
    if t in ("bigint", "smallint"):
        return t.upper()
    if t.startswith("numeric"):
        return t.replace("numeric", "DECIMAL")
    if t in ("real", "double precision"):
        return "DOUBLE"
    if t == "boolean":
        return "BOOLEAN"
    if t.startswith("character varying"):
        return "VARCHAR" + t[len("character varying"):] if "(" in t else "VARCHAR(255)"
    if t.startswith("character("):
        return "CHAR" + t[len("character"):]
    if t == "date":
        return "DATE"
    if t.startswith("timestamp"):
        return "DATETIME"
    if t in ("json", "jsonb"):
        return "JSON"
    if t == "uuid":
        return "CHAR(36)"
    return "VARCHAR(255)" if indexed else "TEXT"   # text (MySQL cannot index TEXT without a prefix length)


def _q(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]{0,63}", name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return f"`{name}`"


def _export_value(v):
    import json
    from datetime import datetime
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, datetime) and v.tzinfo is not None:
        from datetime import UTC
        return v.astimezone(UTC).replace(tzinfo=None)
    return v


class MySqlSandbox:
    engine = "mysql"

    def __init__(self):
        self.s = get_settings()
        if not self.s.mysql_host:
            raise MySQLUnavailable("MySQL engine is not configured (MYSQL_HOST is empty)")

    # ------------------------------------------------------------------ connections & accounts
    def _password(self, who: str) -> str:
        return hmac.new(self.s.sandbox_role_secret.encode(), f"mysql:{who}".encode(), hashlib.sha256).hexdigest()[:40]

    def _connect(self, user: str, password: str, database: str | None = None, *, unbuffered: bool = False,
                 read_timeout: float | None = None) -> pymysql.connections.Connection:
        return pymysql.connect(host=self.s.mysql_host, port=self.s.mysql_port, user=user, password=password,
                               database=database, autocommit=True, charset="utf8mb4", connect_timeout=5,
                               read_timeout=read_timeout, local_infile=False,
                               cursorclass=pymysql.cursors.SSCursor if unbuffered else pymysql.cursors.Cursor)

    def admin_connect(self, database: str | None = None) -> pymysql.connections.Connection:
        return self._connect(self.s.mysql_admin_user, self.s.mysql_admin_password, database)

    @contextmanager
    def _lock(self, name: str):
        with self.admin_connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, 30)", (f"sqlab:{name}",))
            if cur.fetchone()[0] != 1:
                raise RuntimeError("MySQL sandbox is busy, please retry")
            try:
                yield conn
            finally:
                cur.execute("SELECT RELEASE_LOCK(%s)", (f"sqlab:{name}",))

    @staticmethod
    def _check_key(key: str) -> str:
        if not KEY_RE.match(key) or not (SAMPLE_DIR / f"{key}.sql").exists():
            raise ValueError(f"unknown sample database: {key}")
        return key

    def _ensure_account(self, cur, user: str, password: str, max_conn: int) -> None:
        cur.execute(f"CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s WITH MAX_USER_CONNECTIONS {int(max_conn)}",
                    (user, password))
        cur.execute(f"ALTER USER %s@'%%' IDENTIFIED BY %s WITH MAX_USER_CONNECTIONS {int(max_conn)}", (user, password))

    # ------------------------------------------------------------------ targets
    def readonly_target(self, key: str) -> Target:
        self._check_key(key)
        return Target(key, f"ro_{key}", READER, self._password(READER), "readonly")

    def user_target(self, user_id: int, key: str) -> Target:
        uid = int(user_id)
        name = f"sbx_u_{uid}"
        return Target(key, f"u_{uid}_{self._check_key(key)}", name, self._password(name), "writable")

    def _exists(self, cur, database: str) -> bool:
        cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (database,))
        return cur.fetchone() is not None

    def ensure_user_db(self, user_id: int, key: str) -> Target:
        t = self.user_target(user_id, key)
        with self.admin_connect() as conn, conn.cursor() as cur:
            if self._exists(cur, t.database):
                return t
        with self._lock(t.database) as conn, conn.cursor() as cur:
            if not self._exists(cur, t.database):
                self._clone(cur, f"ro_{key}", t.database)
            self._ensure_account(cur, t.user, t.password, 3)
            cur.execute(f"GRANT {USER_PRIVS} ON {_q(t.database)}.* TO %s@'%%'", (t.user,))
        return t

    def reset_user_db(self, user_id: int, key: str) -> None:
        t = self.user_target(user_id, key)
        with self._lock(t.database) as conn, conn.cursor() as cur:
            self._kill_sessions(cur, t.user)
            cur.execute(f"DROP DATABASE IF EXISTS {_q(t.database)}")
            self._clone(cur, f"ro_{key}", t.database)
            self._ensure_account(cur, t.user, t.password, 3)
            cur.execute(f"GRANT {USER_PRIVS} ON {_q(t.database)}.* TO %s@'%%'", (t.user,))

    def user_db_size(self, user_id: int, key: str) -> int:
        t = self.user_target(user_id, key)
        with self.admin_connect() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION information_schema_stats_expiry = 0")
            cur.execute("SELECT COALESCE(SUM(data_length + index_length), 0) FROM information_schema.tables "
                        "WHERE table_schema = %s", (t.database,))
            return int(cur.fetchone()[0])

    @staticmethod
    def _kill_sessions(cur, user: str) -> None:
        cur.execute("SELECT id FROM information_schema.processlist WHERE user = %s", (user,))
        for (pid,) in cur.fetchall():
            try:
                cur.execute(f"KILL {int(pid)}")
            except pymysql.Error:
                pass

    def _clone(self, cur, src: str, dest: str) -> None:
        """Copy every table (with keys, indexes, FKs and AUTO_INCREMENT position) and its rows."""
        cur.execute(f"CREATE DATABASE {_q(dest)} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                    (src,))
        tables = [r[0] for r in cur.fetchall()]
        cur.execute("SET SESSION foreign_key_checks = 0")
        try:
            for tname in tables:
                cur.execute(f"SHOW CREATE TABLE {_q(src)}.{_q(tname)}")
                ddl = cur.fetchone()[1]
                cur.execute(f"USE {_q(dest)}")
                cur.execute(ddl)
                cur.execute(f"INSERT INTO {_q(dest)}.{_q(tname)} SELECT * FROM {_q(src)}.{_q(tname)}")
        finally:
            cur.execute("SET SESSION foreign_key_checks = 1")

    # ------------------------------------------------------------------ export from PostgreSQL
    def export(self, key: str) -> None:
        """(Re)build ro_<key> from the PostgreSQL read-only copy: same tables, keys, indexes, comments and rows."""
        self._check_key(key)
        pg = get_sandbox()
        tables = pg.introspect(pg.readonly_target(key))
        with pg.admin_connect(f"ro_{key}") as pconn:
            idx = list(pconn.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname NOT LIKE '%%_pkey'"))
            parsed = []
            for name, d in idx:
                m = re.match(r"CREATE (UNIQUE )?INDEX \w+ ON public\.(\w+) USING btree \((.+)\)$", d)
                if m:
                    parsed.append((name, bool(m.group(1)), m.group(2), [c.strip() for c in m.group(3).split(",")]))
            indexed = {(t, c) for _, _, t, cols in parsed for c in cols}
            ro = f"ro_{key}"
            with self._lock(ro) as conn, conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS {_q(ro)}")
                cur.execute(f"CREATE DATABASE {_q(ro)} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
                cur.execute(f"USE {_q(ro)}")
                cur.execute("SET SESSION foreign_key_checks = 0")
                for t in tables:
                    pks = [c.name for c in t.columns if c.is_pk]
                    defs = []
                    for c in t.columns:
                        typ = mysql_type(c.type, c.is_pk or (t.name, c.name) in indexed or bool(c.fk))
                        d = f"{_q(c.name)} {typ}"
                        if not c.nullable or c.is_pk:
                            d += " NOT NULL"
                        if len(pks) == 1 and c.is_pk and typ in ("INT", "BIGINT", "SMALLINT"):
                            d += " AUTO_INCREMENT"
                        if c.comment:
                            d += " COMMENT " + conn.escape(c.comment[:1000])
                        defs.append(d)
                    if pks:
                        defs.append("PRIMARY KEY (" + ", ".join(_q(p) for p in pks) + ")")
                    for name, unique, tbl, cols in parsed:
                        if tbl == t.name:
                            defs.append(f"{'UNIQUE ' if unique else ''}KEY {_q(name)} (" + ", ".join(_q(c) for c in cols) + ")")
                    for c in t.columns:
                        if c.fk:
                            rt, rc = c.fk.split(".")
                            defs.append(f"CONSTRAINT {_q(('fk_' + t.name + '_' + c.name)[:64])} FOREIGN KEY ({_q(c.name)}) "
                                        f"REFERENCES {_q(rt)} ({_q(rc)})")
                    comment = f" COMMENT={conn.escape(t.comment[:2000])}" if t.comment else ""
                    cur.execute(f"CREATE TABLE {_q(t.name)} (\n  " + ",\n  ".join(defs) + f"\n) ENGINE=InnoDB{comment}")
                    cols = ", ".join(_q(c.name) for c in t.columns)
                    marks = ", ".join(["%s"] * len(t.columns))
                    with pconn.cursor() as pcur:
                        pcur.execute(f'SELECT * FROM "{t.name}" ORDER BY 1')
                        while batch := pcur.fetchmany(2000):
                            cur.executemany(f"INSERT INTO {_q(t.name)} ({cols}) VALUES ({marks})",
                                            [tuple(_export_value(v) for v in row) for row in batch])
                cur.execute("SET SESSION foreign_key_checks = 1")
                if tables:  # fresh statistics so EXPLAIN shows realistic row estimates
                    cur.execute("ANALYZE TABLE " + ", ".join(_q(t.name) for t in tables))
                    cur.fetchall()
                self._ensure_account(cur, READER, self._password(READER), 30)
                cur.execute(f"GRANT SELECT, SHOW VIEW ON {_q(ro)}.* TO %s@'%%'", (READER,))
        log.info("exported sample database %s to MySQL", key)

    # ------------------------------------------------------------------ execution
    def _precheck(self, sql_text: str):
        if not sql_text.strip():
            return None, ExecutionResult(False, [], 0, 0, ExecError("กรุณาพิมพ์คำสั่ง SQL ก่อนรัน", kind="limit"))
        if len(sql_text) > self.s.max_sql_length:
            return None, ExecutionResult(False, [], 0, 0, ExecError(
                f"SQL ยาวเกินกำหนด ({len(sql_text)} > {self.s.max_sql_length} ตัวอักษร)", kind="limit"))
        stmts = split_statements(sql_text)
        if not stmts:
            return None, ExecutionResult(False, [], 0, 0, ExecError("ไม่พบคำสั่ง SQL (มีแต่ comment)", kind="limit"))
        if len(stmts) > self.s.max_statements:
            return None, ExecutionResult(False, [], 0, len(stmts), ExecError(
                f"จำนวนคำสั่งเกินกำหนด ({len(stmts)} > {self.s.max_statements})", kind="limit"))
        return stmts, None

    def _kill(self, thread_id: int, query_only: bool = True) -> None:
        try:
            with self.admin_connect() as conn, conn.cursor() as cur:
                cur.execute(f"KILL {'QUERY ' if query_only else ''}{int(thread_id)}")
        except pymysql.Error:  # pragma: no cover - best effort (already finished)
            pass

    def execute(self, target: Target, sql_text: str) -> ExecutionResult:
        stmts, bad = self._precheck(sql_text)
        if bad:
            return bad
        timeout_s = self.s.query_timeout_ms / 1000
        t0 = time.monotonic()
        try:
            conn = self._connect(target.user, target.password, target.database, unbuffered=True,
                                 read_timeout=timeout_s + 10)
        except pymysql.err.OperationalError as e:
            code = e.args[0] if e.args else None
            msg = ("Sandbox ของคุณมีการเชื่อมต่อพร้อมกันมากเกินไป ลองใหม่อีกครั้ง" if code == 1226
                   else "เชื่อมต่อ MySQL sandbox ไม่ได้ในขณะนี้")
            return ExecutionResult(False, [], 0, len(stmts), ExecError(msg, kind="limit"))
        try:
            with conn.cursor(pymysql.cursors.Cursor) as cur:
                cur.execute("SET SESSION cte_max_recursion_depth = 100000")
                if target.mode == "readonly":
                    cur.execute("SET SESSION TRANSACTION READ ONLY")
            result = self._run_statements(conn, sql_text, stmts, target.mode, timeout_s)
        finally:
            try:
                conn.close()
            except Exception:  # pragma: no cover
                pass
        result.exec_ms = int((time.monotonic() - t0) * 1000)
        return result

    def _run_statements(self, conn, full_sql: str, stmts, mode: str, timeout_s: float) -> ExecutionResult:
        sets: list[ResultSet] = []
        max_rows = self.s.max_result_rows
        tid = conn.thread_id()
        for i, st in enumerate(stmts):
            rs = ResultSet(statement_index=i, command="")
            fired = threading.Event()

            def watchdog():
                fired.set()
                self._kill(tid)

            timer = threading.Timer(timeout_s, watchdog)
            timer.daemon = True
            timer.start()
            cur = conn.cursor()
            try:
                cur.execute(st.text)
                if cur.description:
                    rs.columns = [ColumnInfo(d[0], TYPE_NAMES.get(d[1], f"type:{d[1]}")) for d in cur.description]
                    while True:
                        row = cur.fetchone()
                        if row is None:
                            break
                        if rs.row_count >= max_rows:
                            rs.truncated = True
                            break
                        rs.rows.append([to_jsonable(v) for v in row])
                        rs.row_count += 1
                    if rs.truncated:
                        timer.cancel()
                        self._kill(tid, query_only=False)  # stop the server streaming the rest; connection is discarded
                        rs.command = f"SELECT (แสดง {max_rows} แถวแรก)"
                        if len(sets) < self.s.max_result_sets:
                            sets.append(rs)
                        return ExecutionResult(True, sets, 0, len(stmts))
                    rs.command = f"SELECT {rs.row_count}"
                else:
                    kw = first_keyword(st.text)
                    rs.command = f"{kw} {cur.rowcount}" if kw in ("INSERT", "UPDATE", "DELETE", "REPLACE") and cur.rowcount >= 0 else kw
                if fired.is_set():  # e.g. SLEEP() returns 1 instead of failing when its query is killed
                    raise pymysql.err.OperationalError(1317, "Query execution was interrupted")
            except pymysql.Error as e:
                timer.cancel()
                return ExecutionResult(False, sets, 0, len(stmts), self._error(e, full_sql, st, i, mode, fired.is_set()))
            finally:
                timer.cancel()
                try:
                    cur.close()
                except Exception:
                    pass
            if len(sets) < self.s.max_result_sets:
                sets.append(rs)
        return ExecutionResult(True, sets, 0, len(stmts))

    def _error(self, e: pymysql.Error, full_sql: str, st, index: int, mode: str, timed_out: bool) -> ExecError:
        code = e.args[0] if e.args and isinstance(e.args[0], int) else None
        msg = str(e.args[1]) if len(e.args) > 1 else str(e)
        kind = "sql"
        if code in TIMEOUT_CODES or timed_out:
            kind = "timeout"
            msg = f"Query ใช้เวลานานเกิน {self.s.query_timeout_ms // 1000} วินาที จึงถูกยกเลิก (Query execution was interrupted)"
        elif code in PERMISSION_CODES:
            kind = "permission"
            write_denied = code == 1792 or (code == 1142 and not msg.upper().startswith(("SELECT", "SHOW")))
            msg = (f"{msg} — {READONLY_HINT}" if mode == "readonly" and write_denied
                   else f"{msg} — Sandbox ไม่อนุญาตคำสั่งนี้ด้วยเหตุผลด้านความปลอดภัย")
        elif isinstance(e, pymysql.err.OperationalError) and code in (2013, 2006):
            kind = "timeout"
            msg = "การเชื่อมต่อถูกยกเลิก (เกินเวลาที่กำหนด หรือ Sandbox ปฏิเสธคำสั่ง)"
        line, col = offset_to_line_col(full_sql, st.offset)
        m = re.search(r"near '(.*)' at line (\d+)", msg, re.S)
        if m:
            rel_line = int(m.group(2))
            stmt_lines = st.text.split("\n")
            if 1 <= rel_line <= len(stmt_lines):
                near = m.group(1)[:20]
                pos = stmt_lines[rel_line - 1].find(near) if near else len(stmt_lines[rel_line - 1])  # near '' = at the end
                line = line + rel_line - 1
                col = (pos + 1 if pos >= 0 else 1) + (col - 1 if rel_line == 1 else 0)
        return ExecError(message=msg, sqlstate=f"MY{code}" if code else None, line=line, column=col, statement_index=index,
                         kind=kind)

    # ------------------------------------------------------------------ introspection (trusted, admin)
    def introspect(self, target: Target) -> list[TableInfo]:
        db = target.database
        with self.admin_connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT table_name, table_comment FROM information_schema.tables WHERE table_schema = %s "
                        "AND table_type IN ('BASE TABLE', 'VIEW') ORDER BY table_name", (db,))
            tables = {name: TableInfo(name, comment or None, 0, []) for name, comment in cur.fetchall()}
            cur.execute("SELECT table_name, column_name, referenced_table_name, referenced_column_name "
                        "FROM information_schema.key_column_usage WHERE table_schema = %s AND referenced_table_name IS NOT NULL",
                        (db,))
            fks = {(t, c): f"{rt}.{rc}" for t, c, rt, rc in cur.fetchall()}
            cur.execute("SELECT table_name, column_name, column_type, is_nullable, column_default, column_key, column_comment "
                        "FROM information_schema.columns WHERE table_schema = %s ORDER BY table_name, ordinal_position", (db,))
            for tname, col, typ, nullable, default, key, comment in cur.fetchall():
                if tname in tables:
                    tables[tname].columns.append(TableColumn(col, typ, nullable == "YES", default, key == "PRI",
                                                             fks.get((tname, col)), comment or None))
            for t in tables.values():
                cur.execute(f"SELECT COUNT(*) FROM {_q(db)}.{_q(t.name)}")
                t.row_estimate = int(cur.fetchone()[0])
        return list(tables.values())

    def preview(self, target: Target, table: str, limit: int = 50) -> ExecutionResult:
        if table not in {t.name for t in self.introspect(target)}:
            raise ValueError("unknown table")
        return self.execute(target, f"SELECT * FROM {_q(table)} LIMIT {min(limit, 200)}")

    def drop_user_dbs(self, user_id: int) -> None:  # pragma: no cover - maintenance helper
        uid = int(user_id)
        with self.admin_connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE %s", (f"u\\_{uid}\\_%",))
            for (name,) in cur.fetchall():
                cur.execute(f"DROP DATABASE IF EXISTS {_q(name)}")


_mysql: MySqlSandbox | None = None


def mysql_enabled() -> bool:
    return bool(get_settings().mysql_host)


def get_mysql() -> MySqlSandbox:
    global _mysql
    if _mysql is None:
        _mysql = MySqlSandbox()
    return _mysql
