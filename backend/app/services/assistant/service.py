"""SQL Learning Assistant orchestration.

Every mode works without AI (rules.py). When an LLM provider is configured, `use_ai` adds an AI
commentary layer; the tutor chat and practice generation are AI-only.

Pedagogy rules enforced here (not left to the model alone):
  * In an exercise context the model never receives the reference solution, and is instructed to
    give hints only — so it cannot leak the answer it does not have.
  * AI-generated practice is accepted only if its solution actually runs on the sandbox; the expected
    result comes from that execution, never from the model.
"""
from __future__ import annotations

import json
from dataclasses import asdict

import pglast
from pglast import ast
from pglast.stream import RawStream
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AssistantLog, Exercise, GeneratedExercise
from app.services import progress
from app.services.assistant import rules
from app.services.assistant.llm import AssistantUnavailable, get_provider
from app.services.sandbox.postgres import get_sandbox

TUTOR_SYSTEM = """คุณคือ "SQLab Tutor" ผู้ช่วยสอน SQL บนแพลตฟอร์มเรียน SQL (ฐานข้อมูล PostgreSQL 16)
- ตอบเป็นภาษาไทย ใช้ SQL keyword และศัพท์เทคนิคเป็นภาษาอังกฤษ ตัวอย่าง SQL ใช้ syntax ของ PostgreSQL
- ปรับความลึกให้เหมาะกับระดับผู้เรียนที่ระบุในบริบท: Novice/Beginner อธิบายทีละขั้นด้วยภาษาง่าย, Advanced/Professional กระชับและลงรายละเอียดเชิงเทคนิค
- ใช้เฉพาะตารางและคอลัมน์ที่มีอยู่ใน schema ที่ให้มา ถ้าไม่แน่ใจให้บอกตรง ๆ
- ตอบเป็น Markdown สั้นกระชับ (ไม่เกิน ~250 คำ เว้นแต่ผู้เรียนขอรายละเอียด) ใส่ SQL ใน ```sql code block
- ตอบเฉพาะเรื่อง SQL, ฐานข้อมูล และการวิเคราะห์ข้อมูล ถ้าถูกถามเรื่องอื่นให้ชวนกลับมาที่การเรียน SQL อย่างสุภาพ"""

HINT_ONLY = """⚠️ ผู้เรียนกำลังทำแบบฝึกหัดที่มีการให้คะแนน: ห้ามเขียน SQL คำตอบที่สมบูรณ์หรือเกือบสมบูรณ์ของโจทย์
ให้ชี้ว่าแนวคิด/ส่วนไหนผิด แนะนำแนวทางและ keyword ที่ควรใช้ และตั้งคำถามชวนคิด (Socratic) แทนการเฉลย
ตัวอย่าง SQL ที่ยกได้ต้องเป็นตัวอย่างสั้นบนตาราง/สถานการณ์อื่นที่ไม่ใช่คำตอบของโจทย์นี้"""

GEN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description_md": {"type": "string"},
        "solution_sql": {"type": "string"},
        "hints": {"type": "array", "items": {"type": "string"}},
        "order_matters": {"type": "boolean"},
    },
    "required": ["title", "description_md", "solution_sql", "hints", "order_matters"],
    "additionalProperties": False,
}


def schema_text(db_key: str) -> str:
    from app.routers.playground import readonly_schema  # cached introspection of the read-only DB
    lines = [f"Database `{db_key}` (PostgreSQL):"]
    for t in readonly_schema(db_key):
        cols = ", ".join(f"{c['name']} {c['type'].replace('character varying', 'varchar')}"
                         f"{' PK' if c['is_pk'] else ''}{' FK->' + c['fk'] if c['fk'] else ''}" for c in t["columns"])
        lines.append(f"- {t['name']}({cols})" + (f"  -- {t['comment']}" if t["comment"] else ""))
    return "\n".join(lines)


def learner_level(db: Session, user_id: int | None) -> str:
    return progress.level_for(progress.user_points(db, user_id))["name"] if user_id else "ไม่ทราบ (ผู้ใช้ทั่วไป)"


