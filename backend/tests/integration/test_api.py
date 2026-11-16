"""Integration tests: real FastAPI app + real main DB + real sandbox cluster."""
import pytest

from tests.integration.conftest import make_client, register

pytestmark = pytest.mark.integration


def execute(c, sql, db="ecommerce", mode="readonly"):
    r = c.post("/api/playground/execute", json={"db_key": db, "mode": mode, "sql": sql})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ auth
def test_register_login_logout_flow(anon):
    u = register(anon)
    assert anon.get("/api/auth/me").json()["user"]["email"] == u["email"]
    anon.post("/api/auth/logout")
    assert anon.get("/api/auth/me").json()["user"] is None
    assert anon.post("/api/auth/login", json={"email": u["email"], "password": "wrong-pass"}).status_code == 401
    assert anon.post("/api/auth/login", json={"email": u["email"].upper(), "password": u["password"]}).status_code == 200


def test_register_validation_and_duplicate(anon):
    assert anon.post("/api/auth/register", json={"email": "bad", "password": "password123", "display_name": "x"}).status_code == 422
    assert anon.post("/api/auth/register", json={"email": "a@b.co", "password": "short", "display_name": "x"}).status_code == 422
    u = register(anon)
    r = make_client().post("/api/auth/register", json={"email": u["email"], "password": "password123", "display_name": "x"})
    assert r.status_code == 409


def test_protected_endpoints_require_login(anon):
    for path in ("/api/dashboard", "/api/playground/history", "/api/saved-queries", "/api/me/library"):
        assert anon.get(path).status_code == 401
    assert anon.post("/api/exercises/EX-E001/submit", json={"sql": "select 1"}).status_code == 401


def test_auth_rate_limited(anon):
    codes = [anon.post("/api/auth/login", json={"email": "x@y.z", "password": "p"}).status_code for _ in range(12)]
    assert 429 in codes


# ------------------------------------------------------------------ sandbox security
def test_readonly_select_works(anon):
    d = execute(anon, "SELECT COUNT(*) AS n FROM customers")
    assert d["ok"] and d["result_sets"][0]["rows"] == [[150]]


@pytest.mark.parametrize("sql", ["DELETE FROM customers", "DROP TABLE orders", "CREATE TABLE x (id int)",
                                 "UPDATE products SET price = 0",
                                 "SET default_transaction_read_only = off; COMMIT; DELETE FROM customers"])
def test_readonly_mode_rejects_writes(anon, sql):
    d = execute(anon, sql)
    assert not d["ok"] and d["error"]["kind"] == "permission"
    assert execute(anon, "SELECT COUNT(*) FROM customers")["result_sets"][0]["rows"] == [[150]]


@pytest.mark.parametrize("sql", ["SELECT pg_read_file('/etc/passwd')", "COPY customers TO PROGRAM 'id'",
                                 "CREATE EXTENSION dblink", "SELECT * FROM pg_authid"])
def test_os_and_privileged_access_denied(anon, sql):
    d = execute(anon, sql)
    assert not d["ok"]


def test_timeout_enforced_even_if_user_disables_it(anon):
    d = execute(anon, "SET statement_timeout = 0; SELECT pg_sleep(30)")
    assert not d["ok"] and d["error"]["kind"] == "timeout" and d["exec_ms"] < 9000


def test_row_cap(anon):
    d = execute(anon, "SELECT generate_series(1, 5000000)")
    rs = d["result_sets"][0]
    assert d["ok"] and rs["truncated"] and rs["row_count"] == 1000


def test_error_position_reported(anon):
    d = execute(anon, "SELECT 1;\nSELECT nope FROM customers")
    assert d["error"]["line"] == 2 and d["error"]["sqlstate"] == "42703"


def test_writable_requires_login(anon):
    r = anon.post("/api/playground/execute", json={"db_key": "hr", "mode": "writable", "sql": "select 1"})
    assert r.status_code == 401


