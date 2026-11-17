"""Phase 3: SQLite engine, dialect comparison, plans/index lab, ER designer, CSV import, challenges,
mock interview, leaderboard, community discussion."""
import pytest

from app.content.exercises import ALL as EXERCISES
from app.content.interview import QUESTIONS
from tests.integration.conftest import make_client, register

pytestmark = pytest.mark.integration
SOLUTIONS = {e.code: e.solution for e in EXERCISES + QUESTIONS}


def run(c, sql, db="ecommerce", engine="sqlite", mode="readonly"):
    r = c.post("/api/playground/execute", json={"db_key": db, "engine": engine, "mode": mode, "sql": sql})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ SQLite engine
def test_sqlite_has_the_same_data(anon):
    for db, table in (("ecommerce", "orders"), ("saas", "events"), ("hr", "salaries")):
        pg = run(anon, f"SELECT COUNT(*) FROM {table}", db, "postgresql")["result_sets"][0]["rows"][0][0]
        sq = run(anon, f"SELECT COUNT(*) FROM {table}", db)["result_sets"][0]["rows"][0][0]
        assert pg == sq > 0


@pytest.mark.parametrize("sql,needle", [
    ("DELETE FROM customers", "Read-only"),
    ("ATTACH DATABASE '/etc/passwd' AS x", "ATTACH"),
    ("PRAGMA writable_schema = 1", "PRAGMA"),
    ("SELECT load_extension('/tmp/x')", "load_extension"),
])
def test_sqlite_sandbox_blocks_dangerous_operations(anon, sql, needle):
    d = run(anon, sql)
    assert not d["ok"] and d["error"]["kind"] == "permission" and needle in d["error"]["message"]


def test_sqlite_timeout_and_row_cap(anon):
    d = run(anon, "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT count(*) FROM r")
    assert d["error"]["kind"] == "timeout"
    d = run(anon, "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT n FROM r")
    assert d["ok"] and d["result_sets"][0]["truncated"] and d["result_sets"][0]["row_count"] == 1000


def test_sqlite_writable_isolated_and_resettable(user_client):
    other = make_client()
    register(other)
    d = run(user_client, "DELETE FROM salaries; SELECT COUNT(*) FROM salaries", "hr", mode="writable")
    assert d["result_sets"][-1]["rows"] == [[0]]
    assert run(other, "SELECT COUNT(*) FROM salaries", "hr", mode="writable")["result_sets"][0]["rows"][0][0] > 0
    assert run(user_client, "SELECT COUNT(*) FROM salaries", "hr")["result_sets"][0]["rows"][0][0] > 0
    assert user_client.post("/api/playground/reset", json={"db_key": "hr", "engine": "sqlite"}).status_code == 200
    assert run(user_client, "SELECT COUNT(*) FROM salaries", "hr", mode="writable")["result_sets"][0]["rows"][0][0] > 0


def test_sqlite_schema_and_history(user_client):
    d = user_client.get("/api/databases/hr?engine=sqlite").json()
    emp = next(t for t in d["tables"] if t["name"] == "employees")
    assert d["engine"] == "sqlite" and any(c["fk"] == "employees.id" for c in emp["columns"])
    run(user_client, "SELECT 1 AS x")
    assert user_client.get("/api/playground/history").json()[0]["engine"] == "sqlite"
    assert user_client.get("/api/databases/hr?engine=oracle").status_code == 422


# ------------------------------------------------------------------ dialects
def test_dialect_comparison(anon):
    same = anon.post("/api/dialects/compare", json={"sql": "SELECT city, COUNT(*) AS n FROM customers GROUP BY city ORDER BY n DESC, city"}).json()
    assert same["comparison"]["same"] is True
    diff = anon.post("/api/dialects/compare", json={"sql": "SELECT DATE_TRUNC('month', order_date)::date AS m FROM orders LIMIT 1"}).json()
    assert diff["postgresql"]["ok"] and not diff["sqlite"]["ok"] and diff["comparison"]["same"] is False
    assert {"date_trunc", "cast_op", "limit"} <= {f["key"] for f in diff["features"]}
    ref = anon.get("/api/dialects/reference").json()
    assert ref["executable"] == ["postgresql", "sqlite"] and len(ref["features"]) >= 20


