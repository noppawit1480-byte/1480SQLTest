"""MySQL engine (needs a MySQL 8 server configured via MYSQL_HOST; skipped otherwise — see docs/INSTALL.md)."""
import pytest

from app.services.sandbox.mysql_engine import mysql_enabled
from tests.integration.conftest import make_client, register

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not mysql_enabled(), reason="MySQL engine not configured (MYSQL_HOST)")]


def run(c, sql, db="ecommerce", mode="readonly"):
    r = c.post("/api/playground/execute", json={"db_key": db, "engine": "mysql", "mode": mode, "sql": sql})
    assert r.status_code == 200, r.text
    return r.json()


def test_engine_listed_and_same_data(anon):
    eng = {e["key"]: e for e in anon.get("/api/engines").json()["engines"]}
    assert eng["mysql"]["available"] is True
    for db, table in (("ecommerce", "orders"), ("saas", "events"), ("hr", "salaries"), ("banking", "transactions")):
        pg = anon.post("/api/playground/execute", json={"db_key": db, "engine": "postgresql", "sql": f"SELECT COUNT(*) FROM {table}"})
        my = run(anon, f"SELECT COUNT(*) FROM {table}", db)
        assert my["result_sets"][0]["rows"][0][0] == pg.json()["result_sets"][0]["rows"][0][0] > 0
    money = "SELECT ROUND(SUM(unit_price * quantity), 2) FROM order_items"
    assert run(anon, money)["result_sets"][0]["rows"] == anon.post(
        "/api/playground/execute", json={"db_key": "ecommerce", "engine": "postgresql", "sql": money}).json()["result_sets"][0]["rows"]


@pytest.mark.parametrize("sql,needle", [
    ("DELETE FROM customers", "Read-only"),
    ("CREATE TABLE x (a int)", "Read-only"),
    ("SELECT * FROM customers INTO OUTFILE '/tmp/x.csv'", "FILE"),
    ("SELECT user FROM mysql.user", "denied"),
    ("SET GLOBAL max_connections = 1", "SYSTEM_VARIABLES_ADMIN"),
])
def test_readonly_blocks_writes_files_and_admin(anon, sql, needle):
    d = run(anon, sql)
    assert not d["ok"] and d["error"]["kind"] == "permission" and needle in d["error"]["message"]


def test_load_file_cannot_read_server_files(anon):
    assert run(anon, "SELECT LOAD_FILE('/etc/passwd') AS f")["result_sets"][0]["rows"] == [[None]]


def test_timeouts_cover_non_select_statements(user_client):
    assert run(user_client, "SELECT SLEEP(30)")["error"]["kind"] == "timeout"
    # max_execution_time does not apply to DML / CALL — the watchdog (KILL QUERY) must
    d = run(user_client, "UPDATE customers SET city = city WHERE SLEEP(1) = 0", mode="writable")
    assert d["error"]["kind"] == "timeout"
    run(user_client, "CREATE PROCEDURE spin() BEGIN DECLARE i INT DEFAULT 0; WHILE 1 DO SET i = i + 1; END WHILE; END",
        mode="writable")
    assert run(user_client, "CALL spin()", mode="writable")["error"]["kind"] == "timeout"
    assert run(user_client, "SELECT COUNT(*) FROM customers", mode="writable")["ok"]  # sandbox still usable


def test_row_cap_and_syntax_error_position(anon):
    d = run(anon, "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 50000) SELECT n FROM r")
    assert d["ok"] and d["result_sets"][0]["truncated"] and d["result_sets"][0]["row_count"] == 1000
    e = run(anon, "SELECT 1;\nSELECT *\nFROMM customers")["error"]
    assert e["kind"] == "sql" and e["line"] == 3 and e["statement_index"] == 1


def test_writable_isolated_privileges_and_reset(user_client):
    other = make_client()
    uid = register(other)["id"]
    d = run(user_client, "DELETE FROM payments; SELECT COUNT(*) FROM payments", mode="writable")
    assert d["result_sets"][-1]["rows"] == [[0]]
    assert run(other, "SELECT COUNT(*) FROM payments", mode="writable")["result_sets"][0]["rows"][0][0] > 0
    assert run(user_client, "SELECT COUNT(*) FROM payments")["result_sets"][0]["rows"][0][0] > 0   # shared copy untouched
    for sql in (f"SELECT * FROM u_{uid}_ecommerce.customers", "GRANT SELECT ON *.* TO sbx_reader",
                "CREATE USER evil IDENTIFIED BY 'x'", "CREATE EVENT e ON SCHEDULE EVERY 1 SECOND DO DELETE FROM orders",
                "LOAD DATA LOCAL INFILE '/etc/passwd' INTO TABLE customers"):
        d = run(user_client, sql, mode="writable")
        assert not d["ok"] and d["error"]["kind"] == "permission", sql
    assert user_client.post("/api/playground/reset", json={"db_key": "ecommerce", "engine": "mysql"}).status_code == 200
    assert run(user_client, "SELECT COUNT(*) FROM payments", mode="writable")["result_sets"][0]["rows"][0][0] > 0


