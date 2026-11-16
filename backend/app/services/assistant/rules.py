"""Deterministic SQL assistant: explain / diagnose errors / review / optimize.

Built on libpg_query (pglast) — the real PostgreSQL parser — so it works without any AI provider
and never hallucinates syntax. The LLM layer (llm.py) is optional and only adds commentary on top.
"""
from __future__ import annotations

import difflib
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

import pglast
from pglast import ast
from pglast.enums import JoinType, SortByDir
from pglast.parser import ParseError
from pglast.stream import RawStream

from app.services.sql_split import split_statements
from app.services.validator import validate_sql


@dataclass
class Finding:
    code: str
    severity: str            # info | warning | danger | perf
    title: str
    body_md: str
    suggestion_sql: str | None = None


@dataclass
class Section:
    title: str
    body_md: str
    sql: str | None = None


@dataclass
class AssistantAnswer:
    mode: str
    source: str = "rules"
    summary: str = ""
    sections: list[Section] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    plan: list[dict] | None = None
    ai_md: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _sql(node) -> str:
    try:
        return RawStream()(node)
    except Exception:  # pragma: no cover - renderer gaps for exotic nodes
        return "…"


def walk(node: Any) -> Iterator[ast.Node]:
    """Yield every AST node under `node` (depth-first)."""
    if isinstance(node, (list, tuple)):
        for n in node:
            yield from walk(n)
        return
    if not isinstance(node, ast.Node):
        return
    yield node
    for attr in node:  # pglast nodes iterate over their attribute names
        yield from walk(getattr(node, attr, None))


def _parse(sql: str):
    try:
        return pglast.parse_sql(sql), None
    except ParseError as e:
        return None, e


JOIN_NAMES = {JoinType.JOIN_INNER: "INNER JOIN", JoinType.JOIN_LEFT: "LEFT JOIN",
              JoinType.JOIN_FULL: "FULL OUTER JOIN", JoinType.JOIN_RIGHT: "RIGHT JOIN"}


def _from_desc(item) -> list[str]:
    if isinstance(item, ast.RangeVar):
        alias = f" (ชื่อย่อ `{item.alias.aliasname}`)" if item.alias else ""
        return [f"อ่านตาราง `{item.relname}`{alias}"]
    if isinstance(item, ast.JoinExpr):
        out = _from_desc(item.larg)
        right = _from_desc(item.rarg)
        kind = "CROSS JOIN" if item.quals is None and not item.usingClause else JOIN_NAMES.get(item.jointype, "JOIN")
        cond = f" โดยจับคู่เมื่อ `{_sql(item.quals)}`" if item.quals is not None else (
            f" ด้วย USING ({', '.join(_sql(c) for c in item.usingClause)})" if item.usingClause else "")
        note = {"LEFT JOIN": " — เก็บทุกแถวฝั่งซ้าย แม้ไม่มีคู่ (ฝั่งขวาเป็น NULL)",
                "RIGHT JOIN": " — เก็บทุกแถวฝั่งขวา", "FULL OUTER JOIN": " — เก็บทุกแถวทั้งสองฝั่ง",
                "INNER JOIN": " — เก็บเฉพาะแถวที่มีคู่", "CROSS JOIN": " — จับคู่ทุกแถว × ทุกแถว"}.get(kind, "")
        return out + [f"**{kind}** กับ {right[0].replace('อ่านตาราง ', '')}{cond}{note}"] + right[1:]
    if isinstance(item, ast.RangeSubselect):
        alias = item.alias.aliasname if item.alias else "?"
        return [f"สร้างตารางชั่วคราว `{alias}` จาก subquery ในวงเล็บ (derived table)"]
    if isinstance(item, ast.RangeFunction):
        return [f"เรียกฟังก์ชันที่คืนค่าเป็นตาราง `{_sql(item.functions[0][0])}`"]
    return [f"แหล่งข้อมูล `{_sql(item)}`"]


def _has_window(target) -> bool:
    return any(isinstance(n, ast.FuncCall) and n.over is not None for n in walk(target))


