"""Phase 2: projects, SQL Learning Assistant (rules + pluggable AI), admin panel."""
import json

import pytest

from app.services.assistant import llm
from app.services.assistant.llm import AssistantUnavailable, LLMResult
from tests.integration.conftest import make_client, register

pytestmark = pytest.mark.integration


class FakeProvider:
    """Stands in for an LLM: records prompts so tests can assert on context and policy."""
    name = "fake"
    model = "fake-model"

    def __init__(self, reply="ok", data=None, fail=False):
        self.reply, self.data, self.fail, self.calls = reply, data, fail, []

    def available(self):
        return True

    def complete(self, system, messages, *, json_schema=None, effort="low", max_tokens=4000):
        self.calls.append({"system": system, "messages": messages, "schema": json_schema})
        if self.fail:
            raise AssistantUnavailable("down")
        data = self.data.pop(0) if isinstance(self.data, list) else self.data
        return LLMResult(text=json.dumps(data) if json_schema else self.reply, data=data, input_tokens=10, output_tokens=5)


@pytest.fixture
def fake_ai():
    p = FakeProvider(reply="**AI says hi**")
    llm.set_provider(p)
    yield p
    llm.set_provider(llm.NullProvider())


@pytest.fixture(autouse=True)
def _no_ai_by_default():
    llm.set_provider(llm.NullProvider())
    yield


def analyze(c, **body):
    return c.post("/api/assistant/analyze", json={"db_key": "ecommerce", **body})


# ------------------------------------------------------------------ projects
def test_projects_list_and_detail(anon):
    ps = anon.get("/api/projects").json()
    assert len(ps) == 6 and sum(p["tasks"] for p in ps) == 25
    d = anon.get("/api/projects/saas-metrics").json()
    assert d["sample_db"] == "saas" and d["brief_md"] and len(d["tasks"]) == 5
    assert anon.get("/api/projects/nope").status_code == 404
    # project tasks are not mixed into the general practice list
    codes = {e["code"] for e in anon.get("/api/exercises").json()["items"]}
    assert not any(c.startswith("PJ-") for c in codes)
    t = anon.get("/api/exercises/PJ-SAAS-5").json()
    assert t["project"]["slug"] == "saas-metrics" and t["project"]["task_no"] == 5 and t["next"] is None


def test_completing_a_project_awards_achievement(user_client):
    from app.content.projects import CUSTOMER
    for t in CUSTOMER.tasks:
        r = user_client.post(f"/api/exercises/{t.code}/submit", json={"sql": t.solution}).json()
        assert r["correct"], (t.code, r["message"])
    assert "real_world_analyst" in r["new_achievements"]
    d = user_client.get("/api/projects/customer-analysis").json()
    assert d["completed"] and d["points_earned"] == d["points_total"]
    dash = user_client.get("/api/dashboard").json()
    assert dash["projects"]["completed"] == 1 and dash["exercises"]["solved"] == 0


def test_saas_jsonb_task_accepts_equivalent_sql(user_client):
    alt = """SELECT e.properties ->> 'report_type' AS report_type, count(*) AS reports,
             round(avg(cast(e.properties ->> 'duration_ms' AS numeric))) AS avg_duration_ms
             FROM events e WHERE e.event_type = 'create_report' AND extract(year FROM e.occurred_at) = 2025 GROUP BY 1"""
    assert user_client.post("/api/exercises/PJ-SAAS-5/submit", json={"sql": alt}).json()["correct"]


# ------------------------------------------------------------------ assistant: rules (no AI needed)
def test_status_without_ai(anon):
    s = anon.get("/api/assistant/status").json()
    assert s["ai_available"] is False and "explain" in s["rule_modes"]


def test_explain_works_for_guests(anon):
    r = analyze(anon, mode="explain", sql="SELECT city, COUNT(*) FROM customers WHERE phone IS NULL GROUP BY city ORDER BY 2 DESC")
    d = r.json()
    assert r.status_code == 200 and d["source"] == "rules"
    titles = [s["title"] for s in d["sections"]]
    assert any("WHERE" in t for t in titles) and any("GROUP BY" in t for t in titles)
    assert titles.index(next(t for t in titles if "WHERE" in t)) < titles.index(next(t for t in titles if t.startswith("5. SELECT")))


def test_review_catches_classic_mistakes(anon):
    d = analyze(anon, mode="review", sql="SELECT * FROM customers c LEFT JOIN orders o ON o.customer_id = c.id "
                                         "WHERE o.status = 'paid' AND c.city = NULL AND c.id NOT IN (SELECT customer_id FROM orders) LIMIT 5").json()
    codes = {f["code"] for f in d["findings"]}
    assert {"SELECT_STAR", "LEFT_JOIN_WHERE", "EQ_NULL", "NOT_IN_SUBQUERY", "LIMIT_NO_ORDER"} <= codes


