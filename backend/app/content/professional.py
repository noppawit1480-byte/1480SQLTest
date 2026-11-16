from app.content.model import Example as E
from app.content.model import LessonDef as L
from app.content.model import Mistake as M

W = True  # writable example

LESSONS = [
L("create-table", "CREATE DATABASE และ CREATE TABLE — สร้างโครงสร้างข้อมูล",
  "สร้างฐานข้อมูลและตารางพร้อมชนิดข้อมูล ค่าเริ่มต้น และ identity column",
  ["อธิบายคำสั่ง CREATE DATABASE", "สร้างตารางพร้อมชนิดข้อมูลที่เหมาะสม", "ใช้ DEFAULT และ GENERATED AS IDENTITY",
   "ใช้โหมด Writable sandbox ฝึก DDL"],
  """
### CREATE DATABASE
```sql
CREATE DATABASE shop_dev;
```
สร้างฐานข้อมูลใหม่ทั้งก้อน — ต้องมีสิทธิ์ `CREATEDB` (ใน Sandbox ของแพลตฟอร์มนี้ **ปิดสิทธิ์นี้** เพื่อความปลอดภัย
คุณจะได้ฐานข้อมูลส่วนตัวแยกให้แต่ละ sample database อยู่แล้วในโหมด **Writable sandbox**)

### CREATE TABLE
```sql
CREATE TABLE table_name (
  column_name data_type [constraints],
  ...
);
```
| เรื่อง | แนวปฏิบัติ |
|---|---|
| Primary key อัตโนมัติ | `id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY` (มาตรฐาน SQL — แนะนำมากกว่า `serial`) |
| เงิน | `numeric(12,2)` |
| ข้อความ | `text` หรือ `varchar(n)` เมื่อมีข้อจำกัดความยาวทางธุรกิจ |
| เวลา | `timestamptz` สำหรับเหตุการณ์จริง (เก็บ timezone) |
| ค่าเริ่มต้น | `DEFAULT now()`, `DEFAULT true` |
| ป้องกันซ้ำ | `CREATE TABLE IF NOT EXISTS` |

> 🧪 ฝึกบทนี้ใน Playground โดยสลับเป็นโหมด **Writable** — ทุกอย่างอยู่ในฐานข้อมูลส่วนตัวของคุณ และกด Reset ได้ตลอด
""",
  [E("สร้างตาราง reviews แล้วตรวจโครงสร้าง", """CREATE TABLE reviews (
  id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_id  integer NOT NULL,
  rating      smallint NOT NULL,
  comment     text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'reviews'
ORDER BY ordinal_position;""", ["`GENERATED ALWAYS AS IDENTITY` ให้ฐานข้อมูลสร้าง id ให้เอง", "`NOT NULL` บังคับต้องมีค่า",
                                 "`DEFAULT now()` ใส่เวลาปัจจุบันอัตโนมัติ", "query ท้ายตรวจว่าตารางถูกสร้างตามที่ต้องการ"], writable=W)],
  [M("ลืมกำหนด primary key", "CREATE TABLE reviews (product_id int, rating int);", "CREATE TABLE reviews (id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY, ...);",
     "ตารางที่ไม่มี PK ระบุแถวไม่ได้ แก้/ลบแถวเดียวยาก และเกิดข้อมูลซ้ำง่าย"),
   M("ใช้ reserved word เป็นชื่อคอลัมน์", "CREATE TABLE t (order int, user text);", "CREATE TABLE t (order_no int, username text);",
     "order และ user เป็นคำสงวน ต้องครอบด้วย \"\" ทุกครั้ง — หลีกเลี่ยงดีกว่า")],
  ["insert", "constraints", "primary-key"]),

L("insert", "INSERT — เพิ่มข้อมูล",
  "เพิ่มข้อมูลทีละแถว หลายแถว จาก SELECT และใช้ RETURNING / ON CONFLICT",
  ["INSERT แบบระบุคอลัมน์", "INSERT หลายแถวและ INSERT ... SELECT", "ใช้ RETURNING และ ON CONFLICT (upsert)"],
  """
```sql
INSERT INTO table (col1, col2) VALUES (v1, v2), (v3, v4);
INSERT INTO table (col1, col2) SELECT ... FROM ...;
```
- **ระบุชื่อคอลัมน์เสมอ** — ไม่พังเมื่อมีคนเพิ่มคอลัมน์ และอ่านง่าย
- คอลัมน์ที่ไม่ระบุจะได้ `DEFAULT` หรือ `NULL`
- `RETURNING id` คืนค่าที่เพิ่งสร้าง (เช่น id อัตโนมัติ) โดยไม่ต้อง query ซ้ำ
- **Upsert**: `ON CONFLICT (key) DO UPDATE SET col = EXCLUDED.col` หรือ `DO NOTHING`
""",
  [E("เพิ่มหมวดหมู่ใหม่และรับ id กลับ", """INSERT INTO categories (name, parent_id, description)
VALUES ('Gaming', 1, 'อุปกรณ์เกม'),
       ('Camping', 5, 'อุปกรณ์แคมป์ปิ้ง')
RETURNING id, name, parent_id;""", ["เพิ่ม 2 แถวในคำสั่งเดียว", "`RETURNING` คืน id ที่ฐานข้อมูลสร้างให้"], writable=W),
   E("Upsert: เพิ่มหรืออัปเดตเมื่อซ้ำ", """INSERT INTO categories (name, description)
VALUES ('Books', 'หนังสือทุกประเภท (อัปเดต)')
ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
RETURNING id, name, description;""", ["`name` มี UNIQUE constraint จึงชนกับ Books ที่มีอยู่", "`EXCLUDED` คือแถวที่พยายามจะ insert"], writable=W)],
  [M("ไม่ระบุคอลัมน์", "INSERT INTO categories VALUES (99, 'X', NULL, NULL);", "INSERT INTO categories (name) VALUES ('X');",
     "ต้องจำลำดับคอลัมน์ทั้งหมด และพังเมื่อโครงสร้างเปลี่ยน"),
   M("ใส่ id เองในคอลัมน์ identity", "INSERT INTO categories (id, name) VALUES (1, 'X');", "INSERT INTO categories (name) VALUES ('X');",
     "ชน primary key หรือทำให้ sequence ไม่ตรง")],
  ["update", "create-table", "constraints"]),

L("update", "UPDATE — แก้ไขข้อมูล",
  "แก้ไขข้อมูลอย่างปลอดภัยด้วย WHERE, อัปเดตจากตารางอื่น และตรวจผลก่อน commit",
  ["UPDATE ด้วย WHERE", "UPDATE หลายคอลัมน์และด้วยนิพจน์", "UPDATE ... FROM อ้างตารางอื่น"],
  """
```sql
UPDATE table SET col1 = expr1, col2 = expr2 WHERE condition;
```
### ⚠️ กฎเหล็ก
1. **ไม่มี WHERE = แก้ทุกแถว**
2. รัน `SELECT` ด้วย WHERE เดียวกันก่อน เพื่อดูว่าจะกระทบแถวไหน
3. ในงานจริงทำใน transaction: `BEGIN; UPDATE ...; SELECT ... ; COMMIT;` (หรือ ROLLBACK ถ้าผิด)

- `UPDATE ... FROM other_table WHERE ...` (PostgreSQL) อัปเดตโดยอ้างข้อมูลอีกตาราง
- `RETURNING` ดูค่าหลังอัปเดต
""",
  [E("ขึ้นราคาสินค้าในหมวด Smartphones 5%", """UPDATE products
SET price = ROUND(price * 1.05, 2)
WHERE category_id = 6
RETURNING id, name, price;""", ["WHERE จำกัดเฉพาะหมวด 6", "RETURNING แสดงราคาใหม่"], writable=W),
   E("UPDATE ... FROM: ตั้ง stock = 0 ให้สินค้าที่ไม่ active", """UPDATE products p
SET stock = 0
FROM categories c
WHERE c.id = p.category_id AND p.is_active = false
RETURNING p.id, p.name, c.name AS category, p.stock;""", ["อ้างตาราง categories เพื่อแสดงชื่อหมวดในผลลัพธ์"], writable=W)],
  [M("ลืม WHERE", "UPDATE products SET price = 0;", "UPDATE products SET price = 0 WHERE id = 42;", "สินค้าทั้งร้านราคา 0 บาท"),
   M("ใช้ AND แทน comma ใน SET", "UPDATE products SET price = 100 AND stock = 5 WHERE id = 1;",
     "UPDATE products SET price = 100, stock = 5 WHERE id = 1;", "PostgreSQL จะพยายามตั้ง price = (100 AND stock = 5) → error ชนิดข้อมูล")],
  ["delete", "transactions"]),

L("delete", "DELETE และ TRUNCATE — ลบข้อมูล",
  "ลบข้อมูลอย่างปลอดภัย ลบตามเงื่อนไขจากตารางอื่น และความต่างของ DELETE กับ TRUNCATE",
  ["DELETE ด้วย WHERE", "DELETE ... USING", "เลือกระหว่าง DELETE / TRUNCATE / soft delete"],
  """
```sql
DELETE FROM table WHERE condition;
```
- ไม่มี WHERE = ลบทุกแถว (เหมือน UPDATE)
- ลบแถวที่มีตารางอื่นอ้างถึง (FK) จะ error เว้นแต่ FK ตั้ง `ON DELETE CASCADE`
- `DELETE ... USING other` ลบโดยอ้างตารางอื่น
- `TRUNCATE table` ลบทั้งตารางเร็วมาก (ไม่ไล่ทีละแถว) แต่ไม่มี WHERE

### Soft delete
ระบบจริงนิยม **ไม่ลบจริง** แต่ตั้ง `is_active = false` หรือ `deleted_at = now()` เพื่อเก็บประวัติและกู้คืนได้
""",
  [E("ลบการชำระเงินแบบ COD ของคำสั่งซื้อที่ยกเลิก", """DELETE FROM payments p
USING orders o
WHERE o.id = p.order_id AND o.status = 'cancelled'
RETURNING p.id, p.order_id;""", ["`USING orders` ใช้ข้อมูลสถานะจากตาราง orders", "ในข้อมูลนี้ order ที่ยกเลิกไม่มี payment จึงได้ 0 แถว — ข้อมูลสอดคล้องดี"], writable=W),
   E("FK ป้องกันการลบ", """DELETE FROM customers WHERE id = 1;""", ["ลูกค้าคนนี้มีคำสั่งซื้อ จึงลบไม่ได้: violates foreign key constraint"], writable=W)],
  [M("ลบโดยไม่ตรวจก่อน", "DELETE FROM orders WHERE status = 'cancel';", "SELECT COUNT(*) FROM orders WHERE status = 'cancelled'; -- ตรวจก่อน แล้วค่อย DELETE",
     "พิมพ์ค่าผิดได้ 0 แถว (ไม่ error) หรือแย่กว่านั้นลบผิดแถว")],
  ["update", "foreign-key", "transactions"]),

L("alter-table", "ALTER TABLE — แก้ไขโครงสร้างตาราง",
  "เพิ่ม/ลบ/เปลี่ยนชื่อคอลัมน์ เปลี่ยนชนิดข้อมูล และเพิ่ม constraint ภายหลัง",
  ["เพิ่มและลบคอลัมน์", "เปลี่ยนชนิดข้อมูลและชื่อ", "เพิ่ม/ลบ constraint"],
  """
| งาน | คำสั่ง |
|---|---|
| เพิ่มคอลัมน์ | `ALTER TABLE t ADD COLUMN c type [DEFAULT ...]` |
| ลบคอลัมน์ | `ALTER TABLE t DROP COLUMN c` |
| เปลี่ยนชื่อ | `ALTER TABLE t RENAME COLUMN a TO b` / `RENAME TO new_table` |
| เปลี่ยนชนิด | `ALTER TABLE t ALTER COLUMN c TYPE new_type [USING expr]` |
| NOT NULL | `ALTER COLUMN c SET NOT NULL` / `DROP NOT NULL` |
| Default | `ALTER COLUMN c SET DEFAULT v` |
| Constraint | `ADD CONSTRAINT name CHECK (...)` / `DROP CONSTRAINT name` |

> ในระบบ production ALTER บางอย่างล็อกตารางและเขียนข้อมูลใหม่ทั้งหมด — ทีมจริงใช้ **migration tool** (เช่น Alembic, Flyway) และทดสอบก่อน
""",
  [E("เพิ่มคอลัมน์ loyalty_points พร้อม default และ CHECK", """ALTER TABLE customers ADD COLUMN loyalty_points integer NOT NULL DEFAULT 0;
ALTER TABLE customers ADD CONSTRAINT chk_points_non_negative CHECK (loyalty_points >= 0);

SELECT id, first_name, loyalty_points FROM customers ORDER BY id LIMIT 3;""",
     ["แถวเดิมทั้งหมดได้ค่า 0 จาก DEFAULT", "CHECK ป้องกันค่าติดลบในอนาคต"], writable=W)],
  [M("เพิ่ม NOT NULL โดยไม่มี DEFAULT ให้ตารางที่มีข้อมูล", "ALTER TABLE customers ADD COLUMN tier text NOT NULL;",
     "ALTER TABLE customers ADD COLUMN tier text NOT NULL DEFAULT 'standard';", "แถวเดิมจะเป็น NULL ซึ่งขัดกับ NOT NULL → error")],
  ["create-table", "drop", "constraints"]),

L("drop", "DROP — ลบวัตถุในฐานข้อมูล",
  "ลบตาราง/คอลัมน์/ดัชนีอย่างระมัดระวัง และผลของ CASCADE",
  ["ใช้ DROP TABLE / IF EXISTS", "เข้าใจ CASCADE vs RESTRICT", "แยก DROP / TRUNCATE / DELETE"],
  """
| คำสั่ง | ลบอะไร | ย้อนกลับ |
|---|---|---|
| `DELETE FROM t` | ข้อมูล (เลือกแถวได้) | ได้ใน transaction |
| `TRUNCATE t` | ข้อมูลทั้งหมด | ได้ใน transaction (PostgreSQL) |
| `DROP TABLE t` | ทั้งตาราง + โครงสร้าง + index | ได้ใน transaction (PostgreSQL) |

- `DROP TABLE IF EXISTS t` ไม่ error ถ้าไม่มีตาราง
- ถ้ามีวัตถุอื่นพึ่งพา (FK, view) จะ error — `CASCADE` ลบสิ่งที่พึ่งพาด้วย (**อันตราย**)
- PostgreSQL รองรับ DDL ใน transaction → `BEGIN; DROP TABLE ...; ROLLBACK;` กู้คืนได้
""",
  [E("DROP ตารางที่ถูกอ้างอิง → error", """DROP TABLE orders;""", ["order_items และ payments อ้างถึง orders → cannot drop table orders because other objects depend on it"], writable=W),
   E("DROP ใน transaction แล้ว ROLLBACK", """BEGIN;
DROP TABLE payments;
ROLLBACK;
SELECT COUNT(*) AS payments_still_here FROM payments;""", ["ROLLBACK ยกเลิกการ DROP — ตารางยังอยู่ครบ"], writable=W)],
  [M("ใช้ CASCADE โดยไม่ตรวจ", "DROP TABLE orders CASCADE;", "ตรวจ dependency ก่อน และ DROP ทีละวัตถุอย่างตั้งใจ",
     "CASCADE ลบ FK constraint ของตารางอื่นทิ้งเงียบ ๆ")],
  ["alter-table", "delete", "commit-rollback"]),

L("primary-key", "Primary Key — ตัวระบุแถวที่ไม่ซ้ำ",
  "หลักการเลือก primary key: natural vs surrogate key, composite key",
  ["อธิบายคุณสมบัติของ PK", "เลือก natural/surrogate key", "สร้าง composite primary key"],
  """
Primary Key = **UNIQUE + NOT NULL** และมีได้ 1 ชุดต่อตาราง PostgreSQL สร้าง unique index ให้อัตโนมัติ

| แบบ | ตัวอย่าง | ข้อดี / ข้อเสีย |
|---|---|---|
| **Surrogate key** | `id` identity | ไม่เปลี่ยน, สั้น, JOIN เร็ว / ไม่มีความหมายทางธุรกิจ |
| **Natural key** | `national_id`, `email` | มีความหมาย / อาจเปลี่ยนได้ (อีเมลเปลี่ยน) |
| **Composite key** | `(playlist_id, track_id)` | เหมาะกับตารางเชื่อม many-to-many |

แนวปฏิบัติทั่วไป: ใช้ surrogate `id` เป็น PK และใส่ `UNIQUE` ให้ natural key (เช่น `customers.email UNIQUE`)
""",
  [E("ดู primary key ของทุกตารางใน music_store", """SELECT tc.table_name, string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS pk_columns
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name AND kcu.table_name = tc.table_name
WHERE tc.constraint_type = 'PRIMARY KEY'
GROUP BY tc.table_name
ORDER BY tc.table_name;""", ["`playlist_tracks` มี composite key 2 คอลัมน์"], db="music_store"),
   E("PK ป้องกันข้อมูลซ้ำ", """INSERT INTO playlist_tracks (playlist_id, track_id)
SELECT playlist_id, track_id FROM playlist_tracks LIMIT 1;""", ["เพิ่มคู่ที่มีอยู่แล้ว → duplicate key value violates unique constraint"], db="music_store", writable=W)],
  [M("ใช้ข้อมูลที่เปลี่ยนได้เป็น PK", "PRIMARY KEY (email)", "id identity PRIMARY KEY, email UNIQUE",
     "เมื่ออีเมลเปลี่ยน ต้องแก้ทุกตารางที่อ้างถึง")],
  ["foreign-key", "constraints", "create-table"]),

L("foreign-key", "Foreign Key — ความถูกต้องของความสัมพันธ์",
  "บังคับให้ข้อมูลอ้างอิงถึงแถวที่มีอยู่จริง และกำหนดพฤติกรรมเมื่อลบ/แก้ไข",
  ["สร้าง FK", "อธิบาย referential integrity", "เลือก ON DELETE RESTRICT/CASCADE/SET NULL"],
  """
```sql
customer_id integer NOT NULL REFERENCES customers(id) ON DELETE RESTRICT
```
FK รับประกัน **referential integrity**: จะมี `orders.customer_id = 999` ไม่ได้ถ้าไม่มีลูกค้า id 999

| ON DELETE | เมื่อลบแถวแม่ |
|---|---|
| `NO ACTION` / `RESTRICT` (ค่าเริ่มต้น) | ห้ามลบถ้ายังมีลูกอ้างถึง |
| `CASCADE` | ลบลูกตามไปด้วย (เช่น order → order_items) |
| `SET NULL` | ตั้ง FK ของลูกเป็น NULL |

> PostgreSQL **ไม่** สร้าง index ให้คอลัมน์ FK อัตโนมัติ — ควรสร้างเอง (`CREATE INDEX ON orders(customer_id)`) เพื่อให้ JOIN และการลบแม่เร็ว
""",
  [E("ดู foreign key ทั้งหมดของ ecommerce", """SELECT conrelid::regclass AS table_name, conname AS constraint_name, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE contype = 'f'
ORDER BY 1;""", ["`pg_constraint` คือ system catalog ของ constraint", "`pg_get_constraintdef` แสดงนิยามเป็น SQL"]),
   E("FK ปฏิเสธข้อมูลที่อ้างถึงลูกค้าที่ไม่มีอยู่", """INSERT INTO orders (customer_id, order_date, status) VALUES (9999, now(), 'pending');""",
     ["insert or update on table \"orders\" violates foreign key constraint"], writable=W)],
  [M("ไม่สร้าง index ให้ FK", "customer_id integer REFERENCES customers(id)", "... + CREATE INDEX idx_orders_customer ON orders(customer_id);",
     "JOIN และการลบลูกค้าต้องสแกนทั้งตาราง orders")],
  ["primary-key", "db-relationships", "constraints"]),

L("constraints", "Constraints — กฎความถูกต้องของข้อมูล",
  "NOT NULL, UNIQUE, CHECK, DEFAULT, PRIMARY KEY, FOREIGN KEY และ EXCLUDE ในภาพรวม",
  ["เลือก constraint ที่เหมาะสมกับกฎธุรกิจ", "ตั้งชื่อ constraint", "อ่าน error จากการละเมิด constraint"],
  """
Constraint คือ **กฎที่ฐานข้อมูลบังคับเอง** — ไม่ว่าข้อมูลจะมาจากแอปไหน ก็ผิดกฎไม่ได้ (ปลอดภัยกว่าตรวจในแอปอย่างเดียว)

| Constraint | ตัวอย่าง |
|---|---|
| `NOT NULL` | `email text NOT NULL` |
| `UNIQUE` | `UNIQUE (email)` |
| `CHECK` | `CHECK (price >= 0)`, `CHECK (max_salary >= min_salary)` |
| `PRIMARY KEY` | `PRIMARY KEY (id)` |
| `FOREIGN KEY` | `REFERENCES customers(id)` |
| `DEFAULT` | (ไม่ใช่ constraint แท้ แต่ใช้คู่กัน) |

ตั้งชื่อเพื่อให้ error อ่านง่าย: `CONSTRAINT chk_price_positive CHECK (price > 0)`
""",
  [E("CHECK ปฏิเสธราคาติดลบ", """UPDATE products SET price = -1 WHERE id = 1;""", ["sample DB มี `CHECK (price >= 0)` → violates check constraint \"products_price_check\""], writable=W),
   E("ดู constraint ทั้งหมดของตาราง products", """SELECT conname, contype, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'products'::regclass
ORDER BY contype;""", ["contype: c = check, f = foreign key, p = primary key, u = unique"])],
  [M("ตรวจความถูกต้องเฉพาะในแอป", "if price < 0: raise ... # ในโค้ดแอปเท่านั้น", "CHECK (price >= 0) ในฐานข้อมูล + ตรวจในแอป",
     "สคริปต์นำเข้าข้อมูลหรือแอปอื่นข้ามการตรวจได้")],
  ["primary-key", "foreign-key", "alter-table"]),

L("db-relationships", "Database Relationships — 1:1, 1:N, N:M",
  "รูปแบบความสัมพันธ์ระหว่างตาราง และวิธีอ่าน ER Diagram",
  ["ระบุความสัมพันธ์ 1:1, 1:N, N:M", "ออกแบบตารางเชื่อม (junction table)", "อ่าน ER diagram"],
  """
| ความสัมพันธ์ | ตัวอย่าง | วิธีทำ |
|---|---|---|
| **1:N** (one-to-many) | ลูกค้า 1 คน → หลายคำสั่งซื้อ | FK อยู่ฝั่ง "many" (`orders.customer_id`) |
| **N:M** (many-to-many) | playlist ↔ track | ตารางเชื่อม `playlist_tracks(playlist_id, track_id)` |
| **1:1** | user ↔ user_profile | FK + UNIQUE หรือใช้ PK เดียวกัน |
| **Self-referencing** | employee → manager | FK ชี้ตารางตัวเอง |

### อ่าน ER Diagram (crow's foot)
`||--o{` อ่านว่า "หนึ่ง (บังคับ) ต่อ ศูนย์หรือหลาย" — ดูได้ในหน้า **Databases** ของทุก sample DB
""",
  [E("N:M — เพลงใน playlist", """SELECT pl.name AS playlist, COUNT(pt.track_id) AS tracks
FROM playlists pl
LEFT JOIN playlist_tracks pt ON pt.playlist_id = pl.id
GROUP BY pl.name
ORDER BY tracks DESC;""", ["playlist_tracks เป็นตารางเชื่อม", "LEFT JOIN ทำให้ 'Empty Playlist' แสดงเป็น 0"], db="music_store")],
  [M("เก็บ N:M เป็นข้อความคั่นด้วย comma", "playlists.track_ids = '1,5,9'", "ตาราง playlist_tracks(playlist_id, track_id)",
     "JOIN ไม่ได้ ไม่มี FK และค้นหายาก")],
  ["foreign-key", "normalization", "db-design"]),

L("normalization", "Database Normalization — ลดความซ้ำซ้อน",
  "Normal forms 1NF–3NF, ปัญหา update anomaly และเมื่อไหร่ควร denormalize",
  ["อธิบาย 1NF, 2NF, 3NF", "ระบุ anomaly จากข้อมูลซ้ำซ้อน", "รู้ trade-off ของ denormalization"],
  """
**Normalization** คือการแยกตารางเพื่อให้ "ข้อเท็จจริงแต่ละอย่างถูกเก็บที่เดียว"

| Normal Form | กฎ | ตัวอย่างที่ผิด |
|---|---|---|
| **1NF** | ค่าในช่องเป็นค่าเดี่ยว (atomic), ไม่มีกลุ่มซ้ำ | `phones = '081..., 089...'` |
| **2NF** | 1NF + ทุกคอลัมน์ขึ้นกับ **ทั้ง** PK (สำหรับ composite key) | `order_items(order_id, product_id, product_name)` — product_name ขึ้นกับ product_id อย่างเดียว |
| **3NF** | 2NF + ไม่มี transitive dependency | `employees(dept_id, dept_name)` — dept_name ขึ้นกับ dept_id ไม่ใช่ employee |

### Anomalies เมื่อไม่ normalize
- **Update**: เปลี่ยนชื่อแผนกต้องแก้หลายแถว ลืมแถวเดียวข้อมูลขัดกัน
- **Insert**: เพิ่มแผนกใหม่ไม่ได้จนกว่าจะมีพนักงาน
- **Delete**: ลบพนักงานคนสุดท้ายแล้วข้อมูลแผนกหายไปด้วย

### Denormalization อย่างตั้งใจ
`order_items.unit_price` เก็บราคา ณ วันซื้อ (ไม่ใช่ลอกจาก products) — เพราะราคาสินค้าเปลี่ยนได้แต่ประวัติการขายต้องไม่เปลี่ยน
Data warehouse ก็ denormalize เพื่อให้ query วิเคราะห์เร็ว
""",
  [E("ตรวจข้อมูลซ้ำซ้อนที่เป็นปัญหา: ชื่อเมืองไม่สม่ำเสมอ", """SELECT LOWER(TRIM(city)) AS normalized, array_agg(DISTINCT city) AS variants, COUNT(*) AS customers
FROM customers
WHERE city IS NOT NULL
GROUP BY 1
HAVING COUNT(DISTINCT city) > 1;""", ["ข้อความอิสระทำให้ 'Bangkok' กับ 'bangkok' เป็นคนละค่า",
                                        "ทางแก้แบบ normalize: ตาราง cities แล้วให้ customers อ้าง city_id"]),
   E("ราคา ณ วันขาย ≠ ราคาปัจจุบัน (denormalization ที่ถูกต้อง)", """SELECT p.name, p.price AS current_price, MIN(oi.unit_price) AS min_sold, MAX(oi.unit_price) AS max_sold
FROM order_items oi JOIN products p ON p.id = oi.product_id
GROUP BY p.name, p.price
HAVING MIN(oi.unit_price) <> p.price
ORDER BY p.name
LIMIT 5;""", ["ถ้าดึงราคาจาก products ตอนทำรายงาน ยอดขายปีก่อนจะผิด"])],
  [M("normalize มากเกินจนทุกอย่างต้อง JOIN 10 ตาราง", "แยก first_name, last_name ไปตารางละคอลัมน์", "normalize ถึง 3NF แล้วพิจารณาตามการใช้งานจริง",
     "ความซับซ้อนเพิ่มโดยไม่ได้ประโยชน์")],
  ["db-relationships", "db-design"]),

L("transactions", "Transactions — ทำหลายคำสั่งแบบทั้งหมดหรือไม่ทำเลย",
  "ACID, ขอบเขตของ transaction และตัวอย่างการโอนเงินที่ต้องสำเร็จพร้อมกัน",
  ["อธิบาย ACID", "เขียน transaction ด้วย BEGIN ... COMMIT", "รู้จัก isolation level"],
  """
**Transaction** คือกลุ่มคำสั่งที่ต้อง **สำเร็จทั้งหมด หรือไม่เกิดผลเลย**

ตัวอย่าง: โอนเงิน 500 บาทจากบัญชี A → B ต้องมี 2 คำสั่ง ถ้าระบบล่มระหว่างกลาง เงินหายไม่ได้!

### ACID
| | ความหมาย |
|---|---|
| **A**tomicity | ทั้งหมดหรือไม่มีเลย |
| **C**onsistency | หลัง transaction ข้อมูลยังถูกตาม constraint |
| **I**solation | transaction ที่ทำพร้อมกันไม่เห็นข้อมูลครึ่ง ๆ กลาง ๆ ของกันและกัน |
| **D**urability | commit แล้วไม่หาย แม้ไฟดับ |

### Isolation levels (PostgreSQL)
`READ COMMITTED` (ค่าเริ่มต้น) · `REPEATABLE READ` · `SERIALIZABLE` — ระดับสูงปลอดภัยกว่าแต่อาจต้อง retry เมื่อชนกัน
""",
  [E("โอนเงินระหว่างบัญชีใน transaction", """BEGIN;
UPDATE accounts SET balance = balance - 500 WHERE id = 1;
UPDATE accounts SET balance = balance + 500 WHERE id = 2;
INSERT INTO transactions (account_id, txn_type, amount, txn_at, description)
VALUES (1, 'transfer_out', -500, now(), 'Transfer to acc 2'),
       (2, 'transfer_in',   500, now(), 'Transfer from acc 1');
COMMIT;

SELECT id, balance FROM accounts WHERE id IN (1, 2) ORDER BY id;""",
     ["`BEGIN` เริ่ม transaction", "หักบัญชี 1, เพิ่มบัญชี 2, บันทึกธุรกรรม 2 รายการ", "`COMMIT` ยืนยันทั้งหมดพร้อมกัน"], db="banking", writable=W)],
  [M("ทำทีละคำสั่งแบบ autocommit", "UPDATE ... -500; -- ระบบล่มตรงนี้\nUPDATE ... +500;", "BEGIN; UPDATE ...; UPDATE ...; COMMIT;",
     "เงินถูกหักแต่ไม่ถูกเพิ่ม")],
  ["commit-rollback", "update"]),

L("commit-rollback", "COMMIT, ROLLBACK และ SAVEPOINT",
  "ยืนยันหรือยกเลิก transaction และย้อนกลับบางส่วนด้วย SAVEPOINT",
  ["ใช้ COMMIT / ROLLBACK", "ใช้ SAVEPOINT และ ROLLBACK TO", "รู้พฤติกรรมเมื่อเกิด error กลาง transaction"],
  """
| คำสั่ง | ผล |
|---|---|
| `COMMIT` | บันทึกถาวร |
| `ROLLBACK` | ยกเลิกทุกอย่างตั้งแต่ BEGIN |
| `SAVEPOINT sp1` | จุดบันทึกย่อย |
| `ROLLBACK TO sp1` | ย้อนกลับไปที่จุดนั้น โดย transaction ยังดำเนินต่อ |

### เมื่อเกิด error ใน transaction (PostgreSQL)
transaction เข้าสถานะ *aborted* — ทุกคำสั่งต่อจากนั้นจะ error *current transaction is aborted* จนกว่าจะ `ROLLBACK` (หรือ ROLLBACK TO savepoint)

> ลองใน Playground โหมด Writable: เขียน `BEGIN; DELETE FROM ...; SELECT ...; ROLLBACK; SELECT ...;` แล้วดูผลแต่ละขั้นในแท็บผลลัพธ์
""",
  [E("ROLLBACK ยกเลิกการลบ", """BEGIN;
DELETE FROM order_items WHERE order_id = 1;
SELECT COUNT(*) AS items_inside_tx FROM order_items WHERE order_id = 1;
ROLLBACK;
SELECT COUNT(*) AS items_after_rollback FROM order_items WHERE order_id = 1;""",
     ["ภายใน transaction เห็นว่าลบแล้ว (0)", "หลัง ROLLBACK ข้อมูลกลับมาครบ"], writable=W),
   E("SAVEPOINT ย้อนกลับบางส่วน", """BEGIN;
UPDATE products SET stock = stock - 1 WHERE id = 1;
SAVEPOINT before_risky;
UPDATE products SET stock = stock - 1000 WHERE id = 2;
ROLLBACK TO before_risky;
COMMIT;
SELECT id, stock FROM products WHERE id IN (1, 2) ORDER BY id;""", ["การลดสต็อกของสินค้า 2 ถูกย้อนกลับ แต่สินค้า 1 ยังถูก commit"], writable=W)],
  [M("ลืม COMMIT", "BEGIN; UPDATE ...; -- แล้วปิดหน้าจอ", "BEGIN; UPDATE ...; COMMIT;",
     "การเชื่อมต่อปิดแล้ว transaction ถูก rollback อัตโนมัติ และระหว่างค้างอยู่จะถือ lock")],
  ["transactions", "delete"]),

L("indexes", "Indexes — ทำให้ค้นหาเร็วขึ้น",
  "หลักการทำงานของ B-tree index, เมื่อไหร่ควร/ไม่ควรสร้าง และ composite index",
  ["อธิบายว่า index ช่วยอย่างไร", "สร้าง index ทั่วไป, composite, partial, unique", "รู้ต้นทุนของ index"],
  """
**Index** เหมือนสารบัญท้ายหนังสือ — แทนที่จะอ่านทุกหน้า (Seq Scan) ฐานข้อมูลกระโดดไปยังแถวที่ต้องการ (Index Scan)

```sql
CREATE INDEX idx_orders_date ON orders (order_date);
CREATE INDEX idx_txn_acc_time ON transactions (account_id, txn_at);   -- composite
CREATE INDEX idx_orders_pending ON orders (order_date) WHERE status = 'pending';  -- partial
CREATE UNIQUE INDEX ux_customers_email ON customers (lower(email));    -- expression + unique
```
### ควรสร้างเมื่อ
- คอลัมน์ใน WHERE / JOIN / ORDER BY ที่ query บ่อย และ **คัดแถวได้น้อย** (high selectivity)
- คอลัมน์ FK

### ไม่ควร / ต้นทุน
- ทุก INSERT/UPDATE/DELETE ต้องอัปเดต index ด้วย → เขียนช้าลง, ใช้พื้นที่
- ตารางเล็กมาก หรือ query ที่ต้องอ่านเกือบทั้งตาราง → Seq Scan เร็วกว่า

### Composite index: ลำดับคอลัมน์สำคัญ
`(account_id, txn_at)` ช่วย `WHERE account_id = ?` และ `WHERE account_id = ? AND txn_at > ?` แต่ **ไม่ช่วย** `WHERE txn_at > ?` อย่างเดียว
""",
  [E("index ที่มีอยู่ใน ecommerce", """SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;""", ["PK และ UNIQUE สร้าง index ให้อัตโนมัติ", "idx_* คือ index ที่สร้างเพิ่มให้คอลัมน์ FK"]),
   E("สร้าง index แล้วดูว่า planner ใช้", """CREATE INDEX idx_customers_email_lower ON customers (lower(email));
ANALYZE customers;
EXPLAIN SELECT * FROM customers WHERE lower(email) = 'somchai.s.dup@example.com';""",
     ["expression index บน lower(email)", "EXPLAIN แสดงว่าใช้ Index Scan / Bitmap Index Scan บน index ใหม่"], writable=W)],
  [M("ใช้ฟังก์ชันกับคอลัมน์ที่มี index ธรรมดา", "WHERE lower(email) = '...' -- มีแค่ index บน email",
     "CREATE INDEX ... ON customers (lower(email))", "index บน email ใช้กับนิพจน์ lower(email) ไม่ได้"),
   M("สร้าง index ทุกคอลัมน์", "CREATE INDEX ... (สิบกว่าตัว)", "สร้างตาม query ที่ใช้จริง และวัดผลด้วย EXPLAIN",
     "เขียนข้อมูลช้าลงมากและเปลืองพื้นที่")],
  ["explain", "query-optimization"]),

L("explain", "EXPLAIN — ดูแผนการทำงานของ query",
  "อ่านผลลัพธ์ EXPLAIN และ EXPLAIN ANALYZE: node, cost, rows, actual time",
  ["รัน EXPLAIN และ EXPLAIN ANALYZE", "อ่าน cost / rows / actual time", "เปรียบเทียบ estimated vs actual rows"],
  """
```sql
EXPLAIN SELECT ...;                  -- แผนที่ planner คาดการณ์ (ไม่รันจริง)
EXPLAIN ANALYZE SELECT ...;          -- รันจริง + เวลาที่ใช้จริง
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;  -- + จำนวน page ที่อ่าน
```
ตัวอย่างบรรทัด:
```
Seq Scan on orders  (cost=0.00..19.25 rows=79 width=40) (actual time=0.010..0.150 rows=79 loops=1)
```
| ส่วน | ความหมาย |
|---|---|
| `Seq Scan on orders` | ชนิด node และตาราง |
| `cost=0.00..19.25` | ต้นทุนก่อนได้แถวแรก..ต้นทุนรวม (หน่วยสมมติ) |
| `rows=79` | จำนวนแถวที่ **คาดว่า** จะได้ |
| `actual time=...` | เวลาจริง (ms) — มีเฉพาะ ANALYZE |
| `loops` | node นี้ทำงานกี่รอบ |

> ⚠️ `EXPLAIN ANALYZE` **รันคำสั่งจริง** — กับ UPDATE/DELETE ให้ห่อด้วย `BEGIN ... ROLLBACK`
""",
  [E("แผนของ query กรองด้วยสถานะ", """EXPLAIN ANALYZE
SELECT id, order_date FROM orders WHERE status = 'cancelled';""", ["ไม่มี index บน status → Seq Scan + Filter",
                                                                  "ดู `Rows Removed by Filter` ว่าทิ้งไปกี่แถว"]),
   E("แผนของ JOIN + GROUP BY", """EXPLAIN
SELECT c.city, COUNT(*)
FROM orders o JOIN customers c ON c.id = o.customer_id
GROUP BY c.city;""", ["อ่านจากด้านในสุด (ย่อหน้าลึกสุด) ขึ้นมา", "Hash Join: สร้าง hash table จากตารางเล็ก แล้วสแกนตารางใหญ่",
                     "HashAggregate: จัดกลุ่มด้วย hash"])],
  [M("ดูแค่ cost แล้วสรุปว่าเร็ว", "EXPLAIN SELECT ...", "EXPLAIN ANALYZE SELECT ...",
     "cost คือค่าประมาณ ถ้าสถิติเก่า ค่าประมาณผิดได้มาก ต้องดู actual time/rows")],
  ["execution-plan", "indexes"]),

L("execution-plan", "Query Execution Plan — node ที่พบบ่อย",
  "เข้าใจ Scan, Join และ Aggregate node แต่ละแบบ และอ่านแผนที่ซ้อนกันหลายชั้น",
  ["รู้จัก Seq/Index/Bitmap/Index Only Scan", "รู้จัก Nested Loop/Hash/Merge Join", "ระบุจุดคอขวดในแผน"],
  """
### Scan nodes
| Node | เมื่อไหร่ |
|---|---|
| **Seq Scan** | อ่านทั้งตาราง — ตารางเล็ก หรือดึงแถวจำนวนมาก |
| **Index Scan** | ใช้ index หาแถวไม่กี่แถวแล้วไปอ่านตาราง |
| **Index Only Scan** | ข้อมูลทั้งหมดอยู่ใน index ไม่ต้องอ่านตาราง (เร็วมาก) |
| **Bitmap Heap Scan** | ได้แถวจำนวนปานกลางจาก index — รวม page ก่อนอ่าน |

### Join nodes
| Node | เหมาะกับ |
|---|---|
| **Nested Loop** | ด้านนอกมีไม่กี่แถว + ด้านในมี index |
| **Hash Join** | equi-join ขนาดกลาง–ใหญ่ ไม่มีลำดับ |
| **Merge Join** | ทั้งสองฝั่งเรียงตาม key อยู่แล้ว |

### อ่านแผนอย่างไร
1. ด้านในสุด (ย่อหน้าลึกสุด) ทำก่อน
2. หา node ที่ `actual time` มากสุด
3. เทียบ `rows` (คาดการณ์) กับ `actual rows` — ต่างกันมาก = สถิติผิด → `ANALYZE table`
""",
  [E("Index Scan บน primary key", """EXPLAIN ANALYZE SELECT * FROM transactions WHERE id = 100;""", ["PK มี index → Index Scan อ่านแค่แถวเดียว"], db="banking"),
   E("Composite index กับ ORDER BY", """EXPLAIN ANALYZE
SELECT txn_at, amount FROM transactions
WHERE account_id = 10
ORDER BY txn_at DESC
LIMIT 5;""", ["index `(account_id, txn_at)` ทำให้ได้แถวเรียงแล้ว ไม่ต้อง Sort", "ดู node `Index Scan Backward`"], db="banking")],
  [M("บังคับปิด Seq Scan ใน production", "SET enable_seqscan = off;", "แก้ที่ index/สถิติ/query",
     "ใช้เพื่อทดลองเท่านั้น planner มักรู้ดีกว่าเมื่อสถิติถูกต้อง")],
  ["explain", "query-optimization", "indexes"]),

L("query-optimization", "Query Optimization — ทำให้ query เร็วขึ้น",
  "เทคนิคปรับปรุงประสิทธิภาพที่ใช้ได้จริง: sargable predicates, เลือกคอลัมน์, pre-aggregate, EXISTS",
  ["เขียนเงื่อนไขแบบ sargable", "ลดข้อมูลก่อน JOIN", "ตรวจผลด้วย EXPLAIN ANALYZE ก่อน–หลัง"],
  """
### Checklist
1. **วัดก่อนเสมอ** — `EXPLAIN (ANALYZE, BUFFERS)` ก่อนและหลังแก้
2. **Sargable predicate** — อย่าห่อคอลัมน์ด้วยฟังก์ชันใน WHERE
   - ❌ `WHERE EXTRACT(YEAR FROM order_date) = 2025`
   - ✅ `WHERE order_date >= '2025-01-01' AND order_date < '2026-01-01'`
3. **เลือกเฉพาะคอลัมน์ที่ใช้** — ลด I/O และเปิดโอกาส Index Only Scan
4. **กรองก่อน JOIN / aggregate ก่อน JOIN** — ลดจำนวนแถวที่ต้องจับคู่ ป้องกัน fan-out
5. **EXISTS แทน IN/DISTINCT** สำหรับ semi-join ขนาดใหญ่
6. **Index ให้ตรงกับ query** (composite ตามลำดับ WHERE → ORDER BY)
7. **Keyset pagination** แทน OFFSET ใหญ่ ๆ
8. **อัปเดตสถิติ** `ANALYZE` หลังโหลดข้อมูลจำนวนมาก
""",
  [E("Sargable vs non-sargable (ดู Index Cond vs Filter)", """EXPLAIN
SELECT * FROM transactions
WHERE account_id = 10 AND txn_at >= '2025-01-01' AND txn_at < '2026-01-01';""",
     ["เงื่อนไขช่วงบนคอลัมน์ดิบ → อยู่ใน `Index Cond` ใช้ index ได้เต็มที่",
      "ลองเปลี่ยนเป็น `EXTRACT(YEAR FROM txn_at) = 2025` แล้วเทียบ — จะกลายเป็น Filter"], db="banking"),
   E("Pre-aggregate ก่อน JOIN", """WITH item_totals AS (
  SELECT order_id, SUM(unit_price * quantity) AS items_total
  FROM order_items GROUP BY order_id
), pay_totals AS (
  SELECT order_id, SUM(amount) AS paid FROM payments GROUP BY order_id
)
SELECT o.status, COUNT(*) AS orders, SUM(i.items_total) AS items_total, SUM(p.paid) AS paid
FROM orders o
JOIN item_totals i ON i.order_id = o.id
LEFT JOIN pay_totals p ON p.order_id = o.id
GROUP BY o.status
ORDER BY o.status;""", ["สรุปแต่ละตาราง 1:N เหลือ 1 แถวต่อ order ก่อน", "แล้ว JOIN — ไม่มีแถวคูณกัน ยอดถูกต้องและเร็วกว่า"])],
  [M("SELECT * ในรายงาน", "SELECT * FROM orders o JOIN order_items ...", "SELECT o.id, o.order_date, oi.quantity ...",
     "ดึงข้อมูลที่ไม่ใช้ เปลือง I/O และเครือข่าย"),
   M("ห่อคอลัมน์ด้วยฟังก์ชัน", "WHERE DATE(order_date) = '2025-03-01'", "WHERE order_date >= '2025-03-01' AND order_date < '2025-03-02'",
     "ใช้ index บน order_date ไม่ได้")],
  ["explain", "indexes", "advanced-techniques"]),

L("db-design", "Database Design Fundamentals — ออกแบบฐานข้อมูลตั้งแต่ศูนย์",
  "กระบวนการออกแบบ: ความต้องการ → entity → ความสัมพันธ์ → ตาราง → constraint → index",
  ["ออกแบบ schema จากความต้องการธุรกิจ", "ตั้งชื่อตาราง/คอลัมน์อย่างสม่ำเสมอ", "ตรวจแบบด้วย checklist"],
  """
### ขั้นตอน
1. **เข้าใจธุรกิจ** — มีใคร ทำอะไร เก็บอะไร ถามคำถามอะไรกับข้อมูล
2. **ระบุ Entity** (คำนาม) → ตาราง: ลูกค้า, สินค้า, คำสั่งซื้อ
3. **ระบุ Attribute** → คอลัมน์ + data type
4. **ระบุ Relationship** → 1:N ใส่ FK, N:M สร้างตารางเชื่อม
5. **Normalize ถึง 3NF** แล้ว denormalize อย่างมีเหตุผล (เช่นราคา ณ วันขาย)
6. **Constraints** — PK, FK, NOT NULL, UNIQUE, CHECK
7. **Index** — ตาม query ที่ใช้จริง + FK
8. **ทดสอบ** ด้วยคำถามธุรกิจจริง: query ที่ต้องเขียนง่ายและเร็วไหม

### Naming conventions
- ชื่อตารางพหูพจน์ `snake_case`: `order_items`
- PK ชื่อ `id`, FK ชื่อ `<entity>_id`: `customer_id`
- วันเวลาลงท้าย `_at` (`created_at`), boolean ขึ้นต้น `is_`/`has_`
- มี `created_at` / `updated_at` เกือบทุกตาราง

### ฝึกปฏิบัติ
ใน Writable sandbox ลองออกแบบระบบ **รีวิวสินค้า**: reviews (1 ลูกค้ารีวิวสินค้าเดียวกันได้ครั้งเดียว, คะแนน 1–5)
""",
  [E("ออกแบบตาราง product_reviews พร้อม constraint ครบ", """CREATE TABLE product_reviews (
  id           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_id   integer NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  customer_id  integer NOT NULL REFERENCES customers(id),
  rating       smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body         text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_one_review_per_customer UNIQUE (product_id, customer_id)
);
CREATE INDEX idx_reviews_customer ON product_reviews (customer_id);

INSERT INTO product_reviews (product_id, customer_id, rating, body)
VALUES (1, 1, 5, 'ดีมาก'), (1, 2, 4, NULL), (2, 1, 3, 'พอใช้');

SELECT p.name, COUNT(*) AS reviews, ROUND(AVG(r.rating), 2) AS avg_rating
FROM product_reviews r JOIN products p ON p.id = r.product_id
GROUP BY p.name;""", ["FK 2 ตัวเชื่อมสินค้าและลูกค้า", "CHECK บังคับคะแนน 1–5", "UNIQUE (product_id, customer_id) = รีวิวได้ครั้งเดียว",
                       "index บน FK customer_id (product_id ถูกครอบด้วย unique index แล้ว)", "ทดสอบด้วยข้อมูลและ query จริง"], writable=W)],
  [M("เก็บหลายค่าในคอลัมน์เดียว", "tags text -- 'sale,new,hot'", "ตาราง product_tags(product_id, tag)", "ผิด 1NF ค้นหาและนับยาก")],
  ["normalization", "db-relationships", "constraints"]),
]
