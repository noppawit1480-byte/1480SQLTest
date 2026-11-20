# Test Report

> STEP 9 — ผลการทดสอบจริง · Phase 3 (2026-11-17) + MySQL engine (2026-11-20) · PostgreSQL 16 · SQLite 3 · MySQL 8.4.13 · Python 3.13 · Node 22 · Chromium (Playwright)

## สรุป
| ชุดทดสอบ | เครื่องมือ | จำนวน | ผล |
|---|---|---|---|
| Unit (checker, splitter, validator, streak/level, serialization) | pytest | 23 | ✅ 23/23 |
| Integration — Phase 1 (API + main DB + sandbox จริง) | pytest + TestClient | 35 | ✅ 35/35 |
| Integration — Phase 2 (projects, assistant rules + AI layer ด้วย fake provider, admin RBAC/CRUD) | pytest + TestClient | 25 | ✅ 25/25 |
| Integration — Phase 3 (SQLite sandbox, explain/index lab, dialects, designer, CSV, challenges, leaderboard, community, MySQL-disabled path) | pytest + TestClient | 26 | ✅ 26/26 |
| Integration — MySQL engine (ข้อมูลตรงกับ PostgreSQL, การโจมตี sandbox, timeout ทุกชนิดคำสั่ง, writable/reset, explain, dialects, designer, CSV) | pytest + TestClient + MySQL 8.4 จริง | 13 | ✅ 13/13 |
| Content validation (ตัวอย่าง 62 บท + เฉลย 70 โจทย์ + 10 โจทย์สัมภาษณ์ + 25 งานโปรเจกต์ รันบน sandbox; export SQLite 7 DB) | `python -m app.seed` | 167 | ✅ ผ่านทั้งหมด |
| Type check / production build | `tsc --noEmit` · `next build` | 27 routes | ✅ |
| End-to-End (เบราว์เซอร์จริง) | Playwright | 24 | ✅ 24/24 local · ✅ 24/24 Docker Compose |
| Docker Compose | build + up + restart + E2E + isolation | 5 services (+ `sandbox-mysql`) + volumes `sqlite-data`, `mysql-data` | ✅ healthy ทั้งหมด · sandbox-db/sandbox-mysql ออก internet ไม่ได้ · frontend เข้า sandbox-db/sandbox-mysql ไม่ได้ · ข้อมูล Writable ของ MySQL อยู่รอดหลัง restart backend |

Backend รันซ้ำ 3 รอบ: 122/122 ทุกรอบ · เมื่อไม่ตั้ง `MYSQL_HOST`: 109 passed, 13 skipped (test MySQL ข้ามอย่างชัดเจน ไม่ fail)
E2E ต้องรัน backend ด้วย `RATE_AUTH_PER_MIN=200` (สมัครสมาชิก > 10 บัญชีต่อนาที) — ด้วยค่า production (10) จะได้ 429 ตามที่ออกแบบไว้