def test_schema_explain_and_analyze_rollback(user_client):
    d = user_client.get("/api/databases/hr?engine=mysql").json()
    emp = next(t for t in d["tables"] if t["name"] == "employees")
    assert d["engine"] == "mysql" and any(c["fk"] == "employees.id" for c in emp["columns"]) and emp["comment"]
    p = user_client.post("/api/plans/explain", json={"engine": "mysql", "sql": "SELECT * FROM orders WHERE customer_id = 5"}).json()
    assert p["ok"] and "idx_orders_customer" in p["summary"]["indexes_used"]
    a = user_client.post("/api/plans/explain", json={"engine": "mysql", "analyze": True, "mode": "writable",
                                                     "sql": "DELETE FROM payments WHERE id > 0"}).json()
    assert a["ok"], a
    assert run(user_client, "SELECT COUNT(*) FROM payments", mode="writable")["result_sets"][0]["rows"] == [[946]]
    assert user_client.post("/api/plans/explain", json={"engine": "mysql", "sql": "SELECT 1; SELECT 2"}).status_code == 422


def test_dialect_comparison_shows_real_mysql_differences(anon):
    d = anon.post("/api/dialects/compare", json={"sql": "SELECT 7/2 AS d"}).json()
    assert d["engines"] == ["postgresql", "sqlite", "mysql"]
    assert d["comparison"]["engines"]["mysql"]["same"] is False and d["mysql"]["result_sets"][0]["rows"] == [["3.5000"]]
    # MySQL's default collation is case-insensitive: inconsistently cased cities collapse into fewer groups
    g = anon.post("/api/dialects/compare", json={"sql": "SELECT city, COUNT(*) AS n FROM customers GROUP BY city"}).json()
    assert g["comparison"]["engines"]["sqlite"]["same"] and not g["comparison"]["engines"]["mysql"]["same"]
    assert "collation" in {f["key"] for f in g["features"]}


def test_designer_apply_and_csv_import(user_client):
    design = {"tables": [
        {"name": "authors", "columns": [{"name": "id", "type": "integer", "pk": True, "identity": True},
                                        {"name": "email", "type": "text", "unique": True},
                                        {"name": "bio", "type": "text", "default": "'n/a'"}]},
        {"name": "books", "columns": [{"name": "id", "type": "integer", "pk": True, "identity": True},
                                      {"name": "author_id", "type": "integer", "not_null": True}]}],
        "relations": [{"from_table": "books", "from_column": "author_id", "to_table": "authors", "to_column": "id",
                       "on_delete": "cascade"}]}
    did = user_client.post("/api/designs", json={"name": "Lib", "design": design}).json()["id"]
    a = user_client.post(f"/api/designs/{did}/apply", json={"engine": "mysql"}).json()
    assert a["ok"], a
    d = run(user_client, "INSERT INTO authors (email) VALUES ('a@x'); INSERT INTO books (author_id) VALUES (1); "
                         "SELECT bio, (SELECT COUNT(*) FROM books) FROM authors", "blank", "writable")
    assert d["ok"] and d["result_sets"][-1]["rows"] == [["n/a", 1]]
    assert not run(user_client, "INSERT INTO books (author_id) VALUES (999)", "blank", "writable")["ok"]  # FK enforced
    csv = "Order ID,Amount,Paid,Order Date\n1,1200.50,true,2025-01-03\n2,,false,2025-01-04\n"
    r = user_client.post("/api/csv/import", json={"csv_text": csv, "table_name": "sales", "engine": "mysql", "replace": True})
    assert r.status_code == 200 and r.json()["rows"] == 2
    d = run(user_client, "SELECT amount FROM sales ORDER BY order_id", "blank", "writable")
    assert d["result_sets"][0]["rows"] == [["1200.50"], [None]]
    assert user_client.post("/api/csv/import", json={"csv_text": csv, "table_name": "sales", "engine": "mysql"}).status_code == 422
