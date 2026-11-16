# Test Report

> STEP 9 — ผลการทดสอบจริง ณ วันที่ส่งมอบ (2026-11-14) · PostgreSQL 16.15 · Python 3.13 · Node 22 · Chromium (Playwright 1.63)

## สรุป
| ชุดทดสอบ | เครื่องมือ | จำนวน | ผล |
|---|---|---|---|
| Unit (checker, splitter, validator, streak/level, serialization) | pytest | 23 | ✅ 23/23 |
| Integration (FastAPI + main DB + sandbox cluster จริง) | pytest + TestClient | 34 | ✅ 34/34 |
| Content validation (รันทุกตัวอย่าง 62 บท + ทุกเฉลย 70 โจทย์บน sandbox) | `python -m app.seed` | 132 | ✅ ผ่านทั้งหมด (~6 วินาที) |
| Type check | `tsc --noEmit` (strict) | – | ✅ 0 error |
| Production build | `next build` | 15 routes | ✅ |
| End-to-End (เบราว์เซอร์จริง) | Playwright | 9 | ✅ 9/9 (local) · ✅ 9/9 (Docker Compose stack) |
| Docker Compose | `docker compose up` | 4 services | ✅ healthy ทั้งหมด; ตรวจ network isolation แล้ว |

Backend tests รันซ้ำ 3 รอบติดกันเพื่อตรวจ flakiness: 57/57 ทุกรอบ

## Security checks ที่ทดสอบอัตโนมัติ (ผลลัพธ์จาก PostgreSQL จริง ไม่ใช่การจำลอง)
| SEC | Test | ผล |
|---|---|---|
| SEC-2 | `DELETE/DROP/CREATE/UPDATE` ในโหมด read-only → ถูกปฏิเสธ, จำนวนแถวไม่เปลี่ยน | ✅ |
| SEC-2 | `SET default_transaction_read_only = off; COMMIT; DELETE ...` → ยังถูกปฏิเสธด้วย privilege | ✅ |
| SEC-8 | `pg_read_file`, `COPY ... TO PROGRAM`, `CREATE EXTENSION dblink`, `SELECT FROM pg_authid` → ปฏิเสธ | ✅ |
| SEC-3 | `SET statement_timeout = 0; SELECT pg_sleep(30)` → ถูกยกเลิกโดย watchdog < 9s | ✅ |
| SEC-5 | `generate_series(1, 5000000)` → ตัดที่ 1,000 แถว (streaming, ไม่ buffer ทั้งหมด) | ✅ |
| SEC-7 | ผู้ใช้ A ลบข้อมูลใน writable sandbox → ผู้ใช้ B และ read-only DB ไม่กระทบ | ✅ |
| SEC-7 | `ALTER ROLE CURRENT_USER SUPERUSER`, `CREATE DATABASE` → ปฏิเสธ | ✅ |
| SEC-7 | ผู้ใช้อื่นแก้/ลบ saved query ที่ไม่ใช่ของตัวเอง → 404 | ✅ |
| SEC-6 | `db_key` = `postgres` → 404, `../etc` → 422; preview ตาราง `pg_authid` → 404 | ✅ |
| SEC-11 | login ผิดเกิน 10 ครั้ง/นาที → 429 | ✅ |
| SEC-1/8 | (Docker) sandbox container ออก internet ไม่ได้; frontend container เชื่อม sandbox-db ไม่ได้ | ✅ |

## Answer-checking checks
- คำตอบที่เขียนต่างจากเฉลย (correlated subquery แทน LEFT JOIN + GROUP BY) → **Correct**
- `COUNT(*)` แทน `COUNT(p.id)` → Incorrect `VALUE_MISMATCH` พร้อมแถว `["Toys", 0]` ที่หายไป
- ลำดับผิดในโจทย์ที่ตรวจลำดับ → `ORDER_MISMATCH`
- โจทย์ DML ตรวจบนสำเนาใหม่ และไม่เปลี่ยน writable sandbox ของผู้เรียน
- คะแนนให้ครั้งแรกที่ทำถูกเท่านั้น; Dashboard อัปเดต accuracy/streak/level/กราฟทันที

