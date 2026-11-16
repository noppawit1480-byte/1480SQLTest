from app.content.model import Example as E
from app.content.model import LessonDef as L
from app.content.model import Mistake as M

LESSONS = [
L("intro-to-sql", "Introduction to SQL — SQL คืออะไร",
  "รู้จักภาษา SQL ภาษามาตรฐานสำหรับสื่อสารกับฐานข้อมูลเชิงสัมพันธ์ และวิธีใช้แพลตฟอร์มนี้ฝึกเขียน",
  ["อธิบายได้ว่า SQL คืออะไรและใช้ทำอะไร", "รู้จักกลุ่มคำสั่ง DQL, DML, DDL, DCL, TCL",
   "รัน SQL คำสั่งแรกใน Playground ได้"],
  """
**SQL (Structured Query Language)** อ่านว่า "เอส-คิว-แอล" หรือ "ซีเควล" เป็นภาษามาตรฐาน (ANSI/ISO) ที่ใช้
**ถาม (query)** และ **จัดการ** ข้อมูลในฐานข้อมูลเชิงสัมพันธ์ (Relational Database) เช่น PostgreSQL, MySQL, SQL Server, Oracle และ SQLite

SQL เป็นภาษาแบบ **Declarative** — เราบอกแค่ว่า *"อยากได้ข้อมูลอะไร"* ไม่ต้องบอกว่า *"ต้องหาอย่างไร"*
ฐานข้อมูลจะมี **Query Planner** คิดวิธีที่เร็วที่สุดให้เอง ต่างจากภาษาโปรแกรมทั่วไปที่ต้องเขียนลูปเอง

### กลุ่มคำสั่งของ SQL
| กลุ่ม | ย่อมาจาก | คำสั่งตัวอย่าง | ใช้ทำอะไร |
|---|---|---|---|
| DQL | Data Query Language | `SELECT` | อ่าน/ค้นหาข้อมูล |
| DML | Data Manipulation Language | `INSERT`, `UPDATE`, `DELETE` | เพิ่ม/แก้/ลบข้อมูล |
| DDL | Data Definition Language | `CREATE`, `ALTER`, `DROP` | สร้าง/แก้โครงสร้างตาราง |
| DCL | Data Control Language | `GRANT`, `REVOKE` | กำหนดสิทธิ์ |
| TCL | Transaction Control Language | `BEGIN`, `COMMIT`, `ROLLBACK` | ควบคุม transaction |

### ใครใช้ SQL บ้าง
- **Data Analyst** — ดึงยอดขาย วิเคราะห์พฤติกรรมลูกค้า ทำรายงาน
- **Backend / Database Developer** — ออกแบบตาราง เขียน query ให้แอปพลิเคชัน
- **BI / Data Engineer** — สร้าง data pipeline, data warehouse

### แพลตฟอร์มนี้ใช้ PostgreSQL จริง
ทุกตัวอย่างในบทเรียนถูกรันบน **PostgreSQL 16** จริง และผลลัพธ์ที่เห็นคือผลลัพธ์จริง
กดปุ่ม **Try it** เพื่อเปิดตัวอย่างใน Playground แล้วลองแก้ไขได้ทันที — ไม่ต้องกลัวพัง เพราะโหมดเริ่มต้นเป็น **Read-only**
""",
  [E("SQL คำสั่งแรก", "SELECT 'Hello, SQL!' AS greeting, 1 + 1 AS answer;",
     ["`SELECT` สั่งให้ฐานข้อมูลคืนค่าออกมา", "`'Hello, SQL!'` คือข้อความ (string) ต้องอยู่ใน single quote",
      "`AS greeting` ตั้งชื่อคอลัมน์ผลลัพธ์", "`1 + 1` ฐานข้อมูลคำนวณให้ได้เลย", "`;` ปิดท้ายคำสั่ง"]),
   E("ดูข้อมูลลูกค้า 5 คนแรก", "SELECT * FROM customers LIMIT 5;",
     ["`SELECT *` เลือกทุกคอลัมน์", "`FROM customers` จากตาราง customers", "`LIMIT 5` เอาแค่ 5 แถว"])],
  [M("ใช้ double quote กับข้อความ", "SELECT \"Hello\";", "SELECT 'Hello';",
     "ใน PostgreSQL double quote ใช้กับ **ชื่อ** (identifier) เช่นชื่อคอลัมน์ ส่วนข้อความต้องใช้ single quote"),
   M("ลืมว่า SQL ไม่สนตัวพิมพ์ของ keyword แต่สนข้อมูล", "SELECT * FROM customers WHERE city = 'BANGKOK';",
     "SELECT * FROM customers WHERE city = 'Bangkok';",
     "`select` กับ `SELECT` เหมือนกัน แต่ค่าข้อความ `'Bangkok'` กับ `'BANGKOK'` ไม่เท่ากัน")],
  ["what-is-database", "select"]),

L("what-is-database", "What is Database? — ฐานข้อมูลคืออะไร",
  "เข้าใจแนวคิดฐานข้อมูล, DBMS, ฐานข้อมูลเชิงสัมพันธ์ และความต่างจากการเก็บข้อมูลใน Excel",
  ["อธิบายความหมายของ Database และ DBMS", "เข้าใจข้อดีของฐานข้อมูลเชิงสัมพันธ์เทียบกับไฟล์ spreadsheet",
   "รู้จัก sample databases ทั้ง 5 ของแพลตฟอร์ม"],
  """
**Database (ฐานข้อมูล)** คือแหล่งเก็บข้อมูลที่จัดระเบียบไว้อย่างเป็นระบบ เพื่อให้ **ค้นหา เพิ่ม แก้ไข ลบ** ได้อย่างมีประสิทธิภาพ
ส่วน **DBMS (Database Management System)** คือซอฟต์แวร์ที่บริหารฐานข้อมูล เช่น PostgreSQL

### Relational Database (ฐานข้อมูลเชิงสัมพันธ์)
เก็บข้อมูลเป็น **ตาราง (table)** หลายตาราง และเชื่อมกันด้วย **key** เช่น `orders.customer_id` อ้างถึง `customers.id`

### ทำไมไม่ใช้ Excel?
| เรื่อง | Spreadsheet | Relational Database |
|---|---|---|
| ข้อมูลจำนวนมาก | ช้าเมื่อหลักแสนแถว | รองรับหลักล้าน–พันล้านแถว |
| หลายคนแก้พร้อมกัน | ชนกันง่าย | มี Transaction & Locking |
| ความถูกต้อง | พิมพ์อะไรก็ได้ | มี Data Type, Constraint, Foreign Key |
| ข้อมูลซ้ำซ้อน | copy ข้อมูลลูกค้าทุกแถว | แยกตาราง อ้างอิงด้วย key |
| ความปลอดภัย | ทั้งไฟล์ | กำหนดสิทธิ์ระดับตาราง/คอลัมน์ |

### Sample databases ในแพลตฟอร์มนี้
- **ecommerce** — ร้านค้าออนไลน์: customers, products, categories, orders, order_items, payments
- **hr** — บริหารบุคคล: employees, departments, positions, salaries
- **banking** — ธนาคาร: customers, accounts, transactions, loans
- **hospital** — โรงพยาบาล: patients, doctors, appointments, treatments
- **music_store** — ร้านเพลง: artists, albums, tracks, playlists, invoices, invoice_items

ดู ER Diagram ของแต่ละฐานข้อมูลได้ที่เมนู **Databases**
""",
  [E("ฐานข้อมูลนี้มีตารางอะไรบ้าง", """SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;""",
     ["`information_schema` คือชุด view มาตรฐานที่อธิบายโครงสร้างฐานข้อมูล", "`tables` เก็บรายชื่อตารางทั้งหมด",
      "`table_schema = 'public'` เอาเฉพาะตารางของเรา ไม่เอาตารางระบบ", "`ORDER BY table_name` เรียงตามชื่อ"])],
  [M("คิดว่า Database = ตาราง", "-- \"ฐานข้อมูล customers\"", "-- \"ตาราง customers ในฐานข้อมูล ecommerce\"",
     "ฐานข้อมูล 1 ตัวมีได้หลายตาราง ตารางคือส่วนหนึ่งของฐานข้อมูล")],
  ["intro-to-sql", "what-is-table", "db-relationships"]),

L("what-is-table", "What is Table? — ตาราง แถว และคอลัมน์",
  "เข้าใจโครงสร้างตาราง: column, row, data type, primary key และ foreign key",
  ["อธิบาย Row, Column, Data Type ได้", "เข้าใจ Primary Key และ Foreign Key เบื้องต้น",
   "อ่านโครงสร้างตารางจาก Database Explorer ได้"],
  """
ตาราง (Table) ประกอบด้วย
- **Column (คอลัมน์ / field)** — คุณลักษณะของข้อมูล เช่น `first_name`, `email` แต่ละคอลัมน์มี **Data Type** กำหนด
- **Row (แถว / record)** — ข้อมูล 1 รายการ เช่นลูกค้า 1 คน

### Data Type ที่พบบ่อยใน PostgreSQL
| Type | ความหมาย | ตัวอย่าง |
|---|---|---|
| `integer` / `bigint` | จำนวนเต็ม | 42 |
| `numeric(10,2)` | ทศนิยมแม่นยำ (เหมาะกับเงิน) | 1990.50 |
| `varchar(n)` / `text` | ข้อความ | 'Bangkok' |
| `date` / `timestamp` | วันที่ / วันที่+เวลา | '2025-01-31' |
| `boolean` | จริง/เท็จ | true |

### Key
- **Primary Key (PK)** — คอลัมน์ที่ระบุแต่ละแถวได้ไม่ซ้ำ เช่น `customers.id` 🔑
- **Foreign Key (FK)** — คอลัมน์ที่อ้างถึง PK ของอีกตาราง เช่น `orders.customer_id → customers.id`

ใน Playground ด้านซ้าย (Database Explorer) จะเห็นไอคอน 🔑 สำหรับ PK และ ↗ สำหรับ FK
""",
  [E("ดูคอลัมน์และชนิดข้อมูลของตาราง products", """SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'products'
ORDER BY ordinal_position;""",
     ["`information_schema.columns` เก็บข้อมูลทุกคอลัมน์", "`table_name = 'products'` เฉพาะตาราง products",
      "`is_nullable` บอกว่าคอลัมน์นี้ว่าง (NULL) ได้หรือไม่", "`ordinal_position` ลำดับคอลัมน์ตามที่สร้าง"]),
   E("ดูตัวอย่างข้อมูลสินค้า", "SELECT * FROM products LIMIT 5;", ["แต่ละแถวคือสินค้า 1 รายการ แต่ละคอลัมน์คือคุณสมบัติของสินค้า"])],
  [M("เก็บราคาเป็น float", "price float", "price numeric(10,2)",
     "float มีความคลาดเคลื่อนจากการปัดเศษฐานสอง ส่วน numeric แม่นยำ เหมาะกับข้อมูลการเงิน")],
  ["what-is-database", "primary-key", "foreign-key"]),

L("select", "SELECT — เลือกคอลัมน์ที่ต้องการ",
  "คำสั่งพื้นฐานที่สุดของ SQL: เลือกคอลัมน์, ตั้งชื่อด้วย AS และคำนวณค่าใหม่",
  ["เลือกเฉพาะคอลัมน์ที่ต้องการแทน SELECT *", "ตั้งชื่อคอลัมน์ผลลัพธ์ด้วย AS (alias)",
   "สร้างคอลัมน์คำนวณ (computed column)"],
  """
```sql
SELECT column1, column2, expression AS alias
FROM table_name;
```
- ระบุชื่อคอลัมน์คั่นด้วย `,` — ผลลัพธ์จะเรียงคอลัมน์ตามที่เราเขียน
- `SELECT *` ดึงทุกคอลัมน์ — สะดวกตอนสำรวจข้อมูล แต่ในงานจริง **ควรระบุคอลัมน์** เพื่อลดข้อมูลที่ส่งผ่านเครือข่าย และไม่พังเมื่อมีคนเพิ่มคอลัมน์
- **Alias** `AS ชื่อใหม่` เปลี่ยนชื่อคอลัมน์ในผลลัพธ์ (ไม่เปลี่ยนในตารางจริง) ถ้าชื่อมีช่องว่างให้ครอบด้วย double quote: `AS "Unit Price"`
- คำนวณได้ทั้ง `+ - * /` และต่อข้อความด้วย `||`

> 💡 ลำดับการทำงานจริงของ SQL ไม่ใช่ลำดับที่เขียน: `FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT`
""",
  [E("เลือกบางคอลัมน์และตั้ง alias", """SELECT name, price, cost, price - cost AS profit_per_unit
FROM products
LIMIT 8;""",
     ["`name, price, cost` เลือก 3 คอลัมน์จากตาราง", "`price - cost` คำนวณกำไรต่อชิ้นทุกแถว",
      "`AS profit_per_unit` ตั้งชื่อคอลัมน์ที่คำนวณได้", "`LIMIT 8` แสดง 8 แถวแรก"]),
   E("ต่อข้อความชื่อ-นามสกุล", """SELECT first_name || ' ' || last_name AS full_name, email
FROM customers
LIMIT 5;""", ["`||` คือตัวต่อข้อความ (concatenate) ของ PostgreSQL", "`' '` ใส่ช่องว่างระหว่างชื่อกับนามสกุล"])],
  [M("ใส่ comma เกินหลังคอลัมน์สุดท้าย", "SELECT name, price, FROM products;", "SELECT name, price FROM products;",
     "comma หลังคอลัมน์สุดท้ายทำให้เกิด syntax error at or near \"FROM\""),
   M("ใช้ alias ใน WHERE", "SELECT price - cost AS profit FROM products WHERE profit > 1000;",
     "SELECT price - cost AS profit FROM products WHERE price - cost > 1000;",
     "WHERE ทำงานก่อน SELECT จึงยังไม่รู้จัก alias `profit`")],
  ["from", "where", "order-by"]),

L("from", "FROM — ระบุแหล่งข้อมูล",
  "FROM บอกว่าจะดึงข้อมูลจากตารางไหน รวมถึงการตั้ง table alias ที่ใช้บ่อยในงานจริง",
  ["ระบุตารางด้วย FROM", "ตั้ง table alias และอ้างคอลัมน์แบบ alias.column", "รู้ว่า FROM ทำงานเป็นลำดับแรก"],
  """
`FROM` คือส่วนที่ระบุ **แหล่งข้อมูล** ของ query — อาจเป็นตาราง, view, subquery หรือผลของการ JOIN

```sql
SELECT p.name, p.price
FROM products AS p;      -- p คือ table alias (AS ละได้: FROM products p)
```
- **Table alias** ทำให้ query สั้นลง และจำเป็นมากเมื่อมีหลายตารางที่มีคอลัมน์ชื่อซ้ำกัน (เช่น `id`)
- ถ้าตั้ง alias แล้ว ต้องอ้างด้วย alias เท่านั้น (`p.name` ไม่ใช่ `products.name`)
- `FROM` เป็นขั้นตอนแรกที่ฐานข้อมูลประมวลผล — ทุกอย่างหลังจากนี้ทำงานบนแถวที่ได้จาก FROM

### Schema
ชื่อตารางเต็มคือ `schema.table` เช่น `public.products` — ในแพลตฟอร์มนี้ทุกตารางอยู่ใน schema `public` จึงละได้
""",
  [E("ใช้ table alias", """SELECT c.id, c.first_name, c.city
FROM customers AS c
LIMIT 5;""", ["`customers AS c` ตั้งชื่อย่อตารางว่า c", "`c.id` อ้างคอลัมน์ id ของตาราง c"]),
   E("SELECT จาก subquery ใน FROM (preview)", """SELECT t.name, t.price
FROM (SELECT name, price FROM products WHERE price > 20000) AS t;""",
     ["วงเล็บด้านในสร้าง 'ตารางชั่วคราว' ของสินค้าราคาเกิน 20,000", "ต้องตั้ง alias ให้ subquery (`AS t`)",
      "เรียนเรื่องนี้ละเอียดในบท Subqueries"])],
  [M("ตั้ง alias แล้วยังใช้ชื่อเต็ม", "SELECT products.name FROM products p;", "SELECT p.name FROM products p;",
     "เมื่อตั้ง alias ชื่อเต็มจะใช้ไม่ได้: missing FROM-clause entry for table \"products\""),
   M("พิมพ์ชื่อตารางผิด", "SELECT * FROM product;", "SELECT * FROM products;",
     "ดูชื่อที่ถูกต้องใน Database Explorer — error: relation \"product\" does not exist")],
  ["select", "inner-join"]),

L("where", "WHERE — กรองแถวด้วยเงื่อนไข",
  "กรองข้อมูลด้วยตัวดำเนินการเปรียบเทียบ = <> < > <= >= กับตัวเลข ข้อความ และวันที่",
  ["กรองแถวด้วย WHERE", "ใช้ comparison operators กับตัวเลข ข้อความ วันที่", "เข้าใจว่า WHERE ทำงานต่อแถว"],
  """
```sql
SELECT ... FROM table WHERE condition;
```
WHERE ตรวจเงื่อนไข **ทีละแถว** — แถวที่เงื่อนไขเป็น `TRUE` เท่านั้นที่จะผ่าน (ถ้าเป็น `FALSE` หรือ `NULL` จะถูกตัดทิ้ง)

| Operator | ความหมาย |
|---|---|
| `=` | เท่ากับ |
| `<>` หรือ `!=` | ไม่เท่ากับ |
| `<` `>` `<=` `>=` | น้อย/มากกว่า |

- **ข้อความ** ต้องอยู่ใน single quote และ **case-sensitive**: `'Bangkok' <> 'bangkok'`
- **วันที่** เขียนเป็นข้อความรูปแบบ ISO `'YYYY-MM-DD'` แล้ว PostgreSQL แปลงให้อัตโนมัติ
- `timestamp` เทียบกับ `'2025-01-01'` หมายถึง `2025-01-01 00:00:00`
""",
  [E("สินค้าราคาไม่เกิน 1,000 บาท", """SELECT name, price
FROM products
WHERE price <= 1000;""", ["`WHERE price <= 1000` เก็บเฉพาะแถวที่ราคาน้อยกว่าหรือเท่ากับ 1000"]),
   E("คำสั่งซื้อที่ถูกยกเลิก", """SELECT id, customer_id, order_date
FROM orders
WHERE status = 'cancelled'
LIMIT 10;""", ["เปรียบเทียบข้อความด้วย `=`", "ค่าต้องสะกดตรงทุกตัวอักษร"]),
   E("คำสั่งซื้อตั้งแต่ 1 ธ.ค. 2025", """SELECT id, order_date, status
FROM orders
WHERE order_date >= '2025-12-01'
LIMIT 10;""", ["วันที่เขียนแบบ ISO `'2025-12-01'`", "`>=` รวมตั้งแต่เที่ยงคืนวันที่ 1"])],
  [M("ใช้ = กับ NULL", "SELECT * FROM customers WHERE phone = NULL;", "SELECT * FROM customers WHERE phone IS NULL;",
     "NULL = อะไรก็ตามได้ NULL (ไม่ใช่ TRUE) จึงไม่มีแถวผ่าน — ดูบท NULL"),
   M("ลืม quote ข้อความ", "SELECT * FROM orders WHERE status = cancelled;", "SELECT * FROM orders WHERE status = 'cancelled';",
     "ไม่มี quote PostgreSQL จะคิดว่าเป็นชื่อคอลัมน์: column \"cancelled\" does not exist")],
  ["and-or-not", "between", "null"]),

L("order-by", "ORDER BY — เรียงลำดับผลลัพธ์",
  "เรียงผลลัพธ์จากน้อยไปมาก/มากไปน้อย หลายคอลัมน์ และจัดการตำแหน่งของ NULL",
  ["เรียงด้วย ASC/DESC", "เรียงหลายคอลัมน์", "ควบคุม NULLS FIRST/LAST"],
  """
ถ้าไม่ใส่ `ORDER BY` **ฐานข้อมูลไม่รับประกันลำดับ** ของผลลัพธ์เลย (ต่อให้ดูเหมือนเรียงตาม id ก็ตาม)

```sql
ORDER BY col1 [ASC|DESC] [NULLS FIRST|LAST], col2 ...
```
- `ASC` (ค่าเริ่มต้น) น้อย → มาก, `DESC` มาก → น้อย
- หลายคอลัมน์: เรียงคอลัมน์แรกก่อน ถ้าเท่ากันจึงดูคอลัมน์ถัดไป
- ใน PostgreSQL ค่า `NULL` ถือว่า "มากที่สุด" → อยู่ท้ายเมื่อ ASC, อยู่หน้าเมื่อ DESC — เปลี่ยนได้ด้วย `NULLS LAST/FIRST`
- ORDER BY ทำงาน **หลัง** SELECT จึงใช้ alias ได้
""",
  [E("สินค้าราคาแพงสุดก่อน", """SELECT name, price
FROM products
ORDER BY price DESC
LIMIT 5;""", ["`ORDER BY price DESC` เรียงราคามากไปน้อย", "`LIMIT 5` เอา 5 อันดับแรก"]),
   E("เรียงหลายคอลัมน์ + จัดการ NULL", """SELECT first_name, last_name, city
FROM customers
ORDER BY city NULLS LAST, last_name, first_name
LIMIT 10;""", ["เรียงตามเมืองก่อน ลูกค้าที่ไม่มีเมือง (NULL) ไปอยู่ท้ายสุด",
                 "ในเมืองเดียวกันเรียงตามนามสกุล แล้วตามชื่อ"])],
  [M("คิดว่าผลลัพธ์เรียงเองอัตโนมัติ", "SELECT * FROM orders LIMIT 5;", "SELECT * FROM orders ORDER BY order_date DESC LIMIT 5;",
     "ไม่มี ORDER BY = ลำดับไม่แน่นอน โดยเฉพาะเมื่อข้อมูลเปลี่ยนหรือมี index"),
   M("DESC ใช้กับทุกคอลัมน์", "ORDER BY city, last_name DESC", "ORDER BY city DESC, last_name DESC",
     "ASC/DESC มีผลเฉพาะคอลัมน์ที่อยู่ข้างหน้ามันเท่านั้น")],
  ["limit", "select"]),

L("limit", "LIMIT และ OFFSET — จำกัดจำนวนแถว",
  "เอาเฉพาะ N แถวแรก, ทำ pagination และหา Top-N",
  ["ใช้ LIMIT เพื่อจำกัดผลลัพธ์", "ใช้ OFFSET ทำ pagination", "รู้ว่าต้องใช้คู่กับ ORDER BY เสมอ"],
  """
```sql
SELECT ... ORDER BY ... LIMIT n OFFSET m;
```
- `LIMIT n` คืนไม่เกิน n แถว
- `OFFSET m` ข้าม m แถวแรก — ใช้ทำหน้าเพจ: หน้า p (เริ่ม 1) ขนาด s → `LIMIT s OFFSET (p-1)*s`
- มาตรฐาน SQL เขียนอีกแบบได้: `FETCH FIRST n ROWS ONLY` (PostgreSQL รองรับทั้งสองแบบ)
- **Top-N** = `ORDER BY ... DESC LIMIT N` — ต้องมี ORDER BY ไม่งั้น "Top" ไม่มีความหมาย

> ⚠️ OFFSET ขนาดใหญ่ช้า เพราะฐานข้อมูลยังต้องอ่านแถวที่ข้ามไป — ระบบจริงนิยม *keyset pagination* (`WHERE id > last_seen_id`)
""",
  [E("หน้า 2 ของรายการสินค้า (หน้าละ 5)", """SELECT id, name, price
FROM products
ORDER BY id
LIMIT 5 OFFSET 5;""", ["`ORDER BY id` ทำให้ลำดับคงที่", "`OFFSET 5` ข้าม 5 แถวแรก (หน้า 1)", "`LIMIT 5` เอา 5 แถวของหน้า 2"]),
   E("Top 3 คำสั่งซื้อล่าสุด (FETCH FIRST)", """SELECT id, order_date, status
FROM orders
ORDER BY order_date DESC
FETCH FIRST 3 ROWS ONLY;""", ["`FETCH FIRST 3 ROWS ONLY` เทียบเท่า `LIMIT 3` ตามมาตรฐาน SQL"])],
  [M("LIMIT โดยไม่มี ORDER BY", "SELECT name FROM products LIMIT 3; -- 'สินค้าแพงสุด 3 อันดับ'",
     "SELECT name FROM products ORDER BY price DESC LIMIT 3;", "ไม่มี ORDER BY ได้ 3 แถวไหนก็ได้")],
  ["order-by", "row-number"]),

L("distinct", "DISTINCT — ตัดค่าที่ซ้ำ",
  "แสดงเฉพาะค่าที่ไม่ซ้ำ ทั้งแบบคอลัมน์เดียวและหลายคอลัมน์ รวมถึง DISTINCT ON ของ PostgreSQL",
  ["ใช้ DISTINCT ตัดแถวซ้ำ", "เข้าใจว่า DISTINCT พิจารณาทุกคอลัมน์ใน SELECT", "รู้จัก COUNT(DISTINCT ...)"],
  """
`SELECT DISTINCT` ตัด **แถว** ที่ซ้ำกันทุกคอลัมน์ออกให้เหลือแถวเดียว

- `SELECT DISTINCT city FROM customers` → รายชื่อเมืองไม่ซ้ำ (NULL นับเป็น 1 ค่า)
- `SELECT DISTINCT city, country` → ตัดซ้ำจาก **คู่** (city, country)
- `COUNT(DISTINCT city)` → นับจำนวนค่าไม่ซ้ำ (ไม่นับ NULL)
- PostgreSQL มี `DISTINCT ON (col)` เลือก "แถวแรก" ของแต่ละกลุ่มตาม ORDER BY

> ข้อมูลจริงมักสกปรก: ใน `customers.city` มีทั้ง `'Bangkok'` และ `'bangkok'` — DISTINCT จะมองว่าเป็น 2 ค่า!
""",
  [E("เมืองที่มีลูกค้า (ไม่ซ้ำ)", """SELECT DISTINCT city
FROM customers
ORDER BY city;""", ["`DISTINCT city` เหลือเมืองละ 1 แถว", "สังเกต `bangkok` ตัวเล็ก และ NULL ที่ท้ายตาราง"]),
   E("DISTINCT ON — คำสั่งซื้อล่าสุดของลูกค้าแต่ละคน", """SELECT DISTINCT ON (customer_id) customer_id, id AS order_id, order_date
FROM orders
ORDER BY customer_id, order_date DESC
LIMIT 8;""", ["`DISTINCT ON (customer_id)` เก็บแถวแรกของแต่ละ customer_id",
               "ORDER BY ต้องขึ้นต้นด้วยคอลัมน์เดียวกับ DISTINCT ON", "`order_date DESC` ทำให้ 'แถวแรก' คือคำสั่งซื้อล่าสุด"])],
  [M("คิดว่า DISTINCT ใช้กับคอลัมน์แรกเท่านั้น", "SELECT DISTINCT city, first_name FROM customers;",
     "SELECT DISTINCT city FROM customers;", "DISTINCT ใช้กับทั้งแถว — ใส่ first_name ทำให้แทบไม่มีอะไรซ้ำ"),
   M("ใช้ DISTINCT ปิดปัญหา JOIN ผิด", "SELECT DISTINCT c.* FROM customers c JOIN orders o ON ...",
     "SELECT c.* FROM customers c WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);",
     "ถ้าได้แถวซ้ำเพราะ JOIN ควรแก้ที่ตรรกะ (เช่นใช้ EXISTS) แทนการโปะด้วย DISTINCT")],
  ["count", "group-by"]),

L("and-or-not", "AND, OR, NOT — รวมหลายเงื่อนไข",
  "สร้างเงื่อนไขซับซ้อนด้วยตัวดำเนินการตรรกะ และลำดับความสำคัญ (precedence) ที่มักพลาด",
  ["รวมเงื่อนไขด้วย AND / OR", "กลับเงื่อนไขด้วย NOT", "ใช้วงเล็บควบคุมลำดับการประเมินผล"],
  """
- `A AND B` — จริงเมื่อ **ทั้งสอง** จริง
- `A OR B` — จริงเมื่อ **อย่างน้อยหนึ่ง** จริง
- `NOT A` — กลับค่า

### ลำดับความสำคัญ: `NOT` > `AND` > `OR`
```sql
WHERE status = 'paid' OR status = 'shipped' AND shipping_city = 'Phuket'
-- ถูกตีความเป็น: status = 'paid' OR (status = 'shipped' AND shipping_city = 'Phuket')
```
**ใส่วงเล็บทุกครั้งที่ผสม AND กับ OR** เพื่อให้ตรงกับความตั้งใจและอ่านง่าย

### ตรรกะ 3 ค่า (Three-valued logic)
SQL มีค่า `TRUE`, `FALSE` และ `UNKNOWN` (เกิดจาก NULL) เช่น `NULL AND FALSE = FALSE` แต่ `NULL AND TRUE = UNKNOWN` → แถวไม่ผ่าน WHERE
""",
  [E("สินค้า Active ราคา 1,000–5,000 หรือหมวด 13", """SELECT name, price, category_id, is_active
FROM products
WHERE (price BETWEEN 1000 AND 5000 AND is_active)
   OR category_id = 13
ORDER BY price;""", ["วงเล็บแรก: ราคาอยู่ในช่วง **และ** ยังขายอยู่", "`is_active` เป็น boolean ใช้เป็นเงื่อนไขได้เลย",
                      "`OR category_id = 13` หรือเป็นหนังสือเขียนโปรแกรม"]),
   E("คำสั่งซื้อที่ไม่ใช่ delivered และไม่ใช่ cancelled", """SELECT id, status
FROM orders
WHERE NOT (status = 'delivered' OR status = 'cancelled')
LIMIT 10;""", ["`NOT (A OR B)` เท่ากับ `NOT A AND NOT B` (De Morgan's law)"])],
  [M("ลืมวงเล็บเมื่อผสม AND/OR", "WHERE city = 'Phuket' OR city = 'Bangkok' AND country = 'Thailand'",
     "WHERE (city = 'Phuket' OR city = 'Bangkok') AND country = 'Thailand'", "AND ถูกประเมินก่อน OR"),
   M("ใช้ AND กับค่าเดียวกัน", "WHERE status = 'paid' AND status = 'shipped'", "WHERE status = 'paid' OR status = 'shipped'",
     "คอลัมน์เดียวเป็นสองค่าพร้อมกันไม่ได้ → ได้ 0 แถวเสมอ")],
  ["where", "in", "null"]),

L("like", "LIKE และ ILIKE — ค้นหาข้อความตามรูปแบบ",
  "ค้นหาข้อความด้วย wildcard % และ _ รวมถึงการค้นหาแบบไม่สนตัวพิมพ์เล็ก-ใหญ่",
  ["ใช้ % และ _ กับ LIKE", "ใช้ ILIKE (PostgreSQL) ค้นหาแบบ case-insensitive", "escape อักขระพิเศษ"],
  """
| Pattern | ความหมาย | ตัวอย่างที่ match |
|---|---|---|
| `'A%'` | ขึ้นต้นด้วย A | Air Fryer |
| `'%Pro%'` | มีคำว่า Pro ตรงไหนก็ได้ | AirBuds **Pro**, Mac**Pro** Air |
| `'%s'` | ลงท้ายด้วย s | Chino Pant**s** |
| `'_a%'` | ตัวที่ 2 คือ a | **Ma**cPro Air |

- `%` = อักขระกี่ตัวก็ได้ (รวม 0), `_` = อักขระ 1 ตัวพอดี
- `LIKE` **case-sensitive**, ใช้ `ILIKE` (เฉพาะ PostgreSQL) หรือ `LOWER(col) LIKE '...'` (มาตรฐาน)
- `NOT LIKE` สำหรับกลับเงื่อนไข
- ต้องการค้นหา `%` หรือ `_` จริง ๆ ให้ escape: `LIKE '50\\%%'`

> ⚡ `LIKE 'abc%'` ใช้ index ได้ แต่ `LIKE '%abc'` ต้องสแกนทั้งตาราง
""",
  [E("สินค้าที่ชื่อมีคำว่า Pro", """SELECT name, price
FROM products
WHERE name LIKE '%Pro%';""", ["`%Pro%` หาคำว่า Pro ตรงไหนก็ได้ในชื่อ (ตัวพิมพ์ต้องตรง)"]),
   E("ลูกค้าในกรุงเทพฯ ทุกการสะกด", """SELECT id, first_name, city
FROM customers
WHERE city ILIKE 'bangkok'
ORDER BY id
LIMIT 10;""", ["`ILIKE` ไม่สนตัวพิมพ์ จึงได้ทั้ง `Bangkok` และ `bangkok`"])],
  [M("ใช้ * แทน %", "WHERE name LIKE 'Air*'", "WHERE name LIKE 'Air%'", "SQL ใช้ % เป็น wildcard ไม่ใช่ *"),
   M("ใช้ LIKE โดยไม่มี wildcard แทน =", "WHERE status LIKE 'paid'", "WHERE status = 'paid'",
     "ได้ผลเหมือนกันแต่สื่อความหมายไม่ชัด ใช้ = เมื่อต้องการค่าตรงตัว")],
  ["where", "string-functions"]),

L("in", "IN — ตรงกับค่าใดค่าหนึ่งในรายการ",
  "เขียนเงื่อนไข OR หลายค่าให้สั้นลงด้วย IN และระวังกับดัก NOT IN + NULL",
  ["ใช้ IN แทน OR หลายตัว", "ใช้ NOT IN", "เข้าใจปัญหา NOT IN เมื่อรายการมี NULL"],
  """
```sql
WHERE status IN ('paid', 'shipped', 'delivered')
-- เท่ากับ status = 'paid' OR status = 'shipped' OR status = 'delivered'
```
- `NOT IN (...)` — ไม่ตรงกับค่าใดเลย
- รายการใน IN มาจาก **subquery** ได้: `WHERE id IN (SELECT customer_id FROM orders)` (เรียนต่อในบท Subqueries)

### ⚠️ กับดัก NOT IN กับ NULL
ถ้ารายการมี `NULL` เช่น `x NOT IN (1, NULL)` → `x <> 1 AND x <> NULL` → ส่วนหลังเป็น UNKNOWN เสมอ → **ไม่มีแถวผ่านเลย**
ทางแก้: กรอง NULL ออกจาก subquery หรือใช้ `NOT EXISTS`
""",
  [E("คำสั่งซื้อที่จ่ายเงินแล้ว", """SELECT status, COUNT(*) AS orders
FROM orders
WHERE status IN ('paid', 'shipped', 'delivered')
GROUP BY status;""", ["`IN (...)` เลือก 3 สถานะ", "`GROUP BY` นับจำนวนต่อสถานะ (เรียนในบท GROUP BY)"]),
   E("ลูกค้านอกเมืองหลัก", """SELECT first_name, city
FROM customers
WHERE city NOT IN ('Bangkok', 'Chiang Mai', 'Phuket')
LIMIT 10;""", ["`NOT IN` ตัดลูกค้าใน 3 เมืองออก", "สังเกต: ลูกค้าที่ city เป็น NULL **ไม่** ถูกนับ เพราะ NULL NOT IN (...) = UNKNOWN"])],
  [M("NOT IN กับ subquery ที่มี NULL", "WHERE id NOT IN (SELECT manager_id FROM employees)",
     "WHERE id NOT IN (SELECT manager_id FROM employees WHERE manager_id IS NOT NULL)",
     "manager_id ของ CEO เป็น NULL ทำให้ผลลัพธ์ว่างเปล่า")],
  ["and-or-not", "subqueries", "exists"]),

L("between", "BETWEEN — อยู่ในช่วง",
  "เลือกค่าที่อยู่ในช่วงตัวเลขหรือวันที่ และข้อควรระวังเรื่องขอบเขตของ timestamp",
  ["ใช้ BETWEEN กับตัวเลขและวันที่", "รู้ว่า BETWEEN รวมค่าขอบทั้งสองฝั่ง", "หลีกเลี่ยงปัญหา BETWEEN กับ timestamp"],
  """
```sql
WHERE price BETWEEN 1000 AND 5000   -- เท่ากับ price >= 1000 AND price <= 5000
```
- **รวมค่าขอบ** ทั้งสองด้าน (inclusive)
- ค่าน้อยต้องอยู่ก่อน: `BETWEEN 5000 AND 1000` ได้ 0 แถว
- `NOT BETWEEN` สำหรับนอกช่วง

### ⚠️ BETWEEN กับ timestamp
`order_date BETWEEN '2025-01-01' AND '2025-01-31'` จะ **ไม่รวม** คำสั่งซื้อวันที่ 31 หลังเที่ยงคืน
เพราะ `'2025-01-31'` = `2025-01-31 00:00:00` → ใช้รูปแบบ **half-open interval** แทน:
```sql
WHERE order_date >= '2025-01-01' AND order_date < '2025-02-01'
```
""",
  [E("สินค้าราคา 1,000–3,000", """SELECT name, price
FROM products
WHERE price BETWEEN 1000 AND 3000
ORDER BY price;""", ["รวมสินค้าที่ราคา 1000 และ 3000 พอดีด้วย"]),
   E("คำสั่งซื้อเดือนมกราคม 2025 (half-open)", """SELECT COUNT(*) AS jan_2025_orders
FROM orders
WHERE order_date >= '2025-01-01' AND order_date < '2025-02-01';""",
     ["`>=` วันแรกของเดือน", "`<` วันแรกของเดือนถัดไป — ครอบคลุมทุกเวลาของวันที่ 31"])],
  [M("BETWEEN กับ timestamp ตัดวันสุดท้าย", "WHERE order_date BETWEEN '2025-01-01' AND '2025-01-31'",
     "WHERE order_date >= '2025-01-01' AND order_date < '2025-02-01'", "คำสั่งซื้อ 31 ม.ค. เวลา 10:00 จะหายไป")],
  ["where", "date-functions"]),

L("null", "NULL และ IS NULL — ค่าที่ไม่ทราบ",
  "เข้าใจความหมายของ NULL, การตรวจด้วย IS NULL / IS NOT NULL และการแทนค่าด้วย COALESCE",
  ["อธิบายได้ว่า NULL ≠ 0 ≠ ''", "ใช้ IS NULL / IS NOT NULL", "แทนค่า NULL ด้วย COALESCE"],
  """
`NULL` หมายถึง **"ไม่ทราบค่า / ไม่มีข้อมูล"** — ไม่ใช่ 0 และไม่ใช่ข้อความว่าง `''`

### กฎสำคัญ
- การเปรียบเทียบใด ๆ กับ NULL ได้ **UNKNOWN**: `NULL = NULL` → UNKNOWN (ไม่ใช่ TRUE!)
- ต้องตรวจด้วย `IS NULL` / `IS NOT NULL`
- คำนวณกับ NULL ได้ NULL: `100 + NULL = NULL`
- Aggregate ส่วนใหญ่ **ข้าม** NULL: `AVG(commission_pct)` คิดเฉพาะคนที่มีค่า, `COUNT(col)` ไม่นับ NULL แต่ `COUNT(*)` นับทุกแถว
- `COALESCE(a, b, c)` คืนค่าแรกที่ไม่ใช่ NULL — ใช้แทนค่าเริ่มต้น
- `IS DISTINCT FROM` เปรียบเทียบโดยถือว่า NULL เท่ากับ NULL

### NULL ใน sample data
ลูกค้าบางคนไม่มี `phone` หรือ `city`, พนักงานบางคนไม่มี `department_id`, ส่วนลด `order_items.discount` เป็น NULL เมื่อไม่มีส่วนลด
""",
  [E("ลูกค้าที่ไม่มีเบอร์โทร", """SELECT id, first_name, last_name, phone
FROM customers
WHERE phone IS NULL
ORDER BY id;""", ["`IS NULL` คือวิธีเดียวที่ถูกต้องในการหาค่าว่าง"]),
   E("แทนค่า NULL ด้วย COALESCE", """SELECT id, first_name, COALESCE(city, 'ไม่ระบุ') AS city, COALESCE(phone, '-') AS phone
FROM customers
WHERE city IS NULL OR phone IS NULL
ORDER BY id
LIMIT 8;""", ["`COALESCE(city, 'ไม่ระบุ')` ถ้า city เป็น NULL จะแสดง 'ไม่ระบุ'"]),
   E("COUNT(*) vs COUNT(column)", """SELECT COUNT(*) AS all_customers, COUNT(phone) AS with_phone, COUNT(city) AS with_city
FROM customers;""", ["`COUNT(*)` นับทุกแถว", "`COUNT(phone)` ไม่นับแถวที่ phone เป็น NULL"])],
  [M("ใช้ = NULL", "WHERE city = NULL", "WHERE city IS NULL", "ได้ 0 แถวเสมอ เพราะผลเปรียบเทียบเป็น UNKNOWN"),
   M("คำนวณโดยไม่กัน NULL", "SELECT unit_price * quantity - discount FROM order_items",
     "SELECT unit_price * quantity - COALESCE(discount, 0) FROM order_items", "แถวที่ไม่มีส่วนลดจะได้ยอดเป็น NULL")],
  ["where", "count", "left-join"]),
]