## MySQL engine — สิ่งที่ทดสอบ
| ด้าน | Test | ผล |
|---|---|---|
| ข้อมูลเหมือนกัน | จำนวนแถวทั้ง 31 ตารางของ 6 sample DB ตรงกับ PostgreSQL (ตรวจด้วยมือ) · ใน test: `orders`, `saas.events`, `salaries`, `transactions` และผลรวมเงิน `SUM(unit_price*quantity)` ตรงกัน | ✅ |
| Read-only | `DELETE`, `CREATE TABLE` → ปฏิเสธพร้อมคำแนะนำ Writable · `INTO OUTFILE` ต้องใช้ FILE privilege → ปฏิเสธ · `mysql.user` → ปฏิเสธ · `SET GLOBAL` → ปฏิเสธ · `LOAD_FILE('/etc/passwd')` ได้ NULL (secure_file_priv=NULL) | ✅ |
| Timeout | `SELECT SLEEP(30)`, `UPDATE … WHERE SLEEP(1)=0` และ `CALL` procedure ที่วนไม่รู้จบ ถูกหยุดที่ 5 วินาทีด้วย watchdog (`max_execution_time` ของ MySQL ไม่ครอบคลุม UPDATE/CALL) และ sandbox ใช้ต่อได้ | ✅ |
| Row cap / error | recursive CTE 50,000 แถว ถูกตัดที่ 1,000 · syntax error ในคำสั่งที่ 2 ชี้บรรทัด 3 ของสคริปต์ถูกต้อง | ✅ |
| Writable | DB แยกต่อผู้ใช้ · DB กลางไม่เปลี่ยน · อ่าน DB ของคนอื่น, `GRANT`, `CREATE USER`, `CREATE EVENT`, `LOAD DATA LOCAL` → ปฏิเสธ · Reset คืนข้อมูลเดิม | ✅ |
| Schema / plan | FK และ comment ของตารางมาครบ · `EXPLAIN FORMAT=TREE` ใช้ `idx_orders_customer` · `EXPLAIN ANALYZE DELETE` บน writable แล้วข้อมูลยังครบ 946 แถว · หลายคำสั่ง → 422 | ✅ |
| Dialects | `7/2` = `3.5000` บน MySQL (ต่างจาก PostgreSQL) · GROUP BY city: SQLite ตรงกับ PostgreSQL แต่ MySQL ได้กลุ่มน้อยกว่าเพราะ collation ไม่แยกตัวพิมพ์ และระบบชี้สาเหตุ (`collation`) | ✅ |
| Designer / CSV | DDL ที่สร้างรันได้จริงบน MySQL (unique TEXT → VARCHAR(255), default ใน TEXT/CURRENT_DATE ใส่วงเล็บ) · FK บังคับใช้ · CSV → DECIMAL ขนาดตามข้อมูล, ค่าว่างเป็น NULL · ตารางซ้ำโดยไม่ replace → 422 | ✅ |
| ไม่ได้ตั้งค่า MySQL | `/api/engines` รายงาน `available: false` พร้อมเหตุผล · execute → 503 · dialects รันแค่ 2 engine | ✅ |
| E2E | Playground บน MySQL (ผล `3.5000`, plan มี index, DELETE ใน read-only ถูกปฏิเสธ) · Dialects 3 engine พร้อมคำอธิบาย collation · Designer สร้างตารางใน MySQL และ `SHOW CREATE TABLE` มี FOREIGN KEY | ✅ |

## Bugs ที่พบระหว่างพัฒนา MySQL engine และแก้แล้ว
| # | พบจาก | ปัญหา | การแก้ |
|---|---|---|---|
| 17 | การโจมตีทดสอบ | `SELECT SLEEP(30)` ที่ถูก `KILL QUERY` คืนค่า 1 แทน error จึงแสดงเป็น "สำเร็จ" | ถ้า watchdog ทำงาน ให้รายงานเป็น timeout เสมอ |
| 18 | การโจมตีทดสอบ | ข้อความ "โหมด Read-only แก้ไขไม่ได้" ติดไปกับการปฏิเสธที่ไม่ใช่การเขียน (เช่นอ่าน `mysql.user`) | แยกข้อความตามชนิดการปฏิเสธ |
| 19 | รัน DDL จริง | DDL MySQL จาก Designer (ก่อนหน้านี้เป็นแค่ข้อความ) สร้าง `TEXT UNIQUE` ซึ่ง MySQL ไม่รับ และ default ของ TEXT/CURRENT_DATE ผิด syntax | ใช้ VARCHAR(255) สำหรับคอลัมน์ที่ต้องมี index และใส่วงเล็บให้ expression default |
| 20 | plan parser | เวลาใน `EXPLAIN ANALYZE` เป็นเลขยกกำลัง (`858e-6`) ทำให้ node นั้นไม่มีเวลาจริง | regex รองรับ notation นี้ |
| 21 | Docker build | pin `PyMySQL==2.2.8` ผิด (อ่านจาก `pymysql.__version__` ซึ่งเป็นเลขเวอร์ชันเข้ากันได้กับ MySQLdb) | pin เวอร์ชันจริง `PyMySQL==1.2.4` |
| 22 | Dialects | ข้อความเทียบผลใช้คำแนะนำของระบบตรวจคำตอบ ("ตรวจ WHERE/JOIN") ซึ่งไม่เกี่ยว | ตัดคำแนะนำนั้นและบอกสาเหตุ collation เมื่อเกี่ยวข้อง |