## Bugs ที่พบระหว่างทดสอบและแก้แล้ว
| # | พบจาก | ปัญหา | การแก้ |
|---|---|---|---|
| 1 | manual sandbox test | `cursor.stream()` error กับคำสั่งที่ไม่คืนแถว (`CREATE`, `SET`) | แยก command statements ใช้ `execute()`; ที่เหลือ stream |
| 2 | validator test | ตำแหน่ง error เพี้ยนเมื่อมีภาษาไทย (คิดว่าเป็น byte offset) | pglast คืน character index อยู่แล้ว — ตัดการแปลงออก + เพิ่ม unit test |
| 3 | browser walkthrough | Autocomplete เปิดทุกครั้งที่กด space ทำให้กด Enter แล้วรับ suggestion แทนขึ้นบรรทัดใหม่ | เหลือ trigger แค่ `.` และ `acceptSuggestionOnEnter: "smart"` |
| 4 | E2E | race: โหลด schema + run พร้อมกันครั้งแรก → `CREATE DATABASE` ซ้อน → 500 | PostgreSQL advisory lock (ข้าม process/worker) รอบการสร้าง/รีเซ็ต DB |
| 5 | regression test ของ #4 | race เดียวกันกับ `CREATE ROLE` | advisory lock รอบการสร้าง role |
| 6 | regression test ของ #4 | request พร้อมกันเกิน `CONNECTION LIMIT` ของ role ได้ 500 | retry สั้น ๆ เมื่อ slot เต็ม, เพิ่ม limit เป็น 5, map เป็น 429 พร้อมข้อความ |

หมายเหตุ: Docker Compose stack ถูก build และทดสอบ E2E ก่อนแก้ข้อ 6; ข้อ 6 ทดสอบแล้วบน local stack (unit + integration + E2E ผ่านทั้งหมด)

## รายละเอียดผลทดสอบ

