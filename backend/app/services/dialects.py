"""SQL dialect comparison: run one query on PostgreSQL and SQLite and explain the differences.

Feature detection uses the PostgreSQL parser (pglast). MySQL and SQL Server appear as *reference
equivalents* only — those engines are not executed by this platform (see docs/05-roadmap.md).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pglast
from pglast import ast

from app.services.assistant.rules import walk
from app.services.checker import compare_results


@dataclass
class Feature:
    key: str
    title: str
    postgresql: str
    sqlite: str
    mysql: str
    sqlserver: str
    note: str


FEATURES: dict[str, Feature] = {f.key: f for f in [
    Feature("limit", "จำกัดจำนวนแถว", "LIMIT n OFFSET m / FETCH FIRST n ROWS ONLY", "LIMIT n OFFSET m", "LIMIT m, n หรือ LIMIT n OFFSET m",
            "SELECT TOP (n) … / OFFSET m ROWS FETCH NEXT n ROWS ONLY", "SQL Server ไม่มี LIMIT"),
    Feature("ilike", "ค้นหาแบบไม่สนตัวพิมพ์", "col ILIKE '%x%'", "col LIKE '%x%' (LIKE ไม่สนตัวพิมพ์สำหรับ ASCII อยู่แล้ว)",
            "col LIKE '%x%' (ขึ้นกับ collation; ค่าเริ่มต้นไม่สนตัวพิมพ์)", "col LIKE '%x%' (ขึ้นกับ collation)", "ILIKE มีเฉพาะ PostgreSQL"),
    Feature("cast_op", "แปลงชนิดข้อมูล", "x::int หรือ CAST(x AS int)", "CAST(x AS INTEGER)", "CAST(x AS SIGNED)", "CAST(x AS int) / CONVERT(int, x)",
            "`::` เป็น syntax เฉพาะ PostgreSQL — CAST() เป็นมาตรฐานที่ใช้ได้ทุกที่"),
    Feature("distinct_on", "DISTINCT ON", "SELECT DISTINCT ON (k) …", "ไม่มี — ใช้ ROW_NUMBER() OVER (PARTITION BY k …) = 1", "ไม่มี — ใช้ ROW_NUMBER()",
            "ไม่มี — ใช้ ROW_NUMBER()", "Window function เป็นทางเลือกที่พกพาได้"),
    Feature("filter", "Aggregate FILTER", "COUNT(*) FILTER (WHERE c)", "COUNT(*) FILTER (WHERE c) (3.30+)", "SUM(CASE WHEN c THEN 1 ELSE 0 END)",
            "SUM(CASE WHEN c THEN 1 ELSE 0 END)", "CASE WHEN ใน aggregate ใช้ได้ทุก engine"),
    Feature("returning", "RETURNING", "INSERT … RETURNING id", "INSERT … RETURNING id (3.35+)", "ไม่มี — ใช้ LAST_INSERT_ID()",
            "OUTPUT inserted.id", ""),
    Feature("upsert", "Upsert", "INSERT … ON CONFLICT (k) DO UPDATE", "INSERT … ON CONFLICT (k) DO UPDATE", "INSERT … ON DUPLICATE KEY UPDATE",
            "MERGE …", ""),
    Feature("generate_series", "สร้างลำดับตัวเลข/วันที่", "generate_series(a, b, step)", "WITH RECURSIVE … (ไม่มี generate_series ในตัว)",
            "WITH RECURSIVE …", "GENERATE_SERIES (2022+) หรือ recursive CTE", ""),
    Feature("date_trunc", "ปัดวันที่เป็นเดือน/ปี", "DATE_TRUNC('month', d)", "strftime('%Y-%m-01', d) หรือ date(d, 'start of month')",
            "DATE_FORMAT(d, '%Y-%m-01')", "DATETRUNC(month, d) (2022+) / DATEFROMPARTS(YEAR(d), MONTH(d), 1)", ""),
    Feature("extract", "ดึงส่วนของวันที่", "EXTRACT(YEAR FROM d)", "CAST(strftime('%Y', d) AS INTEGER)", "EXTRACT(YEAR FROM d) / YEAR(d)",
            "YEAR(d) / DATEPART(year, d)", ""),
    Feature("to_char", "จัดรูปแบบวันที่เป็นข้อความ", "TO_CHAR(d, 'YYYY-MM')", "strftime('%Y-%m', d)", "DATE_FORMAT(d, '%Y-%m')", "FORMAT(d, 'yyyy-MM')", ""),
    Feature("interval", "บวก/ลบช่วงเวลา", "d + INTERVAL '30 days'", "date(d, '+30 days')", "d + INTERVAL 30 DAY / DATE_ADD(d, INTERVAL 30 DAY)",
            "DATEADD(day, 30, d)", ""),
    Feature("age", "ผลต่างของวันที่", "AGE(a, b) / a::date - b::date", "julianday(a) - julianday(b)", "DATEDIFF(a, b) / TIMESTAMPDIFF(…)",
            "DATEDIFF(day, b, a)", ""),
    Feature("now", "วันเวลาปัจจุบัน", "NOW() / CURRENT_DATE", "datetime('now') / date('now') / CURRENT_DATE", "NOW() / CURDATE()",
            "GETDATE() / CAST(GETDATE() AS date)", "SQLite คืนเวลาเป็น UTC"),
    Feature("string_agg", "รวมข้อความในกลุ่ม", "STRING_AGG(x, ', ')", "group_concat(x, ', ') หรือ string_agg (3.44+)", "GROUP_CONCAT(x SEPARATOR ', ')",
            "STRING_AGG(x, ', ')", ""),
    Feature("array_agg", "รวมเป็น array", "ARRAY_AGG(x)", "json_group_array(x)", "JSON_ARRAYAGG(x)", "ไม่มี array — ใช้ STRING_AGG", ""),
    Feature("percentile", "Percentile / median", "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)", "ไม่มีในตัว", "ไม่มีในตัว (ใช้ window function)",
            "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x) OVER ()", ""),
    Feature("regex", "Regular expression", "x ~ 'pattern'", "x REGEXP 'p' (ต้องมี extension)", "x REGEXP 'pattern'", "ไม่มีในตัว — ใช้ LIKE/PATINDEX", ""),
    Feature("json", "อ่านค่าจาก JSON", "props->>'key'", "props->>'key' (3.38+) / json_extract(props, '$.key')", "props->>'$.key' / JSON_UNQUOTE(JSON_EXTRACT(…))",
            "JSON_VALUE(props, '$.key')", ""),
    Feature("concat", "ต่อข้อความ", "a || b / CONCAT(a, b)", "a || b", "CONCAT(a, b) (|| คือ OR โดยค่าเริ่มต้น)", "a + b / CONCAT(a, b)", ""),
    Feature("boolean", "ชนิด boolean", "true / false (ชนิด boolean จริง)", "1 / 0 (TRUE/FALSE เป็น alias ของ 1/0)", "TINYINT(1): 1 / 0",
            "BIT: 1 / 0", "SQLite คืนค่า boolean เป็นตัวเลข — ผลลัพธ์อาจแสดงต่างกัน"),
    Feature("full_join", "FULL / RIGHT JOIN", "รองรับ", "รองรับตั้งแต่ 3.39", "ไม่มี FULL JOIN — ใช้ LEFT JOIN UNION RIGHT JOIN", "รองรับ", ""),
    Feature("numeric", "ทศนิยมแม่นยำ", "numeric(10,2) แม่นยำทุกหลัก", "เก็บเป็น REAL (floating point) — อาจมีเศษทศนิยมเพี้ยนเล็กน้อย",
            "DECIMAL(10,2)", "DECIMAL(10,2)", "ผลรวมเงินบน SQLite อาจต่างจาก PostgreSQL ในหลักทศนิยมท้าย ๆ"),
    Feature("int_division", "หารจำนวนเต็ม", "7 / 2 = 3", "7 / 2 = 3", "7 / 2 = 3.5000 (ใช้ DIV สำหรับหารเต็ม)", "7 / 2 = 3",
            "MySQL หารเป็นทศนิยมเสมอ"),
]}

DATE_FUNCS = {"date_trunc": "date_trunc", "date_part": "extract", "extract": "extract", "to_char": "to_char", "age": "age",
              "generate_series": "generate_series", "string_agg": "string_agg", "array_agg": "array_agg",
              "percentile_cont": "percentile", "percentile_disc": "percentile", "now": "now"}


def detect_features(sql: str) -> list[str]:
    found: list[str] = []

    def add(k: str):
        if k not in found:
            found.append(k)

    if "::" in sql:
        add("cast_op")
    try:
        tree = pglast.parse_sql(sql)
    except Exception:
        return found
    for n in walk(tree):
        if isinstance(n, ast.SelectStmt):
            if n.limitCount is not None or n.limitOffset is not None:
                add("limit")
            if n.distinctClause and any(d is not None for d in n.distinctClause):
                add("distinct_on")
        if isinstance(n, ast.A_Expr) and n.name:
            op = n.name[-1].sval
            if op in ("~~*", "!~~*"):
                add("ilike")
            elif op in ("~", "~*", "!~", "!~*"):
                add("regex")
            elif op in ("->>", "->", "#>>", "@>"):
                add("json")
            elif op == "||":
                add("concat")
            elif op == "/" and all(isinstance(x, ast.A_Const) and isinstance(x.val, ast.Integer) for x in (n.lexpr, n.rexpr)):
                add("int_division")
        if isinstance(n, ast.FuncCall):
            name = n.funcname[-1].sval.lower()
            if name in DATE_FUNCS:
                add(DATE_FUNCS[name])
            if n.agg_filter is not None:
                add("filter")
        if isinstance(n, ast.SQLValueFunction):
            add("now")
        if isinstance(n, ast.TypeCast) and n.typeName and n.typeName.names and n.typeName.names[-1].sval == "interval":
            add("interval")
        if isinstance(n, ast.TypeCast) and n.typeName and n.typeName.names and n.typeName.names[-1].sval in ("numeric",):
            add("numeric")
        if isinstance(n, ast.A_Const) and isinstance(n.val, ast.Boolean):
            add("boolean")
        if isinstance(n, ast.JoinExpr) and int(n.jointype) in (2, 3):  # FULL, RIGHT
            add("full_join")
        if isinstance(n, (ast.InsertStmt, ast.UpdateStmt, ast.DeleteStmt)) and n.returningList:
            add("returning")
        if isinstance(n, ast.InsertStmt) and n.onConflictClause is not None:
            add("upsert")
    return found


def _has_order(sql: str) -> bool:
    try:
        tree = pglast.parse_sql(sql)
        last = tree[-1].stmt
        return isinstance(last, ast.SelectStmt) and bool(last.sortClause)
    except Exception:
        return False


def compare(sql: str, pg_result, sqlite_result) -> dict:
    out: dict = {"same": None, "message": "", "details": {}}
    if not pg_result.ok or not sqlite_result.ok:
        which = [n for n, r in (("PostgreSQL", pg_result), ("SQLite", sqlite_result)) if not r.ok]
        out["message"] = (f"รันไม่สำเร็จบน {' และ '.join(which)} — มักเกิดจากฟังก์ชันหรือ syntax ที่มีเฉพาะบาง engine (ดูตารางเทียบด้านล่าง)"
                          if len(which) == 1 else "รันไม่สำเร็จทั้งสอง engine — ตรวจ SQL อีกครั้ง")
        out["same"] = False if len(which) == 1 else None
        return out
    a, b = pg_result.last_rows, sqlite_result.last_rows
    if a is None and b is None:
        out["same"], out["message"] = True, "ทั้งสอง engine ทำคำสั่งสำเร็จ (ไม่มีผลลัพธ์เป็นตาราง)"
        return out
    if a is None or b is None:
        out["same"], out["message"] = False, "engine หนึ่งคืนผลลัพธ์เป็นตาราง แต่อีก engine ไม่คืน"
        return out
    to_dict = lambda r: {"columns": [asdict(c) for c in r.columns], "rows": r.rows, "truncated": r.truncated}  # noqa: E731
    # compare against SQLite's column types as "expected" so numeric text from PostgreSQL is normalized
    pg = to_dict(a)
    sq = to_dict(b)
    sq["columns"] = [{"name": c["name"], "type": pc["type"]} for c, pc in zip(sq["columns"], pg["columns"], strict=False)]
    chk = compare_results(sq, pg, order_matters=_has_order(sql), check_column_names=False)
    out["same"] = chk.correct
    out["message"] = ("ผลลัพธ์ตรงกันทั้งสอง engine ✔" if chk.correct else
                      f"ผลลัพธ์ต่างกัน: {chk.message.replace('ได้', 'SQLite ได้').replace('คาดหวัง', 'PostgreSQL ได้')}")
    out["details"] = chk.details
    names_a, names_b = [c.name for c in a.columns], [c.name for c in b.columns]
    if names_a != names_b:
        out["details"]["column_names"] = {"postgresql": names_a, "sqlite": names_b}
        out["message"] += " · ชื่อคอลัมน์อัตโนมัติต่างกัน (ตั้งชื่อด้วย AS เพื่อให้เหมือนกันทุก engine)"
    return out