# ------------------------------------------------------------------ plans & index lab
def test_explain_and_analyze_never_persist(user_client):
    d = user_client.post("/api/plans/explain", json={"sql": "SELECT * FROM orders WHERE customer_id = 5", "analyze": True}).json()
    assert d["ok"] and d["plan"]["analyzed"] and d["plan"]["execution_ms"] is not None
    w = user_client.post("/api/plans/explain", json={"sql": "DELETE FROM payments", "analyze": True, "mode": "writable"}).json()
    assert w["ok"]
    assert run(user_client, "SELECT COUNT(*) FROM payments", engine="postgresql", mode="writable")["result_sets"][0]["rows"] == [[946]]
    sq = user_client.post("/api/plans/explain", json={"sql": "SELECT * FROM orders WHERE customer_id = 5", "engine": "sqlite"}).json()
    assert sq["ok"] and "idx_orders_customer" in str(sq["plan"])
    assert user_client.post("/api/plans/explain", json={"sql": "SELECT 1; SELECT 2"}).status_code == 422


def test_index_lab(user_client, anon):
    body = {"db_key": "saas", "sql": "SELECT * FROM events WHERE properties->>'device' = 'ios' AND occurred_at >= '2025-12-01'",
            "index_sql": "CREATE INDEX ON events ((properties->>'device'), occurred_at)"}
    assert anon.post("/api/plans/index-lab", json=body).status_code == 401
    d = user_client.post("/api/plans/index-lab", json=body).json()
    assert d["ok"] and d["new_indexes_used"] and d["summary_before"]["seq_scans"] == ["events"]
    assert user_client.post("/api/plans/index-lab", json=body | {"index_sql": "DROP TABLE events"}).status_code == 422
    # nothing persisted in the shared database
    assert "events_expr" not in str(anon.post("/api/plans/explain", json={"db_key": "saas", "sql": body["sql"]}).json())


# ------------------------------------------------------------------ ER designer & CSV
DESIGN = {"tables": [
    {"name": "authors", "columns": [{"name": "id", "type": "integer", "pk": True, "identity": True},
                                    {"name": "name", "type": "varchar(100)", "not_null": True}]},
    {"name": "books", "columns": [{"name": "id", "type": "integer", "pk": True, "identity": True},
                                  {"name": "author_id", "type": "integer", "not_null": True},
                                  {"name": "price", "type": "numeric(10,2)", "default": "0"}]}],
    "relations": [{"from_table": "books", "from_column": "author_id", "to_table": "authors", "to_column": "id", "on_delete": "cascade"}]}


def test_design_ddl_validation(anon):
    d = anon.post("/api/designs/ddl", json=DESIGN).json()
    assert "GENERATED ALWAYS AS IDENTITY" in d["ddl"]["postgresql"] and "AUTOINCREMENT" in d["ddl"]["sqlite"]
    assert "ON DELETE CASCADE" in d["ddl"]["mysql"] and "erDiagram" in d["mermaid"]
    bad = anon.post("/api/designs/ddl", json={"tables": [{"name": "t1); DROP TABLE x;--", "columns": [{"name": "a", "type": "text"}]}]}).json()
    assert bad["ddl"] is None and any("ไม่ถูกต้อง" in i["message"] for i in bad["issues"])
    bad_fk = {"tables": DESIGN["tables"], "relations": [{"from_table": "books", "from_column": "price", "to_table": "authors", "to_column": "name"}]}
    assert any("PRIMARY KEY หรือ UNIQUE" in i["message"] for i in anon.post("/api/designs/ddl", json=bad_fk).json()["issues"])
    rev = anon.get("/api/designs/from-db/hr").json()
    assert {"employees", "departments"} <= {t["name"] for t in rev["tables"]} and rev["relations"]


@pytest.mark.parametrize("engine", ["postgresql", "sqlite"])
def test_design_apply_and_ownership(user_client, engine):
    did = user_client.post("/api/designs", json={"name": "Library", "design": DESIGN}).json()["id"]
    a = user_client.post(f"/api/designs/{did}/apply", json={"engine": engine}).json()
    assert a["ok"] and set(a["tables"]) == {"authors", "books"}
    d = run(user_client, "INSERT INTO authors (name) VALUES ('A'); INSERT INTO books (author_id) VALUES (1); SELECT COUNT(*) FROM books",
            "blank", engine, "writable")
    assert d["ok"] and d["result_sets"][-1]["rows"] == [[1]]
    fk = run(user_client, "INSERT INTO books (author_id) VALUES (999)", "blank", engine, "writable")
    assert not fk["ok"]  # foreign key enforced on both engines
    intruder = make_client()
    register(intruder)
    assert intruder.get(f"/api/designs/{did}").status_code == 404


CSV = "Order ID,Customer Name,Amount,Paid,Order Date\n1,Somchai,1200.50,true,2025-01-03\n2,Pim,,false,2025-01-04\n3,Krit,99,yes,2025-02-01\n"


