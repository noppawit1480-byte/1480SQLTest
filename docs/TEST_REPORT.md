# Test Report

> STEP 9 — ผลการทดสอบจริง ณ การส่งมอบ Phase 2 (2026-11-16) · PostgreSQL 16.15 · Python 3.13 · Node 22 · Chromium (Playwright 1.63)

## สรุป
| ชุดทดสอบ | เครื่องมือ | จำนวน | ผล |
|---|---|---|---|
| Unit (checker, splitter, validator, streak/level, serialization) | pytest | 23 | ✅ 23/23 |
| Integration — Phase 1 (API + main DB + sandbox จริง) | pytest + TestClient | 35 | ✅ 35/35 |
| Integration — Phase 2 (projects, assistant rules + AI layer ด้วย fake provider, admin RBAC/CRUD) | pytest + TestClient | 25 | ✅ 25/25 |
| Content validation (ตัวอย่าง 62 บท + เฉลย 70 โจทย์ + 25 งานโปรเจกต์ รันบน sandbox) | `python -m app.seed` | 157 | ✅ ผ่านทั้งหมด |
| Type check / production build | `tsc --noEmit` · `next build` | 20 routes | ✅ |
| End-to-End (เบราว์เซอร์จริง) | Playwright | 13 | ✅ 13/13 local · ✅ 13/13 Docker Compose |
| Docker Compose | build + up + E2E + isolation | 4 services | ✅ healthy, sandbox ออก internet ไม่ได้ |

Backend รันซ้ำ 3 รอบ: 83/83 ทุกรอบ

## Phase 2 — สิ่งที่ทดสอบ
| ด้าน | Test | ผล |
|---|---|---|
| Projects | 6 โปรเจกต์ / 25 งาน, งานโปรเจกต์ไม่ปะปนใน /practice, ทำครบทั้งโปรเจกต์ → achievement *Real-World Analyst* | ✅ |
| Projects (JSONB) | คำตอบ JSONB ที่เขียนต่างจากเฉลย (`cast(... AS numeric)`, `extract(year …)`) ได้ Correct | ✅ |
| Assistant rules | Explain เรียงตามลำดับการประมวลผลจริง · Review จับ LEFT JOIN→INNER, `= NULL`, `NOT IN`, `LIMIT` ไม่มี `ORDER BY`, `SELECT *` | ✅ |
| Assistant errors | เดาชื่อ `customer`→`customers`, `frist_name`→`first_name`, อธิบาย GROUP BY, ใช้ error ที่ส่งมา (หารศูนย์ → NULLIF) | ✅ |
| Assistant optimize | อ่าน EXPLAIN จริงบน `saas.events`: พบ Seq Scan + non-sargable · `DELETE` ไม่ถูกรัน (ข้อมูลไม่เปลี่ยน) | ✅ |
| AI layer (fake provider) | context มี schema + ระดับผู้เรียน · **โหมดแบบฝึกหัดไม่ส่งเฉลยเข้า prompt** · provider ล่ม → 503 อย่างสุภาพ · ไม่มี key → 503 พร้อมข้อความ, guest ใช้ AI → 401 | ✅ |
| Generate practice | AI ส่ง `DELETE` → ถูกปฏิเสธ แล้วให้ AI แก้พร้อมเหตุผล · expected มาจากการรันจริง · ตรวจคำตอบด้วย checker เดิม · เจ้าของเท่านั้นที่เห็น (อื่น → 404) · ไม่ผ่านทั้ง 2 รอบ → 503 | ✅ |
| Admin RBAC | guest 401, learner 403 ทุก route | ✅ |
| Admin users | ค้นหา, ระงับบัญชี → session ถูกยกเลิกทันที, แอดมินลดสิทธิ์ตัวเองไม่ได้ (409) | ✅ |
| Admin content | เฉลยผิด → 422 พร้อมเหตุผล · dry-run · โจทย์ใหม่ผู้เรียนเห็นทันทีและผูกกับบทเรียน · โจทย์หลักลบไม่ได้ · DML ต้องมี check_sql | ✅ |
| Content governance | บทเรียนที่แอดมินแก้ **ไม่ถูก seed ทับ**; revert แล้ว seed คืนเวอร์ชันจาก repository | ✅ |
| Admin projects / DBs | ลบโปรเจกต์ → งาน cascade · rebuild `hr` + คำนวณ expected ใหม่ไม่มีข้อผิดพลาด | ✅ |

## Bugs ที่พบระหว่างพัฒนา Phase 2 และแก้แล้ว
| # | พบจาก | ปัญหา | การแก้ |
|---|---|---|---|
| 7 | seeder (โจทย์ PJ-PROD-4) | **SELECT ที่ได้ 0 แถวไม่มีหัวคอลัมน์** — psycopg ทิ้ง metadata ของผลลัพธ์ว่างในโหมด streaming (กระทบผู้เรียนใน Playground และการตรวจคำตอบด้วย) | ขอ metadata จาก server ด้วย prepare + describe (ไม่ execute ซ้ำ) + regression test |
| 8 | การออกแบบโจทย์ | PJ-PROD-4 เดิมมี expected result ว่าง (โจทย์ไม่มีคุณค่า) | ปรับเป็น *months of cover* ที่ได้ผลลัพธ์จริง 6 แถว |
| 9 | browser walkthrough | ฟอนต์โค้ดแสดง ligature (`<=` เป็น `≤`, `->>` เป็นลูกศร) ทำให้ผู้เรียนเห็นตัวอักษรไม่ตรงกับที่ต้องพิมพ์ | ปิด ligature ใน code/pre และ Monaco |
| 10 | E2E | test data ของ admin E2E ค้างในคลังโจทย์ทำให้ test อื่นที่นับจำนวนพัง | test ลบสิ่งที่สร้างเอง + assertion ไม่ผูกกับจำนวนรวม |

