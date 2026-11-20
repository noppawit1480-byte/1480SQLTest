# 05 — Development Roadmap

> STEP 7 — สถานะจริง ณ การส่งมอบครั้งนี้ (✅ เสร็จและทดสอบแล้ว · 🟡 บางส่วน · ⏳ ยังไม่เริ่ม)

## Phase 1 — MVP (ส่งมอบในรอบนี้)
| # | Work item | Requirement | สถานะ |
|---|---|---|---|
| 1 | Docker Compose: main-db, sandbox-db (internal, limited), backend, frontend | SEC-1,4,8 | ✅ (ทดสอบ up + E2E แล้ว) |
| 2 | Alembic migration ของ main DB | NFR-6 | ✅ |
| 3 | Sandbox provisioning (templates, ro DBs, roles, privileges) | SEC-2,7,8 | ✅ |
| 4 | Sandbox executor (timeout watchdog, row cap, streaming, read-only tx) | SEC-3,5 | ✅ |
| 5 | 5 sample DBs + generator + comments + edge cases | FR-DB-* | ✅ |
| 6 | Auth (register/login/logout/me, sessions, RBAC deps, rate limit) | FR-AUTH-*, SEC-10,11 | ✅ |
| 7 | Content: 4 courses / 62 lessons, example results executed at seed | FR-LEARN-* | ✅ |
| 8 | Practice: exercises 4 ระดับ, result-based checker, DML checker, hints, solution | FR-PRAC-* | ✅ |
| 9 | Playground UI: Monaco, completion, validation markers, format, explorer, results, history, saved, reset | FR-PG-* | ✅ |
| 10 | Progress: lesson progress, activity/streak/time, level, achievements, notes, bookmarks | FR-PROG-* | ✅ |
| 11 | Dashboard (ข้อมูลจริง + Recharts) | FR-DASH-* | ✅ |
| 12 | Tests: unit (checker, validator, splitter), integration (API + real sandbox), E2E (Playwright) | NFR-7 | ✅ |
| 13 | Docs: API, install, user guide, test report | Deliverables | ✅ |

## Phase 2 — Advanced Learning (ส่งมอบในรอบนี้)
| # | Work item | สิ่งที่ทำ | สถานะ |
|---|---|---|---|
| 1 | **SQL Learning Assistant** | Explain / Explain Error / Fix / Review / Optimize ทำงานด้วย **rule engine บน parser ของ PostgreSQL (pglast) + EXPLAIN จริง** — ใช้ได้โดยไม่ต้องมี AI · AI layer แบบ pluggable (`LLMProvider`: Anthropic Claude, Null) เพิ่มคำอธิบาย, **SQL Tutor chat**, **Generate Practice** (เฉลยที่ AI สร้างต้องรันผ่านบน sandbox ก่อน) · โหมดแบบฝึกหัดให้คำใบ้เท่านั้น (AI ไม่ได้รับเฉลย) · key อยู่ฝั่ง server · rate limit + โควตารายวัน + usage log | ✅ |
| 2 | Hint & Solution | Hint 3 ระดับ + Show solution (ทำใน Phase 1) | ✅ |
| 3 | **Real-World Projects** | 6 โปรเจกต์ (Sales, Customer, Product, Employee, Financial, SaaS Metrics) · 25 งานตรวจอัตโนมัติ · business brief + นิยาม + deliverables + เกณฑ์ประเมิน · achievement *Real-World Analyst*, *Project Master* | ✅ |
| 4 | Query History / Saved Query | (ทำใน Phase 1) | ✅ |
| 5 | Achievements | เพิ่ม 2 achievement ของ Projects; แก้ชื่อ/คำอธิบายผ่าน Admin | ✅ |
| 6 | **Advanced Sample Database** | `saas`: plans, companies, users, subscriptions (ประวัติ MRR), invoices, **events JSONB ~43,000 แถว** — สำหรับ MRR, retention, cohort, JSON | ✅ |
| 7 | **Admin Panel** | RBAC (`require_role("admin")` ทั้ง router) · สถิติการใช้งาน · จัดการผู้ใช้ (role, ระงับ + revoke session) · CRUD บทเรียน/โจทย์/โปรเจกต์ (**ตรวจโดยรัน SQL จริงก่อนบันทึก**) · แก้ achievements · rebuild sample DB + คำนวณ expected ใหม่ · audit log · seed ไม่ทับงานที่แอดมินแก้ | ✅ |

### ข้อจำกัดที่ทราบของ Phase 2
- AI layer ทดสอบอัตโนมัติด้วย fake provider (ตรวจ context, นโยบายไม่เฉลย, การตรวจโจทย์ที่ AI สร้าง) — **ยังไม่ได้ทดสอบกับ Claude API จริงในสภาพแวดล้อมนี้** เพราะไม่มี API key
- Rate limiter อยู่ใน memory ต่อ process (เหมือน Phase 1); โควตา AI รายวันนับจากฐานข้อมูลจึงถูกต้องข้าม worker
- เงื่อนไขการได้ achievement กำหนดในโค้ด — Admin แก้ได้เฉพาะชื่อ/คำอธิบาย/ไอคอน

