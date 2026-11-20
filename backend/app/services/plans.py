"""Execution plans: normalize PostgreSQL EXPLAIN (FORMAT JSON) and SQLite EXPLAIN QUERY PLAN into one tree
shape for the visualizer, and run the Index Lab (before/after comparison on a throwaway copy)."""
from __future__ import annotations

import json
import re
from typing import Any

import pglast
from pglast import ast
from pglast.stream import RawStream

from app.services.assistant import rules


class PlanError(ValueError):
    pass


def single_statement(sql: str, allowed: tuple[type, ...]) -> str:
    try:
        tree = pglast.parse_sql(sql)
    except Exception as e:
        raise PlanError(f"SQL มี syntax error: {e.args[0] if e.args else e}") from None
    if len(tree) != 1:
        raise PlanError("วิเคราะห์แผนได้ทีละคำสั่ง — เลือกเพียงคำสั่งเดียว")
    st = tree[0].stmt
    if isinstance(st, ast.ExplainStmt):
        st = st.query
    if not isinstance(st, allowed):
        raise PlanError("คำสั่งนี้ไม่รองรับในโหมดนี้")
    return RawStream()(st)


def single_statement_mysql(sql: str) -> str:
    """MySQL statements are not parsed with the PostgreSQL parser: allow exactly one SELECT/WITH/TABLE/DML statement."""
    from app.services.sandbox.postgres import first_keyword
    from app.services.sql_split import split_statements
    stmts = split_statements(sql)
    if len(stmts) != 1:
        raise PlanError("วิเคราะห์แผนได้ทีละคำสั่ง — เลือกเพียงคำสั่งเดียว")
    text = stmts[0].text
    kw = first_keyword(text)
    if kw == "EXPLAIN":
        raise PlanError("ใส่เฉพาะ query — ระบบจะเติม EXPLAIN ให้เอง")
    if kw not in ("SELECT", "WITH", "TABLE", "INSERT", "UPDATE", "DELETE", "REPLACE"):
        raise PlanError("คำสั่งนี้ไม่รองรับในโหมดนี้")
    return text


def _pg_node(n: dict, counter: list[int]) -> dict:
    counter[0] += 1
    rel = n.get("Relation Name")
    label = n.get("Node Type", "?")
    if n.get("Join Type") and "Join" in label or label == "Nested Loop":
        label = f"{n.get('Join Type', '')} {label}".strip()
    detail = [f"{k}: {n[k]}" for k in ("Index Cond", "Filter", "Hash Cond", "Merge Cond", "Join Filter", "Recheck Cond")
              if n.get(k)]
    if n.get("Sort Key"):
        detail.append("Sort Key: " + ", ".join(n["Sort Key"]))
    if n.get("Group Key"):
        detail.append("Group Key: " + ", ".join(n["Group Key"]))
    if n.get("Rows Removed by Filter") is not None:
        detail.append(f"Rows Removed by Filter: {n['Rows Removed by Filter']}")
    node = {
        "id": counter[0], "label": label, "relation": rel, "alias": n.get("Alias"), "index": n.get("Index Name"),
        "detail": detail, "est_rows": n.get("Plan Rows"), "est_cost": n.get("Total Cost"), "startup_cost": n.get("Startup Cost"),
        "actual_rows": n.get("Actual Rows"), "loops": n.get("Actual Loops"),
        "time_ms": (n.get("Actual Total Time") or 0) * (n.get("Actual Loops") or 1) if "Actual Total Time" in n else None,
        "children": [_pg_node(c, counter) for c in n.get("Plans", []) or []],
    }
    if node["actual_rows"] is not None and node["est_rows"]:
        actual = node["actual_rows"] * (node["loops"] or 1)
        ratio = max(actual, 1) / max(node["est_rows"] * (node["loops"] or 1), 1)
        if ratio > 10 or ratio < 0.1:
            node["misestimate"] = round(ratio, 1)
    return node


def normalize_pg(plan_json: Any) -> dict:
    data = json.loads(plan_json) if isinstance(plan_json, str) else plan_json
    root = data[0]
    tree = _pg_node(root["Plan"], [0])
    return {"engine": "postgresql", "root": tree, "planning_ms": root.get("Planning Time"),
            "execution_ms": root.get("Execution Time"), "total_cost": root["Plan"].get("Total Cost"),
            "analyzed": "Execution Time" in root}


def normalize_sqlite(rows: list[list]) -> dict:
    """rows from EXPLAIN QUERY PLAN: (id, parent, notused, detail)."""
    nodes: dict[int, dict] = {0: {"id": 0, "label": "QUERY PLAN", "detail": [], "children": []}}
    for rid, parent, _n, detail in rows:
        label = detail
        rel = None
        for kw in ("SCAN ", "SEARCH "):
            if detail.startswith(kw):
                label = kw.strip()
                rel = detail[len(kw):].split(" ")[0]
        node = {"id": rid, "label": label, "relation": rel, "detail": [detail], "index": "INDEX" in detail and detail or None,
                "children": []}
        nodes[rid] = node
        nodes.get(parent, nodes[0])["children"].append(node)
    return {"engine": "sqlite", "root": nodes[0], "planning_ms": None, "execution_ms": None, "total_cost": None, "analyzed": False}