def _explain_select(st: ast.SelectStmt, steps: list[Section]) -> None:
    if st.op is not None and int(st.op) != 0:  # SETOP_UNION / INTERSECT / EXCEPT
        op = {1: "UNION", 2: "INTERSECT", 3: "EXCEPT"}.get(int(st.op), "SET OPERATION")
        steps.append(Section(f"{op}{' ALL' if st.all else ''}",
                             f"รวมผลลัพธ์ของสอง query แบบแนวตั้ง{' (เก็บแถวซ้ำ)' if st.all else ' และตัดแถวที่ซ้ำ'} — จำนวนคอลัมน์และชนิดข้อมูลต้องเข้ากัน",
                             _sql(st)))
        return
    if st.withClause:
        for cte in st.withClause.ctes:
            rec = " (RECURSIVE: ส่วนแรกคือจุดเริ่มต้น ส่วนหลัง UNION ALL ทำซ้ำจนไม่มีแถวใหม่)" if st.withClause.recursive else ""
            steps.append(Section(f"WITH {cte.ctename}", f"สร้างผลลัพธ์ชั่วคราวชื่อ `{cte.ctename}` ที่ใช้ได้ใน query หลัก{rec}",
                                 _sql(cte.ctequery)))
    if st.valuesLists:
        steps.append(Section("VALUES", f"สร้างแถวข้อมูลคงที่ {len(st.valuesLists)} แถว"))
        return
    if st.fromClause:
        lines = []
        for item in st.fromClause:
            lines += _from_desc(item)
        if len(st.fromClause) > 1:
            lines.append("⚠️ มีหลายตารางคั่นด้วย comma = CROSS JOIN (ต้องมีเงื่อนไขจับคู่ใน WHERE)")
        steps.append(Section("1. FROM / JOIN — หาแหล่งข้อมูล", "\n".join(f"- {x}" for x in lines)))
    if st.whereClause is not None:
        subs = sum(1 for n in walk(st.whereClause) if isinstance(n, ast.SubLink))
        extra = f" (มี subquery {subs} จุดในเงื่อนไข)" if subs else ""
        steps.append(Section("2. WHERE — กรองทีละแถว", f"เก็บเฉพาะแถวที่เงื่อนไขเป็นจริง{extra} — แถวที่ได้ NULL/FALSE ถูกตัดทิ้ง",
                             _sql(st.whereClause)))
    if st.groupClause:
        steps.append(Section("3. GROUP BY — จัดกลุ่ม", "แถวที่มีค่าเหล่านี้เท่ากันรวมเป็นหนึ่งกลุ่ม แล้ว aggregate (COUNT/SUM/…) คำนวณต่อกลุ่ม",
                             ", ".join(_sql(g) for g in st.groupClause)))
    if st.havingClause is not None:
        steps.append(Section("4. HAVING — กรองกลุ่ม", "เก็บเฉพาะกลุ่มที่เงื่อนไขเป็นจริง (ใช้ aggregate ได้ ต่างจาก WHERE)",
                             _sql(st.havingClause)))
    if st.targetList:
        cols = []
        for t in st.targetList:
            expr = _sql(t.val)
            alias = f" → ชื่อคอลัมน์ `{t.name}`" if t.name else ""
            kind = ""
            if isinstance(t.val, ast.FuncCall) and t.val.over is not None:
                kind = " _(window function: คำนวณข้ามแถวโดยไม่ยุบแถว)_"
            elif isinstance(t.val, ast.CaseExpr):
                kind = " _(CASE: เลือกค่าตามเงื่อนไข)_"
            elif isinstance(t.val, ast.SubLink):
                kind = " _(scalar subquery: ต้องคืนค่าเดียว)_"
            cols.append(f"- `{expr}`{alias}{kind}")
        title = "5. SELECT — เลือก/คำนวณคอลัมน์" + (" + window functions" if _has_window(st.targetList) else "")
        steps.append(Section(title, "\n".join(cols)))
    if st.distinctClause is not None:
        on = [d for d in st.distinctClause if d is not None]
        body = (f"DISTINCT ON ({', '.join(_sql(d) for d in on)}): เก็บแถวแรกของแต่ละค่า ตามลำดับ ORDER BY" if on
                else "ตัดแถวที่ซ้ำกันทุกคอลัมน์ให้เหลือแถวเดียว")
        steps.append(Section("6. DISTINCT", body))
    if st.sortClause:
        parts = []
        for s in st.sortClause:
            d = {SortByDir.SORTBY_DESC: "มาก→น้อย", SortByDir.SORTBY_ASC: "น้อย→มาก"}.get(s.sortby_dir, "น้อย→มาก (ค่าเริ่มต้น)")
            parts.append(f"- `{_sql(s.node)}` {d}")
        steps.append(Section("7. ORDER BY — เรียงลำดับ", "\n".join(parts)))
    if st.limitCount is not None or st.limitOffset is not None:
        body = []
        if st.limitOffset is not None:
            body.append(f"ข้าม {_sql(st.limitOffset)} แถวแรก")
        if st.limitCount is not None:
            body.append(f"คืนไม่เกิน {_sql(st.limitCount)} แถว")
        steps.append(Section("8. LIMIT / OFFSET", " แล้ว ".join(body)))