def test_explain_error_suggests_names(anon):
    d = analyze(anon, mode="explain_error", sql="SELECT nme FROM customer").json()
    assert "customers" in json.dumps(d, ensure_ascii=False)
    d = analyze(anon, mode="explain_error", sql="SELECT frist_name FROM customers").json()
    assert "first_name" in json.dumps(d, ensure_ascii=False)
    d = analyze(anon, mode="explain_error", sql="SELECT city, first_name, COUNT(*) FROM customers GROUP BY city").json()
    assert "GROUP BY" in d["sections"][0]["title"]


def test_explain_error_uses_supplied_error(anon):
    err = {"message": "division by zero", "sqlstate": "22012", "line": 1, "column": 8, "kind": "sql"}
    d = analyze(anon, mode="explain_error", sql="SELECT 1/0", error=err).json()
    assert "NULLIF" in d["sections"][0]["body_md"]


def test_optimize_reads_real_plan(anon):
    r = anon.post("/api/assistant/analyze", json={"mode": "optimize", "db_key": "saas",
                                                  "sql": "SELECT * FROM events WHERE CAST(occurred_at AS date) = '2025-03-01'"})
    d = r.json()
    assert r.status_code == 200 and d["plan"] and d["plan"][0]["node"]
    codes = {f["code"] for f in d["findings"]}
    assert "NON_SARGABLE" in codes and any(c.startswith("SEQ_SCAN_events") for c in codes)


def test_optimize_never_executes_writes(anon):
    d = analyze(anon, mode="optimize", sql="DELETE FROM customers").json()
    assert any(f["code"] == "NO_WHERE" for f in d["findings"])
    assert anon.post("/api/playground/execute", json={"db_key": "ecommerce", "mode": "readonly",
                                                     "sql": "SELECT COUNT(*) FROM customers"}).json()["result_sets"][0]["rows"] == [[150]]