## Phase 3 — Professional Platform (ส่งมอบในรอบนี้)
| # | Work item | สิ่งที่ทำ | สถานะ |
|---|---|---|---|
| 1 | **Multiple Database Engines** | **SQLite 3** เป็น engine ที่สองที่รันจริง: ทุก sample DB ถูก export จาก PostgreSQL เป็นไฟล์ SQLite (ข้อมูลชุดเดียวกัน) · Read-only และ Writable sandbox ต่อผู้ใช้ + Reset · รันใน worker process แยก (`python -I`, rlimit CPU/RAM/ขนาดไฟล์/จำนวนไฟล์, session ใหม่) + SQLite authorizer (ห้าม `ATTACH`, `load_extension`, PRAGMA ที่อันตราย, เขียนในโหมด read-only) + timeout · เลือก engine ใน Playground, History และ Saved query จำ engine | ✅ |
| 1a | **MySQL 8.4** | engine ที่สามที่รันจริง (server แยก `sandbox-mysql` ใน network ภายใน) · sample DB ทุกตัว export จาก PostgreSQL (ตาราง key index FK comment และข้อมูลครบ) · Read-only ผ่าน `sbx_reader` ที่มีแค่ SELECT + `TRANSACTION READ ONLY` · Writable = database `u_<uid>_<key>` และบัญชี MySQL ของผู้ใช้แต่ละคนที่มีสิทธิ์เฉพาะ DB ของตัวเอง (ไม่มี FILE/SUPER/PROCESS/EVENT/GRANT) · server ปิด `local_infile` และ `secure_file_priv=NULL` · watchdog `KILL QUERY` เมื่อเกินเวลา (ครอบคลุม UPDATE/DELETE/CALL ที่ `max_execution_time` ของ MySQL ไม่ครอบคลุม) · ใช้ได้ใน Playground, Explain/Analyze (`EXPLAIN FORMAT=TREE` / `EXPLAIN ANALYZE`), Dialect comparison, Designer และ CSV import · เปิดใช้เมื่อตั้งค่า `MYSQL_HOST` (ถ้าไม่ตั้ง UI แสดงว่าไม่พร้อมใช้งานพร้อมเหตุผล) | ✅ |
| 2 | **Query Execution Plan** | ปุ่ม Explain / Explain Analyze ใน Playground → tree viewer (cost, rows ประมาณการ vs จริง, เวลา, buffer) + findings จาก rule engine ของ Assistant (Seq Scan + Filter บนตารางใหญ่, sort ข้อมูลจำนวนมาก, Nested Loop ขนาดใหญ่) · SQLite ใช้ `EXPLAIN QUERY PLAN` · ANALYZE ของคำสั่งที่แก้ข้อมูลถูกห่อใน `BEGIN … ROLLBACK` จึงไม่มีผลถาวร | ✅ |
| 3 | **Query Optimization Lab** | หน้า Optimization: ใส่ query + `CREATE INDEX` (สูงสุด 3) → รัน EXPLAIN ANALYZE ก่อน/หลังบน **สำเนาฐานข้อมูลใหม่** แล้วเทียบเวลา cost และ node (เช่น ~10× บน `saas.events`) — ไม่แตะฐานข้อมูลของใคร | ✅ |
| 4 | **ER Diagram Builder / Database Design Playground** | ออกแบบตาราง คอลัมน์ PK/NN/UNIQUE/identity/default และ FK (on delete) → ตรวจแบบอัตโนมัติ (ชื่อซ้ำ, ไม่มี PK, FK ชี้คอลัมน์ที่ไม่ใช่ key, ชนิดไม่ตรงกัน, ชื่อ/ชนิดที่ไม่ปลอดภัย) · ER diagram สด · DDL 3 dialect (PostgreSQL, SQLite, MySQL) · บันทึก/โหลดแบบ · reverse-engineer จาก sample DB · **สร้างจริงในฐานข้อมูล `blank` ของผู้ใช้** บน PostgreSQL, SQLite หรือ MySQL | ✅ |
| 5 | **CSV Import** | อัปโหลด CSV (≤ 5 MB, ≤ 50,000 แถว, ≤ 100 คอลัมน์) → ตรวจชนิดข้อมูลอัตโนมัติ (แก้ได้) → นำเข้าใน Writable sandbox ด้วย `COPY` ใน role ของผู้ใช้เอง (PostgreSQL) หรือ parameterized insert (SQLite) · ชื่อถูก sanitize, ค่าไม่ถูกต่อเป็น SQL | ✅ |
| 6 | **SQL Dialect Comparison** | ตารางอ้างอิง 25 หัวข้อ (PostgreSQL / SQLite / MySQL / SQL Server) · รัน query เดียวกันบน PostgreSQL, SQLite และ MySQL แล้วเทียบกับ PostgreSQL ด้วย checker เดียวกับระบบตรวจคำตอบ (เช่น เห็นจริงว่า MySQL รวมกลุ่ม 'Bangkok'/'bangkok' เป็นค่าเดียวเพราะ collation ไม่แยกตัวพิมพ์ และ `7/2` = 3.5000) + ตรวจจับ feature เฉพาะ dialect จาก parse tree | ✅ |
| 7 | **Timed Challenges** | 3–10 ข้อ 5–60 นาที · เวลาและ deadline บังคับที่ server · คะแนน = points × (1 + 0.5 × เวลาที่เหลือ) × 0.9^hint × ลด 10% ต่อการส่งผิด (ต่ำสุด 50%) · achievement *Beat the Clock* | ✅ |
| 8 | **Random Challenges** | สุ่ม 1 ข้อตามระดับ/หมวด | ✅ |
| 9 | **Mock Interview** | ชุดโจทย์สัมภาษณ์ 10 ข้อแยกจากแบบฝึกหัด · ช่องอธิบายแนวคิด · rubric: ความถูกต้อง 50 / ประสิทธิภาพ 20 / เวลา 10 / การอธิบาย 20 (ผ่าน ≥ 70) · achievement *Interview Ready* · ระหว่าง challenge ปิดการดูเฉลยของข้อนั้น | ✅ |
| 10 | **Leaderboard** | คะแนนแบบฝึกหัด (นับครั้งแรกที่ทำถูก) และคะแนน Challenges · 7 วัน / ทั้งหมด · แสดงเฉพาะ display name · ผู้ใช้เลือกซ่อนตัวเองได้ | ✅ |
| 11 | **Community** | กระทู้สนทนาในทุกโจทย์และบทเรียน · ตอบกลับ 1 ระดับ · โหวต · แก้/ลบโพสต์ตัวเอง · **spoiler gating ที่ server** (ผู้ที่ยังไม่ทำโจทย์ถูกจะไม่ได้รับเนื้อหา spoiler เว้นแต่กดขอดู; โพสต์ที่มี ```sql ในโจทย์เป็น spoiler อัตโนมัติ) · รายงานโพสต์ → คิว moderation ใน Admin (ซ่อน/ปิดรายงาน) · rate limit | ✅ |

### ข้อจำกัดที่ทราบของ Phase 3
- MySQL: ขนาดฐานข้อมูลส่วนตัวตรวจ**หลัง**รันแต่ละครั้ง (เกินแล้วรีเซ็ต) ไม่ใช่ quota แบบ hard limit ที่ระดับไฟล์ — ภายในหนึ่ง query จำกัดด้วย timeout และ `mem_limit` ของ container · CHECK constraint ของ PostgreSQL ไม่ถูก export ไป SQLite/MySQL · คำสั่งที่ MySQL commit อัตโนมัติ (DDL) ใน Analyze ไม่สามารถ rollback ได้ — จึงรับเฉพาะ SELECT/DML
- SQL Server เป็นข้อมูลอ้างอิงเท่านั้น (ไม่ได้รันจริง)
- การตรวจคำตอบแบบฝึกหัด/challenge ยังใช้ PostgreSQL เป็นหลัก (expected result คำนวณจาก PostgreSQL); SQLite และ MySQL ใช้ใน Playground, Explain, Designer, CSV import และ Dialect comparison
- การปิดเฉลยระหว่าง challenge ป้องกันการเปิดดูโดยบังเอิญในบัญชีเดียวกัน ไม่ใช่ระบบกันโกง (ผู้ใช้ที่ออกจากระบบยังเปิดเฉลยได้เหมือนโจทย์ทั่วไป) — leaderboard จึงเหมาะกับการฝึก ไม่ใช่การแข่งขันที่มีรางวัล
- Rubric ของ Mock Interview คำนวณจากตัวชี้วัดที่วัดได้ (ถูก/ผิด, จำนวนครั้ง, hint, เวลา, ความยาวคำอธิบาย) — **ไม่ได้ประเมินคุณภาพเนื้อหาคำอธิบาย**
- Community ไม่มีการแจ้งเตือน (notification) และไม่มีการค้นหาข้ามกระทู้
- ไฟล์ SQLite ของผู้ใช้อยู่บน volume ของ backend (`sqlite-data`) — ถ้า scale backend หลายเครื่องต้องใช้ shared volume (MySQL ไม่มีข้อจำกัดนี้ เพราะเป็น server)

## Milestones
1. M1 Infrastructure + sandbox security ✔
2. M2 Content & checker ✔
3. M3 UI ✔
4. M4 Tests & docs ✔
5. M5 Phase 2 — Advanced Learning ✔
6. M6 Phase 3 — Professional Platform ✔
7. M7 MySQL engine ✔