def explain_sql(sql: str) -> AssistantAnswer:
    ans = AssistantAnswer(mode="explain")
    tree, err = _parse(sql)
    if err:
        issue = validate_sql(sql)[0]
        ans.summary = f"SQL นี้มี syntax error ที่บรรทัด {issue.line} คอลัมน์ {issue.column}: {issue.message} — แก้ syntax ก่อนจึงจะอธิบายได้"
        ans.findings.append(Finding("SYNTAX", "danger", "Syntax error", ans.summary))
        return ans
    stmts = split_statements(sql)
    ans.summary = (f"SQL นี้มี {len(tree)} คำสั่ง — อธิบายตามลำดับที่ PostgreSQL ประมวลผลจริง "
                   "(FROM → WHERE → GROUP BY → HAVING → SELECT → DISTINCT → ORDER BY → LIMIT)")
    for i, raw in enumerate(tree):
        st = raw.stmt
        head = f"คำสั่งที่ {i + 1}: " if len(tree) > 1 else ""
        text = stmts[i].text if i < len(stmts) else _sql(st)
        if isinstance(st, ast.SelectStmt):
            steps: list[Section] = []
            _explain_select(st, steps)
            ans.sections.append(Section(f"{head}SELECT — อ่านข้อมูล", "query นี้อ่านข้อมูลอย่างเดียว ไม่แก้ไขฐานข้อมูล", text))
            ans.sections += steps
        elif isinstance(st, ast.InsertStmt):
            src = "VALUES" if st.selectStmt is not None and getattr(st.selectStmt, "valuesLists", None) else "ผลของ SELECT"
            cols = f" คอลัมน์ ({', '.join(c.name for c in st.cols)})" if st.cols else ""
            ret = " แล้วคืนค่าคอลัมน์ที่ระบุใน RETURNING" if st.returningList else ""
            conflict = " ถ้าชน unique key จะทำตาม ON CONFLICT" if st.onConflictClause else ""
            ans.sections.append(Section(f"{head}INSERT — เพิ่มข้อมูล", f"เพิ่มแถวในตาราง `{st.relation.relname}`{cols} จาก{src}{conflict}{ret}", text))
        elif isinstance(st, ast.UpdateStmt):
            sets = "\n".join(f"- `{t.name}` = `{_sql(t.val)}`" for t in st.targetList)
            where = f"เฉพาะแถวที่ `{_sql(st.whereClause)}`" if st.whereClause is not None else "**ทุกแถวในตาราง** (ไม่มี WHERE!)"
            ans.sections.append(Section(f"{head}UPDATE — แก้ไขข้อมูล", f"แก้ไขตาราง `{st.relation.relname}` {where}\n{sets}", text))
        elif isinstance(st, ast.DeleteStmt):
            where = f"เฉพาะแถวที่ `{_sql(st.whereClause)}`" if st.whereClause is not None else "**ทุกแถวในตาราง** (ไม่มี WHERE!)"
            ans.sections.append(Section(f"{head}DELETE — ลบข้อมูล", f"ลบแถวจากตาราง `{st.relation.relname}` {where}", text))
        elif isinstance(st, ast.CreateStmt):
            cols = [e for e in st.tableElts if isinstance(e, ast.ColumnDef)]
            body = "\n".join(f"- `{c.colname}` {_sql(c.typeName)}" for c in cols)
            ans.sections.append(Section(f"{head}CREATE TABLE {st.relation.relname}", f"สร้างตารางใหม่ {len(cols)} คอลัมน์\n{body}", text))
        elif isinstance(st, ast.TransactionStmt):
            ans.sections.append(Section(f"{head}Transaction control", "ควบคุม transaction: BEGIN เริ่ม, COMMIT ยืนยัน, ROLLBACK ยกเลิก", text))
        elif isinstance(st, ast.ExplainStmt):
            ans.sections.append(Section(f"{head}EXPLAIN", "แสดงแผนการทำงานของ query (ANALYZE = รันจริงและวัดเวลา)", text))
        else:
            ans.sections.append(Section(f"{head}{type(st).__name__.replace('Stmt', '')}", "คำสั่ง DDL/utility", text))
    ans.findings = review_findings(sql, tree)
    return ans


# --------------------------------------------------------------------------- review (lint)
NON_SARGABLE_FUNCS = {"lower", "upper", "date", "extract", "date_trunc", "to_char", "coalesce", "trim", "substring", "date_part"}


def _colrefs(node) -> list[ast.ColumnRef]:
    return [n for n in walk(node) if isinstance(n, ast.ColumnRef)]


def _col_qualifier(c: ast.ColumnRef) -> str | None:
    parts = [f.sval for f in c.fields if isinstance(f, ast.String)]
    return parts[0] if len(parts) > 1 else None


def _alias_of(item) -> str | None:
    if isinstance(item, ast.RangeVar):
        return item.alias.aliasname if item.alias else item.relname
    if isinstance(item, ast.RangeSubselect) and item.alias:
        return item.alias.aliasname
    return None


