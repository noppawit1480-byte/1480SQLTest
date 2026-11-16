from app.services.checker import compare_results

COLS = [{"name": "city", "type": "varchar"}, {"name": "n", "type": "int8"}]


def res(rows, cols=COLS, truncated=False):
    return {"columns": cols, "rows": rows, "truncated": truncated}


def test_identical_results_are_correct():
    r = compare_results(res([["A", 1], ["B", 2]]), res([["A", 1], ["B", 2]]))
    assert r.correct and r.reason_code == "CORRECT"


def test_row_order_ignored_when_not_required():
    assert compare_results(res([["B", 2], ["A", 1]]), res([["A", 1], ["B", 2]])).correct


def test_row_order_enforced_when_required():
    r = compare_results(res([["B", 2], ["A", 1]]), res([["A", 1], ["B", 2]]), order_matters=True)
    assert not r.correct and r.reason_code == "ORDER_MISMATCH"


def test_column_name_case_insensitive_but_must_match():
    cols = [{"name": "CITY", "type": "varchar"}, {"name": "N", "type": "int8"}]
    assert compare_results(res([["A", 1]], cols), res([["A", 1]])).correct
    bad = [{"name": "town", "type": "varchar"}, {"name": "n", "type": "int8"}]
    r = compare_results(res([["A", 1]], bad), res([["A", 1]]))
    assert r.reason_code == "COLUMN_NAME_MISMATCH"


def test_column_names_can_be_ignored():
    bad = [{"name": "x", "type": "varchar"}, {"name": "y", "type": "int8"}]
    assert compare_results(res([["A", 1]], bad), res([["A", 1]]), check_column_names=False).correct


def test_column_count_mismatch():
    r = compare_results(res([["A"]], COLS[:1]), res([["A", 1]]))
    assert r.reason_code == "COLUMN_COUNT_MISMATCH"


def test_row_count_mismatch():
    r = compare_results(res([["A", 1]]), res([["A", 1], ["B", 2]]))
    assert r.reason_code == "ROW_COUNT_MISMATCH" and r.details == {"actual_rows": 1, "expected_rows": 2}


def test_duplicates_matter_multiset():
    # same set of distinct rows, different multiplicity → wrong (catches missing/extra DISTINCT)
    r = compare_results(res([["A", 1], ["A", 1], ["B", 2]]), res([["A", 1], ["B", 2], ["B", 2]]))
    assert r.reason_code == "VALUE_MISMATCH"


def test_null_is_not_zero_or_empty():
    assert not compare_results(res([["A", 0]]), res([["A", None]])).correct
    assert not compare_results(res([["", 1]]), res([[None, 1]])).correct
    assert compare_results(res([[None, None]]), res([[None, None]])).correct


def test_numeric_tolerance_and_types():
    cols = [{"name": "v", "type": "numeric"}]
    assert compare_results(res([["10.00"]], cols), res([[10]], [{"name": "v", "type": "int8"}])).correct
    assert compare_results(res([[3.3333333]], cols), res([["3.33"]], cols)).correct
    assert not compare_results(res([["3.35"]], cols), res([["3.33"]], cols)).correct


def test_text_vs_number_is_a_type_mismatch():
    r = compare_results(res([["5"]], [{"name": "v", "type": "text"}]), res([[5]], [{"name": "v", "type": "int4"}]))
    assert not r.correct


def test_no_result_set():
    assert compare_results({"columns": [], "rows": []}, res([["A", 1]])).reason_code == "NO_RESULT"


def test_truncated_result_rejected():
    assert compare_results(res([["A", 1]], truncated=True), res([["A", 1]])).reason_code == "TOO_MANY_ROWS"


def test_mismatch_details_show_samples():
    r = compare_results(res([["A", 1], ["B", 3]]), res([["A", 1], ["B", 2]]))
    assert r.details["missing_rows"] == [["B", 2]] and r.details["unexpected_rows"] == [["B", 3]]