def exercise_context(db: Session, code: str | None) -> tuple[Exercise | None, str]:
    if not code:
        return None, ""
    ex = db.scalar(select(Exercise).where(Exercise.code == code.upper()))
    if ex is None:
        return None, ""
    # NOTE: the solution is deliberately NOT included
    return ex, f"\n\nโจทย์ที่ผู้เรียนกำลังทำ ({ex.code}, {ex.difficulty}, หมวด {ex.category}): {ex.title}\n{ex.description_md}\n\n{HINT_ONLY}"


def log_use(db: Session, user_id: int | None, mode: str, provider: str, ok: bool, tin: int = 0, tout: int = 0) -> None:
    db.add(AssistantLog(user_id=user_id, mode=mode, provider=provider, ok=ok, input_tokens=tin, output_tokens=tout))


def ai_used_today(db: Session, user_id: int) -> int:
    since = func.date_trunc("day", func.now())
    return db.scalar(select(func.count()).select_from(AssistantLog).where(
        AssistantLog.user_id == user_id, AssistantLog.provider != "rules", AssistantLog.created_at >= since)) or 0


def _ai(db: Session, user_id: int | None, mode: str, system: str, messages: list[dict], **kw):
    provider = get_provider()
    try:
        res = provider.complete(system, messages, **kw)
    except AssistantUnavailable:
        log_use(db, user_id, mode, provider.name, False)
        db.commit()
        raise
    log_use(db, user_id, mode, provider.name, True, res.input_tokens, res.output_tokens)
    return res


def analyze(db: Session, *, mode: str, sql: str, db_key: str, user_id: int | None, error: dict | None = None,
            exercise_code: str | None = None, use_ai: bool = False) -> dict:
    """mode: explain | review | explain_error | fix | optimize"""
    tables = _tables(db_key)
    if mode == "explain":
        ans = rules.explain_sql(sql)
    elif mode == "review":
        ans = rules.review(sql)
    elif mode in ("explain_error", "fix"):
        if not error:
            res = get_sandbox().execute(get_sandbox().readonly_target(db_key), sql) if _is_read_only(sql) else None
            error = asdict(res.error) if res is not None and res.error else None
        if error:
            ans = rules.explain_error(sql, error, tables)
        else:
            ans = rules.review(sql)
            ans.summary = "SQL นี้รันได้โดยไม่มี error — ด้านล่างคือข้อสังเกตจากการตรวจคุณภาพ" + (f" ({ans.summary})" if ans.findings else "")
        ans.mode = mode
        if mode == "fix":
            ans.findings += [f for f in rules.review_findings(sql) if f.code not in {x.code for x in ans.findings}]
    elif mode == "optimize":
        ans = optimize(sql, db_key, tables)
    else:
        raise ValueError(mode)

    if exercise_code and mode == "fix":
        ans.sections.append(rules.Section("โหมดแบบฝึกหัด", "ผู้ช่วยจะชี้จุดที่ผิดและแนวทางแก้ แต่จะไม่เขียนคำตอบให้ — ลองใช้ Hint ของโจทย์ประกอบด้วย"))
    log_use(db, user_id, mode, "rules", True)

    if use_ai:
        ex, ex_ctx = exercise_context(db, exercise_code)
        system = TUTOR_SYSTEM + f"\n\nระดับผู้เรียน: {learner_level(db, user_id)}\n\n{schema_text(db_key)}{ex_ctx}"
        task = {
            "explain": "อธิบาย SQL นี้ทีละส่วนให้ผู้เรียนเข้าใจ เสริมจากการวิเคราะห์อัตโนมัติด้านล่าง (อย่าทวนซ้ำทั้งหมด) และบอกว่าผลลัพธ์จะออกมาเป็นอย่างไร",
            "review": "รีวิวคุณภาพ SQL นี้: ความถูกต้อง ความอ่านง่าย ประสิทธิภาพ เสริมจาก findings ด้านล่าง",
            "explain_error": "อธิบายสาเหตุของ error นี้ด้วยภาษาที่เข้าใจง่าย และวิธีตรวจสอบ/แก้ไข",
            "fix": "ช่วยแก้ SQL นี้" + (" (ให้คำใบ้เท่านั้น ตามกฎแบบฝึกหัด)" if ex else " — เสนอ SQL ที่แก้แล้วพร้อมอธิบายสิ่งที่เปลี่ยน"),
            "optimize": "แนะนำการปรับปรุงประสิทธิภาพจากแผนการทำงานและ findings ด้านล่าง เรียงตามผลกระทบ",
        }[mode]
        rule_ctx = json.dumps({"summary": ans.summary, "findings": [asdict(f) for f in ans.findings],
                               "plan": ans.plan[:15] if ans.plan else None, "error": error}, ensure_ascii=False)
        user_msg = f"{task}\n\n```sql\n{sql}\n```\n\nผลวิเคราะห์อัตโนมัติ (JSON):\n{rule_ctx}"
        res = _ai(db, user_id, mode, system, [{"role": "user", "content": user_msg}], effort="low", max_tokens=3000)
        ans.ai_md = res.text
        ans.source = "rules+ai"
    db.commit()
    return ans.to_dict()


