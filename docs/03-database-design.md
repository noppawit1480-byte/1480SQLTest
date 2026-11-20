# 03 — Database Schema & ER Diagram

> STEP 4 — ฐานข้อมูลหลักของแพลตฟอร์ม (`sqlplatform` บน main-db)
> Schema จริงสร้างด้วย Alembic migration `backend/alembic/versions/0001_initial.py`
> ER Diagram ของ **sample databases** ทั้ง 5 ถูก generate จาก catalog จริงและแสดงในหน้า Databases ของเว็บ (ดู [`sample-databases.md`](sample-databases.md))

## 1. ER Diagram (main DB)

```mermaid
erDiagram
  users ||--o{ sessions : has
  users ||--o{ lesson_progress : tracks
  users ||--o{ submissions : makes
  users ||--o{ query_history : runs
  users ||--o{ saved_queries : saves
  users ||--o{ user_achievements : earns
  users ||--o{ bookmarks : bookmarks
  users ||--o{ notes : writes
  users ||--o{ activity_days : "active on"
  courses ||--o{ lessons : contains
  lessons ||--o{ lesson_progress : ""
  lessons ||--o{ exercises : "end-of-lesson"
  lessons ||--o{ bookmarks : ""
  lessons ||--o{ notes : ""
  sample_databases ||--o{ lessons : "examples use"
  sample_databases ||--o{ exercises : "runs on"
  exercises ||--o{ submissions : ""
  achievements ||--o{ user_achievements : ""

  users {
    int id PK
    text email UK "lower-cased"
    text display_name
    text password_hash
    text role "learner|admin"
    timestamptz created_at
  }
  sessions {
    text token_hash PK "sha256"
    int user_id FK
    timestamptz expires_at
  }
  courses {
    int id PK
    text slug UK
    text title
    text level "beginner..professional"
    int position
  }
  lessons {
    int id PK
    int course_id FK
    text slug UK
    text title
    text summary
    jsonb objectives
    text content_md
    jsonb examples "sql, explanation, result preview"
    jsonb common_mistakes
    text sample_db FK
    jsonb related_slugs
    int position
  }
  sample_databases {
    text key PK
    text engine "postgresql"
    text name
    text description
    jsonb table_docs
  }
  exercises {
    int id PK
    text code UK "EX-E001"
    text title
    text description_md
    text difficulty "easy|medium|hard|expert"
    text category
    int points
    text sample_db FK
    text check_type "select|dml"
    text solution_sql
    text check_sql
    bool order_matters
    jsonb expected "columns + rows"
    jsonb hints "3 levels"
    text explanation_md
    int lesson_id FK
    int position
  }
  submissions {
    bigint id PK
    int user_id FK
    int exercise_id FK
    text sql
    bool is_correct
    text reason_code
    int exec_ms
    timestamptz created_at
  }
  lesson_progress {
    int user_id PK
    int lesson_id PK
    text status "in_progress|completed"
    timestamptz started_at
    timestamptz completed_at
  }
  query_history {
    bigint id PK
    int user_id FK
    text db_key
    text mode
    text sql
    bool success
    int row_count
    int exec_ms
    timestamptz created_at
  }
  saved_queries {
    int id PK
    int user_id FK
    text title
    text db_key
    text sql
  }
  achievements {
    text key PK
    text title
    text description
    text icon
  }
  user_achievements {
    int user_id PK
    text achievement_key PK
    timestamptz earned_at
  }
  activity_days {
    int user_id PK
    date day PK
    int seconds
    int events
  }
  bookmarks {
    int user_id PK
    int lesson_id PK
  }
  notes {
    int user_id PK
    int lesson_id PK
    text body
    timestamptz updated_at
  }
```

### Phase 2 additions (migration `0002_phase_2.py`)
```mermaid
erDiagram
  projects ||--o{ exercises : "tasks (project_id)"
  users ||--o{ assistant_logs : uses
  users ||--o{ generated_exercises : owns
  sample_databases ||--o{ projects : "runs on"
  projects {
    int id PK
    text slug UK
    text title
    text role
    text brief_md
    jsonb deliverables
    text sample_db FK
    bool is_custom
    bool admin_edited
  }
  assistant_logs {
    bigint id PK
    int user_id FK
    text mode
    text provider "rules | anthropic | ..."
    bool ok
    int input_tokens
    int output_tokens
  }
  generated_exercises {
    int id PK
    int user_id FK
    text db_key FK
    text title
    text solution_sql
    jsonb expected "from sandbox execution"
    timestamptz solved_at
  }
```
- `lessons`, `exercises` เพิ่ม `is_custom`, `admin_edited` (content governance) และ `exercises.project_id`
- `assistant_logs` ไม่เก็บ prompt/คำตอบ — เก็บเฉพาะ metadata สำหรับสถิติและโควตา

