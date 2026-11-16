"""SQL syntax validation using libpg_query (the real PostgreSQL parser) via pglast.

Runs entirely in-process — nothing is executed — so it is safe to call on every keystroke (debounced).
"""
from __future__ import annotations

from dataclasses import dataclass

import pglast
from pglast.parser import ParseError

from app.services.sql_split import offset_to_line_col


@dataclass
class SyntaxIssue:
    message: str
    line: int
    column: int
    end_column: int


def validate_sql(sql: str) -> list[SyntaxIssue]:
    if not sql.strip():
        return []
    try:
        pglast.parser.parse_sql_json(sql)
        return []
    except ParseError as e:
        msg = e.args[0] if e.args else str(e)
        loc = e.args[1] if len(e.args) > 1 and isinstance(e.args[1], int) else len(sql)
        char_index = min(loc, len(sql))  # pglast already converts to a str (character) index
        line, col = offset_to_line_col(sql, char_index)
        rest = sql[char_index:].split("\n", 1)[0]
        token_len = len(rest.split()[0]) if rest.split() else 1
        return [SyntaxIssue(message=msg, line=line, column=col, end_column=col + max(1, token_len))]