@pytest.mark.parametrize("engine", ["postgresql", "sqlite"])
def test_csv_import(user_client, engine):
    p = user_client.post("/api/csv/preview", json={"csv_text": CSV}).json()
    assert [(c["name"], c["type"]) for c in p["columns"]] == [("order_id", "integer"), ("customer_name", "text"),
                                                             ("amount", "numeric"), ("paid", "boolean"), ("order_date", "date")]
    r = user_client.post("/api/csv/import", json={"csv_text": CSV, "table_name": "sales", "engine": engine, "replace": True})
    assert r.status_code == 200 and r.json()["rows"] == 3
    d = run(user_client, "SELECT COUNT(*) FROM sales WHERE amount IS NULL", "blank", engine, "writable")
    assert d["result_sets"][0]["rows"] == [[1]]
    assert user_client.post("/api/csv/import", json={"csv_text": CSV, "table_name": "sales", "engine": engine}).status_code == 422
    assert user_client.post("/api/csv/import", json={"csv_text": CSV, "table_name": "bad name"}).status_code == 422
    bad = user_client.post("/api/csv/import", json={"csv_text": CSV, "table_name": "s2", "engine": engine, "replace": True,
                                                    "columns": [{"name": "a", "type": "integer"}] * 2})
    assert bad.status_code == 422


def test_csv_requires_login(anon):
    assert anon.post("/api/csv/preview", json={"csv_text": CSV}).status_code == 401


# ------------------------------------------------------------------ challenges, interview, leaderboard
def test_timed_challenge_flow(user_client):
    s = user_client.post("/api/challenges", json={"kind": "timed", "count": 3, "minutes": 10, "difficulty": "easy"}).json()
    assert s["status"] == "active" and len(s["items"]) == 3 and 590 <= s["remaining_seconds"] <= 600
    assert "solution" not in str(s).lower()
    assert user_client.post(f"/api/challenges/{s['id']}/items/0/hint").json()["hints_used"] == 1
    assert user_client.post(f"/api/challenges/{s['id']}/items/0/submit", json={"sql": "SELECT 1"}).json()["correct"] is False
    for it in s["items"]:
        r = user_client.post(f"/api/challenges/{s['id']}/items/{it['position']}/submit", json={"sql": SOLUTIONS[it["code"]]}).json()
        assert r["correct"]
    assert r["session_status"] == "finished" and "beat_the_clock" in r["new_achievements"]
    assert user_client.post(f"/api/challenges/{s['id']}/items/0/submit", json={"sql": "SELECT 1"}).status_code == 409
    d = user_client.get(f"/api/challenges/{s['id']}").json()
    first = d["report"]["items"][0]
    assert first["points"] < 15 and first["hints_used"] == 1  # hint + extra attempt penalties applied
    other = make_client()
    register(other)
    assert other.get(f"/api/challenges/{s['id']}").status_code == 404


def test_challenge_deadline_enforced(user_client):
    from datetime import UTC, datetime, timedelta

    from app.db import SessionLocal
    from app.models import ChallengeSession
    s = user_client.post("/api/challenges", json={"kind": "random"}).json()
    with SessionLocal() as db:
        cs = db.get(ChallengeSession, s["id"])
        cs.started_at = datetime.now(UTC) - timedelta(minutes=20)
        cs.deadline_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    code = s["items"][0]["code"]
    r = user_client.post(f"/api/challenges/{s['id']}/items/0/submit", json={"sql": SOLUTIONS[code]})
    assert r.status_code == 409 and "หมดเวลา" in r.json()["detail"]
    assert user_client.get(f"/api/challenges/{s['id']}").json()["status"] == "expired"


def test_solution_locked_during_active_challenge(user_client, anon):
    s = user_client.post("/api/challenges", json={"kind": "random"}).json()
    code = s["items"][0]["code"]
    r = user_client.get(f"/api/exercises/{code}/solution")
    assert r.status_code == 409
    sub = user_client.post(f"/api/exercises/{code}/submit", json={"sql": "SELECT 1"}).json()
    assert sub["solution_sql"] is None and sub["explanation_md"] is None
    user_client.post(f"/api/challenges/{s['id']}/finish")
    assert user_client.get(f"/api/exercises/{code}/solution").status_code == 200


def test_active_session_limit(user_client):
    for _ in range(3):
        assert user_client.post("/api/challenges", json={"kind": "random"}).status_code == 201
    assert user_client.post("/api/challenges", json={"kind": "random"}).status_code == 409