### Phase 3 additions (migration `0003_phase3.py`)
```mermaid
erDiagram
  users ||--o{ er_designs : owns
  users ||--o{ challenge_sessions : plays
  challenge_sessions ||--|{ challenge_items : contains
  exercises ||--o{ challenge_items : "picked as"
  users ||--o{ posts : writes
  posts ||--o{ posts : "replies (parent_id)"
  posts ||--o{ post_votes : receives
  users ||--o{ post_votes : casts
  posts ||--o{ post_reports : "reported in"
  er_designs {
    int id PK
    int user_id FK
    text name
    jsonb design "tables + relations"
  }
  challenge_sessions {
    int id PK
    int user_id FK
    text kind "timed | random | interview"
    jsonb config
    text status "active | finished | expired"
    int score
    timestamptz started_at
    timestamptz deadline_at "enforced by server"
    timestamptz finished_at
  }
  challenge_items {
    int session_id PK, FK
    int position PK
    int exercise_id FK
    int attempts
    int hints_used
    timestamptz solved_at
    int points
    text last_sql
    text approach_text "mock interview"
  }
  posts {
    int id PK
    int user_id FK
    text target_type "exercise | lesson"
    text target_key
    int parent_id FK
    text body
    bool is_spoiler
    bool is_hidden
  }
  post_votes {
    int user_id PK, FK
    int post_id PK, FK
  }
  post_reports {
    int id PK
    int post_id FK
    int user_id FK
    text reason
    bool resolved
  }
```
- `users.show_on_leaderboard` (opt-out) · `exercises.is_interview` (ชุดโจทย์ Mock Interview ไม่ปนกับแบบฝึกหัด) · `query_history.engine`, `saved_queries.engine`
- `posts` อ้างเป้าหมายด้วย `(target_type, target_key)` + index แทน FK สองชุด เพราะบทเรียน/โจทย์อาจถูกแก้รหัสโดย admin และกระทู้ควรอยู่ต่อ
- Leaderboard คำนวณสดจาก `submissions` (คำตอบถูกครั้งแรกของแต่ละข้อ) และ `challenge_sessions` — ไม่มีตารางสรุปที่ต้อง sync
- ฐานข้อมูล SQLite ไม่อยู่ใน main DB: เป็นไฟล์ใน `var/sqlite/` · ฐานข้อมูล MySQL อยู่บน server `sandbox-mysql` แยก (`ro_<key>`, `u_<uid>_<key>`) — ไม่มีตารางใหม่ใน main DB สำหรับ MySQL (ดู architecture §3.3)

## 2. Design decisions
| เรื่อง | การตัดสินใจ | เหตุผล |
|---|---|---|
| Session | ตาราง `sessions` เก็บ SHA-256 ของ token | revoke ได้ทันที (logout / ban), token รั่วจาก DB dump ใช้ไม่ได้ |
| Expected result | เก็บใน `exercises.expected` (JSONB) คำนวณตอน seed | ไม่ต้องรันเฉลยทุกครั้งที่ submit, แสดงใน UI ได้ทันที; ถ้าแก้ sample DB → re-seed คำนวณใหม่อัตโนมัติ |
| Activity / streak | `activity_days(user_id, day)` upsert ต่อ event | คำนวณ streak ด้วย query เดียว, เก็บ learning time รายวัน |
| Learning time | heartbeat จาก frontend ทุก 60s ขณะแท็บ active (cap 60s/heartbeat) | ตัวเลขจริง ไม่ใช่ประมาณ |
| Level (ความสามารถ) | คำนวณจากคะแนนรวมของโจทย์ที่ทำถูก (distinct) | deterministic, อธิบายได้ |
| Engine | `sample_databases.engine` | พร้อมรองรับ MySQL/SQLite |
| Index | `submissions(user_id, created_at)`, `submissions(user_id, exercise_id)`, `query_history(user_id, created_at)` | หน้า Dashboard/History |

## 3. Sample databases (sandbox cluster)

| Key | Tables | กรณีพิเศษที่ตั้งใจใส่ |
|---|---|---|
| `ecommerce` | customers, categories (มี parent_id → recursive), products, orders, order_items, payments | ลูกค้าไม่เคยสั่งซื้อ, สินค้าไม่เคยขาย, หมวดไม่มีสินค้า, phone/city เป็น NULL, order ที่ไม่มี payment, ชื่อเมืองสะกดซ้ำ, ราคาซ้ำ |
| `hr` | departments, positions, employees (manager_id → self join), salaries (ประวัติ) | แผนกไม่มีพนักงาน, พนักงานไม่มีแผนก (NULL), CEO ไม่มี manager, commission NULL |
| `banking` | customers, accounts, transactions, loans | ลูกค้าไม่มีบัญชี, บัญชีปิด, transaction ยอดติดลบ (withdraw), loan ที่ยังไม่อนุมัติ (approved_at NULL) |
| `hospital` | patients, doctors, appointments, treatments | appointment ถูกยกเลิก (ไม่มี treatment), แพทย์ไม่มีนัด, ผู้ป่วยไม่มี phone |
| `music_store` | artists, albums, tracks, playlists, playlist_tracks, invoices, invoice_items | ศิลปินไม่มีอัลบั้ม, track ไม่เคยขาย, composer NULL, playlist ว่าง |
| `saas` *(advanced, Phase 2)* | plans, companies, users, subscriptions, invoices, events (JSONB, ~43k) | แพ็กเกจ Legacy ที่ปิดขาย, trial ที่ไม่ convert, บริษัทที่ churn, ผู้ใช้ไม่เคยกลับมา (last_seen NULL), event ที่ properties ว่าง, invoice ค้างชำระ |
| `blank` *(Phase 3)* | — (ว่าง) | พื้นที่สำหรับสร้างตารางจาก DB Designer และนำเข้า CSV ใน Writable sandbox ของแต่ละผู้ใช้ |

> `playlist_tracks` เพิ่มเป็น junction table ที่จำเป็นสำหรับความสัมพันธ์ many-to-many ระหว่าง playlists ↔ tracks

ข้อมูลถูก generate แบบ deterministic (`random.seed`) โดย `backend/app/sample_dbs/generate.py` → ไฟล์ `*.sql` ที่ commit ไว้ ทำให้ผลลัพธ์ที่คาดหวังของโจทย์คงที่ทุกการติดตั้ง