def test_writable_sandboxes_are_isolated_and_resettable(user_client):
    other = make_client()
    register(other)
    d = execute(user_client, "DELETE FROM salaries; SELECT COUNT(*) FROM salaries", db="hr", mode="writable")
    assert d["ok"] and d["result_sets"][-1]["rows"] == [[0]]
    # another user's sandbox and the shared read-only DB are unaffected
    assert execute(other, "SELECT COUNT(*) FROM salaries", db="hr", mode="writable")["result_sets"][0]["rows"][0][0] > 0
    assert execute(other, "SELECT COUNT(*) FROM salaries", db="hr")["result_sets"][0]["rows"][0][0] > 0
    # cannot escalate
    assert not execute(user_client, "ALTER ROLE CURRENT_USER SUPERUSER", db="hr", mode="writable")["ok"]
    assert not execute(user_client, "CREATE DATABASE evil", db="hr", mode="writable")["ok"]
    assert user_client.post("/api/playground/reset", json={"db_key": "hr"}).status_code == 200
    assert execute(user_client, "SELECT COUNT(*) FROM salaries", db="hr", mode="writable")["result_sets"][0]["rows"][0][0] > 0


def test_transactions_in_writable_mode(user_client):
    d = execute(user_client, "BEGIN; DELETE FROM order_items; ROLLBACK; SELECT COUNT(*) FROM order_items", mode="writable")
    assert d["result_sets"][-1]["rows"][0][0] > 0


def test_unknown_database_rejected(anon):
    r = anon.post("/api/playground/execute", json={"db_key": "postgres", "mode": "readonly", "sql": "select 1"})
    assert r.status_code == 404
    r = anon.post("/api/playground/execute", json={"db_key": "../etc", "mode": "readonly", "sql": "select 1"})
    assert r.status_code == 422


# ------------------------------------------------------------------ practice / answer checking
def test_equivalent_sql_is_accepted(user_client):
    alt = ("SELECT cat.name AS category, (SELECT count(*) FROM products p WHERE p.category_id = cat.id) AS products "
           "FROM categories cat")
    r = user_client.post("/api/exercises/EX-M009/submit", json={"sql": alt}).json()
    assert r["correct"] and r["points_awarded"] == 20 and "first_correct" in r["new_achievements"]
    # solving again gives no extra points
    assert user_client.post("/api/exercises/EX-M009/submit", json={"sql": alt}).json()["points_awarded"] == 0


def test_wrong_answer_explained(user_client):
    wrong = "SELECT c.name AS category, COUNT(*) AS products FROM categories c LEFT JOIN products p ON p.category_id = c.id GROUP BY c.name"
    r = user_client.post("/api/exercises/EX-M009/submit", json={"sql": wrong}).json()
    assert not r["correct"] and r["reason_code"] == "VALUE_MISMATCH"
    assert ["Toys", 0] in r["details"]["missing_rows"] and r["solution_sql"] and r["expected"]["row_count"] == 15


def test_sql_error_submission(user_client):
    r = user_client.post("/api/exercises/EX-E004/submit", json={"sql": "SELEC name FROM products"}).json()
    assert not r["correct"] and r["reason_code"] == "SQL_ERROR"


def test_order_sensitive_exercise(user_client):
    r = user_client.post("/api/exercises/EX-E008/submit", json={"sql": "SELECT id, order_date FROM (SELECT id, order_date FROM orders ORDER BY order_date DESC LIMIT 5) t ORDER BY order_date"}).json()
    assert r["reason_code"] == "ORDER_MISMATCH"


def test_dml_exercise_checked_on_fresh_copy(user_client):
    sql = "INSERT INTO categories (name, parent_id) VALUES ('Pet Supplies', NULL), ('Gaming', 1);"
    r = user_client.post("/api/exercises/EX-P002/submit", json={"sql": sql}).json()
    assert r["correct"], r["message"]
    # grading did not touch the learner's own sandbox
    d = execute(user_client, "SELECT COUNT(*) FROM categories WHERE name = 'Gaming'", mode="writable")
    assert d["result_sets"][0]["rows"] == [[0]]


def test_exercise_list_and_detail(anon):
    data = anon.get("/api/exercises").json()
    assert len(data["items"]) >= 60 and {"easy", "medium", "hard", "expert"} <= {e["difficulty"] for e in data["items"]}
    d = anon.get("/api/exercises/EX-E001").json()
    assert len(d["hints"]) == 3 and d["expected"]["columns"][0]["name"] == "greeting"
    assert anon.get("/api/exercises/NOPE").status_code == 404


