"""ER Diagram Builder: validate a schema design, generate DDL per dialect and Mermaid, reverse-engineer a DB.

Designs are plain JSON:
  {"tables": [{"name", "columns": [{"name", "type", "pk", "not_null", "unique", "identity", "default"}], "x", "y"}],
   "relations": [{"from_table", "from_column", "to_table", "to_column", "on_delete"}]}
Identifiers and types are validated against strict whitelists before any DDL is produced, so generated DDL
never contains user-controlled SQL fragments beyond validated names and whitelisted types/defaults.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
TYPE_RE = re.compile(r"^(integer|bigint|smallint|text|boolean|date|timestamp|timestamptz|jsonb|uuid|real|"
                     r"numeric(\(\d{1,2}(,\d{1,2})?\))?|varchar\(\d{1,4}\))$")
DEFAULT_RE = re.compile(r"^(-?\d+(\.\d+)?|true|false|now\(\)|current_date|'[^'\\]{0,100}')$", re.IGNORECASE)
ON_DELETE = {"no action": "NO ACTION", "restrict": "RESTRICT", "cascade": "CASCADE", "set null": "SET NULL"}
RESERVED = {"user", "order", "group", "table", "select", "where", "from", "limit", "offset", "check", "default", "column",
            "primary", "foreign", "references", "index", "key", "desc", "asc", "all", "and", "or", "not", "null"}
MAX_TABLES, MAX_COLUMNS = 30, 60


class DesignError(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


@dataclass
class Issue:
    level: str   # error | warning
    message: str


def validate(design: dict) -> list[Issue]:
    issues: list[Issue] = []
    tables = design.get("tables") or []
    rels = design.get("relations") or []
    if not isinstance(tables, list) or not isinstance(rels, list):
        return [Issue("error", "รูปแบบ design ไม่ถูกต้อง")]
    if len(tables) > MAX_TABLES:
        issues.append(Issue("error", f"มีตารางได้ไม่เกิน {MAX_TABLES} ตาราง"))
    names: dict[str, dict] = {}
    for t in tables:
        tn = str(t.get("name", ""))
        if not IDENT.match(tn):
            issues.append(Issue("error", f"ชื่อตาราง '{tn}' ไม่ถูกต้อง (ตัวพิมพ์เล็ก a-z, 0-9, _ และขึ้นต้นด้วยตัวอักษร)"))
            continue
        if tn in names:
            issues.append(Issue("error", f"ชื่อตาราง '{tn}' ซ้ำ"))
        if tn in RESERVED:
            issues.append(Issue("error", f"'{tn}' เป็นคำสงวนของ SQL — ตั้งชื่ออื่น เช่น {tn}s"))
        names[tn] = t
        cols = t.get("columns") or []
        if not cols:
            issues.append(Issue("error", f"ตาราง '{tn}' ต้องมีอย่างน้อย 1 คอลัมน์"))
        if len(cols) > MAX_COLUMNS:
            issues.append(Issue("error", f"ตาราง '{tn}' มีคอลัมน์เกิน {MAX_COLUMNS}"))
        seen = set()
        for c in cols:
            cn = str(c.get("name", ""))
            if not IDENT.match(cn):
                issues.append(Issue("error", f"{tn}: ชื่อคอลัมน์ '{cn}' ไม่ถูกต้อง"))
                continue
            if cn in seen:
                issues.append(Issue("error", f"{tn}: คอลัมน์ '{cn}' ซ้ำ"))
            if cn in RESERVED:
                issues.append(Issue("error", f"{tn}: '{cn}' เป็นคำสงวน"))
            seen.add(cn)
            if not TYPE_RE.match(str(c.get("type", "")).lower().replace(" ", "")):
                issues.append(Issue("error", f"{tn}.{cn}: ชนิดข้อมูล '{c.get('type')}' ไม่รองรับ"))
            if c.get("default") not in (None, "") and not DEFAULT_RE.match(str(c["default"])):
                issues.append(Issue("error", f"{tn}.{cn}: ค่า default รองรับเฉพาะตัวเลข, true/false, now(), current_date หรือข้อความใน '...'"))
            if c.get("identity") and str(c.get("type")).lower() not in ("integer", "bigint"):
                issues.append(Issue("error", f"{tn}.{cn}: identity ใช้ได้กับ integer/bigint"))
        if not any(c.get("pk") for c in cols):
            issues.append(Issue("warning", f"ตาราง '{tn}' ไม่มี primary key — ระบุแถวไม่ได้และเกิดข้อมูลซ้ำง่าย"))
        if str(tn).endswith("s") is False and not tn.endswith(("_data", "_info")):
            issues.append(Issue("warning", f"แนะนำตั้งชื่อตารางเป็นพหูพจน์ เช่น '{tn}s'"))
    for r in rels:
        ft, fc, tt, tc = (str(r.get(k, "")) for k in ("from_table", "from_column", "to_table", "to_column"))
        src, dst = names.get(ft), names.get(tt)
        label = f"{ft}.{fc} → {tt}.{tc}"
        if not src or not dst:
            issues.append(Issue("error", f"ความสัมพันธ์ {label}: ไม่พบตาราง"))
            continue
        scol = next((c for c in src["columns"] if c.get("name") == fc), None)
        dcol = next((c for c in dst["columns"] if c.get("name") == tc), None)
        if not scol or not dcol:
            issues.append(Issue("error", f"ความสัมพันธ์ {label}: ไม่พบคอลัมน์"))
            continue
        if not (dcol.get("pk") or dcol.get("unique")):
            issues.append(Issue("error", f"ความสัมพันธ์ {label}: คอลัมน์ปลายทางต้องเป็น PRIMARY KEY หรือ UNIQUE"))
        if _base(scol.get("type")) != _base(dcol.get("type")):
            issues.append(Issue("warning", f"ความสัมพันธ์ {label}: ชนิดข้อมูลไม่ตรงกัน ({scol.get('type')} vs {dcol.get('type')})"))
        if str(r.get("on_delete", "no action")).lower() not in ON_DELETE:
            issues.append(Issue("error", f"ความสัมพันธ์ {label}: on_delete ไม่ถูกต้อง"))
        if str(r.get("on_delete", "")).lower() == "set null" and scol.get("not_null"):
            issues.append(Issue("error", f"ความสัมพันธ์ {label}: SET NULL ใช้กับคอลัมน์ NOT NULL ไม่ได้"))
    return issues


def _base(t) -> str:
    t = str(t or "").lower()
    return {"bigint": "integer", "smallint": "integer"}.get(t, t.split("(")[0])


def _col_type(t: str, dialect: str) -> str:
    t = t.lower().replace(" ", "")
    if dialect == "postgresql":
        return t
    if dialect == "sqlite":
        return {"timestamptz": "TEXT", "timestamp": "TEXT", "date": "TEXT", "jsonb": "TEXT", "uuid": "TEXT",
                "boolean": "BOOLEAN"}.get(t, "TEXT" if t.startswith("varchar") or t == "text" else
                                            "NUMERIC" if t.startswith("numeric") else t.upper())
    # mysql
    return {"timestamptz": "DATETIME", "timestamp": "DATETIME", "jsonb": "JSON", "uuid": "CHAR(36)", "boolean": "BOOLEAN",
            "text": "TEXT"}.get(t, t.upper().replace("NUMERIC", "DECIMAL"))


def _default(v, dialect: str) -> str:
    s = str(v)
    if s.lower() == "now()":
        return {"postgresql": "now()", "sqlite": "CURRENT_TIMESTAMP", "mysql": "CURRENT_TIMESTAMP"}[dialect]
    if s.lower() == "current_date":
        return "CURRENT_DATE"
    if dialect == "sqlite" and s.lower() in ("true", "false"):
        return "1" if s.lower() == "true" else "0"
    return s


def _ordered(tables: list[dict], rels: list[dict]) -> list[dict]:
    deps = {t["name"]: {r["to_table"] for r in rels if r["from_table"] == t["name"] and r["to_table"] != t["name"]} for t in tables}
    out, done = [], set()
    while len(out) < len(tables):
        ready = [t for t in tables if t["name"] not in done and deps[t["name"]] <= done]
        if not ready:  # cycle: emit the rest; FKs for cycles are added with ALTER TABLE below
            ready = [t for t in tables if t["name"] not in done]
        for t in ready:
            out.append(t)
            done.add(t["name"])
    return out


def generate_ddl(design: dict, dialect: str = "postgresql") -> str:
    errors = [i.message for i in validate(design) if i.level == "error"]
    if errors:
        raise DesignError(errors)
    tables, rels = design.get("tables", []), design.get("relations", [])
    q = (lambda n: f"`{n}`") if dialect == "mysql" else (lambda n: f'"{n}"' if n in RESERVED else n)
    order = _ordered(tables, rels)
    position = {t["name"]: i for i, t in enumerate(order)}
    stmts, deferred = [], []
    keyed: dict[str, set[str]] = {}  # columns used in foreign keys (both ends) — they need an indexable type in MySQL
    for r in rels:
        keyed.setdefault(r["from_table"], set()).add(r["from_column"])
        keyed.setdefault(r["to_table"], set()).add(r["to_column"])
    for t in order:
        lines = []
        pks = [c["name"] for c in t["columns"] if c.get("pk")]
        for c in t["columns"]:
            parts = [q(c["name"])]
            if c.get("identity"):
                parts.append({"postgresql": f"{c['type'].lower()} GENERATED ALWAYS AS IDENTITY",
                              "sqlite": "INTEGER", "mysql": f"{c['type'].upper()} AUTO_INCREMENT"}[dialect])
            else:
                ctype = _col_type(c["type"], dialect)
                if dialect == "mysql" and ctype == "TEXT" and (c.get("pk") or c.get("unique") or c["name"] in keyed.get(t["name"], ())):
                    ctype = "VARCHAR(255)"  # MySQL cannot index TEXT without a prefix length
                parts.append(ctype)
            if len(pks) == 1 and c.get("pk"):
                parts.append("PRIMARY KEY" + (" AUTOINCREMENT" if dialect == "sqlite" and c.get("identity") else ""))
            if c.get("not_null") and not c.get("pk"):
                parts.append("NOT NULL")
            if c.get("unique") and not c.get("pk"):
                parts.append("UNIQUE")
            if c.get("default") not in (None, ""):
                dflt = _default(c["default"], dialect)
                if dialect == "mysql" and (parts[1] in ("TEXT", "JSON") or dflt == "CURRENT_DATE"):
                    dflt = f"({dflt})"  # MySQL 8 only accepts expression defaults in parentheses here
                parts.append("DEFAULT " + dflt)
            lines.append("  " + " ".join(parts))
        if len(pks) > 1:
            lines.append(f"  PRIMARY KEY ({', '.join(q(p) for p in pks)})")
        for r in rels:
            if r["from_table"] != t["name"]:
                continue
            fk = (f"FOREIGN KEY ({q(r['from_column'])}) REFERENCES {q(r['to_table'])} ({q(r['to_column'])})"
                  f" ON DELETE {ON_DELETE[str(r.get('on_delete', 'no action')).lower()]}")
            if position[r["to_table"]] > position[t["name"]] and dialect != "sqlite":
                deferred.append(f"ALTER TABLE {q(t['name'])} ADD {fk};")
            else:
                lines.append("  " + fk)
        stmts.append(f"CREATE TABLE {q(t['name'])} (\n" + ",\n".join(lines) + "\n);")
        if dialect == "postgresql":
            for r in rels:  # PostgreSQL does not index FK columns automatically
                if r["from_table"] == t["name"] and not (len(pks) >= 1 and pks[0] == r["from_column"]):
                    stmts.append(f"CREATE INDEX ON {q(t['name'])} ({q(r['from_column'])});")
    return "\n\n".join(stmts + deferred) + "\n"


def mermaid(design: dict) -> str:
    lines = ["erDiagram"]
    for r in design.get("relations", []):
        src = next((t for t in design["tables"] if t["name"] == r["from_table"]), None)
        col = next((c for c in (src or {}).get("columns", []) if c["name"] == r["from_column"]), {})
        card = "||--o{" if col.get("not_null") else "|o--o{"
        if col.get("unique"):
            card = "||--o|" if col.get("not_null") else "|o--o|"
        lines.append(f'  {r["to_table"]} {card} {r["from_table"]} : "{r["from_column"]}"')
    for t in design.get("tables", []):
        lines.append(f"  {t['name']} {{")
        fks = {r["from_column"] for r in design.get("relations", []) if r["from_table"] == t["name"]}
        for c in t.get("columns", []):
            key = " PK" if c.get("pk") else (" FK" if c["name"] in fks else (" UK" if c.get("unique") else ""))
            lines.append(f"    {re.sub(r'[^a-z0-9_]', '_', str(c.get('type', 'text')).lower())} {c['name']}{key}")
        lines.append("  }")
    return "\n".join(lines)


def from_schema(tables: list[dict]) -> dict:
    """Reverse-engineer a design from introspected tables (PostgreSQL catalog)."""
    tmap = {"integer": "integer", "bigint": "bigint", "smallint": "smallint", "text": "text", "boolean": "boolean",
            "date": "date", "jsonb": "jsonb", "uuid": "uuid", "real": "real", "double precision": "real",
            "timestamp without time zone": "timestamp", "timestamp with time zone": "timestamptz"}
    out_tables, rels = [], []
    for i, t in enumerate(tables):
        cols = []
        for c in t["columns"]:
            ty = c["type"]
            m = re.match(r"character varying\((\d+)\)", ty)
            n = re.match(r"numeric(\(\d+,\d+\))?", ty)
            ty = f"varchar({m.group(1)})" if m else (f"numeric{n.group(1) or ''}" if n else tmap.get(ty, "text"))
            cols.append({"name": c["name"], "type": ty, "pk": c["is_pk"], "not_null": not c["nullable"], "unique": False,
                         "identity": bool(c["default"] and "nextval" in str(c["default"])) or (c["is_pk"] and ty in ("integer", "bigint")),
                         "default": None})
            if c["fk"]:
                rt, rc = c["fk"].split(".")
                rels.append({"from_table": t["name"], "from_column": c["name"], "to_table": rt, "to_column": rc, "on_delete": "no action"})
        out_tables.append({"name": t["name"], "columns": cols, "x": 40 + (i % 3) * 300, "y": 40 + (i // 3) * 260})
    return {"tables": out_tables, "relations": rels}