def test_ai_endpoints_explain_unavailability(user_client, anon):
    assert analyze(anon, mode="explain", sql="SELECT 1", use_ai=True).status_code == 401
    r = analyze(user_client, mode="explain", sql="SELECT 1", use_ai=True)
    assert r.status_code == 503 and "อัตโนมัติ" in r.json()["detail"]
    assert user_client.post("/api/assistant/tutor", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 503


def test_recommendations(user_client):
    d = user_client.get("/api/assistant/recommendations").json()
    assert 1 <= len(d["weak_categories"]) <= 3 and d["weak_categories"][0]["next"]


# ------------------------------------------------------------------ assistant: AI layer (fake provider)
def test_ai_commentary_and_schema_context(user_client, fake_ai):
    d = analyze(user_client, mode="explain", sql="SELECT * FROM products", use_ai=True).json()
    assert d["source"] == "rules+ai" and d["ai_md"] == "**AI says hi**"
    system = fake_ai.calls[0]["system"]
    assert "products(" in system and "ระดับผู้เรียน" in system


def test_exercise_context_never_leaks_solution(user_client, fake_ai):
    analyze(user_client, mode="fix", sql="SELECT name FROM categories", exercise_code="EX-M009", use_ai=True)
    from app.content.exercises import ALL
    sol = next(e.solution for e in ALL if e.code == "EX-M009")
    blob = json.dumps(fake_ai.calls, ensure_ascii=False)
    assert "ห้ามเขียน SQL คำตอบ" in blob and sol not in blob and "COUNT(p.id)" not in blob


def test_tutor_chat(user_client, fake_ai):
    r = user_client.post("/api/assistant/tutor", json={"messages": [{"role": "user", "content": "LEFT JOIN ต่างจาก INNER JOIN ยังไง"}],
                                                        "db_key": "hr"})
    assert r.status_code == 200 and r.json()["reply_md"] == "**AI says hi**"
    assert "employees(" in fake_ai.calls[0]["system"]
    bad = user_client.post("/api/assistant/tutor", json={"messages": [{"role": "assistant", "content": "x"}]})
    assert bad.status_code == 422


def test_provider_failure_is_graceful(user_client):
    llm.set_provider(FakeProvider(fail=True))
    r = analyze(user_client, mode="review", sql="SELECT 1", use_ai=True)
    assert r.status_code == 503 and r.json()["detail"] == "down"


def test_generated_practice_validated_by_sandbox(user_client):
    bad = {"title": "t", "description_md": "d", "solution_sql": "DELETE FROM customers", "hints": ["a", "b", "c"], "order_matters": False}
    good = {"title": "ลูกค้าในภูเก็ต", "description_md": "แสดง **id** ของลูกค้าที่ city = Phuket", "order_matters": False,
            "solution_sql": "SELECT id FROM customers WHERE city = 'Phuket'", "hints": ["h1", "h2", "h3"]}
    fake = FakeProvider(data=[bad, good])
    llm.set_provider(fake)
    r = user_client.post("/api/assistant/generate", json={"db_key": "ecommerce", "topic": "WHERE"})
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["expected"]["row_count"] > 0 and "solution_sql" not in g
    assert "SELECT เดียว" in fake.calls[1]["messages"][-1]["content"]  # model was told why the first one was rejected
    wrong = user_client.post(f"/api/assistant/generated/{g['id']}/submit", json={"sql": "SELECT id FROM customers"}).json()
    assert not wrong["correct"] and wrong["solution_sql"] is None
    ok = user_client.post(f"/api/assistant/generated/{g['id']}/submit",
                          json={"sql": "SELECT c.id FROM customers c WHERE c.city IN ('Phuket')"}).json()
    assert ok["correct"]
    assert user_client.get("/api/assistant/generated").json()[0]["solved"] is True
    other = make_client()
    register(other)
    assert other.get(f"/api/assistant/generated/{g['id']}").status_code == 404


def test_generation_rejected_when_never_valid(user_client):
    bad = {"title": "t", "description_md": "d", "solution_sql": "SELECT * FROM nope", "hints": ["a", "b", "c"], "order_matters": False}
    llm.set_provider(FakeProvider(data=[bad, dict(bad)]))
    r = user_client.post("/api/assistant/generate", json={"db_key": "ecommerce", "topic": "JOIN"})
    assert r.status_code == 503 and "ตรวจ" in r.json()["detail"]


# ------------------------------------------------------------------ admin panel
@pytest.fixture
def admin_client():
    from sqlalchemy import update

    from app.db import SessionLocal
    from app.models import User
    c = make_client()
    u = register(c)
    with SessionLocal() as db:
        db.execute(update(User).where(User.id == u["id"]).values(role="admin"))
        db.commit()
    c.user = u
    return c


NEW_EX = {"code": "EX-C900", "title": "ลูกค้าในเชียงใหม่", "description_md": "แสดง **id** ของลูกค้าใน Chiang Mai",
          "difficulty": "easy", "category": "Filtering", "sample_db": "ecommerce",
          "solution_sql": "SELECT id FROM customers WHERE city = 'Chiang Mai'", "hints": ["a", "b", "c"],
          "explanation_md": "WHERE กรองแถว", "lesson_slug": "where"}


def test_admin_requires_admin_role(anon, user_client):
    assert anon.get("/api/admin/stats").status_code == 401
    assert user_client.get("/api/admin/stats").status_code == 403
    assert user_client.post("/api/admin/exercises", json=NEW_EX).status_code == 403


def test_admin_stats_and_users(admin_client, user_client):
    s = admin_client.get("/api/admin/stats").json()
    assert s["users"]["total"] >= 2 and len(s["daily"]) == 14 and s["content"]["lessons"] >= 62
    target = user_client.user["id"]
    found = admin_client.get(f"/api/admin/users?q={user_client.user['email']}").json()
    assert found["total"] == 1 and found["items"][0]["id"] == target
    assert "lessons" in admin_client.get(f"/api/admin/users/{target}").json()["progress"]
    # deactivate → that user's sessions are revoked immediately
    assert admin_client.patch(f"/api/admin/users/{target}", json={"is_active": False}).json()["is_active"] is False
    assert user_client.get("/api/auth/me").json()["user"] is None
    assert admin_client.patch(f"/api/admin/users/{target}", json={"is_active": True}).status_code == 200
    # an admin cannot demote or lock themselves out
    me = admin_client.user["id"]
    assert admin_client.patch(f"/api/admin/users/{me}", json={"role": "learner"}).status_code == 409


def test_admin_exercise_crud_validates_on_sandbox(admin_client, user_client):
    bad = admin_client.post("/api/admin/exercises", json=NEW_EX | {"solution_sql": "SELECT idd FROM customers"})
    assert bad.status_code == 422 and "idd" in bad.json()["detail"]
    dry = admin_client.post("/api/admin/exercises/validate", json=NEW_EX).json()
    assert dry["row_count"] > 0
    r = admin_client.post("/api/admin/exercises", json=NEW_EX)
    assert r.status_code == 201, r.text
    ex = r.json()
    assert ex["points"] == 10 and ex["is_custom"] and ex["expected"]["row_count"] == dry["row_count"]
    # learners see and can solve it immediately; it is linked to its lesson
    assert user_client.post("/api/exercises/EX-C900/submit",
                            json={"sql": "SELECT c.id FROM customers c WHERE c.city IN ('Chiang Mai')"}).json()["correct"]
    assert any(x["code"] == "EX-C900" for x in user_client.get("/api/lessons/where").json()["exercises"])
    assert admin_client.post("/api/admin/exercises", json=NEW_EX).status_code == 409  # duplicate code
    seeded = next(e for e in admin_client.get("/api/admin/exercises").json() if e["code"] == "EX-E001")
    assert admin_client.delete(f"/api/admin/exercises/{seeded['id']}").status_code == 409
    assert admin_client.delete(f"/api/admin/exercises/{ex['id']}").status_code == 204


def test_admin_dml_exercise_needs_check_sql(admin_client):
    body = NEW_EX | {"code": "EX-C901", "check_type": "dml", "solution_sql": "DELETE FROM payments WHERE id = 1"}
    assert admin_client.post("/api/admin/exercises/validate", json=body).status_code == 422
    ok = admin_client.post("/api/admin/exercises/validate", json=body | {"check_sql": "SELECT COUNT(*) AS n FROM payments"}).json()
    assert ok["row_count"] == 1


def test_admin_edits_survive_reseed(admin_client):
    from app.db import SessionLocal
    from app.seed import seed
    lesson = next(l for c in admin_client.get("/api/admin/courses").json() for l in c["lessons"] if l["slug"] == "distinct")
    full = admin_client.get(f"/api/admin/lessons/{lesson['id']}").json()
    body = {k: full[k] for k in ("course_slug", "slug", "title", "summary", "objectives", "content_md", "related_slugs", "sample_db")}
    body["examples"] = [{k: e[k] for k in ("title", "sql", "explain", "db", "writable")} for e in full["examples"]]
    body["common_mistakes"] = full["common_mistakes"]
    body["title"] = "DISTINCT — แก้ไขโดยแอดมิน"
    body["examples"][0]["sql"] = "SELECT DISTINCT country FROM customers ORDER BY country"
    r = admin_client.put(f"/api/admin/lessons/{lesson['id']}", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["examples"][0]["result"]["row_count"] >= 2  # result re-executed on the sandbox
    with SessionLocal() as db:
        seed(db)
    assert admin_client.get("/api/lessons/distinct").json()["title"] == "DISTINCT — แก้ไขโดยแอดมิน"
    # revert hands it back to content-as-code
    assert admin_client.post(f"/api/admin/lessons/{lesson['id']}/revert").status_code == 200
    with SessionLocal() as db:
        seed(db)
    assert admin_client.get("/api/lessons/distinct").json()["title"].startswith("DISTINCT — ตัดค่าที่ซ้ำ")


def test_admin_lesson_example_errors_rejected(admin_client):
    body = {"course_slug": "beginner", "slug": "custom-lesson-x", "title": "Custom", "summary": "สรุปบทเรียน", "content_md": "เนื้อหา",
            "examples": [{"title": "t", "sql": "SELECT 1", "db": "nope_db"}]}
    assert admin_client.post("/api/admin/lessons", json=body).status_code == 422
    body["examples"][0]["db"] = "hr"
    r = admin_client.post("/api/admin/lessons", json=body)
    assert r.status_code == 201 and r.json()["is_custom"]
    assert admin_client.delete(f"/api/admin/lessons/{r.json()['id']}").status_code == 204


def test_admin_projects_achievements_databases(admin_client):
    p = admin_client.post("/api/admin/projects", json={"slug": "custom-proj", "title": "Custom", "role": "Analyst", "summary": "สรุปโปรเจกต์",
                                                        "brief_md": "สถานการณ์", "sample_db": "hr", "difficulty": "hard"})
    assert p.status_code == 201
    t = admin_client.post("/api/admin/exercises", json=NEW_EX | {"code": "PJ-CUSTOM-1", "lesson_slug": None, "project_slug": "custom-proj",
                                                                 "sample_db": "hr", "solution_sql": "SELECT COUNT(*) AS n FROM employees"})
    assert t.status_code == 201
    assert admin_client.get("/api/projects/custom-proj").json()["tasks"][0]["code"] == "PJ-CUSTOM-1"
    assert admin_client.delete(f"/api/admin/projects/{p.json()['id']}").status_code == 204
    assert admin_client.get("/api/exercises/PJ-CUSTOM-1").status_code == 404  # tasks cascade
    ach = admin_client.get("/api/admin/achievements").json()
    assert any(a["key"] == "first_query" for a in ach)
    assert admin_client.put("/api/admin/achievements/first_query", json={"title": "First Query", "description": "รัน SQL สำเร็จครั้งแรก", "icon": "play"}).status_code == 200
    dbs = admin_client.get("/api/admin/databases").json()
    assert {d["key"] for d in dbs} >= {"ecommerce", "saas"}
    r = admin_client.post("/api/admin/databases/hr/rebuild").json()
    assert r["ok"] and r["recomputed_failures"] == []
