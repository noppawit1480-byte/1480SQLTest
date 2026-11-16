"""Split a SQL script into statements while keeping their offsets in the original text.

sqlparse preserves every character, so concatenating its statements reproduces the input —
this lets us map PostgreSQL error positions back to line/column in the editor.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlparse
from sqlparse import tokens as T


@dataclass
class Statement:
    text: str
    offset: int  # character offset of `text` within the original script


def _is_empty(stmt) -> bool:
    for tok in stmt.flatten():
        if tok.ttype in T.Whitespace or tok.ttype in T.Newline or tok.ttype in T.Comment \
                or tok.ttype in T.Comment.Single or tok.ttype in T.Comment.Multiline:
            continue
        if tok.ttype is T.Punctuation and tok.value == ";":
            continue
        return False
    return True


def split_statements(sql: str) -> list[Statement]:
    out: list[Statement] = []
    pos = 0
    for stmt in sqlparse.parse(sql):
        raw = str(stmt)
        start = pos
        pos += len(raw)
        if _is_empty(stmt):
            continue
        # trim leading whitespace (keep offset accurate) and a trailing semicolon
        lead = len(raw) - len(raw.lstrip())
        body = raw[lead:].rstrip()
        if body.endswith(";"):
            body = body[:-1].rstrip()
        out.append(Statement(text=body, offset=start + lead))
    return out


def offset_to_line_col(sql: str, offset: int) -> tuple[int, int]:
    """0-based character offset -> 1-based (line, column)."""
    offset = max(0, min(offset, len(sql)))
    before = sql[:offset]
    line = before.count("\n") + 1
    col = offset - (before.rfind("\n") + 1) + 1
    return line, col