def review_findings(sql: str, tree=None) -> list[Finding]:
    if tree is None:
        tree, err = _parse(sql)
        if err:
            return [Finding("SYNTAX", "danger", "Syntax error", str(err.args[0] if err.args else err))]
    out: list[Finding] = []
    seen: set[str] = set()

    def add(f: Finding):
        if f.code not in seen:
            seen.add(f.code)
            out.append(f)

    for raw in tree:
        st = raw.stmt
        if isinstance(st, (ast.UpdateStmt, ast.DeleteStmt)) and st.whereClause is None:
            verb = "UPDATE" if isinstance(st, ast.UpdateStmt) else "DELETE"
            add(Finding("NO_WHERE", "danger", f"{verb} โดยไม่มี WHERE",
                        f"คำสั่งนี้จะ{'แก้ไข' if verb == 'UPDATE' else 'ลบ'} **ทุกแถว** ในตาราง `{st.relation.relname}` — ถ้าไม่ได้ตั้งใจ ให้เพิ่ม WHERE และรัน SELECT ด้วยเงื่อนไขเดียวกันก่อนเพื่อตรวจแถวที่จะโดน"))
        for n in walk(st):
            if isinstance(n, ast.SelectStmt) and n.targetList:
                if any(isinstance(f, ast.A_Star) for t in n.targetList if isinstance(t.val, ast.ColumnRef) for f in t.val.fields):
                    add(Finding("SELECT_STAR", "info", "ใช้ SELECT *",
                                "เหมาะกับการสำรวจข้อมูล แต่ใน query จริงควรระบุคอลัมน์ — ลดข้อมูลที่ส่ง, ไม่พังเมื่อมีคนเพิ่มคอลัมน์ และอาจใช้ Index Only Scan ได้"))
                if n.limitCount is not None and not n.sortClause:
                    add(Finding("LIMIT_NO_ORDER", "warning", "LIMIT โดยไม่มี ORDER BY",
                                "ถ้าไม่มี ORDER BY ฐานข้อมูลไม่รับประกันลำดับ — 'N แถวแรก' อาจเปลี่ยนไปในแต่ละครั้งที่รัน"))
                if n.limitOffset is not None and isinstance(n.limitOffset, ast.A_Const) and isinstance(n.limitOffset.val, ast.Integer) \
                        and n.limitOffset.val.ival > 1000:
                    add(Finding("BIG_OFFSET", "perf", "OFFSET ขนาดใหญ่",
                                "OFFSET ต้องอ่านแถวที่ข้ามไปทั้งหมด ยิ่งเพจลึกยิ่งช้า — พิจารณา keyset pagination: `WHERE id > :last_id ORDER BY id LIMIT n`"))
                if n.distinctClause is not None and n.groupClause:
                    add(Finding("DISTINCT_GROUP", "info", "DISTINCT ซ้ำซ้อนกับ GROUP BY",
                                "ผลของ GROUP BY ไม่มีแถวซ้ำอยู่แล้ว (เมื่อ SELECT เฉพาะคอลัมน์ที่ group) — DISTINCT ไม่จำเป็น"))
                if n.sortClause and any(isinstance(s.node, ast.A_Const) for s in n.sortClause):
                    add(Finding("ORDER_BY_ORDINAL", "info", "ORDER BY ด้วยเลขลำดับคอลัมน์",
                                "`ORDER BY 2` ใช้ได้ แต่ถ้าสลับคอลัมน์ใน SELECT ลำดับจะเปลี่ยนตาม — ใช้ชื่อหรือ alias อ่านง่ายและปลอดภัยกว่า"))
                if n.havingClause is not None and not any(isinstance(x, ast.FuncCall) for x in walk(n.havingClause)):
                    add(Finding("HAVING_NO_AGG", "perf", "HAVING ที่ไม่มี aggregate",
                                "เงื่อนไขนี้ไม่ใช้ aggregate จึงย้ายไป WHERE ได้ — กรองก่อนจัดกลุ่มเร็วกว่า"))
                if n.fromClause and len(n.fromClause) > 1 and all(isinstance(x, ast.RangeVar) for x in n.fromClause):
                    add(Finding("IMPLICIT_JOIN", "warning", "JOIN แบบ comma (implicit)",
                                "`FROM a, b` คือ CROSS JOIN — ถ้าลืมเงื่อนไขใน WHERE จะได้แถว a × b ทั้งหมด ใช้ `JOIN ... ON` ให้เงื่อนไขอยู่ติดกับการ JOIN"))
                # LEFT JOIN turned into INNER JOIN by a WHERE filter on the right side
                if n.whereClause is not None and n.fromClause:
                    rights = {_alias_of(j.rarg) for x in n.fromClause for j in walk(x)
                              if isinstance(j, ast.JoinExpr) and j.jointype == JoinType.JOIN_LEFT}
                    rights.discard(None)
                    null_tested = {id(c) for t in walk(n.whereClause) if isinstance(t, ast.NullTest) for c in _colrefs(t)}
                    if any(_col_qualifier(c) in rights and id(c) not in null_tested for c in _colrefs(n.whereClause)):
                        add(Finding("LEFT_JOIN_WHERE", "warning", "LEFT JOIN ถูกกรองด้วย WHERE ฝั่งขวา",
                                    "เงื่อนไขใน WHERE ที่อ้างคอลัมน์ของตารางฝั่งขวาของ LEFT JOIN จะตัดแถวที่ไม่มีคู่ (NULL) ทิ้ง → ได้ผลเหมือน INNER JOIN — ถ้าต้องการเก็บแถวซ้ายไว้ ให้ย้ายเงื่อนไขไปไว้ใน `ON`"))
                if n.groupClause and n.fromClause and any(isinstance(j, ast.JoinExpr) and j.jointype == JoinType.JOIN_LEFT
                                                        for x in n.fromClause for j in walk(x)):
                    if any(isinstance(f, ast.FuncCall) and f.agg_star and f.funcname[-1].sval == "count" for f in walk(n.targetList)):
                        add(Finding("COUNT_STAR_LEFT", "warning", "COUNT(*) กับ LEFT JOIN",
                                    "แถวที่ไม่มีคู่จาก LEFT JOIN ถูกนับเป็น 1 — ถ้าต้องการให้ได้ 0 ใช้ `COUNT(right_table.id)`"))
            if isinstance(n, ast.BoolExpr) and int(n.boolop) == 2:  # NOT
                for a in n.args:
                    if isinstance(a, ast.SubLink) and int(a.subLinkType) == 2:  # NOT (x IN (subquery))
                        add(Finding("NOT_IN_SUBQUERY", "warning", "NOT IN กับ subquery",
                                    "ถ้า subquery คืนค่า NULL แม้แถวเดียว `NOT IN` จะได้ผล 0 แถวเสมอ — ใช้ `NOT EXISTS (SELECT 1 FROM ... WHERE ...)` ปลอดภัยกว่าและมักเร็วกว่า"))
            if isinstance(n, ast.A_Expr) and n.name and n.name[0].sval in ("=", "<>", "!=") and \
                    (isinstance(n.rexpr, ast.A_Const) and n.rexpr.isnull):
                add(Finding("EQ_NULL", "danger", "เปรียบเทียบกับ NULL ด้วย = หรือ <>",
                            "`x = NULL` ได้ UNKNOWN เสมอ จึงไม่มีแถวผ่าน — ใช้ `IS NULL` / `IS NOT NULL`"))
            if isinstance(n, ast.A_Expr) and n.name and n.name[0].sval in ("~~", "~~*") and isinstance(n.rexpr, ast.A_Const) \
                    and isinstance(n.rexpr.val, ast.String) and n.rexpr.val.sval.startswith("%"):
                add(Finding("LEADING_WILDCARD", "perf", "LIKE ขึ้นต้นด้วย %",
                            "pattern ที่ขึ้นต้นด้วย `%` ใช้ B-tree index ไม่ได้ ต้องสแกนทั้งตาราง (ตารางใหญ่ใช้ pg_trgm index แทน)"))
            if isinstance(n, ast.A_Expr) and n.name and n.name[0].sval == "/" and \
                    all(isinstance(x, ast.A_Const) and isinstance(x.val, ast.Integer) for x in (n.lexpr, n.rexpr)):
                add(Finding("INT_DIVISION", "info", "หารจำนวนเต็มด้วยจำนวนเต็ม",
                            "ใน PostgreSQL `1 / 3 = 0` (ตัดเศษ) — ใช้ `1.0 / 3` หรือ cast เป็น numeric"))
        where_nodes = []
        for n in walk(st):
            if isinstance(n, (ast.SelectStmt, ast.UpdateStmt, ast.DeleteStmt)) and getattr(n, "whereClause", None) is not None:
                where_nodes.append(n.whereClause)
        for w in where_nodes:
            for n in walk(w):
                if isinstance(n, ast.A_Expr) and n.name and n.name[0].sval in ("=", "<", ">", "<=", ">=", "~~"):
                    side = n.lexpr
                    fn = side.funcname[-1].sval if isinstance(side, ast.FuncCall) else None
                    if (fn in NON_SARGABLE_FUNCS and _colrefs(side)) or (isinstance(side, ast.TypeCast) and isinstance(side.arg, ast.ColumnRef)):
                        add(Finding("NON_SARGABLE", "perf", "ห่อคอลัมน์ด้วยฟังก์ชันใน WHERE",
                                    f"`{_sql(side)}` ทำให้ใช้ index ปกติบนคอลัมน์ไม่ได้ — เขียนเป็นเงื่อนไขช่วงบนคอลัมน์ดิบ เช่น `order_date >= '2025-01-01' AND order_date < '2026-01-01'` หรือสร้าง expression index"))
    return out


