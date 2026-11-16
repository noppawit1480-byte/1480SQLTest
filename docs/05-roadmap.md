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

## Phase 2 — Advanced Learning
| Work item | Design hook ที่เตรียมไว้แล้ว | สถานะ |
|---|---|---|
| SQL Learning Assistant (Explain/Fix/Review/Optimize/Generate/Tutor) | ออกแบบ: `services/assistant/` + `LLMProvider` protocol (เปลี่ยนผู้ให้บริการได้), key อยู่ใน env ฝั่ง backend เท่านั้น, โหมด hint-only ไม่เฉลย, ส่ง error/schema จาก executor เป็น context — **ยังไม่มีโค้ด** | ⏳ |
| Real-World Projects (Sales, Customer, Product, Employee, Financial) | ใช้ตาราง `exercises` + เพิ่ม `projects`, `project_id` — checker เดิมใช้ได้ทันที | ⏳ (หน้า /projects แสดงสถานะ) |
| Admin Panel (CRUD lessons/exercises/DBs/users, stats) | มีแล้ว: `users.role`, dependency `require_role("admin")`, `ADMIN_EMAIL` สร้าง admin ตอน seed, เนื้อหาอยู่ในตาราง DB · ยังไม่มี: UI และ endpoints CRUD | ⏳ |
| Advanced sample DBs, more exercises | generator + seed pipeline | ⏳ |
| Query history / Saved query / Achievements / Hints | — | ✅ ทำเสร็จใน Phase 1 แล้ว |

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
