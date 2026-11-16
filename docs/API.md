# API Documentation

- Base path: `/api` (เบราว์เซอร์เรียกผ่าน Next.js same-origin proxy; ตรงไปที่ FastAPI ได้ที่ `http://backend:8000/api`)
- Interactive docs (Swagger UI): **`/api/docs`** · OpenAPI spec: `/api/openapi.json` (สำเนาอยู่ที่ [`docs/openapi.json`](openapi.json))
- Auth: session cookie `sqlab_session` (httpOnly, SameSite=Lax) ได้จาก register/login
- Error format: `{"detail": "ข้อความภาษาไทย"}` · validation (422): `{"detail": "...", "errors": [{"field", "message"}]}`
- Rate limit: execute/run/submit/preview 60 ครั้ง/นาที, auth 10 ครั้ง/นาที, reset 10 ครั้ง/นาที → `429` + header `Retry-After`

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

## Health
`GET /api/health` → `{"status": "ok"}`
