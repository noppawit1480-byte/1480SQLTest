# Installation Guide

## Option A — Docker Compose (แนะนำ)

ต้องมี Docker 24+ และ Docker Compose v2

```bash
git clone <repo> sqlab && cd sqlab
cp .env.example .env
```
แก้ทุกค่าที่ขึ้นต้นด้วย `CHANGE_ME` ใน `.env` (สร้างค่าสุ่มได้ด้วย `openssl rand -hex 24`) แล้วรัน:
```bash
docker compose up -d --build
```
เปิด **http://localhost:3000** (เปลี่ยน port ได้ด้วย `WEB_PORT`)

สิ่งที่เกิดขึ้นตอน backend start (อัตโนมัติ, idempotent):
1. `alembic upgrade head` — สร้าง/อัปเดต schema ของ main DB
2. `python -m app.seed` — provision sandbox (roles, template DBs, read-only DBs) และ seed บทเรียน/โจทย์
   โดย **รันทุกตัวอย่างและทุกเฉลยจริง** เพื่อเก็บผลลัพธ์ — ถ้าเฉลยข้อใดรันไม่ผ่าน backend จะไม่ start และ log จะบอกโจทย์ที่ผิด
3. `uvicorn` (2 workers)

คำสั่งที่ใช้บ่อย
```bash
docker compose logs -f backend                         # ดู log
docker compose exec backend python -m app.seed         # seed ใหม่หลังแก้เนื้อหา
docker compose exec backend python -m app.seed --rebuild  # สร้าง sample DB template ใหม่ (หลังแก้ generator)
docker compose down        # หยุด (ข้อมูลยังอยู่)
docker compose down -v     # หยุดและลบข้อมูลทั้งหมด
```

### Production checklist
- ใส่ reverse proxy (Caddy/Nginx) ทำ HTTPS แล้วตั้ง `COOKIE_SECURE=true`
- ใช้ secret ที่ยาวและสุ่มทุกตัว; อย่า commit `.env`
- ปรับ `cpus`/`mem_limit` ของ `sandbox-db` ตามจำนวนผู้ใช้
- สำรองข้อมูลเฉพาะ volume `main-data` (sandbox สร้างใหม่ได้ทั้งหมดด้วย seed)
- ถ้า scale backend หลาย instance: เปลี่ยน rate limiter เป็น Redis (`app/ratelimit.py` มี interface เดียว) — การสร้าง/รีเซ็ต DB ใช้ PostgreSQL advisory lock จึงปลอดภัยข้าม instance อยู่แล้ว

### เครือข่ายใน compose
| network | สมาชิก | internet |
|---|---|---|
| `web` | frontend, backend | ✅ (เปิด port 3000) |
| `core` | backend, main-db | ❌ internal |
| `sandbox` | backend, sandbox-db | ❌ internal |

---

## Option B — Local development (ไม่ใช้ Docker)

ต้องมี Python 3.12+ (ทดสอบบน 3.13), Node.js 22, PostgreSQL 16 **สองตัว** (main และ sandbox — แยก server/port กัน)

### 1. PostgreSQL
```bash
# ตัวอย่างด้วย pg_ctl (Linux) — main: 5433, sandbox: 5434
initdb -D ~/pg/main -U postgres --auth=trust
initdb -D ~/pg/sandbox -U postgres --auth=scram-sha-256 --pwprompt   # ตั้งรหัส superuser ของ sandbox
pg_ctl -D ~/pg/main -o "-p 5433" -l ~/pg/main.log start
pg_ctl -D ~/pg/sandbox -o "-p 5434" -l ~/pg/sandbox.log start
psql -p 5433 -U postgres -c "CREATE USER app PASSWORD 'app'"
psql -p 5433 -U postgres -c "CREATE DATABASE sqlplatform OWNER app"
```

### 2. Backend
```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env        # ใส่รหัส sandbox superuser และ secret
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```
Swagger UI: http://localhost:8000/api/docs

### 3. Frontend
```bash
cd frontend
npm install          # postinstall คัดลอก Monaco ไป public/monaco (ไม่พึ่ง CDN)
npm run dev          # http://localhost:3000  (proxy /api → http://127.0.0.1:8000 หรือ BACKEND_URL)
```

### 4. Tests
```bash
cd backend && pytest                 # unit + integration (ต้องมี DB ทั้งสองตัวและ seed แล้ว)
cd frontend && npm run typecheck
cd frontend && npm run build && npm run start &   # หรือ docker compose up
cd frontend && npx playwright test --trace off   # E2E (E2E_BASE_URL=http://host:port ถ้าไม่ใช่ :3000)
```

### แก้ไข sample data
```bash
cd backend
python -m app.sample_dbs.generate    # สร้าง app/sample_dbs/*.sql ใหม่ (deterministic)
python -m app.seed --rebuild         # สร้าง template ใหม่ + คำนวณ expected result ใหม่
```