def _is_read_only(sql: str) -> bool:
    try:
        return all(isinstance(r.stmt, (ast.SelectStmt, ast.ExplainStmt)) for r in pglast.parse_sql(sql))
    except Exception:
        return True  # a syntax error is still safe to run read-only — it fails at parse time


def _tables(db_key: str) -> list[dict]:
    from app.routers.playground import readonly_schema
    return readonly_schema(db_key)


def optimize(sql: str, db_key: str, tables: list[dict]) -> rules.AssistantAnswer:
    try:
        tree = pglast.parse_sql(sql)
    except Exception:
        return rules.explain_sql(sql)  # carries the syntax error explanation
    selects = [r for r in tree if isinstance(r.stmt, ast.SelectStmt)]
    if not selects:
        ans = rules.review(sql)
        ans.mode = "optimize"
        ans.summary = "โหมด Optimize วิเคราะห์แผนการทำงานของคำสั่ง SELECT — คำสั่งนี้ไม่มี SELECT จึงแสดงเฉพาะผลตรวจคุณภาพ"
        return ans
    stmt_sql = RawStream()(selects[0].stmt)
    sb = get_sandbox()
    res = sb.execute(sb.readonly_target(db_key), "EXPLAIN (FORMAT JSON) " + stmt_sql)  # EXPLAIN without ANALYZE: never executes
    if not res.ok or not res.last_rows or not res.last_rows.rows:
        ans = rules.explain_error(sql, asdict(res.error) if res.error else {"message": "EXPLAIN failed"}, tables)
        ans.mode = "optimize"
        return ans
    plan = res.last_rows.rows[0][0]
    if isinstance(plan, str):
        plan = json.loads(plan)
    ans = rules.optimize_from_plan(sql, plan, {t["name"]: t["row_estimate"] for t in tables})
    if len(selects) > 1:
        ans.sections.append(rules.Section("หมายเหตุ", "มีหลายคำสั่ง — วิเคราะห์แผนเฉพาะคำสั่ง SELECT แรก"))
    return ans


def tutor(db: Session, *, user_id: int, messages: list[dict], db_key: str | None, exercise_code: str | None) -> dict:
    ex, ex_ctx = exercise_context(db, exercise_code)
    system = TUTOR_SYSTEM + f"\n\nระดับผู้เรียน: {learner_level(db, user_id)}"
    if db_key:
        system += "\n\n" + schema_text(db_key)
    system += ex_ctx
    res = _ai(db, user_id, "tutor", system, messages[-12:], effort="low", max_tokens=3000)
    db.commit()
    return {"reply_md": res.text, "provider": get_provider().name}


def recommendations(db: Session, user_id: int) -> dict:
    """Rule-based 'what to practice next': weakest categories → unsolved exercises."""
    solved = progress.solved_exercise_ids(db, user_id)
    cats = db.execute(select(Exercise.category, func.count()).where(Exercise.project_id.is_(None))
                      .group_by(Exercise.category)).all()
    by_cat = progress.solved_counts_by(db, user_id, Exercise.category)
    ranked = sorted(cats, key=lambda c: (by_cat.get(c[0], 0) / c[1], c[0]))
    out = []
    order = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}
    for cat, total in ranked:
        todo = [e for e in db.scalars(select(Exercise).where(Exercise.category == cat, Exercise.project_id.is_(None)))
                if e.id not in solved]
        if not todo:
            continue
        todo.sort(key=lambda e: (order.get(e.difficulty, 9), e.position))
        out.append({"category": cat, "solved": by_cat.get(cat, 0), "total": total,
                    "next": [{"code": e.code, "title": e.title, "difficulty": e.difficulty} for e in todo[:3]]})
        if len(out) == 3:
            break
    return {"weak_categories": out}