_MY_COST = re.compile(r"\(cost=([\d.e+-]+) rows=([\d.e+-]+)\)")
_MY_ACTUAL = re.compile(r"\(actual time=([\d.e+-]+)\.\.([\d.e+-]+) rows=([\d.e+-]+) loops=(\d+)\)")
_MY_KINDS = (("Covering index lookup on ", "Covering index lookup"), ("Index lookup on ", "Index lookup"),
             ("Single-row index lookup on ", "Single-row index lookup"), ("Index range scan on ", "Index range scan"),
             ("Covering index scan on ", "Covering index scan"), ("Index scan on ", "Index scan"),
             ("Single-row covering index lookup on ", "Single-row covering index lookup"), ("Table scan on ", "Table scan"))


def normalize_mysql(tree_text: str) -> dict:
    """MySQL `EXPLAIN FORMAT=TREE` / `EXPLAIN ANALYZE` text -> the common plan tree shape."""
    root = {"id": 0, "label": "QUERY PLAN", "detail": [], "children": []}
    stack: list[tuple[int, dict]] = [(-1, root)]
    counter = 0
    for raw in tree_text.splitlines():
        if "->" not in raw:
            continue
        depth = (len(raw) - len(raw.lstrip())) // 4
        text = raw.strip()[2:].strip()
        cost, actual = _MY_COST.search(text), _MY_ACTUAL.search(text)
        cut = min([m.start() for m in (cost, actual) if m] or [len(text)])
        desc = text[:cut].strip()
        counter += 1
        label, rel, index, detail = desc, None, None, []
        for prefix, name in _MY_KINDS:
            if desc.startswith(prefix):
                label = name
                rest = desc[len(prefix):]
                rel = rest.split(" ")[0]
                m = re.search(r" using (\S+)", rest)
                index = m.group(1) if m else None
                cond = re.search(r"\((.*)\)$", rest)
                if cond and index:
                    detail.append(f"Index Cond: {cond.group(1)}")
                break
        else:
            if ":" in desc:
                label, _, d = desc.partition(":")
                detail.append(f"{label.strip()}: {d.strip()}")
        loops = int(actual.group(4)) if actual else None
        node = {"id": counter, "label": label.strip(), "relation": rel if rel and not rel.startswith("<") else None,
                "alias": None, "index": index, "detail": detail,
                "est_rows": float(cost.group(2)) if cost else None, "est_cost": float(cost.group(1)) if cost else None,
                "startup_cost": None, "actual_rows": float(actual.group(3)) if actual else None, "loops": loops,
                "time_ms": float(actual.group(2)) * (loops or 1) if actual else None, "children": []}
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1]["children"].append(node)
        stack.append((depth, node))
    top = root["children"][0] if len(root["children"]) == 1 else root
    first_cost = None

    def find_cost(n):
        nonlocal first_cost
        if first_cost is None and n.get("est_cost") is not None:
            first_cost = n["est_cost"]
        for c in n.get("children", []):
            find_cost(c)
    find_cost(top)
    analyzed = top.get("time_ms") is not None
    return {"engine": "mysql", "root": top, "planning_ms": None, "execution_ms": top.get("time_ms") if analyzed else None,
            "total_cost": first_cost, "analyzed": analyzed}


def summarize(plan: dict) -> dict:
    flat = []

    def walk_(n):
        flat.append(n)
        for c in n.get("children", []):
            walk_(c)
    walk_(plan["root"])
    return {"nodes": len(flat), "seq_scans": sorted({n["relation"] for n in flat if n["label"] in ("Seq Scan", "SCAN", "Table scan") and n.get("relation")}),
            "indexes_used": sorted({n["index"] for n in flat if n.get("index")}),
            "total_cost": plan.get("total_cost"), "execution_ms": plan.get("execution_ms")}


def plan_findings(sql: str, plan: dict, table_rows: dict[str, int]) -> list[dict]:
    from dataclasses import asdict
    if plan["engine"] != "postgresql":
        return [asdict(f) for f in rules.review_findings(sql) if f.severity in ("perf", "warning", "danger")]
    raw = [{"Plan": _denormalize(plan["root"])}]
    ans = rules.optimize_from_plan(sql, raw, table_rows)
    return [asdict(f) for f in ans.findings]


def _denormalize(n: dict) -> dict:
    """Back to the minimal PostgreSQL JSON shape that rules.optimize_from_plan reads."""
    filt = next((d.split(": ", 1)[1] for d in n["detail"] if d.startswith(("Filter:", "Index Cond:", "Hash Cond:"))), None)
    sort_key = next((d.split(": ", 1)[1].split(", ") for d in n["detail"] if d.startswith("Sort Key:")), None)
    return {"Node Type": n["label"].split(" ")[-1] if n["label"].endswith(("Join", "Loop")) and n["label"] != "Nested Loop" else n["label"],
            "Relation Name": n.get("relation"), "Plan Rows": n.get("est_rows"), "Total Cost": n.get("est_cost"),
            "Filter": filt, "Sort Key": sort_key, "Index Name": n.get("index"),
            "Plans": [_denormalize(c) for c in n.get("children", [])]}