def review(sql: str) -> AssistantAnswer:
    ans = AssistantAnswer(mode="review")
    ans.findings = review_findings(sql)
    if not ans.findings:
        ans.summary = "ไม่พบปัญหาที่ตรวจจับได้จากกฎมาตรฐาน 👍 (ระบบตรวจ: NULL comparison, NOT IN, LIMIT ไม่มี ORDER BY, UPDATE/DELETE ไม่มี WHERE, LEFT JOIN ที่กลายเป็น INNER, COUNT(*) กับ LEFT JOIN, เงื่อนไขที่ใช้ index ไม่ได้ ฯลฯ)"
    else:
        counts = {s: sum(1 for f in ans.findings if f.severity == s) for s in ("danger", "warning", "perf", "info")}
        ans.summary = (f"พบ {len(ans.findings)} ประเด็น: " +
                       ", ".join(f"{n} {lbl}" for lbl, n in (("ร้ายแรง", counts["danger"]), ("ควรแก้", counts["warning"]),
                                                              ("ประสิทธิภาพ", counts["perf"]), ("แนะนำ", counts["info"])) if n))
    return ans


# --------------------------------------------------------------------------- error diagnosis
_COL_RE = re.compile(r'column "?([\w.]+)"? does not exist')
_REL_RE = re.compile(r'relation "([\w.]+)" does not exist')
_MISSING_FROM_RE = re.compile(r'missing FROM-clause entry for table "(\w+)"')


