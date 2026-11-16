# 01 — Requirements Analysis & Software Requirements Specification (SRS)

> STEP 1 (วิเคราะห์ความต้องการ) + STEP 2 (SRS) — เอกสารฉบับนี้คือ "สัญญา" ของสิ่งที่ระบบต้องทำ
> ทุก requirement มีรหัส (FR-/NFR-/SEC-) เพื่อใช้อ้างอิงใน Roadmap และ Test Report

## 1. วิเคราะห์ความต้องการ (Requirement Analysis)

### 1.1 ปัญหาที่ต้องแก้
| ปัญหาของผู้เรียน | แนวทางของแพลตฟอร์ม |
|---|---|
| อ่านเนื้อหาแล้วไม่ได้ลงมือ (W3Schools-style) | ทุกบทเรียนมีตัวอย่างที่ **รันได้จริง** และผลลัพธ์ที่ได้จากการ execute จริง |
| ทำโจทย์แล้วไม่รู้ว่าผิดตรงไหน (SQLZoo-style) | ตรวจด้วย **ผลลัพธ์** ไม่ใช่ข้อความ SQL แสดง diff ระหว่าง Actual vs Expected |
| ต้องติดตั้ง Database เอง | SQL Playground บน PostgreSQL จริงใน Sandbox |
| ไม่เห็นภาพการใช้งานจริง | ฐานข้อมูล 5 โดเมนธุรกิจ + ข้อมูลกรณีพิเศษ (NULL, ซ้ำ, orphan) |
| ไม่รู้ว่าตัวเองเก่งขึ้นแค่ไหน | Dashboard จากข้อมูลการใช้งานจริง, streak, skill progress |

### 1.2 Stakeholders
- **Learner** (Beginner → Professional) — ผู้ใช้หลัก
- **Admin / Content Editor** — ดูแลบทเรียน โจทย์ ฐานข้อมูล (Phase 2 UI; Phase 1 ใช้ content-as-code + seed)
- **Operator** — ติดตั้ง/ดูแลระบบ (Docker Compose)

### 1.3 สมมติฐานและข้อจำกัด
- Engine ใน Phase 1 = PostgreSQL 16 เท่านั้น (สถาปัตยกรรมเตรียม `EngineAdapter` ไว้สำหรับ MySQL/SQLite)
- เนื้อหาบทเรียนเก็บเป็น content-as-code (`backend/app/content/`) แล้ว seed ลง DB — ทำให้ review ผ่าน Git ได้ และ Admin Panel (Phase 2) จะเขียนลงตารางเดียวกัน
- AI Assistant เป็น Phase 2 และเป็น optional — ระบบตรวจคำตอบไม่พึ่ง AI

## 2. Functional Requirements

### FR-AUTH — Authentication & Session
| ID | Requirement | Phase |
|---|---|---|
| FR-AUTH-1 | สมัครสมาชิกด้วย email + password (ตรวจรูปแบบ, ความยาวรหัสผ่าน ≥ 8) | 1 |
| FR-AUTH-2 | Login / Logout, session เก็บใน httpOnly cookie, revoke ได้ฝั่ง server | 1 |
| FR-AUTH-3 | Role: `learner`, `admin` (RBAC) | 1 (model) / 2 (UI) |
| FR-AUTH-4 | หน้าที่ต้อง login: Dashboard, Progress, Submit, Saved queries | 1 |

### FR-DASH — Dashboard (ข้อมูลจริงเท่านั้น)
| ID | Requirement | Phase |
|---|---|---|
| FR-DASH-1 | บทเรียนที่เรียนจบ / ทั้งหมด, โจทย์ที่ทำสำเร็จ / ทั้งหมด | 1 |
| FR-DASH-2 | Accuracy rate = submissions ถูก / submissions ทั้งหมด | 1 |
| FR-DASH-3 | ความคืบหน้าแต่ละหลักสูตร (Level 1–4) | 1 |
| FR-DASH-4 | Learning streak (วันต่อเนื่องที่มี activity, timezone Asia/Bangkok) | 1 |
| FR-DASH-5 | ระดับความสามารถ SQL (คำนวณจากคะแนนโจทย์) | 1 |
| FR-DASH-6 | โจทย์ที่ทำล่าสุด, บทเรียนที่กำลังเรียน (continue learning) | 1 |
| FR-DASH-7 | Achievements / Badges ที่ได้รับ | 1 |
| FR-DASH-8 | กราฟพัฒนาการ 30 วัน (submissions & correct ต่อวัน) | 1 |

