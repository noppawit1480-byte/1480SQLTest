# API Documentation

- Base path: `/api` (เบราว์เซอร์เรียกผ่าน Next.js same-origin proxy; ตรงไปที่ FastAPI ได้ที่ `http://backend:8000/api`)
- Interactive docs (Swagger UI): **`/api/docs`** · OpenAPI spec: `/api/openapi.json` (สำเนาอยู่ที่ [`docs/openapi.json`](openapi.json))
- Auth: session cookie `sqlab_session` (httpOnly, SameSite=Lax) ได้จาก register/login
- Error format: `{"detail": "ข้อความภาษาไทย"}` · validation (422): `{"detail": "...", "errors": [{"field", "message"}]}`
- Rate limit: execute/run/submit/preview 60 ครั้ง/นาที, auth 10 ครั้ง/นาที (`RATE_AUTH_PER_MIN`), reset 10 ครั้ง/นาที → `429` + header `Retry-After`

🔒 = ต้อง login · 👤 = ใช้ได้ทั้ง guest และ user (ผลลัพธ์เพิ่มข้อมูลส่วนตัวเมื่อ login)

## Auth
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password (≥8), display_name}` | `201` user · `409` อีเมลซ้ำ |
| POST | `/auth/login` | `{email, password}` | user · `401` |
| POST | `/auth/logout` | – | `204` (ลบ session ฝั่ง server) |
| GET | `/auth/me` | – | `{user: User \| null}` |

`User = {id, email, display_name, role: "learner"|"admin", created_at}`

## Playground 👤
| Method | Path | Notes |
|---|---|---|
| POST | `/playground/execute` | `{db_key, mode: "readonly"\|"writable", sql}` → `ExecutionResult` · writable 🔒 |
| POST | `/playground/validate` | `{sql}` → `{issues: [{message, line, column, end_column}]}` (libpg_query, ไม่รัน SQL) |
| POST | `/playground/reset` 🔒 | `{db_key}` → drop + clone ฐานข้อมูล writable ของผู้ใช้จาก template |
| GET / DELETE | `/playground/history` 🔒 | 50 รายการล่าสุด / ล้างทั้งหมด |
| GET / POST | `/saved-queries` 🔒 | `{title, db_key, sql}` |
| PUT / DELETE | `/saved-queries/{id}` 🔒 | `404` ถ้าไม่ใช่ของผู้ใช้ (ไม่เปิดเผยว่ามีอยู่) |

```jsonc
// ExecutionResult
{
  "ok": true, "exec_ms": 11, "statements": 2,
  "result_sets": [
    {"statement_index": 0, "command": "DELETE 9", "columns": [], "rows": [], "row_count": 0, "truncated": false},
    {"statement_index": 1, "command": "SELECT 1", "columns": [{"name": "count", "type": "int8"}], "rows": [[122]], "row_count": 1, "truncated": false}
  ],
  "error": null,            // หรือ {message, sqlstate, detail, hint, line, column, statement_index, kind: sql|timeout|limit|permission|internal}
  "notices": [],
  "new_achievements": []    // key ของ achievement ที่เพิ่งได้
}
```
- `numeric` คืนเป็น string เพื่อความแม่นยำ, `date/timestamp` เป็น ISO string, `NULL` เป็น `null`
- ผลลัพธ์ตัดที่ `MAX_RESULT_ROWS` (1000) → `truncated: true`

## Sample databases 👤
| Method | Path | Notes |
|---|---|---|
| GET | `/databases` | `[{key, name, engine, description, tables: [{name, rows}]}]` |
| GET | `/databases/{key}?mode=readonly\|writable` | `{..., tables: TableInfo[], er_mermaid}` — introspect จาก catalog จริง |
| GET | `/databases/{key}/tables/{table}/preview?mode=` | 50 แถวแรก (`ExecutionResult`) — ชื่อตารางถูกตรวจกับ catalog ก่อน |

`TableInfo = {name, comment, row_estimate, columns: [{name, type, nullable, default, is_pk, fk: "table.col"|null, comment}]}`

## Learning 👤
| Method | Path | Notes |
|---|---|---|
| GET | `/courses` | 4 หลักสูตร + `completed/percent` ของผู้ใช้ |
| GET | `/courses/{slug}` | Table of contents + สถานะรายบท |
| GET | `/lessons/{slug}` | เนื้อหา, objectives, examples (พร้อม `result` ที่รันจริงตอน seed), common_mistakes, exercises, prev/next, related, status, bookmarked, note |
| POST | `/lessons/{slug}/progress` 🔒 | `{status: "in_progress"\|"completed"}` (ไม่ downgrade บทที่จบแล้ว) |
| PUT / DELETE | `/lessons/{slug}/bookmark` 🔒 | `204` |
| PUT | `/lessons/{slug}/note` 🔒 | `{body}` (ว่าง = ลบโน้ต) |

## Practice 👤
| Method | Path | Notes |
|---|---|---|
| GET | `/exercises?difficulty=&category=` | `{categories, items: [{code, title, difficulty, category, points, sample_db, check_type, status}]}` |
| GET | `/exercises/{code}` | โจทย์, expected (10 แถวแรก + row_count), hints (3), prev/next, status, attempts |
| POST | `/exercises/{code}/run` | `{sql}` → `ExecutionResult` (ไม่บันทึกคะแนน) · โจทย์ DML ต้อง 🔒 |
| POST | `/exercises/{code}/submit` 🔒 | `{sql}` → `SubmitResult` |
| GET | `/exercises/{code}/solution` | `{solution_sql, explanation_md}` |

```jsonc
// SubmitResult
{
  "correct": false,
  "reason_code": "VALUE_MISMATCH",   // CORRECT | SQL_ERROR | NO_RESULT | COLUMN_COUNT_MISMATCH | COLUMN_NAME_MISMATCH
                                     // | ROW_COUNT_MISMATCH | VALUE_MISMATCH | ORDER_MISMATCH | TOO_MANY_ROWS
  "message": "ข้อมูลในผลลัพธ์ไม่ตรง: ...",
  "details": {"missing_rows": [["Toys", 0]], "unexpected_rows": [["Toys", 1]]},
  "points_awarded": 0,               // ให้คะแนนเฉพาะครั้งแรกที่ทำถูก
  "execution": { /* ExecutionResult */ },
  "actual": {"columns": [], "rows": []}, "expected": {"columns": [], "rows": [], "row_count": 15},
  "explanation_md": "...", "solution_sql": "...", "new_achievements": ["first_correct"]
}
```

## Me 🔒
| Method | Path | Notes |
|---|---|---|
| GET | `/dashboard` | lessons, exercises, submissions (accuracy), streak, learning_seconds, level, courses, skills, recent_exercises, current_lesson, activity (30 วัน), achievements |
| POST | `/me/heartbeat` | `{seconds: 1..60}` — เวลาเรียนจริงจากแท็บที่เปิดอยู่ |
| GET | `/me/library` | bookmarks + notes |

## Projects 👤 (Phase 2)
| Method | Path | Notes |
|---|---|---|
| GET | `/projects` | 6 โปรเจกต์ + `tasks`, `solved`, `completed` ของผู้ใช้ |
| GET | `/projects/{slug}` | `brief_md`, `deliverables`, รายการงาน (status), คะแนน |

งานในโปรเจกต์เป็น exercise ที่มี `project_id` — ส่งคำตอบผ่าน `/exercises/{code}/run|submit` เหมือนโจทย์ทั่วไป (`GET /exercises/{code}` คืน `project: {slug, title, task_no, task_count}`) และไม่ปรากฏใน `GET /exercises`

## SQL Learning Assistant (Phase 2)
| Method | Path | Notes |
|---|---|---|
| GET | `/assistant/status` | `{ai_available, provider, model}` |
| POST | `/assistant/analyze` 👤 | `{mode: explain\|review\|explain_error\|fix\|optimize, sql, db_key, error?, exercise_code?, use_ai?}` → `AssistantAnswer` · `use_ai` ต้อง 🔒 และต้องเปิด AI บนเซิร์ฟเวอร์ |
| POST | `/assistant/tutor` 🔒 | `{messages: [{role, content}], db_key?, exercise_code?}` → `{reply_md}` (AI) |
| GET | `/assistant/recommendations` 🔒 | หมวดที่อ่อน + โจทย์ที่ควรทำต่อ (rules) |
| POST | `/assistant/generate` 🔒 | `{db_key, topic, difficulty}` → โจทย์ที่ AI สร้าง (`201`) — เฉลยถูกรันบน sandbox ก่อนบันทึก |
| GET | `/assistant/generated`, `/assistant/generated/{id}` 🔒 | เฉพาะของผู้ใช้เอง (`404` ถ้าไม่ใช่) |
| POST | `/assistant/generated/{id}/run`, `/submit` 🔒 | ตรวจด้วย checker เดียวกับโจทย์หลัก (ไม่ให้คะแนน) |
| GET | `/assistant/generated/{id}/solution` 🔒 | เฉลย |

```jsonc
// AssistantAnswer
{
  "mode": "review", "source": "rules",          // "rules+ai" เมื่อ use_ai
  "summary": "พบ 2 ประเด็น: 2 ควรแก้",
  "sections": [{"title": "2. WHERE — กรองทีละแถว", "body_md": "...", "sql": "o.status = 'paid'"}],
  "findings": [{"code": "LEFT_JOIN_WHERE", "severity": "warning", "title": "...", "body_md": "...", "suggestion_sql": null}],
  "plan": [{"depth": 0, "node": "Seq Scan", "relation": "events", "rows": 216, "cost": 1085.2, "filter": "..."}],  // optimize
  "ai_md": null
}
```
- Error codes: `401` (AI ต้อง login), `429` (rate limit / เกินโควตา AI รายวัน), `503` (ยังไม่ตั้งค่า AI หรือ provider ขัดข้อง — โหมด rules ยังใช้ได้)
- Finding codes: `NO_WHERE`, `SELECT_STAR`, `LIMIT_NO_ORDER`, `BIG_OFFSET`, `DISTINCT_GROUP`, `ORDER_BY_ORDINAL`, `HAVING_NO_AGG`, `IMPLICIT_JOIN`, `LEFT_JOIN_WHERE`, `COUNT_STAR_LEFT`, `NOT_IN_SUBQUERY`, `EQ_NULL`, `LEADING_WILDCARD`, `INT_DIVISION`, `NON_SARGABLE`, `SEQ_SCAN_<table>`, `BIG_SORT`, `BIG_NESTED_LOOP`

## Admin 🛡️ (Phase 2 — ทุก route ต้อง `role = admin`, อื่น ๆ ได้ `403`)
| Method | Path | Notes |
|---|---|---|
| GET | `/admin/stats` | ผู้ใช้, active, submissions, โจทย์ที่ยากที่สุด, กิจกรรม 14 วัน, การใช้ assistant |
| GET | `/admin/users?q=&page=` · `/admin/users/{id}` | รายชื่อ + progress ของผู้ใช้ |
| PATCH | `/admin/users/{id}` | `{role?, is_active?}` — ระงับแล้ว revoke session ทันที; แก้ตัวเองไม่ได้ (`409`) |
| GET / PUT | `/admin/courses`, `/admin/courses/{id}` | |
| GET / POST / PUT / DELETE | `/admin/lessons[/{id}]` | ตัวอย่างถูกรันจริงตอนบันทึก; ลบได้เฉพาะบทที่สร้างเอง |
| POST | `/admin/lessons/{id}/revert` | คืนบทเรียนหลักให้ seed (content-as-code) |
| GET / POST / PUT / DELETE | `/admin/exercises[/{id}]` | เฉลยต้องรันผ่าน (`422` พร้อมเหตุผล) — expected คำนวณจากการรัน |
| POST | `/admin/exercises/validate` | dry-run เฉลย |
| GET / POST / PUT / DELETE | `/admin/projects[/{id}]` | ลบโปรเจกต์ = ลบงานในโปรเจกต์ (cascade) |
| GET / PUT | `/admin/achievements[/{key}]` | แก้ title/description/icon |
| GET / PUT | `/admin/databases[/{key}]` | |
| POST | `/admin/databases/{key}/rebuild` | สร้าง template + read-only ใหม่ แล้วคำนวณ expected ของโจทย์บน DB นั้นใหม่ |

ทุก action ถูกบันทึกใน log: `event=admin_action admin=<id> action=<...> target=<...>`

## Multiple engines (Phase 3)
`GET /engines` → `{engines: [{key, name, available, reason}]}` — engine ที่เซิร์ฟเวอร์นี้รันได้จริง (MySQL `available: false` พร้อม `reason` ถ้าไม่ได้ตั้งค่า `MYSQL_HOST`; ขอ `engine: "mysql"` ตอนนั้นได้ `503`)

Playground endpoints รับ `engine: "postgresql" | "sqlite" | "mysql"` (ค่าเริ่มต้น `postgresql`):
`POST /playground/execute`, `POST /playground/reset`, `POST /saved-queries` (บันทึก engine), `GET /databases/{key}?mode=&engine=`, `GET /databases/{key}/tables/{table}/preview?engine=` · รายการ History/Saved คืน `engine`
SQLite error `kind`: `timeout` (เกิน `QUERY_TIMEOUT_MS`), `permission` (ATTACH, load_extension, PRAGMA ที่ไม่อนุญาต, เขียนในโหมด read-only), `limit` (ฐานข้อมูลส่วนตัวเกินขนาด)
MySQL error `kind`: `timeout` (watchdog `KILL QUERY` — ทุกชนิดคำสั่ง), `permission` (เขียนในโหมด read-only, `INTO OUTFILE`/`LOAD DATA`, `mysql.*`, `SET GLOBAL`, GRANT/CREATE USER/EVENT, DB ของคนอื่น) · `sqlstate` เป็น `MY<รหัส MySQL>` เช่น `MY1064`

## Execution plan & optimization 👤 (Phase 3)
| Method | Path | Notes |
|---|---|---|
| POST | `/plans/explain` | `{sql, db_key, engine, mode, analyze}` (1 statement) → `{ok, plan: {engine, root: PlanNode, total_cost, execution_ms, …}, summary: {nodes, seq_scans, indexes_used, total_cost, execution_ms}, findings}` (ล้มเหลว: `{ok: false, error, sqlstate}`) · `analyze` ใช้ได้กับ PostgreSQL และ MySQL (`EXPLAIN ANALYZE`); บน writable คำสั่งที่แก้ข้อมูลถูก rollback · MySQL รับเฉพาะ SELECT/WITH/TABLE/INSERT/UPDATE/DELETE/REPLACE · SQLite ใช้ `EXPLAIN QUERY PLAN` · `mode: writable` ต้อง 🔒 |
| POST | `/plans/index-lab` 🔒 | `{sql, index_sql, db_key}` — `index_sql` รับเฉพาะ `CREATE INDEX` ≤ 3 คำสั่ง · รัน EXPLAIN ANALYZE ก่อน/หลังบนสำเนาฐานข้อมูลใหม่ → `{ok, before, after, summary_before, summary_after, new_indexes_used, speedup, verdict, note}` |

## SQL dialects 👤 (Phase 3)
| Method | Path | Notes |
|---|---|---|
| GET | `/dialects/reference` | 25 หัวข้อ: วิธีเขียนใน PostgreSQL / SQLite / MySQL / SQL Server + หมายเหตุ · `executable` = engine ที่รันจริงได้ |
| POST | `/dialects/compare` | `{sql, db_key}` → รันบนทุก engine ที่เปิดอยู่ (read-only) → `{engines, postgresql, sqlite, mysql?, comparison: {same, message, details, engines: {sqlite: {same, message}, mysql: {…}}}, features}` · PostgreSQL เป็นตัวอ้างอิง |

## Database design & CSV import (Phase 3)
| Method | Path | Notes |
|---|---|---|
| POST | `/designs/ddl` 👤 | `{tables, relations}` → `{issues: [{level: error\|warning, message}], mermaid, ddl: {postgresql, sqlite, mysql} \| null}` (`ddl` เป็น null ถ้ามี error) |
| GET | `/designs/from-db/{key}` 👤 | reverse-engineer sample DB เป็น design |
| GET / POST | `/designs` 🔒 | แบบของฉัน / บันทึกแบบใหม่ `{name, design}` (ต้องไม่มี error) |
| GET / PUT / DELETE | `/designs/{id}` 🔒 | เฉพาะเจ้าของ (คนอื่นได้ `404`) |
| POST | `/designs/{id}/apply` 🔒 | `{engine}` (`postgresql`/`sqlite`/`mysql`) → **ล้าง** ฐานข้อมูล `blank` ของผู้ใช้ (Writable) แล้วรัน DDL |
| POST | `/csv/preview` 🔒 | `{csv_text, delimiter: , ; \| tab, has_header}` → `{columns: [{name, type, nulls, sample}], row_count, sample}` |
| POST | `/csv/import` 🔒 | `{csv_text, delimiter, has_header, db_key: "blank", engine, table_name, columns?, replace}` → นำเข้าใน Writable sandbox · `422` พร้อมเหตุผลถ้ามีตารางอยู่แล้วและไม่ได้เลือก `replace` หรือข้อมูลแปลงตามชนิดไม่ได้ · จำกัด 5 MB / 50,000 แถว / 100 คอลัมน์ |

## Challenges, mock interview & leaderboard (Phase 3)
| Method | Path | Notes |
|---|---|---|
| POST | `/challenges` 🔒 | `{kind: timed\|random\|interview, count?, minutes?, difficulty?, category?}` → session (`items` ไม่มีเฉลย, `remaining_seconds` จาก server) · `409` ถ้ามี session ที่ยังไม่จบ ≥ 3 หรือโจทย์ตามเงื่อนไขไม่พอ |
| GET | `/challenges` 🔒 | ประวัติ 30 รายการล่าสุด |
| GET | `/challenges/{id}` 🔒 | session + `report` เมื่อจบ (มี `rubric` สำหรับ interview) · ของคนอื่นได้ `404` |
| POST | `/challenges/{id}/items/{pos}/submit` 🔒 | `{sql, approach?}` → `{correct, message, points_awarded, execution, session_status, new_achievements}` · หลัง deadline ได้ `409` |
| POST | `/challenges/{id}/items/{pos}/hint` 🔒 | เปิด hint ถัดไป (คะแนนข้อนั้น ×0.9) |
| POST | `/challenges/{id}/items/{pos}/approach` 🔒 | บันทึกคำอธิบายแนวคิด (interview) |
| POST | `/challenges/{id}/finish` 🔒 | จบ session → report |
| GET | `/leaderboard?board=points\|challenges&period=week\|all` 👤 | top 20 `{rank, display_name, score, count}` + `me`, `me_hidden` |
| PATCH | `/me/settings` 🔒 | `{show_on_leaderboard}` |

ระหว่างที่โจทย์อยู่ใน challenge ที่ยัง active ของผู้ใช้: `GET /exercises/{code}/solution` ได้ `409` และ `POST /exercises/{code}/submit` ไม่คืน `solution_sql`/`explanation_md`

## Community (Phase 3)
| Method | Path | Notes |
|---|---|---|
| GET | `/discussions?target_type=exercise\|lesson&target_key=&reveal_spoilers=` 👤 | กระทู้ (ตอบกลับ 1 ระดับ) เรียงตามโหวต · โพสต์ spoiler บนโจทย์ได้ `body: null, spoiler_locked: true` จนกว่าจะทำโจทย์ถูกหรือส่ง `reveal_spoilers=true` |
| POST | `/discussions` 🔒 | `{target_type, target_key, body, is_spoiler, parent_id?}` · โพสต์บนโจทย์ที่มี ```sql เป็น spoiler อัตโนมัติ · 10 โพสต์/นาที |
| PATCH / DELETE | `/discussions/{id}` 🔒 | เจ้าของ (DELETE: admin ได้ด้วย) |
| POST | `/discussions/{id}/vote` 🔒 | toggle · โหวตโพสต์ตัวเองไม่ได้ (`409`) |
| POST | `/discussions/{id}/report` 🔒 | `{reason}` → คิว moderation |
| GET | `/admin/reports` 🛡️ | รายงานที่ยังไม่ปิด |
| POST | `/admin/posts/{id}/hide` 🛡️ | `{hidden}` · ซ่อนแล้วปิดรายงานของโพสต์นั้น |
| POST | `/admin/reports/{id}/resolve` 🛡️ | ปิดรายงาน (ไม่ผิดกฎ) |

## Health
`GET /api/health` → `{"status": "ok"}`