def _closest(name: str, options: list[str]) -> list[str]:
    return difflib.get_close_matches(name.lower(), [o.lower() for o in options], n=3, cutoff=0.5)


def explain_error(sql: str, error: dict, tables: list[dict]) -> AssistantAnswer:
    """`error` = ExecError dict from the executor; `tables` = introspected schema of the target DB."""
    ans = AssistantAnswer(mode="explain_error")
    msg = error.get("message") or ""
    state = error.get("sqlstate") or ""
    loc = f" (บรรทัด {error['line']}, คอลัมน์ {error['column']})" if error.get("line") else ""
    table_names = [t["name"] for t in tables]
    all_cols = sorted({c["name"] for t in tables for c in t["columns"]})

    def sec(title, body, sql_=None):
        ans.sections.append(Section(title, body, sql_))

    if state == "42601" or "syntax error" in msg:
        near = re.search(r'at or near "([^"]+)"', msg)
        sec("Syntax error — PostgreSQL อ่านคำสั่งไม่ออก",
            f"ตัวแยกคำ (parser) หยุดที่{(' `' + near.group(1) + '`') if near else 'ท้ายคำสั่ง'}{loc} ปัญหามักอยู่ **ก่อนหน้า** ตำแหน่งนั้นเล็กน้อย")
        sec("สาเหตุที่พบบ่อย", "- comma เกินก่อน `FROM` หรือขาด comma ระหว่างคอลัมน์\n- ลืมปิด quote `'` หรือวงเล็บ\n"
            "- สะกด keyword ผิด เช่น `SELEC`, `WHER`, `GROUPBY`\n- ลำดับ clause ผิด (ต้องเป็น SELECT → FROM → WHERE → GROUP BY → HAVING → ORDER BY → LIMIT)\n"
            "- ใช้ double quote กับข้อความ (`\"Bangkok\"` คือชื่อคอลัมน์ ไม่ใช่ข้อความ)")
    elif state == "42P01":
        m = _REL_RE.search(msg) or _MISSING_FROM_RE.search(msg)
        name = m.group(1) if m else "?"
        if _MISSING_FROM_RE.search(msg):
            sec(f"อ้างถึง `{name}` ที่ไม่ได้อยู่ใน FROM",
                f"มีการใช้ `{name}.คอลัมน์` แต่ไม่มีตาราง/alias ชื่อ `{name}` ใน FROM/JOIN — ถ้าตั้ง alias ให้ตารางแล้ว ต้องใช้ alias นั้นแทนชื่อเต็ม")
        else:
            near = _closest(name.split(".")[-1], table_names)
            sec(f"ไม่พบตาราง `{name}`", f"ในฐานข้อมูลนี้ไม่มีตารางชื่อนี้{loc}" +
                (f" — หมายถึง {', '.join(f'`{n}`' for n in near)} หรือเปล่า?" if near else "") +
                f"\n\nตารางที่มี: {', '.join(f'`{t}`' for t in table_names)}")
    elif state == "42703":
        m = _COL_RE.search(msg)
        full = m.group(1) if m else "?"
        col = full.split(".")[-1]
        owners = [t["name"] for t in tables if any(c["name"] == col for c in t["columns"])]
        near = _closest(col, all_cols)
        body = f"ไม่พบคอลัมน์ `{full}`{loc}"
        if owners:
            body += f" — คอลัมน์ `{col}` มีอยู่ในตาราง {', '.join(f'`{o}`' for o in owners)} ตรวจว่า JOIN ตารางนั้นแล้วและใช้ alias ถูกตัว"
        elif near:
            body += f" — หมายถึง {', '.join(f'`{n}`' for n in near)} หรือเปล่า?"
        sec("ไม่พบคอลัมน์", body)
        sec("สาเหตุอื่นที่พบบ่อย", "- ใช้ alias จาก SELECT ใน WHERE/GROUP BY (WHERE ทำงานก่อน SELECT จึงยังไม่รู้จัก alias)\n"
            "- ใส่ข้อความโดยลืม single quote: `WHERE city = Bangkok` → PostgreSQL คิดว่า Bangkok คือชื่อคอลัมน์")
    elif state == "42803":
        if "aggregate functions are not allowed in WHERE" in msg:
            sec("ใช้ aggregate ใน WHERE ไม่ได้", "WHERE กรอง *ทีละแถว* ก่อนจัดกลุ่ม จึงยังคำนวณ COUNT/SUM ไม่ได้ — ย้ายเงื่อนไขไปที่ `HAVING` (หลัง GROUP BY) หรือใช้ subquery")
        else:
            m = re.search(r'column "([\w.]+)" must appear in the GROUP BY clause', msg)
            sec("GROUP BY ไม่ครบ", f"คอลัมน์ {'`' + m.group(1) + '`' if m else ''} อยู่ใน SELECT แต่ไม่อยู่ใน GROUP BY และไม่ได้ห่อด้วย aggregate — "
                "เมื่อจัดกลุ่มแล้ว แต่ละกลุ่มมีหลายค่า ฐานข้อมูลไม่รู้ว่าจะเลือกค่าไหน\n\n**แก้:** เพิ่มคอลัมน์นั้นใน GROUP BY หรือห่อด้วย aggregate เช่น `MAX(...)`")
    elif state == "42702":
        m = re.search(r'column reference "(\w+)" is ambiguous', msg)
        col = m.group(1) if m else "?"
        owners = [t["name"] for t in tables if any(c["name"] == col for c in t["columns"])]
        sec("ชื่อคอลัมน์กำกวม", f"คอลัมน์ `{col}` มีอยู่ในหลายตารางที่ JOIN ({', '.join(owners)}) — ระบุให้ชัดด้วย alias เช่น `o.{col}`")
    elif state == "42P20" or "window functions are not allowed in WHERE" in msg:
        sec("ใช้ window function ใน WHERE ไม่ได้", "window function คำนวณหลัง WHERE — ห่อ query ไว้ใน subquery/CTE แล้วกรองที่ query นอก เช่น `SELECT * FROM (SELECT ..., ROW_NUMBER() OVER (...) AS rn FROM t) x WHERE rn = 1`")
    elif state == "42883":
        sec("ชนิดข้อมูลไม่ตรงกับฟังก์ชัน/ตัวดำเนินการ", f"{msg} — มักเกิดจากเปรียบเทียบข้อความกับตัวเลข หรือส่งชนิดข้อมูลผิดให้ฟังก์ชัน\n\n**แก้:** cast ให้ตรงกัน เช่น `id::text` หรือ `'42'::int` และดูคำใบ้ HINT ใต้ error")
    elif state in ("42804", "22P02", "22007", "22008"):
        sec("ค่าหรือชนิดข้อมูลไม่ถูกต้อง", f"{msg} — ตรวจรูปแบบค่าคงที่: วันที่ใช้ `'YYYY-MM-DD'`, ตัวเลขไม่ต้องมี quote, boolean ใช้ true/false")
    elif state == "22012":
        sec("หารด้วยศูนย์", "ตัวหารเป็น 0 ในบางแถว — ใช้ `NULLIF(ตัวหาร, 0)` ให้กลายเป็น NULL แทน error: `x / NULLIF(y, 0)`")
    elif state == "21000":
        sec("subquery คืนมากกว่าหนึ่งแถว", "subquery ที่ใช้กับ `=` หรือใน SELECT ต้องคืนค่าเดียว — เปลี่ยนเป็น `IN (...)`, ใช้ aggregate (`MAX`), หรือเพิ่มเงื่อนไขให้เหลือแถวเดียว")
    elif state == "23503":
        sec("ละเมิด Foreign Key", f"{msg}\n\nข้อมูลนี้ถูกอ้างอิง (หรืออ้างถึง) แถวในตารางอื่น — ลบ/แก้แถวลูกก่อน หรือใส่ค่า FK ที่มีอยู่จริง")
    elif state == "23505":
        sec("ค่าซ้ำกับ UNIQUE / PRIMARY KEY", f"{msg}\n\nใช้ค่าอื่น หรือใช้ `INSERT ... ON CONFLICT (...) DO UPDATE/DO NOTHING` (upsert)")
    elif state in ("23502", "23514"):
        sec("ละเมิด constraint", f"{msg}\n\nค่าที่ใส่ขัดกับกฎของตาราง (NOT NULL หรือ CHECK) — ดูนิยามตารางใน Database Explorer")
    elif state in ("25006", "42501") or error.get("kind") == "permission":
        sec("ไม่มีสิทธิ์ในโหมดนี้", "โหมด Read-only ใช้ได้เฉพาะการอ่าน — สลับเป็น **Writable sandbox** ใน Playground เพื่อฝึก INSERT/UPDATE/DELETE/DDL (ฐานข้อมูลส่วนตัว กด Reset ได้)")
    elif state == "57014" or error.get("kind") == "timeout":
        sec("Query ใช้เวลานานเกินกำหนด", "ลองใช้โหมด **Optimize** เพื่อดูแผนการทำงาน — สาเหตุที่พบบ่อย: JOIN ไม่มีเงื่อนไข (แถวคูณกัน), subquery ต่อแถวบนตารางใหญ่, หรือฟังก์ชันอย่าง `pg_sleep`")
        ans.findings = review_findings(sql)
    else:
        sec("ข้อผิดพลาดจาก PostgreSQL", msg + (f"\n\nDETAIL: {error['detail']}" if error.get("detail") else "") +
            (f"\n\nHINT: {error['hint']}" if error.get("hint") else ""))
    ans.summary = f"{msg}{loc}"
    return ans