### FR-LEARN — Learning System
| ID | Requirement | Phase |
|---|---|---|
| FR-LEARN-1 | 4 หลักสูตร (Beginner 14, Intermediate 16, Advanced 14, Professional 18 บท = 62 บท) | 1 |
| FR-LEARN-2 | แต่ละบท: ชื่อ, คำอธิบาย, วัตถุประสงค์, เนื้อหา, ตัวอย่าง SQL, อธิบายทีละส่วน, ตัวอย่างผลลัพธ์, ข้อผิดพลาดที่พบบ่อย, แบบฝึกหัดท้ายบท, บทที่เกี่ยวข้อง, Prev/Next | 1 |
| FR-LEARN-3 | ตัวอย่างผลลัพธ์ต้องได้จากการ execute จริงบน sample DB (คำนวณตอน seed) | 1 |
| FR-LEARN-4 | ปุ่ม "Try it" เปิดตัวอย่างใน Playground พร้อม DB ที่ถูกต้อง | 1 |
| FR-LEARN-5 | Table of Contents ต่อหลักสูตร + สถานะเรียนจบรายบท | 1 |
| FR-LEARN-6 | Mark lesson complete, Bookmark, Personal note ต่อบท | 1 |

### FR-PG — SQL Playground
| ID | Requirement | Phase |
|---|---|---|
| FR-PG-1 | Monaco editor: line numbers, syntax highlight, auto-indent | 1 |
| FR-PG-2 | Auto completion: keywords + ชื่อ table/column ของ DB ที่เลือก | 1 |
| FR-PG-3 | Syntax validation ด้วย parser ของ PostgreSQL จริง (libpg_query) แสดง marker ในบรรทัดที่ผิด | 1 |
| FR-PG-4 | Run (Ctrl/Cmd+Enter), Clear, Format SQL | 1 |
| FR-PG-5 | Results: ตาราง, ชื่อคอลัมน์ + type, จำนวนแถว, เวลา, สถานะ, scroll, error message พร้อมตำแหน่ง | 1 |
| FR-PG-6 | Database Explorer: DB list, tables, columns, types, PK/FK, preview data | 1 |
| FR-PG-7 | Database selector + โหมด **Read-only (shared)** และ **Writable sandbox (ส่วนตัว)** | 1 |
| FR-PG-8 | Reset database (เฉพาะ writable sandbox ของผู้ใช้) | 1 |
| FR-PG-9 | Query history (อัตโนมัติ) และ Saved queries | 1 (ทำก่อนกำหนด) |

### FR-PRAC — Practice System
| ID | Requirement | Phase |
|---|---|---|
| FR-PRAC-1 | โจทย์ 4 ระดับ: easy / medium / hard / expert พร้อม filter ตามระดับ & หมวด | 1 |
| FR-PRAC-2 | ข้อมูลโจทย์: ID, ชื่อ, รายละเอียด, ระดับ, หมวด, คะแนน, DB, schema, expected result | 1 |
| FR-PRAC-3 | Run (ดูผลเอง) แยกจาก Submit (ตรวจ + บันทึก) | 1 |
| FR-PRAC-4 | ตรวจคำตอบด้วย **ผลลัพธ์**: ชื่อคอลัมน์, จำนวนแถว, ค่า NULL, ค่าซ้ำ (multiset), ลำดับ (ถ้าโจทย์กำหนด), ชนิดข้อมูลแบบ numeric-tolerant | 1 |
| FR-PRAC-5 | โจทย์ DML/DDL: รัน SQL ผู้ใช้ + `check_sql` ใน transaction ที่ ROLLBACK เสมอ แล้วเทียบกับผลของ solution | 1 |
| FR-PRAC-6 | Hint 3 ระดับ (เปิดทีละขั้น), Show solution, Explanation | 1 |
| FR-PRAC-7 | หลัง submit: Correct/Incorrect, actual, expected, เหตุผลที่ผิด (diff), วิธีแก้, เฉลย | 1 |
| FR-PRAC-8 | Previous / Next exercise | 1 |

### FR-DB — Sample Databases
| ID | Requirement | Phase |
|---|---|---|
| FR-DB-1 | 5 DB: ecommerce, hr, banking, hospital, music_store ตามตารางที่กำหนด | 1 |
| FR-DB-2 | มี PK/FK, ความสัมพันธ์, ข้อมูลกรณีพิเศษ (NULL, ซ้ำ, ไม่มีความสัมพันธ์) | 1 |
| FR-DB-3 | คำอธิบาย table/column (`COMMENT ON`), ER Diagram (generate จาก catalog จริง) | 1 |
| FR-DB-4 | Preview data, Reset, Selector | 1 |

### FR-PROG — Progress & Gamification
| ID | Requirement | Phase |
|---|---|---|
| FR-PROG-1 | Completed lessons/exercises, accuracy, streak, learning time, level, skill progress | 1 |
| FR-PROG-2 | Achievements (First Query, SQL Beginner, JOIN Master, Subquery Expert, Window Function Master, SQL Professional, …) ให้รางวัลอัตโนมัติจากเหตุการณ์จริง | 1 |
| FR-PROG-3 | Notes, Bookmarks | 1 |

### Phase 2/3 (ระบุไว้เพื่อออกแบบรองรับ — ยังไม่ทำใน MVP)
FR-AI (Learning Assistant), FR-PROJ (Real-World Projects), FR-ADMIN (Admin Panel UI), FR-ENGINE (MySQL/SQLite), FR-PLAN (EXPLAIN visualizer), ER builder, CSV import, dialect comparison, timed challenges, mock interview, leaderboard, community