### Backend (pytest -v)
- integration/test_api.py::test_register_login_logout_flow ✅
- integration/test_api.py::test_register_validation_and_duplicate ✅
- integration/test_api.py::test_protected_endpoints_require_login ✅
- integration/test_api.py::test_auth_rate_limited ✅
- integration/test_api.py::test_readonly_select_works ✅
- integration/test_api.py::test_readonly_mode_rejects_writes[DELETE FROM customers] ✅
- integration/test_api.py::test_readonly_mode_rejects_writes[DROP TABLE orders] ✅
- integration/test_api.py::test_readonly_mode_rejects_writes[CREATE TABLE x (id int)] ✅
- integration/test_api.py::test_readonly_mode_rejects_writes[UPDATE products SET price = 0] ✅
- integration/test_api.py::test_readonly_mode_rejects_writes[SET default_transaction_read_only = off; COMMIT; DELETE FROM customers] ✅
- integration/test_api.py::test_os_and_privileged_access_denied[SELECT pg_read_file('/etc/passwd')] ✅
- integration/test_api.py::test_os_and_privileged_access_denied[COPY customers TO PROGRAM 'id'] ✅
- integration/test_api.py::test_os_and_privileged_access_denied[CREATE EXTENSION dblink] ✅
- integration/test_api.py::test_os_and_privileged_access_denied[SELECT * FROM pg_authid] ✅
- integration/test_api.py::test_timeout_enforced_even_if_user_disables_it ✅
- integration/test_api.py::test_row_cap ✅
- integration/test_api.py::test_error_position_reported ✅
- integration/test_api.py::test_writable_requires_login ✅
- integration/test_api.py::test_writable_sandboxes_are_isolated_and_resettable ✅
- integration/test_api.py::test_transactions_in_writable_mode ✅
- integration/test_api.py::test_unknown_database_rejected ✅
- integration/test_api.py::test_equivalent_sql_is_accepted ✅
- integration/test_api.py::test_wrong_answer_explained ✅
- integration/test_api.py::test_sql_error_submission ✅
- integration/test_api.py::test_order_sensitive_exercise ✅
- integration/test_api.py::test_dml_exercise_checked_on_fresh_copy ✅
- integration/test_api.py::test_exercise_list_and_detail ✅
- integration/test_api.py::test_courses_and_lessons ✅
- integration/test_api.py::test_progress_updates_dashboard ✅
- integration/test_api.py::test_bookmarks_notes_and_ownership ✅
- integration/test_api.py::test_history_recorded ✅
- integration/test_api.py::test_validate_endpoint ✅
- integration/test_api.py::test_databases_and_er ✅
- integration/test_api.py::test_concurrent_first_use_of_writable_db ✅
- unit/test_checker.py::test_identical_results_are_correct ✅
- unit/test_checker.py::test_row_order_ignored_when_not_required ✅
- unit/test_checker.py::test_row_order_enforced_when_required ✅
- unit/test_checker.py::test_column_name_case_insensitive_but_must_match ✅
- unit/test_checker.py::test_column_names_can_be_ignored ✅
- unit/test_checker.py::test_column_count_mismatch ✅
- unit/test_checker.py::test_row_count_mismatch ✅
- unit/test_checker.py::test_duplicates_matter_multiset ✅
- unit/test_checker.py::test_null_is_not_zero_or_empty ✅
- unit/test_checker.py::test_numeric_tolerance_and_types ✅
- unit/test_checker.py::test_text_vs_number_is_a_type_mismatch ✅
- unit/test_checker.py::test_no_result_set ✅
- unit/test_checker.py::test_truncated_result_rejected ✅
- unit/test_checker.py::test_mismatch_details_show_samples ✅
- unit/test_sql_tools.py::test_split_keeps_offsets_and_handles_quotes_comments_dollar ✅
- unit/test_sql_tools.py::test_split_ignores_empty ✅
- unit/test_sql_tools.py::test_offset_to_line_col ✅
- unit/test_sql_tools.py::test_validator_reports_line_and_column_with_thai_text ✅
- unit/test_sql_tools.py::test_validator_accepts_valid_multi_statement ✅
- unit/test_sql_tools.py::test_command_detection ✅
- unit/test_sql_tools.py::test_to_jsonable ✅
- unit/test_sql_tools.py::test_streak ✅
- unit/test_sql_tools.py::test_levels ✅

### E2E (Playwright)
- ✅ new learner sees a zeroed dashboard (no fake numbers)
- ✅ guest can run SQL in the playground (read-only) and writes are refused
- ✅ SQL error shows line and column
- ✅ lesson → Try it opens the playground with the example
- ✅ practice: hints, incorrect then correct submission updates progress
- ✅ writable sandbox: modify then reset
- ✅ lesson completion is reflected in the course table of contents
- ✅ database page renders the ER diagram
- ✅ mobile layout uses a drawer menu

## สิ่งที่ยังไม่ได้ทดสอบ / ข้อจำกัดที่ทราบ
- **Load test** ยังไม่ได้ทำ — ตัวเลข NFR-1 (p95 < 1s) วัดได้เพียงจากการใช้งานเดี่ยว (query ปกติ 5–20 ms, fresh-copy grading ~100–400 ms)
- **ความจำของ sandbox**: ผู้ใช้ใน writable sandbox ตั้ง `SET work_mem` สูงเองได้ (PostgreSQL ไม่มีวิธีห้ามระดับ role) — ป้องกันด้วย timeout + `mem_limit` ของ container; production ขนาดใหญ่ควรพิจารณา sandbox ต่อผู้ใช้/ต่อกลุ่ม
- **ขนาด writable DB**: ตรวจหลังแต่ละ execute (>200 MB → reset อัตโนมัติ) ไม่ใช่ระหว่าง statement
- Rate limiter อยู่ใน memory ต่อ process (2 workers = limit คูณ 2) — ใช้ Redis เมื่อ scale
- Cross-browser: ทดสอบเฉพาะ Chromium
- Accessibility: มี aria-label/role/keyboard navigation หลัก แต่ยังไม่ได้ audit ด้วย screen reader
