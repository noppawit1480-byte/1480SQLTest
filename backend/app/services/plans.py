"""Execution plans: normalize PostgreSQL EXPLAIN (FORMAT JSON) and SQLite EXPLAIN QUERY PLAN into one tree
shape for the visualizer, and run the Index Lab (before/after comparison on a throwaway copy)."""
from __future__ import annotations

import json
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


def summarize(plan: dict) -> dict:
    flat = []

    def walk_(n):
        flat.append(n)
        for c in n.get("children", []):
            walk_(c)
    walk_(plan["root"])
    return {"nodes": len(flat), "seq_scans": sorted({n["relation"] for n in flat if n["label"] in ("Seq Scan", "SCAN") and n.get("relation")}),
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