# ------------------------------------------------------------------ learning & progress
def test_courses_and_lessons(anon):
    courses = anon.get("/api/courses").json()
    assert [c["lesson_count"] for c in courses] == [14, 16, 14, 18]
    lesson = anon.get("/api/lessons/left-join").json()
    assert lesson["examples"] and lesson["examples"][0]["result"]["ok"]
    assert lesson["prev"]["slug"] == "inner-join" and lesson["next"]["slug"] == "right-join" and lesson["exercises"]


def test_progress_updates_dashboard(user_client):
    d0 = user_client.get("/api/dashboard").json()
    assert d0["lessons"]["completed"] == 0 and d0["submissions"]["accuracy"] is None and d0["streak"] == 0
    user_client.post("/api/lessons/select/progress", json={"status": "completed"})
    user_client.post("/api/exercises/EX-E001/submit", json={"sql": "select 'Hello, SQL!' as greeting"})
    user_client.post("/api/exercises/EX-E004/submit", json={"sql": "select 1"})
    d = user_client.get("/api/dashboard").json()
    assert d["lessons"]["completed"] == 1 and d["exercises"]["solved"] == 1
    assert d["submissions"] == {"total": 2, "correct": 1, "accuracy": 50.0}
    assert d["streak"] == 1 and d["level"]["points"] == 10
    assert d["activity"][-1]["submissions"] == 2
    # completed lessons are never downgraded
    user_client.post("/api/lessons/select/progress", json={"status": "in_progress"})
    assert user_client.get("/api/lessons/select").json()["status"] == "completed"


def test_bookmarks_notes_and_ownership(user_client):
    assert user_client.put("/api/lessons/where/bookmark").status_code == 204
    user_client.put("/api/lessons/where/note", json={"body": "remember IS NULL"})
    lib = user_client.get("/api/me/library").json()
    assert lib["bookmarks"][0]["slug"] == "where" and lib["notes"][0]["body"] == "remember IS NULL"
    q = user_client.post("/api/saved-queries", json={"title": "t", "db_key": "hr", "sql": "select 1"}).json()
    intruder = make_client()
    register(intruder)
    assert intruder.delete(f"/api/saved-queries/{q['id']}").status_code == 404
    assert intruder.put(f"/api/saved-queries/{q['id']}", json={"title": "x", "db_key": "hr", "sql": "x"}).status_code == 404
    assert user_client.delete(f"/api/saved-queries/{q['id']}").status_code == 204


def test_history_recorded(user_client):
    execute(user_client, "SELECT 42")
    h = user_client.get("/api/playground/history").json()
    assert h[0]["sql"] == "SELECT 42" and h[0]["success"]


def test_validate_endpoint(anon):
    r = anon.post("/api/playground/validate", json={"sql": "SELEC 1"}).json()
    assert r["issues"][0]["line"] == 1


def test_databases_and_er(anon):
    dbs = anon.get("/api/databases").json()
    assert {d["key"] for d in dbs} == {"ecommerce", "hr", "banking", "hospital", "music_store", "saas"}
    hr = anon.get("/api/databases/hr").json()
    assert "employees |o--o{ employees" in hr["er_mermaid"]
    assert anon.get("/api/databases/hr/tables/employees/preview").json()["result_sets"][0]["row_count"] > 0
    assert anon.get("/api/databases/hr/tables/pg_authid/preview").status_code == 404


def test_concurrent_first_use_of_writable_db(user_client):
    """Regression: schema fetch + execute fired together on first use must not race on CREATE DATABASE."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as pool:
        futs = [pool.submit(user_client.get, "/api/databases/banking?mode=writable") for _ in range(3)]
        futs += [pool.submit(user_client.post, "/api/playground/execute",
                             json={"db_key": "banking", "mode": "writable", "sql": "SELECT 1"}) for _ in range(3)]
        assert [f.result().status_code for f in futs] == [200] * 6


def test_zero_row_select_keeps_column_headers(anon):
    d = execute(anon, "SELECT id, name FROM products WHERE false")
    rs = d["result_sets"][0]
    assert d["ok"] and rs["row_count"] == 0 and [c["name"] for c in rs["columns"]] == ["id", "name"]
    assert rs["command"] == "SELECT 0"
