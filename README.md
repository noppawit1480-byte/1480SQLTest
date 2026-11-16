# SQLab — SQL Learning & Practice Platform

แพลตฟอร์มเรียนรู้และฝึก SQL ตั้งแต่ศูนย์ถึงระดับมืออาชีพ: **LEARN → EXPERIMENT → PRACTICE → ANALYZE → APPLY**
ทุก query รันบน **PostgreSQL 16 จริง** ใน sandbox ที่แยกจากระบบหลัก และระบบตรวจคำตอบจาก **ผลลัพธ์** ไม่ใช่ข้อความ SQL

| | |
|---|---|
| 📚 บทเรียน | 4 หลักสูตร · 62 บท (ภาษาไทย) · ตัวอย่างพร้อมผลลัพธ์ที่รันจริงตอน seed · ข้อผิดพลาดที่พบบ่อย · Try it |
| 🧪 Playground | Monaco editor, autocomplete จาก schema, syntax validation ด้วย parser ของ PostgreSQL, Format, multi-statement, History, Saved, Database Explorer, Read-only / Writable sandbox ส่วนตัว + Reset |
| 🏋️ แบบฝึกหัด | 70 โจทย์ Easy/Medium/Hard/Expert · Hint 3 ระดับ · ตรวจ columns/rows/NULL/ค่าซ้ำ/ลำดับ · โจทย์ DML/DDL ตรวจบนสำเนาฐานข้อมูลใหม่ |
| 🗄️ Sample DBs | ecommerce · hr · banking · hospital · music_store · **saas (advanced, JSONB ~43k events)** — PK/FK, comments, ER diagram, ข้อมูลกรณีพิเศษ |
| 💼 Real-World Projects | 6 สถานการณ์ธุรกิจ (Sales, Customer, Product, Employee, Financial, SaaS Metrics) · 25 งานตรวจอัตโนมัติ |
| 🤖 SQL Learning Assistant | Explain · Explain Error · Fix · Review · Optimize (rule engine บน parser ของ PostgreSQL + EXPLAIN — ไม่ต้องมี AI) · AI Tutor และ Generate Practice ผ่าน provider ที่เปลี่ยนได้ (Claude) |
| 🛡️ Admin Panel | RBAC · สถิติ · ผู้ใช้ · CRUD บทเรียน/โจทย์/โปรเจกต์ที่ตรวจด้วยการรันจริง · achievements · rebuild ฐานข้อมูล |
| 📈 Progress | Dashboard จากข้อมูลจริง, streak, เวลาเรียน, level, skill progress, achievements, bookmarks, notes |
| 🔒 Security | sandbox cluster แยก, role จำกัดสิทธิ์, timeout watchdog, row cap, network ภายใน, rate limit, session ฝั่ง server |

## Quick start
```bash
cp .env.example .env      # แก้ค่า CHANGE_ME ทั้งหมด
docker compose up -d --build
# → http://localhost:3000
```
รายละเอียด (รวมการรันแบบไม่ใช้ Docker): [docs/INSTALL.md](docs/INSTALL.md)

## Tech stack
Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · Monaco Editor · Recharts · Mermaid — FastAPI · SQLAlchemy 2 · Alembic · psycopg 3 · pglast (libpg_query) · argon2 · anthropic SDK (optional) — PostgreSQL 16 ×2 (main + sandbox) — Docker Compose · pytest · Playwright

Authentication ใช้ session ฝั่ง server ของ FastAPI (token สุ่ม 256-bit ใน httpOnly cookie, เก็บ SHA-256 ใน DB) แทน Auth.js
เพราะ backend เป็น Python และ cookie ผ่าน Next.js same-origin proxy — ดูเหตุผลใน [docs/02-architecture.md](docs/02-architecture.md)

## เอกสาร
| ขั้นตอน | เอกสาร |
|---|---|
| STEP 1–2 วิเคราะห์ความต้องการ & SRS | [docs/01-requirements-srs.md](docs/01-requirements-srs.md) |
| STEP 3 System Architecture (รวม sandbox security design) | [docs/02-architecture.md](docs/02-architecture.md) |
| STEP 4 Database Schema & ER Diagram | [docs/03-database-design.md](docs/03-database-design.md) · [docs/sample-databases.md](docs/sample-databases.md) |
| STEP 5–6 User Flow, Sitemap, หน้าจอหลัก | [docs/04-user-flow-sitemap.md](docs/04-user-flow-sitemap.md) |
| STEP 7 Roadmap & สถานะ | [docs/05-roadmap.md](docs/05-roadmap.md) |
| STEP 9 Test Report | [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| STEP 10 Installation / User Guide | [docs/INSTALL.md](docs/INSTALL.md) · [docs/USER_GUIDE.md](docs/USER_GUIDE.md) |
| API | [docs/API.md](docs/API.md) · Swagger UI ที่ `/api/docs` · [docs/openapi.json](docs/openapi.json) |

## Project structure
```
.
├── docker-compose.yml            # main-db, sandbox-db (internal network, CPU/RAM limits), backend, frontend
├── .env.example
├── docs/                         # SRS, architecture, DB design, flows, roadmap, API, install, user guide, test report
├── backend/                      # FastAPI
│   ├── alembic/versions/         # database migrations
│   ├── app/
│   │   ├── main.py               # app, middleware, error handlers
│   │   ├── config.py · db.py · models.py · schemas.py · security.py · ratelimit.py
│   │   ├── routers/              # auth · me · learn · practice · projects · playground · assistant · admin
│   │   ├── services/
│   │   │   ├── sandbox/          # EngineAdapter types + PostgreSQL executor & provisioning
│   │   │   ├── checker.py        # result-based answer checking (pure)
│   │   │   ├── validator.py      # syntax validation (libpg_query)
│   │   │   ├── sql_split.py      # statement splitting with offsets
│   │   │   ├── progress.py       # streak, level, achievements, projects, dashboard
│   │   │   ├── content.py        # executes examples/solutions (seeder + admin)
│   │   │   └── assistant/        # rules engine (pglast + EXPLAIN) + pluggable LLM provider
│   │   ├── content/              # 62 lessons + 70 exercises + 6 projects / 25 tasks (content-as-code)
│   │   ├── sample_dbs/           # deterministic generator + generated *.sql (6 DBs)
│   │   └── seed.py               # provision sandbox + seed content (executes every example/solution)
│   └── tests/{unit,integration}/
└── frontend/                     # Next.js App Router
    ├── app/                      # dashboard · learn · playground · practice · projects · assistant · databases · profile · admin · auth
    ├── components/               # AppShell, SqlEditor (Monaco), ResultView, SchemaExplorer, Markdown, Mermaid, ui
    ├── lib/                      # typed API client, types, hooks
    └── e2e/                      # Playwright tests
```

## สถานะ
- **Phase 1 (MVP)** และ **Phase 2 (Advanced Learning)** เสร็จและทดสอบแล้ว — ผลทดสอบล่าสุดใน [docs/TEST_REPORT.md](docs/TEST_REPORT.md)
- Phase 3 (multiple engines, ER builder, CSV import, leaderboard ฯลฯ) ยังไม่ได้พัฒนา — ดู [docs/05-roadmap.md](docs/05-roadmap.md)
- AI layer ของ Assistant ทดสอบด้วย fake provider; ยังไม่ได้ทดสอบกับ Claude API จริง (ต้องใส่ `ANTHROPIC_API_KEY`)