## 3. Non-Functional Requirements
| ID | Requirement |
|---|---|
| NFR-1 | Query ใน sandbox ตอบกลับ p95 < 1s สำหรับ query ปกติ; timeout แข็งที่ 5s |
| NFR-2 | UI รองรับ Desktop / Tablet / Mobile, Dark & Light mode |
| NFR-3 | ภาษาไทยเป็นหลัก, SQL keyword เป็นภาษาอังกฤษ |
| NFR-4 | ทุกปุ่มต้องทำงานจริง; ฟีเจอร์ที่ยังไม่ทำต้องแสดงสถานะ "Coming in Phase N" ชัดเจน (ไม่ใช่ปุ่มหลอก) |
| NFR-5 | ไม่มี secret ใน source code; config ผ่าน environment variables |
| NFR-6 | Schema เปลี่ยนผ่าน migrations (Alembic) |
| NFR-7 | มี unit / integration / E2E tests |

## 4. Security Requirements
| ID | Requirement | วิธีการ (ระดับ infra/permission — ไม่พึ่ง regex) |
|---|---|---|
| SEC-1 | ไม่รัน SQL ผู้ใช้บน production DB | Sandbox เป็น PostgreSQL **cluster แยก** (container แยก) — backend ไม่มี credential ของ main DB ในโค้ด sandbox |
| SEC-2 | จำกัดสิทธิ์ | role `sbx_reader` มีแค่ `SELECT`, `default_transaction_read_only=on`, ไม่มี `CREATE`/`TEMP`; role ผู้ใช้ `sbx_u_<id>` เป็นเจ้าของเฉพาะ DB ของตัวเอง, `NOSUPERUSER NOCREATEDB NOCREATEROLE` |
| SEC-3 | จำกัดเวลา | `statement_timeout=5s`, `lock_timeout=2s`, `idle_in_transaction_session_timeout=10s` ตั้งที่ระดับ ROLE (ผู้ใช้เปลี่ยนเองได้ผ่าน SET เท่านั้นในขอบเขต session ที่ถูกปิดทันที + client-side timeout ซ้อนอีกชั้น) |
| SEC-4 | จำกัด memory/CPU | `work_mem`, `temp_file_limit` (superuser-only → ผู้ใช้เปลี่ยนไม่ได้) + Docker `cpus`/`mem_limit` ของ container sandbox |
| SEC-5 | จำกัดแถว | stream ผลลัพธ์แบบ single-row mode แล้วหยุดที่ `MAX_ROWS` (ไม่โหลดทั้งหมดเข้า memory) |
| SEC-6 | SQL injection ใน backend | ทุก query ของระบบใช้ SQLAlchemy/psycopg parameter binding; identifiers ใช้ `psycopg.sql.Identifier` |
| SEC-7 | แยกข้อมูลผู้ใช้ | `REVOKE CONNECT ... FROM PUBLIC` ทุก DB; ผู้ใช้ connect ได้เฉพาะ DB ของตัวเอง; API ตรวจ ownership ทุก endpoint |
| SEC-8 | ป้องกัน OS / external | ไม่ติดตั้ง extension (dblink, postgres_fdw, plpython); ไม่ให้ `pg_read_server_files`, `pg_execute_server_program`; `COPY ... PROGRAM` ใช้ไม่ได้; sandbox container ไม่มี outbound network (internal network) |
| SEC-9 | Reset | `DROP DATABASE ... WITH (FORCE)` + `CREATE DATABASE ... TEMPLATE tpl_<key>` |
| SEC-10 | Session/Permissions | random 256-bit token, เก็บ SHA-256 ใน DB, httpOnly + SameSite=Lax cookie, หมดอายุ 14 วัน; RBAC dependency `require_role` |
| SEC-11 | Rate limiting | token bucket ต่อ user/IP สำหรับ execute/submit/auth |
| SEC-12 | Secrets ฝั่ง server | `.env` (ไม่ commit), `.env.example` มีแต่ placeholder |
| SEC-13 | Logging & Error handling | structured log ทุก execution (user, db, ms, status) ไม่ log password; error ส่งกลับเป็นข้อความที่ปลอดภัย |

## 5. Acceptance Criteria (MVP)
1. ผู้ใช้ใหม่สมัคร → เข้า Dashboard เห็นตัวเลข 0 ทั้งหมด (ไม่ใช่ตัวเลขปลอม)
2. เปิดบทเรียน → กด Try it → Playground เปิดพร้อม SQL และ DB ที่ถูกต้อง → Run ได้ผลจริง
3. ทำโจทย์ → Submit คำตอบที่เขียนต่างจากเฉลยแต่ผลเหมือนกัน → **Correct**
4. Submit คำตอบที่ผลต่าง → **Incorrect** พร้อมเหตุผล (เช่น "จำนวนแถวไม่ตรง: ได้ 12 คาดหวัง 10")
5. `DROP TABLE customers` ในโหมด read-only → ถูกปฏิเสธโดย PostgreSQL permission
6. `SELECT pg_sleep(30)` → ถูกยกเลิกที่ 5s
7. Dashboard อัปเดตทันทีหลัง submit (accuracy, streak, chart, achievement "First Query")
