"""PostgreSQL implementation of the sandbox EngineAdapter.

Security model (enforced by PostgreSQL itself, not by inspecting SQL text):
  * separate cluster from the main platform DB
  * `sbx_reader`  — SELECT-only, default_transaction_read_only, connects only to ro_* DBs
  * `sbx_u_<id>`  — owns only that user's u_<id>_* databases; NOSUPERUSER NOCREATEDB NOCREATEROLE
  * role-level statement_timeout / work_mem / temp_file_limit (temp_file_limit is superuser-only)
  * every request uses a fresh connection, closed afterwards; a watchdog cancels the backend
    even if the user ran `SET statement_timeout = 0`
  * results are streamed in single-row mode and cut at MAX_ROWS (never fully buffered)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
import sqlparse
from psycopg import sql as psql

from app.config import Settings, get_settings
from app.services.sandbox.base import (ColumnInfo, ExecError, ExecutionResult, ResultSet, TableColumn, TableInfo,
                                       Target, to_jsonable)
from app.services.sql_split import offset_to_line_col, split_statements

log = logging.getLogger("sandbox")

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_dbs"
DB_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
OWNER_ROLE = "sbx_owner"
READER_ROLE = "sbx_reader"
SYSTEM_USER_ID = 0  # used by the seeder to compute expected results of DML exercises

PERMISSION_SQLSTATES = {"42501"}
TIMEOUT_SQLSTATES = {"57014"}


COMMAND_KEYWORDS = {
    "CREATE", "DROP", "ALTER", "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "BEGIN", "START", "COMMIT", "END",
    "ROLLBACK", "ABORT", "SAVEPOINT", "RELEASE", "SET", "RESET", "GRANT", "REVOKE", "COMMENT", "ANALYZE", "VACUUM",
    "DISCARD", "PREPARE", "DEALLOCATE", "LOCK", "DO", "REINDEX", "CLUSTER", "REFRESH", "DECLARE", "CLOSE", "LISTEN",
    "NOTIFY", "UNLISTEN", "CHECKPOINT", "SECURITY", "IMPORT", "LOAD", "REASSIGN",
}
ROW_KEYWORDS = {"SELECT", "WITH", "VALUES", "TABLE", "("}


class SandboxBusy(Exception):
    """The learner already has the maximum number of concurrent sandbox connections."""


def first_keyword(stmt_text: str) -> str:
    parsed = sqlparse.parse(stmt_text)
    if not parsed:
        return ""
    tok = parsed[0].token_first(skip_cm=True, skip_ws=True)
    return tok.value.split()[0].upper() if tok is not None and tok.value.split() else ""


def is_command_statement(stmt_text: str) -> bool:
    """True for statements that never return rows. Used only to pick execute() vs stream() —
    NOT a security control (permissions are enforced by PostgreSQL)."""
    if first_keyword(stmt_text) not in COMMAND_KEYWORDS:
        return False
    return not any(t.ttype in sqlparse.tokens.Keyword and t.value.upper() == "RETURNING"
                   for t in sqlparse.parse(stmt_text)[0].flatten())


def user_role(user_id: int) -> str:
    return f"sbx_u_{int(user_id)}"


def user_db(user_id: int, db_key: str) -> str:
    return f"u_{int(user_id)}_{db_key}"


class PostgresSandbox:
    engine = "postgresql"

    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self._lock = threading.Lock()  # serialises CREATE/DROP DATABASE operations

    # ------------------------------------------------------------------ connections
    def _role_password(self, user_id: int) -> str:
        return hmac.new(self.s.sandbox_role_secret.encode(), f"sbx-user:{user_id}".encode(), hashlib.sha256).hexdigest()

    def _connect(self, database: str, user: str, password: str, autocommit: bool = True) -> psycopg.Connection:
        """Connect; if the role's CONNECTION LIMIT is momentarily reached (a burst of parallel requests from
        one learner), wait briefly instead of failing. Persistent exhaustion raises SandboxBusy."""
        deadline = time.monotonic() + 3.0
        while True:
            try:
                return psycopg.connect(host=self.s.sandbox_host, port=self.s.sandbox_port, dbname=database, user=user,
                                       password=password, connect_timeout=5, autocommit=autocommit,
                                       options=f"-c statement_timeout={self.s.query_timeout_ms}",
                                       application_name="sqlab-sandbox")
            except psycopg.OperationalError as e:
                if "too many connections" not in str(e):
                    raise
                if time.monotonic() > deadline:
                    raise SandboxBusy() from e
                time.sleep(0.15)

    def admin_connect(self, database: str = "postgres") -> psycopg.Connection:
        return self._connect(database, self.s.sandbox_admin_user, self.s.sandbox_admin_password)

    @staticmethod
    def _check_key(db_key: str) -> str:
        if not DB_KEY_RE.match(db_key) or not (SAMPLE_DIR / f"{db_key}.sql").exists():
            raise ValueError(f"unknown sample database: {db_key}")
        return db_key

    # ------------------------------------------------------------------ targets
    def readonly_target(self, db_key: str) -> Target:
        self._check_key(db_key)
        return Target(db_key, f"ro_{db_key}", READER_ROLE, self.s.sandbox_reader_password, "readonly")

    def user_target(self, user_id: int, db_key: str) -> Target:
        self._check_key(db_key)
        return Target(db_key, user_db(user_id, db_key), user_role(user_id), self._role_password(user_id), "writable")

    # ------------------------------------------------------------------ execution
    def execute(self, target: Target, sql_text: str) -> ExecutionResult:
        """Run a user script. Read-only targets run inside BEGIN READ ONLY … ROLLBACK."""
        started = time.perf_counter()
        pre = self._precheck(sql_text)
        if pre:
            return pre
        stmts = split_statements(sql_text)
        try:
            conn = self._connect(target.database, target.user, target.password)
        except SandboxBusy:
            return ExecutionResult(False, [], 0, len(stmts), ExecError(
                "คุณมี query ที่กำลังทำงานพร้อมกันมากเกินไป กรุณารอสักครู่แล้วลองใหม่", kind="limit"))
        except psycopg.OperationalError as e:
            log.error("sandbox connect failed db=%s: %s", target.database, e)
            return ExecutionResult(False, [], 0, len(stmts),
                                   ExecError("ไม่สามารถเชื่อมต่อฐานข้อมูล Sandbox ได้ กรุณาลองใหม่", kind="internal"))
        notices: list[str] = []
        conn.add_notice_handler(lambda d: notices.append(d.message_primary or ""))
        watchdog = threading.Timer(self.s.query_timeout_ms / 1000 + 1.0, self._cancel, args=(conn,))
        watchdog.start()
        try:
            if target.mode == "readonly":
                conn.execute("BEGIN READ ONLY")
            result = self._run_statements(conn, sql_text, stmts, target.mode)
        finally:
            watchdog.cancel()
            conn.close()  # discards any open transaction
        result.exec_ms = int((time.perf_counter() - started) * 1000)
        result.notices = notices[:20]
        return result

    def execute_on_fresh_copy(self, user_id: int, db_key: str, sql_text: str,
                              check_sql: str | None = None) -> ExecutionResult:
        """Run `sql_text` then `check_sql` on a brand-new throwaway copy of the template.

        Used for DML/DDL exercises: grading is isolated from the learner's own sandbox state,
        and COMMIT/ROLLBACK inside the answer behave exactly like on a real server.
        """
        self._check_key(db_key)
        pre = self._precheck(sql_text)
        if pre:
            return pre
        self.ensure_role(user_id)
        dbname = f"chk_{int(user_id)}_{secrets.token_hex(4)}"
        self._clone_template(db_key, dbname, user_role(user_id))
        try:
            target = Target(db_key, dbname, user_role(user_id), self._role_password(user_id), "writable")
            started = time.perf_counter()
            user_res = self.execute(target, sql_text)
            if not user_res.ok or check_sql is None:
                return user_res
            check_res = self.execute(target, check_sql)
            check_res.exec_ms = int((time.perf_counter() - started) * 1000)
            if not check_res.ok:
                check_res.error.message = "ตรวจสอบผลไม่สำเร็จหลังรันคำตอบ: " + check_res.error.message  # type: ignore[union-attr]
                check_res.error.line = check_res.error.column = None  # type: ignore[union-attr]
            check_res.notices = user_res.notices
            return check_res
        finally:
            self._drop_database(dbname)

    def run_scripts_on_fresh_copy(self, user_id: int, db_key: str, scripts: list[str],
                                  stop_on_error: bool = True) -> list[ExecutionResult]:
        """Run several scripts in order on one throwaway copy (e.g. EXPLAIN → CREATE INDEX → EXPLAIN)."""
        self._check_key(db_key)
        self.ensure_role(user_id)
        dbname = f"lab_{int(user_id)}_{secrets.token_hex(4)}"
        self._clone_template(db_key, dbname, user_role(user_id))
        try:
            target = Target(db_key, dbname, user_role(user_id), self._role_password(user_id), "writable")
            out = []
            for sql_text in scripts:
                res = self.execute(target, sql_text)
                out.append(res)
                if stop_on_error and not res.ok:
                    break
            return out
        finally:
            self._drop_database(dbname)

    def _precheck(self, sql_text: str) -> ExecutionResult | None:
        if not sql_text.strip():
            return ExecutionResult(False, [], 0, 0, ExecError("กรุณาพิมพ์คำสั่ง SQL ก่อนรัน", kind="limit"))
        if len(sql_text) > self.s.max_sql_length:
            return ExecutionResult(False, [], 0, 0, ExecError(
                f"SQL ยาวเกินกำหนด ({len(sql_text)} > {self.s.max_sql_length} ตัวอักษร)", kind="limit"))
        n = len(split_statements(sql_text))
        if n == 0:
            return ExecutionResult(False, [], 0, 0, ExecError("ไม่พบคำสั่ง SQL (มีแต่ comment)", kind="limit"))
        if n > self.s.max_statements:
            return ExecutionResult(False, [], 0, n, ExecError(
                f"จำนวนคำสั่งเกินกำหนด ({n} > {self.s.max_statements})", kind="limit"))
        return None

    @staticmethod
    def _cancel(conn: psycopg.Connection) -> None:
        try:
            conn.cancel_safe(timeout=2)
        except Exception:  # pragma: no cover - best effort
            pass

    def _run_statements(self, conn: psycopg.Connection, full_sql: str, stmts, mode: str = "readonly") -> ExecutionResult:
        sets: list[ResultSet] = []
        max_rows = self.s.max_result_rows
        for i, st in enumerate(stmts):
            cur = conn.cursor()
            rs = ResultSet(statement_index=i, command="")
            try:
                if is_command_statement(st.text):
                    cur.execute(st.text)
                    if cur.description:  # e.g. FETCH/EXECUTE that unexpectedly returned rows
                        rs.columns = self._columns(conn, cur)
                        for row in cur.fetchmany(max_rows + 1):
                            if rs.row_count >= max_rows:
                                rs.truncated = True
                                break
                            rs.rows.append([to_jsonable(v) for v in row])
                            rs.row_count += 1
                    rs.command = cur.statusmessage or first_keyword(st.text)
                else:
                    first = True
                    try:
                        for row in cur.stream(st.text):
                            if first:
                                rs.columns = self._columns(conn, cur)
                                first = False
                            if rs.row_count >= max_rows:
                                rs.truncated = True
                                break
                            rs.rows.append([to_jsonable(v) for v in row])
                            rs.row_count += 1
                    except psycopg.ProgrammingError as pe:
                        # statement completed but returned no rows (e.g. WITH … DELETE without RETURNING)
                        if "didn't produce a result" not in str(pe):
                            raise
                    if rs.truncated:
                        # abort remaining server-side work; the connection is unusable afterwards
                        self._cancel(conn)
                        rs.command = f"SELECT (แสดง {max_rows} แถวแรก)"
                        if len(sets) < self.s.max_result_sets:
                            sets.append(rs)
                        return ExecutionResult(True, sets, 0, len(stmts))
                    if first:
                        # zero rows: psycopg drops the empty result's metadata, so ask the server to
                        # *describe* the statement (prepare + describe, never executed) for column headers
                        rs.columns = self._describe(conn, cur, st.text)
                    rs.command = (f"SELECT {rs.row_count}" if rs.columns and first_keyword(st.text) in ROW_KEYWORDS
                                  else f"{first_keyword(st.text)} {rs.row_count}" if rs.columns else first_keyword(st.text))
            except psycopg.Error as e:
                return ExecutionResult(False, sets, 0, len(stmts), self._error(e, full_sql, st, i, mode))
            finally:
                try:
                    cur.close()
                except Exception:
                    pass
            if len(sets) < self.s.max_result_sets:
                sets.append(rs)
        return ExecutionResult(True, sets, 0, len(stmts))

    @staticmethod
    def _describe(conn: psycopg.Connection, cur: psycopg.Cursor, stmt: str) -> list[ColumnInfo]:
        if cur.description:
            return PostgresSandbox._columns(conn, cur)
        try:
            pg = conn.pgconn
            if pg.prepare(b"", stmt.encode()).status != 1:  # PGRES_COMMAND_OK
                return []
            d = pg.describe_prepared(b"")
            cols = []
            for i in range(d.nfields):
                info = conn.adapters.types.get(d.ftype(i))
                cols.append(ColumnInfo((d.fname(i) or b"?").decode(), info.name if info else f"oid:{d.ftype(i)}"))
            return cols
        except Exception:  # metadata is best-effort; never fail the user's query because of it
            return []

    @staticmethod
    def _columns(conn: psycopg.Connection, cur: psycopg.Cursor) -> list[ColumnInfo]:
        cols = []
        for d in cur.description or []:
            info = conn.adapters.types.get(d.type_code)
            cols.append(ColumnInfo(d.name, info.name if info else f"oid:{d.type_code}"))
        return cols

    def _error(self, e: psycopg.Error, full_sql: str, st, index: int, mode: str = "readonly") -> ExecError:
        diag = e.diag
        state = diag.sqlstate
        kind = "sql"
        msg = diag.message_primary or str(e).strip()
        if state in TIMEOUT_SQLSTATES:
            kind = "timeout"
            msg = f"Query ใช้เวลานานเกิน {self.s.query_timeout_ms // 1000} วินาที จึงถูกยกเลิก (canceling statement due to statement timeout)"
        elif state in PERMISSION_SQLSTATES or state == "25006":
            kind = "permission"
            if mode == "readonly":
                msg = f"{msg} — โหมด Read-only แก้ไขข้อมูลไม่ได้ (ถ้าต้องการฝึก INSERT/UPDATE/DDL ให้สลับเป็นโหมด Writable sandbox)"
            else:
                msg = f"{msg} — Sandbox ไม่อนุญาตคำสั่งนี้ด้วยเหตุผลด้านความปลอดภัย"
        elif isinstance(e, psycopg.OperationalError) and not state:
            kind = "timeout"
            msg = "การเชื่อมต่อถูกยกเลิก (เกินเวลาที่กำหนด หรือ Sandbox ปฏิเสธคำสั่ง)"
        line = col = None
        pos = diag.statement_position
        if pos:
            line, col = offset_to_line_col(full_sql, st.offset + int(pos) - 1)
        else:
            line, col = offset_to_line_col(full_sql, st.offset)
        return ExecError(message=msg, sqlstate=state, detail=diag.message_detail, hint=diag.message_hint,
                         line=line, column=col, statement_index=index, kind=kind)

    # ------------------------------------------------------------------ introspection
    def introspect(self, target: Target) -> list[TableInfo]:
        q = """
        SELECT c.relname, obj_description(c.oid, 'pg_class'), GREATEST(c.reltuples, 0)::bigint,
               a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull,
               pg_get_expr(ad.adbin, ad.adrelid),
               EXISTS (SELECT 1 FROM pg_constraint p WHERE p.conrelid = c.oid AND p.contype = 'p' AND a.attnum = ANY(p.conkey)),
               (SELECT rc.relname || '.' || ra.attname
                  FROM pg_constraint f
                  JOIN pg_class rc ON rc.oid = f.confrelid
                  JOIN pg_attribute ra ON ra.attrelid = f.confrelid AND ra.attnum = f.confkey[array_position(f.conkey, a.attnum)]
                 WHERE f.conrelid = c.oid AND f.contype = 'f' AND a.attnum = ANY(f.conkey) LIMIT 1),
               col_description(c.oid, a.attnum)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
          LEFT JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
         WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'p')
         ORDER BY c.relname, a.attnum
        """
        tables: dict[str, TableInfo] = {}
        with self._connect(target.database, target.user, target.password) as conn:
            for rel, tcomment, est, col, typ, nullable, default, is_pk, fk, ccomment in conn.execute(q):
                t = tables.setdefault(rel, TableInfo(rel, tcomment, int(est), []))
                t.columns.append(TableColumn(col, typ, nullable, default, is_pk, fk, ccomment))
            # exact counts are cheap for sample-size data and more useful to learners than estimates
            for t in tables.values():
                ident = psql.Identifier(t.name)
                t.row_estimate = conn.execute(psql.SQL("SELECT count(*) FROM {}").format(ident)).fetchone()[0]
        return list(tables.values())

    def preview(self, target: Target, table: str, limit: int = 50) -> ExecutionResult:
        names = {t.name for t in self.introspect(target)}
        if table not in names:
            raise ValueError("unknown table")
        q = psql.SQL("SELECT * FROM {} LIMIT {}").format(psql.Identifier(table), psql.Literal(min(limit, 200)))
        with self._connect(target.database, target.user, target.password) as conn:
            return self.execute(target, q.as_string(conn))

    # ------------------------------------------------------------------ provisioning (admin)
    def ensure_role(self, user_id: int) -> str:
        role = user_role(user_id)
        with self._db_lock(f"role:{role}") as conn:
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            ident = psql.Identifier(role)
            if not exists:
                conn.execute(psql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                                      "NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5 PASSWORD {}")
                             .format(ident, psql.Literal(self._role_password(user_id))))
            conn.execute(psql.SQL("ALTER ROLE {} CONNECTION LIMIT 5").format(ident))
            self._apply_role_limits(conn, role)
        return role

    def _apply_role_limits(self, conn: psycopg.Connection, role: str) -> None:
        ident = psql.Identifier(role)
        for setting, value in (("statement_timeout", f"{self.s.query_timeout_ms}"), ("lock_timeout", "2000"),
                               ("idle_in_transaction_session_timeout", "10000"), ("work_mem", "8MB"),
                               ("temp_file_limit", "64MB"), ("search_path", "public")):
            conn.execute(psql.SQL("ALTER ROLE {} SET {} = {}").format(ident, psql.Identifier(setting), psql.Literal(value)))

    @contextmanager
    def _db_lock(self, name: str):
        """Cross-process lock (advisory lock in the sandbox cluster) around create/drop of one database —
        concurrent requests (and multiple API workers) must not race on CREATE DATABASE."""
        with self.admin_connect() as conn:
            conn.execute("SELECT pg_advisory_lock(hashtext(%s))", (name,))
            try:
                yield conn
            finally:
                conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (name,))

    def ensure_user_db(self, user_id: int, db_key: str) -> Target:
        self._check_key(db_key)
        self.ensure_role(user_id)
        name = user_db(user_id, db_key)
        with self._db_lock(name) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
            if not exists:
                self._clone_template(db_key, name, user_role(user_id))
        return self.user_target(user_id, db_key)

    def reset_user_db(self, user_id: int, db_key: str) -> None:
        self._check_key(db_key)
        self.ensure_role(user_id)
        name = user_db(user_id, db_key)
        with self._db_lock(name):
            self._drop_database(name)
            self._clone_template(db_key, name, user_role(user_id))

    def user_db_size(self, user_id: int, db_key: str) -> int:
        with self.admin_connect() as conn:
            row = conn.execute("SELECT pg_database_size(%s)", (user_db(user_id, db_key),)).fetchone()
        return int(row[0]) if row else 0

    def _clone_template(self, db_key: str, new_db: str, owner_role: str) -> None:
        with self._lock:
            with self.admin_connect() as conn:
                conn.execute(psql.SQL("CREATE DATABASE {} TEMPLATE {} OWNER {}").format(
                    psql.Identifier(new_db), psql.Identifier(f"tpl_{db_key}"), psql.Identifier(owner_role)))
                conn.execute(psql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(psql.Identifier(new_db)))
                conn.execute(psql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(
                    psql.Identifier(new_db), psql.Identifier(owner_role)))
            with self.admin_connect(new_db) as conn:
                # objects in the template are owned by sbx_owner (which owns nothing shared),
                # so REASSIGN only touches this database's tables/sequences.
                conn.execute(psql.SQL("REASSIGN OWNED BY {} TO {}").format(
                    psql.Identifier(OWNER_ROLE), psql.Identifier(owner_role)))

    def _drop_database(self, name: str) -> None:
        with self._lock:
            with self.admin_connect() as conn:
                conn.execute(psql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(psql.Identifier(name)))

    def provision_templates(self, force: bool = False) -> list[str]:
        """Create roles, tpl_<key> templates and ro_<key> read-only copies. Idempotent."""
        created = []
        with self.admin_connect() as conn:
            for role, login in ((OWNER_ROLE, False), (READER_ROLE, True)):
                if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                    conn.execute(psql.SQL("CREATE ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                                          + ("LOGIN" if login else "NOLOGIN")).format(psql.Identifier(role)))
            conn.execute(psql.SQL("ALTER ROLE {} LOGIN CONNECTION LIMIT 50 PASSWORD {}").format(
                psql.Identifier(READER_ROLE), psql.Literal(self.s.sandbox_reader_password)))
            self._apply_role_limits(conn, READER_ROLE)
            conn.execute(psql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(psql.Identifier(READER_ROLE)))
            # nobody but explicitly granted roles may connect to the maintenance DB either
            conn.execute("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC")
        for path in sorted(SAMPLE_DIR.glob("*.sql")):
            if self.provision_one(path.stem, force=force):
                created.append(path.stem)
        return created

    def provision_one(self, key: str, force: bool = False) -> bool:
        """(Re)build tpl_<key> and ro_<key> from app/sample_dbs/<key>.sql. Users' writable copies are untouched."""
        self._check_key(key)
        path = SAMPLE_DIR / f"{key}.sql"
        tpl, ro = f"tpl_{key}", f"ro_{key}"
        with self.admin_connect() as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (tpl,)).fetchone()
        if exists and not force:
            return False
        for db in (ro, tpl):
            self._drop_database(db)
        with self.admin_connect() as conn:
            conn.execute(psql.SQL("CREATE DATABASE {} OWNER {}").format(psql.Identifier(tpl),
                                                                        psql.Identifier(self.s.sandbox_admin_user)))
            conn.execute(psql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(psql.Identifier(tpl)))
        with self.admin_connect(tpl) as conn:
            conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            conn.execute(psql.SQL("GRANT CREATE, USAGE ON SCHEMA public TO {}").format(psql.Identifier(OWNER_ROLE)))
            conn.execute(psql.SQL("SET ROLE {}").format(psql.Identifier(OWNER_ROLE)))
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))  # trusted, generated by us
            conn.execute("RESET ROLE")
            conn.execute(psql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(psql.Identifier(OWNER_ROLE)))
            conn.execute("ANALYZE")
        with self._lock, self.admin_connect() as conn:
            conn.execute(psql.SQL("CREATE DATABASE {} TEMPLATE {} OWNER {}").format(
                psql.Identifier(ro), psql.Identifier(tpl), psql.Identifier(self.s.sandbox_admin_user)))
            conn.execute(psql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(psql.Identifier(ro)))
            conn.execute(psql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(psql.Identifier(ro), psql.Identifier(READER_ROLE)))
        with self.admin_connect(ro) as conn:
            conn.execute(psql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(psql.Identifier(READER_ROLE)))
            conn.execute(psql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(psql.Identifier(READER_ROLE)))
        log.info("provisioned sample database %s", key)
        return True


_instance: PostgresSandbox | None = None


def get_sandbox() -> PostgresSandbox:
    global _instance
    if _instance is None:
        _instance = PostgresSandbox()
    return _instance