# --------------------------------------------------------------------------- optimize (EXPLAIN-based)
def _plan_rows(node: dict, depth: int = 0, out: list | None = None) -> list[dict]:
    out = [] if out is None else out
    out.append({"depth": depth, "node": node.get("Node Type"), "relation": node.get("Relation Name"),
                "alias": node.get("Alias"), "index": node.get("Index Name"), "rows": node.get("Plan Rows"),
                "cost": node.get("Total Cost"), "filter": node.get("Filter") or node.get("Index Cond") or node.get("Hash Cond"),
                "sort_key": node.get("Sort Key")})
    for child in node.get("Plans", []) or []:
        _plan_rows(child, depth + 1, out)
    return out


def optimize_from_plan(sql: str, plan_json: Any, table_rows: dict[str, int]) -> AssistantAnswer:
    ans = AssistantAnswer(mode="optimize")
    plan = plan_json[0]["Plan"] if isinstance(plan_json, list) else json.loads(plan_json)[0]["Plan"]
    rows = _plan_rows(plan)
    ans.plan = rows
    top = max(rows, key=lambda r: r["cost"] or 0)
    ans.summary = f"ต้นทุนรวมโดยประมาณ {plan.get('Total Cost')} (หน่วยของ planner) · คาดว่าได้ {plan.get('Plan Rows')} แถว · node หลัก: {plan.get('Node Type')}"
    for r in rows:
        rel = r["relation"]
        size = table_rows.get(rel or "", 0)
        if r["node"] == "Seq Scan" and rel and size >= 500 and r["filter"]:
            cols = sorted(set(re.findall(r"\b(?:\w+\.)?(\w+)\s*(?:=|>=|<=|>|<|~~)", r["filter"])) - {"text", "numeric", "timestamp", "date"})
            idx = f"CREATE INDEX ON {rel} ({', '.join(cols[:2])});" if cols else None
            ans.findings.append(Finding(f"SEQ_SCAN_{rel}", "perf", f"Seq Scan บน `{rel}` (~{size:,} แถว) พร้อม Filter",
                                        f"ต้องอ่านทุกแถวแล้วกรองด้วย `{r['filter']}` — ถ้า query นี้ใช้บ่อยและคัดแถวได้น้อย index จะช่วยได้ "
                                        "(ทดลองได้ใน Writable sandbox แล้วรัน EXPLAIN เทียบ)", idx))
        if r["node"] == "Sort" and (r["rows"] or 0) > 1000:
            ans.findings.append(Finding("BIG_SORT", "perf", f"เรียงข้อมูล ~{r['rows']:,} แถว",
                                        f"Sort key: `{', '.join(r['sort_key'] or [])}` — index ตามคอลัมน์ ORDER BY (หรือ LIMIT ที่เล็กลง) ช่วยลดงานได้"))
        if r["node"] == "Nested Loop" and (r["rows"] or 0) > 10000:
            ans.findings.append(Finding("BIG_NESTED_LOOP", "warning", f"Nested Loop ได้ ~{r['rows']:,} แถว",
                                        "จำนวนแถวสูงผิดปกติ — ตรวจว่า JOIN มีเงื่อนไขครบ (ไม่เกิด cartesian product)"))
    ans.findings += [f for f in review_findings(sql) if f.severity in ("perf", "warning", "danger")]
    ans.sections.append(Section("node ที่มีต้นทุนสูงสุด",
                                f"`{top['node']}`{' บน `' + top['relation'] + '`' if top['relation'] else ''} (cost {top['cost']})"))
    ans.sections.append(Section("อ่านแผนอย่างไร", "อ่านจาก node ที่ย่อหน้าลึกสุดขึ้นมา · `rows` คือจำนวนแถวที่ planner *คาดการณ์* · "
                                "ใช้ `EXPLAIN ANALYZE` ใน Playground เพื่อดูเวลาและจำนวนแถวจริง"))
    if not ans.findings:
        ans.sections.append(Section("ผลการวิเคราะห์", "แผนการทำงานดูสมเหตุสมผลสำหรับขนาดข้อมูลนี้ — ไม่พบจุดที่ควรปรับ"))
    return ans
