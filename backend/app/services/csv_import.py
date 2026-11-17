"""CSV import into a learner's writable sandbox (PostgreSQL via COPY as the learner's own role, or SQLite).

All identifiers are sanitized to [a-z_][a-z0-9_]*; values are always passed as data (COPY rows / bound
parameters), never interpolated into SQL.
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime

from psycopg import sql as psql

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
MAX_COLS = 100
TYPES = ("integer", "bigint", "numeric", "boolean", "date", "timestamp", "text")


class CsvError(ValueError):
    pass


@dataclass
class CsvColumn:
    name: str
    type: str
    nulls: int
    sample: list[str]


def sanitize(name: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
    if not s or not re.match(r"[a-z_]", s[0]):
        s = f"{fallback}_{s}" if s else fallback
    return s[:63]


def _is_int(v: str) -> bool:
    return bool(re.fullmatch(r"[-+]?\d{1,18}", v))


def _is_num(v: str) -> bool:
    return bool(re.fullmatch(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", v))


def _is_bool(v: str) -> bool:
    return v.lower() in ("true", "false", "t", "f", "yes", "no")


def _is_date(v: str) -> bool:
    try:
        date.fromisoformat(v)
        return len(v) == 10
    except ValueError:
        return False


def _is_ts(v: str) -> bool:
    try:
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return len(v) > 10
    except ValueError:
        return False


def infer_type(values: list[str]) -> str:
    vals = [v for v in values if v != ""]
    if not vals:
        return "text"
    for t, check in (("integer", _is_int), ("numeric", _is_num), ("boolean", _is_bool), ("date", _is_date),
                     ("timestamp", _is_ts)):
        if all(check(v) for v in vals):
            if t == "integer" and any(abs(int(v)) > 2_147_483_647 for v in vals):
                return "bigint"
            return t
    return "text"


def parse(csv_text: str, delimiter: str = ",", has_header: bool = True) -> tuple[list[str], list[list[str]]]:
    if len(csv_text.encode("utf-8")) > MAX_BYTES:
        raise CsvError(f"ไฟล์ใหญ่เกิน {MAX_BYTES // 1048576} MB")
    if delimiter not in (",", ";", "\t", "|"):
        raise CsvError("delimiter ต้องเป็น , ; | หรือ tab")
    rows = list(csv.reader(io.StringIO(csv_text.lstrip("﻿")), delimiter=delimiter))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise CsvError("ไม่พบข้อมูลในไฟล์")
    width = max(len(r) for r in rows)
    if width > MAX_COLS:
        raise CsvError(f"คอลัมน์เกิน {MAX_COLS}")
    header = rows[0] if has_header else [f"column_{i + 1}" for i in range(width)]
    data = rows[1:] if has_header else rows
    if len(data) > MAX_ROWS:
        raise CsvError(f"จำนวนแถวเกิน {MAX_ROWS:,}")
    names, seen = [], set()
    for i in range(width):
        n = sanitize(header[i] if i < len(header) else "", f"col{i + 1}")
        base, k = n, 2
        while n in seen:
            n, k = f"{base}_{k}", k + 1
        seen.add(n)
        names.append(n)
    data = [[c.strip() for c in (r + [""] * (width - len(r)))[:width]] for r in data]
    return names, data


def preview(csv_text: str, delimiter: str, has_header: bool) -> dict:
    names, data = parse(csv_text, delimiter, has_header)
    cols = [CsvColumn(n, infer_type([r[i] for r in data]), sum(1 for r in data if r[i] == ""), [r[i] for r in data[:3]])
            for i, n in enumerate(names)]
    return {"columns": [asdict(c) for c in cols], "row_count": len(data), "sample": data[:10],
            "suggested_table": None}


def _convert(v: str, t: str):
    if v == "":
        return None
    if t in ("integer", "bigint"):
        return int(v)
    if t == "numeric":
        return v
    if t == "boolean":
        return v.lower() in ("true", "t", "yes")
    return v


def import_postgres(sandbox, target, table: str, columns: list[dict], data: list[list[str]], replace: bool) -> int:
    """Runs as the learner's own sandbox role, inside one transaction."""
    with sandbox._connect(target.database, target.user, target.password, autocommit=False) as conn:
        ident = psql.Identifier(table)
        exists = conn.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",)).fetchone()[0]
        if exists and not replace:
            raise CsvError(f"มีตาราง '{table}' อยู่แล้ว — เลือก 'แทนที่ตารางเดิม' หรือเปลี่ยนชื่อ")
        if exists:
            conn.execute(psql.SQL("DROP TABLE {} CASCADE").format(ident))
        cols_sql = psql.SQL(", ").join(psql.SQL("{} {}").format(psql.Identifier(c["name"]), psql.SQL(c["type"])) for c in columns)
        conn.execute(psql.SQL("CREATE TABLE {} ({})").format(ident, cols_sql))
        names = psql.SQL(", ").join(psql.Identifier(c["name"]) for c in columns)
        try:
            with conn.cursor().copy(psql.SQL("COPY {} ({}) FROM STDIN").format(ident, names)) as cp:
                for i, r in enumerate(data):
                    try:
                        cp.write_row([_convert(v, c["type"]) for v, c in zip(r, columns, strict=True)])
                    except ValueError as e:
                        raise CsvError(f"แถวที่ {i + 1}: {e}") from None
        except CsvError:
            raise
        except Exception as e:
            raise CsvError(f"นำเข้าไม่สำเร็จ: {str(e).splitlines()[0]}") from None
        conn.commit()
    return len(data)


def import_sqlite(path: str, table: str, columns: list[dict], data: list[list[str]], replace: bool) -> int:
    affinity = {"integer": "INTEGER", "bigint": "INTEGER", "numeric": "NUMERIC", "boolean": "BOOLEAN"}
    conn = sqlite3.connect(path)
    try:
        exists = conn.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND name=?", (table,)).fetchone()
        if exists and not replace:
            raise CsvError(f"มีตาราง '{table}' อยู่แล้ว — เลือก 'แทนที่ตารางเดิม' หรือเปลี่ยนชื่อ")
        with conn:
            if exists:
                conn.execute(f'DROP TABLE "{table}"')
            conn.execute(f'CREATE TABLE "{table}" (' + ", ".join(f'"{c["name"]}" {affinity.get(c["type"], "TEXT")}' for c in columns) + ")")
            marks = ", ".join("?" for _ in columns)
            conn.executemany(f'INSERT INTO "{table}" VALUES ({marks})',
                             [[(int(v) if isinstance(v, bool) else v) for v in (_convert(x, c["type"]) for x, c in zip(r, columns, strict=True))]
                              for r in data])
    except (ValueError, sqlite3.Error) as e:
        if isinstance(e, CsvError):
            raise
        raise CsvError(f"นำเข้าไม่สำเร็จ: {e}") from None
    finally:
        conn.close()
    return len(data)