ปัญหาของ **สภาพแวดล้อมทดสอบ** (ไม่ใช่ของระบบ): สคริปต์ deploy ของผมคัดลอก `.next/static` ซ้อนโฟลเดอร์ และ server เก่ายังจับ port อยู่ — แก้ในสคริปต์ทดสอบแล้ว ไม่กระทบ Dockerfile ที่ส่งมอบ

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
- integration/test_api.py::test_zero_row_select_keeps_column_headers ✅
- integration/test_phase2.py::test_projects_list_and_detail ✅
- integration/test_phase2.py::test_completing_a_project_awards_achievement ✅
- integration/test_phase2.py::test_saas_jsonb_task_accepts_equivalent_sql ✅
- integration/test_phase2.py::test_status_without_ai ✅
- integration/test_phase2.py::test_explain_works_for_guests ✅
- integration/test_phase2.py::test_review_catches_classic_mistakes ✅
- integration/test_phase2.py::test_explain_error_suggests_names ✅
- integration/test_phase2.py::test_explain_error_uses_supplied_error ✅
- integration/test_phase2.py::test_optimize_reads_real_plan ✅
- integration/test_phase2.py::test_optimize_never_executes_writes ✅
- integration/test_phase2.py::test_ai_endpoints_explain_unavailability ✅
- integration/test_phase2.py::test_recommendations ✅
- integration/test_phase2.py::test_ai_commentary_and_schema_context ✅
- integration/test_phase2.py::test_exercise_context_never_leaks_solution ✅
- integration/test_phase2.py::test_tutor_chat ✅
- integration/test_phase2.py::test_provider_failure_is_graceful ✅
- integration/test_phase2.py::test_generated_practice_validated_by_sandbox ✅
- integration/test_phase2.py::test_generation_rejected_when_never_valid ✅
- integration/test_phase2.py::test_admin_requires_admin_role ✅
- integration/test_phase2.py::test_admin_stats_and_users ✅
- integration/test_phase2.py::test_admin_exercise_crud_validates_on_sandbox ✅
- integration/test_phase2.py::test_admin_dml_exercise_needs_check_sql ✅
- integration/test_phase2.py::test_admin_edits_survive_reseed ✅
- integration/test_phase2.py::test_admin_lesson_example_errors_rejected ✅
- integration/test_phase2.py::test_admin_projects_achievements_databases ✅
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

### E2E (Playwright — Docker Compose stack)
- ✅ [platform] new learner sees a zeroed dashboard (no fake numbers)
- ✅ [platform] guest can run SQL in the playground (read-only) and writes are refused
- ✅ [phase2] projects: brief, tasks, and a task page linked back to its project
- ✅ [platform] SQL error shows line and column
- ✅ [phase2] assistant (rules) explains, reviews and optimizes without any AI key
- ✅ [platform] lesson → Try it opens the playground with the example
- ✅ [phase2] assistant explains the last SQL error
- ✅ [platform] practice: hints, incorrect then correct submission updates progress
- ✅ [phase2] admin panel is restricted and lets an admin create a validated exercise
- ✅ [platform] writable sandbox: modify then reset
- ✅ [platform] lesson completion is reflected in the course table of contents
- ✅ [platform] database page renders the ER diagram
- ✅ [platform] mobile layout uses a drawer menu

## สิ่งที่ยังไม่ได้ทดสอบ / ข้อจำกัดที่ทราบ
- **AI layer กับ Claude API จริง** — ไม่มี `ANTHROPIC_API_KEY` ในสภาพแวดล้อมนี้ จึงทดสอบเส้นทาง AI ด้วย fake provider (context, นโยบายไม่เฉลย, การตรวจโจทย์ที่สร้าง, error handling) ส่วนการเรียก SDK จริงยังไม่ได้รัน — ควรทดสอบ smoke test หลังใส่ key
- **Load test** ยังไม่ได้ทำ
- Integration tests ใช้ฐานข้อมูล dev ร่วมกัน (สร้างผู้ใช้ใหม่ทุก test) — ควรแยก test database ใน CI
- **ความจำของ sandbox**: ผู้ใช้ใน writable sandbox ตั้ง `work_mem` สูงเองได้ — ป้องกันด้วย timeout + `mem_limit` ของ container
- Rate limiter ต่อนาทีอยู่ใน memory ต่อ process (โควตา AI รายวันนับจาก DB ถูกต้องข้าม worker)
- Cross-browser: ทดสอบเฉพาะ Chromium · Accessibility: ยังไม่ได้ audit ด้วย screen reader
