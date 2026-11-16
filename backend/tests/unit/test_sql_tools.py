from datetime import date

from app.services.progress import compute_streak, level_for
from app.services.sandbox.base import to_jsonable
from app.services.sandbox.postgres import first_keyword, is_command_statement
from app.services.sql_split import offset_to_line_col, split_statements
from app.services.validator import validate_sql


def test_split_keeps_offsets_and_handles_quotes_comments_dollar():
    sql = "-- c;\nselect ';' as x;\n$$a;b$$;\n\n/* only comment */;\nselect 2"
    stmts = split_statements(sql)
    assert len(stmts) == 3
    for s in stmts:
        assert sql[s.offset:s.offset + len(s.text)] == s.text
    assert stmts[-1].text == "select 2"


def test_split_ignores_empty():
    assert split_statements(" ;; -- x\n") == []


def test_offset_to_line_col():
    assert offset_to_line_col("ab\ncd", 3) == (2, 1)
    assert offset_to_line_col("ab\ncd", 0) == (1, 1)


def test_validator_reports_line_and_column_with_thai_text():
    issues = validate_sql("select 'ชื่อ' from t\nwher x = 1")
    assert len(issues) == 1 and issues[0].line == 2 and issues[0].column == 6


def test_validator_accepts_valid_multi_statement():
    assert validate_sql("CREATE TABLE t (id int primary key); INSERT INTO t VALUES (1); SELECT * FROM t;") == []


def test_command_detection():
    assert is_command_statement("INSERT INTO t VALUES (1)")
    assert not is_command_statement("INSERT INTO t VALUES (1) RETURNING id")
    assert not is_command_statement("-- c\nWITH x AS (SELECT 1) SELECT * FROM x")
    assert first_keyword("  /* c */ select 1") == "SELECT"


def test_to_jsonable():
    from decimal import Decimal
    assert to_jsonable(Decimal("1.50")) == "1.50"
    assert to_jsonable(date(2025, 1, 2)) == "2025-01-02"
    assert to_jsonable(b"\x01") == "\\x01"
    assert to_jsonable(float("nan")) == "nan"


def test_streak():
    t = date(2025, 5, 10)
    assert compute_streak([], t) == 0
    assert compute_streak([date(2025, 5, 10), date(2025, 5, 9), date(2025, 5, 7)], t) == 2
    # yesterday still counts if the learner hasn't studied yet today
    assert compute_streak([date(2025, 5, 9), date(2025, 5, 8)], t) == 2
    assert compute_streak([date(2025, 5, 8)], t) == 0


def test_levels():
    assert level_for(0)["name"] == "Novice"
    assert level_for(260)["name"] == "Intermediate" and level_for(260)["next_threshold"] == 600
    assert level_for(5000)["next_name"] is None
