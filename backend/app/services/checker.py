"""Result-based answer checking (pure functions — no I/O, fully unit-tested).

We never compare SQL text: two different queries producing the same result are both correct.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

NUMERIC_TYPES = {"int2", "int4", "int8", "numeric", "float4", "float8", "money", "oid"}


@dataclass
class CheckResult:
    correct: bool
    reason_code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _is_numeric_type(t: str | None) -> bool:
    return (t or "").split("(")[0] in NUMERIC_TYPES


def normalize_value(v: Any, col_type: str | None, decimals: int) -> Any:
    """NULL stays None (never equal to 0 or ''); numbers are rounded; everything else as-is."""
    if v is None:
        return None
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, (int, float)) or (_is_numeric_type(col_type) and isinstance(v, str)):
        try:
            f = float(v)
        except ValueError:
            return ("str", v)
        if math.isnan(f) or math.isinf(f):
            return ("num", str(f))
        r = round(f, decimals)
        return ("num", 0.0 if r == 0 else r)
    if isinstance(v, (list, dict)):
        return ("json", repr(v))
    return ("str", str(v))


def _normalize_rows(rows: list[list[Any]], types: list[str], decimals: int) -> list[tuple]:
    return [tuple(normalize_value(v, types[i] if i < len(types) else None, decimals) for i, v in enumerate(r))
            for r in rows]


def _display(row: tuple) -> list[Any]:
    out: list[Any] = []
    for v in row:
        if v is None:
            out.append(None)
        elif v[0] == "num" and isinstance(v[1], float) and v[1].is_integer():
            out.append(int(v[1]))
        else:
            out.append(v[1])
    return out


def compare_results(actual: dict, expected: dict, *, order_matters: bool = False, check_column_names: bool = True,
                    decimals: int = 2) -> CheckResult:
    """actual/expected: {"columns": [{"name","type"}], "rows": [[...]]}"""
    a_cols = [c["name"] for c in actual.get("columns", [])]
    e_cols = [c["name"] for c in expected.get("columns", [])]
    a_types = [c.get("type") for c in actual.get("columns", [])]
    e_types = [c.get("type") for c in expected.get("columns", [])]

    if not a_cols:
        return CheckResult(False, "NO_RESULT", "คำตอบไม่ได้คืนผลลัพธ์เป็นตาราง (ต้องมีคำสั่ง SELECT ที่คืนข้อมูล)")
    if len(a_cols) != len(e_cols):
        return CheckResult(False, "COLUMN_COUNT_MISMATCH",
                           f"จำนวนคอลัมน์ไม่ตรง: ได้ {len(a_cols)} คอลัมน์ แต่คาดหวัง {len(e_cols)} คอลัมน์ ({', '.join(e_cols)})",
                           {"actual_columns": a_cols, "expected_columns": e_cols})
    if check_column_names:
        wrong = [(a, e) for a, e in zip(a_cols, e_cols, strict=True) if a.lower() != e.lower()]
        if wrong:
            a, e = wrong[0]
            return CheckResult(False, "COLUMN_NAME_MISMATCH",
                               f"ชื่อคอลัมน์ไม่ตรง: ได้ '{a}' แต่คาดหวัง '{e}' (ใช้ AS ตั้งชื่อคอลัมน์ให้ตรงโจทย์ และเรียงลำดับคอลัมน์ให้ถูกต้อง)",
                               {"actual_columns": a_cols, "expected_columns": e_cols})

    types = [e if _is_numeric_type(e) or _is_numeric_type(a) else e for a, e in zip(a_types, e_types, strict=True)]
    a_rows = _normalize_rows(actual.get("rows", []), [a or t for a, t in zip(a_types, types, strict=True)], decimals)
    e_rows = _normalize_rows(expected.get("rows", []), types, decimals)

    if actual.get("truncated"):
        return CheckResult(False, "TOO_MANY_ROWS", "ผลลัพธ์มีจำนวนแถวมากเกินไป (เกินขีดจำกัด) — ตรวจสอบเงื่อนไข WHERE/JOIN")
    if len(a_rows) != len(e_rows):
        hint = "ลองตรวจสอบเงื่อนไข WHERE, การ JOIN (แถวซ้ำ/หาย), DISTINCT หรือ LIMIT"
        return CheckResult(False, "ROW_COUNT_MISMATCH",
                           f"จำนวนแถวไม่ตรง: ได้ {len(a_rows)} แถว แต่คาดหวัง {len(e_rows)} แถว — {hint}",
                           {"actual_rows": len(a_rows), "expected_rows": len(e_rows)})

    ca, ce = Counter(a_rows), Counter(e_rows)
    if ca != ce:
        missing = list((ce - ca).elements())[:5]
        extra = list((ca - ce).elements())[:5]
        null_note = ""
        if any(v is None for r in missing + extra for v in r):
            null_note = " (สังเกตค่า NULL — NULL ไม่เท่ากับ 0 หรือข้อความว่าง)"
        return CheckResult(False, "VALUE_MISMATCH",
                           f"ข้อมูลในผลลัพธ์ไม่ตรง: มี {sum((ce - ca).values())} แถวที่คาดหวังแต่ไม่พบ{null_note}",
                           {"missing_rows": [_display(r) for r in missing], "unexpected_rows": [_display(r) for r in extra]})
    if order_matters and a_rows != e_rows:
        first = next(i for i, (x, y) in enumerate(zip(a_rows, e_rows, strict=True)) if x != y)
        return CheckResult(False, "ORDER_MISMATCH",
                           f"ข้อมูลครบถูกต้อง แต่ลำดับแถวไม่ตรง (เริ่มต่างที่แถวที่ {first + 1}) — ตรวจสอบ ORDER BY",
                           {"first_diff_row": first + 1})
    return CheckResult(True, "CORRECT", "ถูกต้อง! ผลลัพธ์ตรงกับที่คาดหวัง")
