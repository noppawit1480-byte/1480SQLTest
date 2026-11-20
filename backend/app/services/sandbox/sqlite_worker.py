"""Isolated SQLite executor — runs as its own short-lived process (stdlib only, started with `python -I`).

Reads one JSON request on stdin, writes one JSON result on stdout. The parent process applies OS resource
limits (address space, CPU seconds, max file size, open files) before exec, so a runaway query can only
kill this worker. Inside, SQLite's authorizer denies ATTACH/DETACH, non-introspection PRAGMAs and
extension loading, and read-only targets are opened with `mode=ro`.
"""
import json
import sqlite3
import sys
import time

DENY_ALWAYS = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}
SAFE_PRAGMAS = {"table_info", "table_xinfo", "index_list", "index_info", "foreign_key_list", "table_list",
                "database_list", "collation_list", "function_list"}
WRITE_ACTIONS = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE,
                 sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_INDEX,
                 sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                 sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_TEMP_TABLE,
                 sqlite3.SQLITE_CREATE_TEMP_INDEX, sqlite3.SQLITE_CREATE_TEMP_VIEW, sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
                 sqlite3.SQLITE_REINDEX, sqlite3.SQLITE_ANALYZE, sqlite3.SQLITE_CREATE_VTABLE, sqlite3.SQLITE_DROP_VTABLE}
DENIED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


def _type_of(values):
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool) or isinstance(v, int):
            return "integer"
        if isinstance(v, float):
            return "real"
        if isinstance(v, bytes):
            return "blob"
        return "text"
    return "null"


def _jsonable(v):
    if isinstance(v, bytes):
        return "\\x" + v.hex()
    if isinstance(v, float) and v != v:
        return "nan"
    return v


def main() -> None:
    req = json.loads(sys.stdin.read())
    readonly = req["readonly"]
    deadline = time.monotonic() + req["timeout_ms"] / 1000
    denied = {"reason": None}

    def authorizer(action, arg1, arg2, dbname, source):
        if action in DENY_ALWAYS:
            denied["reason"] = "ATTACH/DETACH ไม่อนุญาตใน sandbox"
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() not in SAFE_PRAGMAS:
            denied["reason"] = f"PRAGMA {arg1} ไม่อนุญาตใน sandbox"
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in DENIED_FUNCTIONS:
            denied["reason"] = f"ฟังก์ชัน {arg2} ไม่อนุญาตใน sandbox"
            return sqlite3.SQLITE_DENY
        if readonly and action in WRITE_ACTIONS and dbname != "temp":
            denied["reason"] = "โหมด Read-only แก้ไขข้อมูลไม่ได้ (สลับเป็น Writable sandbox เพื่อฝึก DML/DDL)"
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    uri = f"file:{req['db_path']}?mode={'ro' if readonly else 'rw'}"
    conn = sqlite3.connect(uri, uri=True, isolation_level=None, check_same_thread=False)
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 10_000_000)
    conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 100_000)
    conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.set_authorizer(authorizer)
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 2000)

    sets, error = [], None
    started = time.perf_counter()
    for i, st in enumerate(req["statements"]):
        denied["reason"] = None
        try:
            cur = conn.execute(st["text"])
            rs = {"statement_index": i, "command": "", "columns": [], "rows": [], "row_count": 0, "truncated": False}
            if cur.description:
                rows = cur.fetchmany(req["max_rows"] + 1)
                rs["truncated"] = len(rows) > req["max_rows"]
                rows = rows[: req["max_rows"]]
                names = [d[0] for d in cur.description]
                rs["columns"] = [{"name": n, "type": _type_of([r[j] for r in rows])} for j, n in enumerate(names)]
                rs["rows"] = [[_jsonable(v) for v in r] for r in rows]
                rs["row_count"] = len(rows)
                rs["command"] = f"SELECT {len(rows)}" + (" (แสดงบางส่วน)" if rs["truncated"] else "")
            else:
                verb = st["keyword"] or "OK"
                rs["command"] = f"{verb} {cur.rowcount}" if cur.rowcount >= 0 and verb in ("INSERT", "UPDATE", "DELETE") else verb
            if len(sets) < req["max_sets"]:
                sets.append(rs)
            if rs["truncated"]:
                break
        except sqlite3.Error as e:
            msg = str(e)
            kind = "sql"
            if msg == "interrupted":
                kind, msg = "timeout", f"Query ใช้เวลานานเกิน {req['timeout_ms'] // 1000} วินาที จึงถูกยกเลิก"
            elif denied["reason"] or "not authorized" in msg:
                kind, msg = "permission", f"{msg} — {denied['reason'] or 'ไม่อนุญาตใน sandbox'}"
            elif "disk I/O error" in msg or "database or disk is full" in msg:
                kind, msg = "limit", "ฐานข้อมูลส่วนตัวมีขนาดเกินขีดจำกัดของ sandbox — กด Reset เพื่อคืนค่าเริ่มต้น"
            elif "readonly database" in msg:
                kind, msg = "permission", f"{msg} — โหมด Read-only แก้ไขข้อมูลไม่ได้"
            error = {"message": msg, "sqlstate": getattr(e, "sqlite_errorname", None), "detail": None, "hint": None,
                     "line": st["line"], "column": st["column"], "statement_index": i, "kind": kind}
            break
    conn.close()
    out = {"ok": error is None, "result_sets": sets, "exec_ms": int((time.perf_counter() - started) * 1000),
           "statements": len(req["statements"]), "error": error, "notices": []}
    sys.stdout.write(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