def test_mock_interview_rubric(user_client):
    s = user_client.post("/api/challenges", json={"kind": "interview", "count": 2}).json()
    assert all(i["code"].startswith("IV-") for i in s["items"]) and s["config"]["minutes"] == 45
    approach = "เริ่มจากหา grain ของผลลัพธ์ แล้วเลือก join/aggregate ให้เหมาะ ตรวจ NULL และค่าซ้ำก่อนส่งคำตอบ"
    for it in s["items"]:
        r = user_client.post(f"/api/challenges/{s['id']}/items/{it['position']}/submit",
                             json={"sql": SOLUTIONS[it["code"]], "approach": approach}).json()
        assert r["correct"]
    d = user_client.get(f"/api/challenges/{s['id']}").json()
    rub = d["report"]["rubric"]
    assert d["status"] == "finished" and rub["passed"] and rub["overall"] >= 70 and len(rub["criteria"]) == 4
    assert "interview_ready" in r["new_achievements"]
    # interview questions are not in the practice list
    assert not [e for e in user_client.get("/api/exercises").json()["items"] if e["code"].startswith("IV-")]


def test_leaderboard_and_opt_out(user_client):
    user_client.post("/api/exercises/EX-E001/submit", json={"sql": "SELECT 'Hello, SQL!' AS greeting"})
    lb = user_client.get("/api/leaderboard?board=points&period=week").json()
    assert lb["me"] and lb["me"]["score"] >= 10 and lb["entries"]
    assert "@" not in str(lb["entries"])  # display names only, never e-mail addresses
    assert user_client.patch("/api/me/settings", json={"show_on_leaderboard": False}).json() == {"show_on_leaderboard": False}
    lb = user_client.get("/api/leaderboard?board=points&period=week").json()
    assert lb["me"] is None and lb["me_hidden"] and all(e["user_id"] != user_client.user["id"] for e in lb["entries"])


# ------------------------------------------------------------------ community
def test_discussion_spoilers_votes_and_ownership(user_client):
    other = make_client()
    register(other)
    q = user_client.post("/api/discussions", json={"target_type": "exercise", "target_key": "ex-m009", "body": "ทำไมหมวดว่างได้ 1"}).json()
    sp = user_client.post("/api/discussions", json={"target_type": "exercise", "target_key": "EX-M009",
                                                     "body": "คำตอบของผม\n```sql\nSELECT 1\n```"}).json()
    assert sp["auto_spoiler"]
    assert other.post("/api/discussions", json={"target_type": "exercise", "target_key": "EX-M009", "body": "ใช้ COUNT(p.id)",
                                                "parent_id": q["id"]}).status_code == 201
    assert other.post(f"/api/discussions/{q['id']}/vote").json()["votes"] == 1
    assert user_client.post(f"/api/discussions/{q['id']}/vote").status_code == 409
    d = other.get("/api/discussions?target_type=exercise&target_key=EX-M009").json()
    locked = next(t for t in d["threads"] if t["id"] == sp["id"])
    assert locked["body"] is None and locked["spoiler_locked"]
    assert next(t for t in d["threads"] if t["id"] == q["id"])["replies"][0]["body"] == "ใช้ COUNT(p.id)"
    other.post("/api/exercises/EX-M009/submit", json={"sql": SOLUTIONS["EX-M009"]})
    d = other.get("/api/discussions?target_type=exercise&target_key=EX-M009").json()
    assert next(t for t in d["threads"] if t["id"] == sp["id"])["body"].startswith("คำตอบ")
    assert other.delete(f"/api/discussions/{q['id']}").status_code == 404
    assert other.get("/api/admin/reports").status_code == 403
    assert user_client.delete(f"/api/discussions/{q['id']}").status_code == 204


def test_moderation(user_client):
    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import User
    admin = make_client()
    u = register(admin)
    with SessionLocal() as db:
        db.execute(update(User).where(User.id == u["id"]).values(role="admin"))
        db.commit()
    p = user_client.post("/api/discussions", json={"target_type": "lesson", "target_key": "select", "body": "spam spam spam"}).json()
    assert admin.post(f"/api/discussions/{p['id']}/report", json={"reason": "spam"}).status_code == 201
    rep = next(r for r in admin.get("/api/admin/reports").json() if r["post"]["id"] == p["id"])
    assert admin.post(f"/api/admin/posts/{p['id']}/hide", json={"hidden": True}).status_code == 200
    assert all(r["id"] != rep["id"] for r in admin.get("/api/admin/reports").json())
    viewer = make_client()
    t = next(t for t in viewer.get("/api/discussions?target_type=lesson&target_key=select").json()["threads"] if t["id"] == p["id"])
    assert t["is_hidden"] and t["body"] is None