## Phase 3 — สิ่งที่ทดสอบ
| ด้าน | Test | ผล |
|---|---|---|
| SQLite = ข้อมูลเดียวกัน | จำนวนแถวของ `ecommerce.orders`, `saas.events`, `hr.salaries` บน SQLite ตรงกับ PostgreSQL | ✅ |
| SQLite security | `DELETE` ในโหมด read-only, `ATTACH '/etc/passwd'`, `PRAGMA writable_schema`, `load_extension` → ถูกปฏิเสธพร้อมข้อความ | ✅ |
| SQLite limits | recursive CTE ไม่รู้จบ → timeout (ตรวจซ้ำด้วยมือใน container ด้วย) · ผลเกิน `MAX_RESULT_ROWS` ถูกตัดที่ 1,000 แถว | ✅ |
| SQLite writable | แยกต่อผู้ใช้ · ไม่กระทบ read-only · Reset คืนค่าเดิม · schema มี FK · History จำ engine · engine ที่ไม่รองรับ → 422 | ✅ |
| Dialect comparison | GROUP BY ที่ได้ผลเหมือนกันบน SQLite → `engines.sqlite.same: true` · `DATE_TRUNC … ::date` รันได้เฉพาะ PostgreSQL → `same: false` และตรวจพบ feature `date_trunc`, `cast_op`, `limit` · ตารางอ้างอิง ≥ 20 หัวข้อ | ✅ |
| Explain / Analyze | ANALYZE มีเวลา execution · `EXPLAIN ANALYZE DELETE FROM payments` บน writable sandbox แล้วข้อมูลยังครบ 946 แถว · SQLite plan ใช้ index `idx_orders_customer` · หลาย statement → 422 | ✅ |
| Index lab | ก่อน: Seq Scan บน `saas.events` · หลัง: index ใหม่ถูกใช้ (ทดลองด้วยมือวัดได้เร็วขึ้น ~10×) · `DROP TABLE` แทน `CREATE INDEX` → 422 · guest → 401 · index ไม่ค้างในฐานข้อมูลกลาง | ✅ |
| Designer | DDL 3 dialect (identity/AUTOINCREMENT, ON DELETE CASCADE) + Mermaid · ชื่อตารางแบบ injection (`t1); DROP TABLE x;--`) ถูกปฏิเสธและไม่สร้าง DDL · FK ที่ชี้คอลัมน์ที่ไม่ใช่ PK/UNIQUE ถูกเตือน · reverse-engineer `hr` · apply สร้างตารางจริงบน PostgreSQL และ SQLite และ **FK ถูกบังคับใช้ทั้งสอง engine** · แบบของคนอื่น → 404 | ✅ |
| CSV import | หัวคอลัมน์ถูก sanitize (`Order ID` → `order_id`) · infer ชนิด integer/text/numeric/boolean/date · ค่าว่างเป็น NULL · นำเข้าทั้งสอง engine · ตารางซ้ำโดยไม่ replace, ชื่อตารางไม่ถูกต้อง, ชื่อคอลัมน์ซ้ำ → 422 · guest → 401 | ✅ |
| Timed challenge | ไม่มีเฉลยใน response · hint ลดคะแนน · ทำครบในเวลา → *Beat the Clock* · session ของคนอื่น → 404 | ✅ |
| Deadline | ส่งหลัง deadline → 409 และ session เป็น `expired` · เปิดพร้อมกันได้ไม่เกิน 3 | ✅ |
| เฉลยระหว่าง challenge | `GET /exercises/{code}/solution` → 409 และ submit ปกติไม่คืนเฉลย จนกว่าจะจบ challenge | ✅ |
| Mock interview | rubric 4 เกณฑ์ น้ำหนัก 50/20/10/20 · ผ่าน → *Interview Ready* · โจทย์สัมภาษณ์ไม่ปนใน /practice | ✅ |
| Leaderboard | คะแนนของผู้เรียนปรากฏใน `me` · ไม่มีอีเมลในรายการ · ซ่อนตัวเองแล้วหายจากรายการและ `me_hidden: true` | ✅ |
| Community | โพสต์ที่มี ```sql เป็น spoiler อัตโนมัติ · ผู้ที่ยังไม่ทำโจทย์ถูกไม่ได้รับ body จนกว่าจะทำถูก (การกด “แสดง spoiler” ทดสอบใน E2E) · ตอบกลับ · โหวต 1 ครั้ง, โหวตตัวเอง → 409 · ลบโพสต์คนอื่น → 404 · learner เปิดคิว report → 403 · report → admin ซ่อน → body ไม่ถูกส่งให้ผู้ใช้อื่น และรายงานถูกปิด · admin ซ่อนโพสต์ผ่าน UI (E2E) | ✅ |

## Bugs ที่พบระหว่างพัฒนา Phase 3 และแก้แล้ว
| # | พบจาก | ปัญหา | การแก้ |
|---|---|---|---|
| 11 | integration test | SQLite ส่ง "disk I/O error" เมื่อฐานข้อมูลส่วนตัวเกินขนาด (rlimit) — ผู้เรียนไม่เข้าใจ | map เป็น error `limit` พร้อมข้อความภาษาไทย |
| 12 | seeder | โจทย์สัมภาษณ์ IV-03 มี expected result ว่าง | เปลี่ยนเป็นโจทย์ "พนักงานที่เข้างานก่อนหัวหน้า" ที่มีผลลัพธ์จริง |
| 13 | code review | รางวัล achievement ของ challenge ถูกเก็บใน dict ระดับ module (ปะปนข้าม request/worker) | คืนค่าจากฟังก์ชันโดยตรง |
| 14 | security review | ระหว่าง challenge ผู้เรียนเปิดเฉลยของข้อเดียวกันผ่านหน้าแบบฝึกหัดได้ | ล็อกเฉลย (409) และไม่ส่งเฉลยใน submit ระหว่าง session active + test |
| 15 | E2E | checkbox ซ่อนชื่อใน Leaderboard เปลี่ยนสถานะหลังโหลดใหม่เท่านั้น | อัปเดตทันที (optimistic) และย้อนกลับเมื่อ error |
| 16 | log review | log ของ seed ไม่นับโจทย์สัมภาษณ์ | แสดงจำนวนแยก |

ปัญหาของ **สภาพแวดล้อมทดสอบ**: Docker Hub ตอบ 429 (rate limit) ระหว่างดึง `node:22-alpine` ครั้งแรก — ลองใหม่แล้วผ่าน; E2E ต้องเพิ่ม `RATE_AUTH_PER_MIN` (เพิ่มตัวแปรนี้ใน compose ให้ตั้งได้ ค่าเริ่มต้นยังเป็น 10)

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

### Backend (pytest -v) — 122 passed
- integration/test_api.py::test_register_login_logout_flow ✅
- integration/test_api.py::test_register_validation_and_duplicate ✅
- integration/test_api.py::test_protected_endpoints_require_login ✅
- integration/test_api.py::test_auth_rate_limited ✅
- integration/test_api.py::test_readonly_select_works ✅
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
- integration/test_mysql.py::test_engine_listed_and_same_data ✅
- integration/test_mysql.py::test_load_file_cannot_read_server_files ✅
- integration/test_mysql.py::test_timeouts_cover_non_select_statements ✅
- integration/test_mysql.py::test_row_cap_and_syntax_error_position ✅
- integration/test_mysql.py::test_writable_isolated_privileges_and_reset ✅
- integration/test_mysql.py::test_schema_explain_and_analyze_rollback ✅
- integration/test_mysql.py::test_dialect_comparison_shows_real_mysql_differences ✅
- integration/test_mysql.py::test_designer_apply_and_csv_import ✅
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
- integration/test_phase3.py::test_sqlite_has_the_same_data ✅
- integration/test_phase3.py::test_sqlite_timeout_and_row_cap ✅
- integration/test_phase3.py::test_sqlite_writable_isolated_and_resettable ✅
- integration/test_phase3.py::test_sqlite_schema_and_history ✅
- integration/test_phase3.py::test_dialect_comparison ✅
- integration/test_phase3.py::test_explain_and_analyze_never_persist ✅
- integration/test_phase3.py::test_index_lab ✅
- integration/test_phase3.py::test_design_ddl_validation ✅
- integration/test_phase3.py::test_design_apply_and_ownership[postgresql] ✅
- integration/test_phase3.py::test_design_apply_and_ownership[sqlite] ✅
- integration/test_phase3.py::test_csv_import[postgresql] ✅
- integration/test_phase3.py::test_csv_import[sqlite] ✅
- integration/test_phase3.py::test_csv_requires_login ✅
- integration/test_phase3.py::test_timed_challenge_flow ✅
- integration/test_phase3.py::test_challenge_deadline_enforced ✅
- integration/test_phase3.py::test_solution_locked_during_active_challenge ✅
- integration/test_phase3.py::test_active_session_limit ✅
- integration/test_phase3.py::test_mock_interview_rubric ✅
- integration/test_phase3.py::test_leaderboard_and_opt_out ✅
- integration/test_phase3.py::test_discussion_spoilers_votes_and_ownership ✅
- integration/test_phase3.py::test_moderation ✅
- integration/test_phase3.py::test_mysql_disabled_is_reported_not_faked ✅
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

### E2E (Playwright) — 24 passed (local และ Docker Compose stack)
- ✅ [mysql] playground runs on MySQL, shows a plan, and writes go to the learner's own MySQL database
- ✅ [mysql] dialect comparison runs on three engines and explains MySQL's case-insensitive grouping
- ✅ [mysql] ER designer creates the tables in MySQL
- ✅ [phase2] projects: brief, tasks, and a task page linked back to its project
- ✅ [phase2] assistant (rules) explains, reviews and optimizes without any AI key
- ✅ [phase2] assistant explains the last SQL error
- ✅ [phase2] admin panel is restricted and lets an admin create a validated exercise
- ✅ [phase3] playground runs the same query on SQLite and shows an execution plan
- ✅ [phase3] dialect comparison reports differences between engines
- ✅ [phase3] ER designer validates, generates DDL and creates the tables in the learner's sandbox
- ✅ [phase3] CSV import previews types and loads rows
- ✅ [phase3] random challenge: server timer, wrong answer, finish and report
- ✅ [phase3] mock interview shows the approach box and a rubric
- ✅ [phase3] discussion hides SQL spoilers from learners who have not solved the exercise; leaderboard opt-out
- ✅ [phase3] admin can hide a reported post
- ✅ [platform] new learner sees a zeroed dashboard (no fake numbers)
- ✅ [platform] guest can run SQL in the playground (read-only) and writes are refused
- ✅ [platform] SQL error shows line and column
- ✅ [platform] lesson → Try it opens the playground with the example
- ✅ [platform] practice: hints, incorrect then correct submission updates progress
- ✅ [platform] writable sandbox: modify then reset
- ✅ [platform] lesson completion is reflected in the course table of contents
- ✅ [platform] database page renders the ER diagram
- ✅ [platform] mobile layout uses a drawer menu

## สิ่งที่ยังไม่ได้ทดสอบ / ข้อจำกัดที่ทราบ
- MySQL: ไม่ได้ทดสอบ load (ผู้ใช้พร้อมกันจำนวนมาก) · ขนาด DB ส่วนตัวตรวจหลังรันแต่ละครั้ง ไม่ใช่ hard quota · ทดสอบกับ MySQL 8.4 เท่านั้น (ไม่ได้ทดสอบ MariaDB)
- SQLite worker ใช้ rlimit ของ Linux — ทดสอบบน Linux (local + container) เท่านั้น
- Challenges/leaderboard ไม่ได้ทดสอบภายใต้ผู้ใช้พร้อมกันจำนวนมาก (ไม่มี load test)
- **AI layer กับ Claude API จริง** — ไม่มี `ANTHROPIC_API_KEY` ในสภาพแวดล้อมนี้ จึงทดสอบเส้นทาง AI ด้วย fake provider (context, นโยบายไม่เฉลย, การตรวจโจทย์ที่สร้าง, error handling) ส่วนการเรียก SDK จริงยังไม่ได้รัน — ควรทดสอบ smoke test หลังใส่ key
- **Load test** ยังไม่ได้ทำ
- Integration tests ใช้ฐานข้อมูล dev ร่วมกัน (สร้างผู้ใช้ใหม่ทุก test) — ควรแยก test database ใน CI
- **ความจำของ sandbox**: ผู้ใช้ใน writable sandbox ตั้ง `work_mem` สูงเองได้ — ป้องกันด้วย timeout + `mem_limit` ของ container
- Rate limiter ต่อนาทีอยู่ใน memory ต่อ process (โควตา AI รายวันนับจาก DB ถูกต้องข้าม worker)
- Cross-browser: ทดสอบเฉพาะ Chromium · Accessibility: ยังไม่ได้ audit ด้วย screen reader
