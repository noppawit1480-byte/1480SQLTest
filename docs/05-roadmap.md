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

## Phase 3 — Professional Platform
| Work item | Design hook |
|---|---|
| Multiple engines (MySQL, SQLite) | `EngineAdapter` protocol, `engine` column |
| Query Execution Plan visualizer / optimization | `EXPLAIN (FORMAT JSON)` ใช้ได้แล้วใน sandbox (บทเรียน EXPLAIN) → เพิ่ม tree viewer |
| ER Diagram Builder, Database Design Playground | writable sandbox per user มีอยู่แล้ว |
| CSV Import | writable sandbox + `COPY FROM STDIN` ผ่าน backend |
| SQL Dialect comparison, Timed/Random challenges, Mock interview, Leaderboard, Community | `submissions` มีเวลา/คะแนนพร้อมคำนวณ leaderboard |

## Milestones
1. M1 Infrastructure + sandbox security ✔
2. M2 Content & checker ✔
3. M3 UI ✔
4. M4 Tests & docs ✔