def generate_practice(db: Session, *, user_id: int, db_key: str, topic: str, difficulty: str) -> GeneratedExercise:
    system = (TUTOR_SYSTEM + "\n\nหน้าที่: สร้างโจทย์ฝึก SQL 1 ข้อ ที่แก้ได้ด้วยคำสั่ง SELECT เดียวบน schema ที่ให้มา\n"
              "- description_md: โจทย์ภาษาไทย ระบุชื่อคอลัมน์ผลลัพธ์ที่ต้องการให้ชัด (ใช้ AS) และบอกถ้าต้องเรียงลำดับ\n"
              "- solution_sql: SELECT เดียวที่ถูกต้องบน PostgreSQL 16 ได้ผลลัพธ์ 1–200 แถว ห้ามใช้ CURRENT_DATE/NOW()/random()\n"
              "- hints: 3 ข้อ (คำใบ้เบื้องต้น → แนวทาง → keyword ที่ควรใช้)\n- order_matters: true ถ้าโจทย์กำหนดลำดับแถว\n\n"
              + schema_text(db_key))
    prompt = f"หัวข้อ: {topic}\nระดับความยาก: {difficulty}\nระดับผู้เรียน: {learner_level(db, user_id)}"
    messages = [{"role": "user", "content": prompt}]
    sb = get_sandbox()
    last_problem = ""
    for _attempt in range(2):
        res = _ai(db, user_id, "generate", system, messages, json_schema=GEN_SCHEMA, effort="medium", max_tokens=4000)
        d = res.data or {}
        sol = (d.get("solution_sql") or "").strip()
        problem = _validate_generated(sol)
        if not problem:
            run = sb.execute(sb.readonly_target(db_key), sol)
            last = run.last_rows
            if not run.ok:
                problem = f"solution_sql รันไม่ผ่าน: {run.error.message if run.error else ''}"
            elif last is None or last.row_count == 0:
                problem = "solution_sql ได้ผลลัพธ์ 0 แถว — ปรับให้ได้ผลลัพธ์อย่างน้อย 1 แถว"
            elif last.truncated or last.row_count > 200:
                problem = "solution_sql ได้ผลลัพธ์มากเกินไป (เกิน 200 แถว)"
            else:
                hints = (list(d.get("hints") or []) + ["", "", ""])[:3]
                g = GeneratedExercise(user_id=user_id, db_key=db_key, topic=topic[:80], title=d["title"][:160],
                                      description_md=d["description_md"], solution_sql=sol, hints=hints,
                                      expected={"columns": [asdict(c) for c in last.columns], "rows": last.rows},
                                      order_matters=bool(d.get("order_matters")))
                db.add(g)
                db.commit()
                return g
        last_problem = problem
        messages = messages + [{"role": "assistant", "content": json.dumps(d, ensure_ascii=False)},
                               {"role": "user", "content": f"โจทย์ก่อนหน้าใช้ไม่ได้: {problem} — สร้างใหม่ให้ถูกต้อง"}]
    db.commit()
    raise AssistantUnavailable(f"AI สร้างโจทย์ที่ผ่านการตรวจไม่ได้ ({last_problem}) กรุณาลองใหม่หรือเปลี่ยนหัวข้อ")


def _validate_generated(sql: str) -> str:
    if not sql:
        return "ไม่มี solution_sql"
    try:
        tree = pglast.parse_sql(sql)
    except Exception as e:
        return f"solution_sql มี syntax error: {e}"
    if len(tree) != 1 or not isinstance(tree[0].stmt, ast.SelectStmt):
        return "solution_sql ต้องเป็นคำสั่ง SELECT เดียว"
    return ""
