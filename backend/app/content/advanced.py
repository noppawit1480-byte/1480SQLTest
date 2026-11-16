from app.content.model import Example as E
from app.content.model import LessonDef as L
from app.content.model import Mistake as M

LESSONS = [
L("subqueries", "Subqueries — query ซ้อน query",
  "ใช้ผลลัพธ์ของ query หนึ่งเป็นข้อมูลให้อีก query ใน WHERE, FROM และ SELECT",
  ["แยกประเภท subquery: scalar, row-list, table", "ใช้ subquery ใน WHERE, FROM, SELECT", "รู้ข้อจำกัดของ scalar subquery"],
  """
Subquery คือ `SELECT` ที่อยู่ในวงเล็บภายใน query อื่น

| ประเภท | คืนค่า | ใช้กับ |
|---|---|---|
| **Scalar** | 1 แถว 1 คอลัมน์ | `=`, `>`, ใน SELECT list |
| **List** | หลายแถว 1 คอลัมน์ | `IN`, `ANY`, `ALL` |
| **Table (derived table)** | หลายแถวหลายคอลัมน์ | `FROM (...) AS alias` |

- Scalar subquery ที่คืนมากกว่า 1 แถวจะ error: *more than one row returned by a subquery used as an expression*
- Scalar subquery ที่ไม่มีแถวได้ `NULL`
- Derived table **ต้องมี alias**

คำถามแบบ "สินค้าที่ราคาสูงกว่าค่าเฉลี่ย" ต้องรู้ค่าเฉลี่ยก่อน → subquery คือคำตอบตามธรรมชาติ
""",
  [E("สินค้าที่ราคาสูงกว่าค่าเฉลี่ย", """SELECT name, price
FROM products
WHERE price > (SELECT AVG(price) FROM products)
ORDER BY price DESC;""", ["subquery คำนวณค่าเฉลี่ยครั้งเดียว", "query นอกเปรียบเทียบทุกแถวกับค่านั้น"]),
   E("Derived table: ค่าเฉลี่ยของยอดต่อคำสั่งซื้อ", """SELECT ROUND(AVG(order_total), 2) AS avg_order_value, MAX(order_total) AS biggest_order
FROM (
  SELECT order_id, SUM(unit_price * quantity - COALESCE(discount, 0)) AS order_total
  FROM order_items
  GROUP BY order_id
) AS t;""", ["ด้านใน: ยอดรวมของแต่ละคำสั่งซื้อ", "ด้านนอก: เฉลี่ยของยอดเหล่านั้น — aggregate ซ้อน aggregate ต้องทำแบบนี้"]),
   E("Scalar subquery ใน SELECT", """SELECT name, price,
       ROUND(price / (SELECT AVG(price) FROM products), 2) AS times_avg
FROM products
ORDER BY times_avg DESC
LIMIT 5;""", ["subquery ใน SELECT list ต้องคืนค่าเดียว"])],
  [M("ใช้ = กับ subquery ที่คืนหลายแถว", "WHERE id = (SELECT customer_id FROM orders)", "WHERE id IN (SELECT customer_id FROM orders)",
     "more than one row returned by a subquery used as an expression"),
   M("ลืม alias ให้ derived table", "SELECT * FROM (SELECT 1 AS x);", "SELECT * FROM (SELECT 1 AS x) AS t;",
     "PostgreSQL < 16 บังคับ alias และเป็นแนวปฏิบัติที่ดีในทุกเวอร์ชัน")],
  ["nested-subqueries", "correlated-subqueries", "cte"]),

L("nested-subqueries", "Nested Subqueries — subquery หลายชั้น",
  "ซ้อน subquery หลายระดับเพื่อตอบคำถามหลายขั้น และรู้ว่าเมื่อไหร่ควรเปลี่ยนเป็น CTE",
  ["อ่านและเขียน subquery 2–3 ชั้น", "อ่านจากด้านในสุดออกมา", "รู้สัญญาณว่าควร refactor เป็น CTE"],
  """
Subquery ซ้อนกันได้หลายชั้น — อ่าน **จากในสุดออกมา**

ตัวอย่างคำถาม: *"ลูกค้าที่เคยซื้อสินค้าในหมวด Laptops"*
1. ชั้นในสุด: id ของหมวด Laptops
2. ชั้นกลาง: id สินค้าในหมวดนั้น → id คำสั่งซื้อที่มีสินค้านั้น
3. ชั้นนอก: ลูกค้าของคำสั่งซื้อเหล่านั้น

เมื่อซ้อนเกิน 2–3 ชั้น query จะอ่านยาก → ใช้ **CTE** (บทถัดไป) ซึ่งให้ผลเหมือนกันแต่อ่านจากบนลงล่าง
""",
  [E("ลูกค้าที่เคยซื้อโน้ตบุ๊ก", """SELECT id, first_name, last_name
FROM customers
WHERE id IN (
  SELECT customer_id FROM orders
  WHERE id IN (
    SELECT order_id FROM order_items
    WHERE product_id IN (
      SELECT id FROM products
      WHERE category_id = (SELECT id FROM categories WHERE name = 'Laptops')
    )
  )
)
ORDER BY id
LIMIT 10;""", ["ชั้น 4: id หมวด Laptops", "ชั้น 3: สินค้าในหมวด", "ชั้น 2: รายการขายของสินค้านั้น → order_id",
                "ชั้น 1: ลูกค้าเจ้าของคำสั่งซื้อ", "ใช้ IN ทำให้ลูกค้าไม่ซ้ำแม้ซื้อหลายครั้ง"])],
  [M("ซ้อนลึกจนอ่านไม่ออก", "WHERE x IN (SELECT ... WHERE y IN (SELECT ... WHERE z IN (...)))",
     "WITH laptops AS (...), laptop_orders AS (...) SELECT ...", "CTE ให้ชื่อแต่ละขั้น อ่านและ debug ง่ายกว่า")],
  ["subqueries", "cte"]),

L("correlated-subqueries", "Correlated Subqueries — subquery ที่อ้างถึง query นอก",
  "subquery ที่ทำงานใหม่ทุกแถวของ query นอก ใช้เปรียบเทียบแถวกับกลุ่มของตัวเอง",
  ["อธิบายความต่างของ correlated กับ non-correlated", "เปรียบเทียบแถวกับค่าเฉลี่ยของกลุ่มตัวเอง",
   "รู้ผลต่อประสิทธิภาพและทางเลือกอื่น"],
  """
**Correlated subquery** อ้างถึงคอลัมน์ของ query นอก จึงถูกประเมิน **ใหม่สำหรับแต่ละแถว**

```sql
SELECT p.name, p.price, p.category_id
FROM products p
WHERE p.price > (SELECT AVG(p2.price) FROM products p2 WHERE p2.category_id = p.category_id);
--                                                              ^^^^^^^^^^^^^^^ อ้างถึงแถวปัจจุบันของ p
```
อ่านว่า: *"สินค้าที่แพงกว่าค่าเฉลี่ย **ในหมวดของมันเอง**"*

- ต้องตั้ง alias ต่างกัน (p vs p2) เพื่อแยกแถวนอก/แถวใน
- PostgreSQL มักแปลง (decorrelate) ให้มีประสิทธิภาพ แต่ถ้าช้า ให้พิจารณา JOIN กับ derived table หรือ window function (`AVG() OVER (PARTITION BY ...)`)
""",
  [E("สินค้าที่แพงกว่าค่าเฉลี่ยของหมวดตัวเอง", """SELECT p.name, p.category_id, p.price
FROM products p
WHERE p.price > (
  SELECT AVG(p2.price) FROM products p2 WHERE p2.category_id = p.category_id
)
ORDER BY p.category_id, p.price DESC;""", ["subquery คำนวณค่าเฉลี่ยของหมวดเดียวกับแถว p ปัจจุบัน"]),
   E("คำสั่งซื้อล่าสุดของลูกค้าแต่ละคน", """SELECT o.customer_id, o.id, o.order_date
FROM orders o
WHERE o.order_date = (SELECT MAX(o2.order_date) FROM orders o2 WHERE o2.customer_id = o.customer_id)
ORDER BY o.customer_id
LIMIT 8;""", ["ต่อแถว: หาวันที่ล่าสุดของลูกค้าคนนั้น แล้วเก็บเฉพาะแถวที่ตรง"])],
  [M("ไม่ตั้ง alias แยก", "WHERE price > (SELECT AVG(price) FROM products WHERE category_id = category_id)",
     "WHERE p.price > (SELECT AVG(p2.price) FROM products p2 WHERE p2.category_id = p.category_id)",
     "category_id = category_id อ้างตารางในเสมอ จึงจริงทุกแถว → ได้ค่าเฉลี่ยรวมทั้งตาราง")],
  ["subqueries", "exists", "partition-by"]),

L("cte", "Common Table Expressions (CTE) — WITH",
  "ตั้งชื่อให้ผลลัพธ์ชั่วคราวด้วย WITH เพื่อแบ่ง query ซับซ้อนเป็นขั้นตอน",
  ["เขียน CTE หนึ่งและหลายตัว", "ใช้ CTE ตัวก่อนหน้าใน CTE ถัดไป", "เปรียบเทียบ CTE กับ subquery"],
  """
```sql
WITH step1 AS (
  SELECT ...
),
step2 AS (
  SELECT ... FROM step1 ...
)
SELECT * FROM step2;
```
- CTE เหมือน "ตัวแปรตาราง" ที่มีชีวิตอยู่ใน query เดียว
- อ่าน **บนลงล่าง** ตามลำดับความคิด → เหมาะกับงานวิเคราะห์ที่มีหลายขั้น
- อ้างถึง CTE เดียวกันได้หลายครั้ง
- ตั้งแต่ PostgreSQL 12 CTE ที่ใช้ครั้งเดียวจะถูก inline เข้า query หลัก (ประสิทธิภาพเท่า subquery) — บังคับให้คำนวณครั้งเดียวด้วย `AS MATERIALIZED`
""",
  [E("ลูกค้าที่ใช้จ่ายสูงกว่าค่าเฉลี่ย", """WITH customer_spend AS (
  SELECT o.customer_id, SUM(p.amount) AS total_spent
  FROM orders o
  JOIN payments p ON p.order_id = o.id
  GROUP BY o.customer_id
),
avg_spend AS (
  SELECT AVG(total_spent) AS avg_total FROM customer_spend
)
SELECT c.first_name, c.last_name, cs.total_spent
FROM customer_spend cs
JOIN customers c ON c.id = cs.customer_id
CROSS JOIN avg_spend a
WHERE cs.total_spent > a.avg_total
ORDER BY cs.total_spent DESC
LIMIT 10;""", ["`customer_spend` ยอดชำระรวมต่อลูกค้า", "`avg_spend` ค่าเฉลี่ยของยอดเหล่านั้น (ใช้ CTE แรกซ้ำ)",
                "`CROSS JOIN` แถวเดียวของ avg_spend เพื่อเอาค่าเฉลี่ยมาเทียบ"])],
  [M("ใส่ comma หลัง CTE ตัวสุดท้าย", "WITH a AS (...), b AS (...), SELECT ...", "WITH a AS (...), b AS (...) SELECT ...",
     "syntax error at or near \"SELECT\""),
   M("ใช้ WITH ซ้ำทุก CTE", "WITH a AS (...) WITH b AS (...)", "WITH a AS (...), b AS (...)", "WITH เขียนครั้งเดียว แล้วคั่น CTE ด้วย comma")],
  ["recursive-cte", "subqueries", "advanced-techniques"]),

L("recursive-cte", "Recursive CTE — ข้อมูลลำดับชั้นและการวนซ้ำ",
  "ไล่ข้อมูลแบบต้นไม้ (สายบังคับบัญชา, หมวดหมู่หลายชั้น) และสร้างลำดับตัวเลข/วันที่",
  ["เขียน recursive CTE ส่วน anchor และ recursive", "ไล่ลำดับชั้นพร้อมระดับและ path", "ป้องกันการวนไม่รู้จบ"],
  """
```sql
WITH RECURSIVE tree AS (
  -- 1) anchor: จุดเริ่มต้น
  SELECT id, name, manager_id, 1 AS level FROM employees WHERE manager_id IS NULL
  UNION ALL
  -- 2) recursive: JOIN กับผลรอบก่อนหน้า
  SELECT e.id, e.name, e.manager_id, t.level + 1
  FROM employees e JOIN tree t ON e.manager_id = t.id
)
SELECT * FROM tree;
```
การทำงาน: รัน anchor → นำผลไป JOIN ในส่วน recursive → ทำซ้ำกับแถวใหม่ → หยุดเมื่อรอบไหนไม่มีแถวใหม่

- ใส่ตัวนับ `level` / `depth` และเงื่อนไข `WHERE depth < 20` เพื่อกันวนไม่รู้จบเมื่อข้อมูลมี cycle
- สร้าง path ด้วยการต่อข้อความ `t.path || ' > ' || e.name`
- ใช้สร้าง series ได้ (แต่ PostgreSQL มี `generate_series` ที่ง่ายกว่า)
""",
  [E("แผนผังองค์กรพร้อมระดับ", """WITH RECURSIVE org AS (
  SELECT id, first_name, manager_id, 1 AS level, first_name::text AS path
  FROM employees WHERE manager_id IS NULL
  UNION ALL
  SELECT e.id, e.first_name, e.manager_id, o.level + 1, o.path || ' > ' || e.first_name
  FROM employees e
  JOIN org o ON e.manager_id = o.id
)
SELECT id, level, path
FROM org
ORDER BY path
LIMIT 12;""", ["anchor = CEO (ไม่มีหัวหน้า)", "แต่ละรอบหาลูกน้องของคนที่ได้มาจากรอบก่อน",
                "`path` สะสมชื่อเพื่อเห็นสายบังคับบัญชา", "`::text` ให้ชนิดข้อมูลคงที่ทั้งสองส่วนของ UNION"], db="hr"),
   E("หมวดหมู่ย่อยทั้งหมดภายใต้ Electronics", """WITH RECURSIVE sub AS (
  SELECT id, name, 0 AS depth FROM categories WHERE name = 'Electronics'
  UNION ALL
  SELECT c.id, c.name, s.depth + 1 FROM categories c JOIN sub s ON c.parent_id = s.id
)
SELECT * FROM sub ORDER BY depth, name;""", ["ไล่ลงไปทุกระดับ รวมหมวดระดับ 3 (Wireless Earbuds)"])],
  [M("ไม่มีเงื่อนไขหยุด/ตัวนับ", "... JOIN tree t ON e.manager_id = t.id", "... JOIN tree t ON e.manager_id = t.id WHERE t.level < 20",
     "ถ้าข้อมูลมีวงวน query จะวิ่งจนหมดเวลา"),
   M("ชนิดข้อมูลสองฝั่ง UNION ไม่ตรง", "SELECT name AS path ... UNION ALL SELECT t.path || ' > ' || e.name",
     "SELECT name::text AS path ...", "recursive query column has type character varying in non-recursive term but type text overall")],
  ["cte", "self-join"]),

L("window-functions", "Window Functions — คำนวณข้ามแถวโดยไม่ยุบแถว",
  "แนวคิด OVER(): คำนวณ aggregate/ranking บนกลุ่มของแถว แต่ยังคงทุกแถวไว้",
  ["อธิบายความต่างระหว่าง GROUP BY กับ window function", "เขียน OVER() กับ PARTITION BY และ ORDER BY",
   "ทำ running total และ moving average"],
  """
GROUP BY **ยุบ** แถวเหลือกลุ่มละ 1 แถว — Window function **คงทุกแถวไว้** แล้วเพิ่มคอลัมน์ที่คำนวณจาก "หน้าต่าง" ของแถวที่เกี่ยวข้อง

```sql
function(...) OVER (
  PARTITION BY ...      -- แบ่งกลุ่ม (ไม่ใส่ = ทั้งตาราง)
  ORDER BY ...          -- ลำดับภายในกลุ่ม
  ROWS BETWEEN ...      -- ขอบเขตหน้าต่าง (frame)
)
```

| ประเภท | ฟังก์ชัน |
|---|---|
| Ranking | `ROW_NUMBER`, `RANK`, `DENSE_RANK`, `NTILE`, `PERCENT_RANK` |
| Offset | `LAG`, `LEAD`, `FIRST_VALUE`, `LAST_VALUE` |
| Aggregate | `SUM`, `AVG`, `COUNT`, `MIN`, `MAX` + `OVER` |

- `SUM(x) OVER (ORDER BY d)` = **running total** (ผลรวมสะสม)
- `AVG(x) OVER (ORDER BY d ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` = ค่าเฉลี่ยเคลื่อนที่ 3 งวด
- Window function ทำงาน **หลัง** WHERE/GROUP BY/HAVING → กรองผลของมันต้องห่อด้วย subquery/CTE
""",
  [E("ยอดขายรายเดือนและยอดสะสม (2025)", """WITH monthly AS (
  SELECT DATE_TRUNC('month', payment_date)::date AS month, SUM(amount) AS revenue
  FROM payments
  WHERE payment_date >= '2025-01-01' AND payment_date < '2026-01-01'
  GROUP BY 1
)
SELECT month, revenue,
       SUM(revenue) OVER (ORDER BY month) AS running_total,
       ROUND(AVG(revenue) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3m
FROM monthly
ORDER BY month;""", ["CTE สรุปยอดรายเดือนก่อน", "`SUM ... OVER (ORDER BY month)` สะสมจากเดือนแรกถึงเดือนปัจจุบัน",
                      "`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW` หน้าต่าง 3 เดือนล่าสุด"]),
   E("เทียบเงินเดือนกับค่าเฉลี่ยของแผนก (คงทุกแถว)", """SELECT e.first_name, e.department_id, s.amount,
       ROUND(AVG(s.amount) OVER (PARTITION BY e.department_id), 2) AS dept_avg
FROM employees e
JOIN salaries s ON s.employee_id = e.id AND s.effective_to IS NULL
WHERE e.department_id IS NOT NULL
ORDER BY e.department_id, s.amount DESC
LIMIT 10;""", ["`PARTITION BY department_id` คำนวณค่าเฉลี่ยแยกแผนก แต่ไม่ยุบแถว",
                "`effective_to IS NULL` = เงินเดือนปัจจุบัน"], db="hr")],
  [M("ใช้ window function ใน WHERE", "WHERE ROW_NUMBER() OVER (...) = 1", "SELECT * FROM (SELECT ..., ROW_NUMBER() OVER (...) AS rn ...) t WHERE rn = 1",
     "window functions are not allowed in WHERE")],
  ["row-number", "partition-by", "lag-lead"]),

L("row-number", "ROW_NUMBER() — ลำดับแถวที่ไม่ซ้ำ",
  "ใส่เลขลำดับให้แถว ใช้หา Top-N ต่อกลุ่ม และตัดข้อมูลซ้ำ (deduplication)",
  ["ใส่ลำดับด้วย ROW_NUMBER", "หา Top-N ต่อกลุ่ม", "ใช้ ROW_NUMBER ตัดแถวซ้ำ"],
  """
`ROW_NUMBER() OVER (PARTITION BY g ORDER BY x)` ให้เลข 1, 2, 3, ... ในแต่ละกลุ่ม **ไม่ซ้ำแม้ค่าเท่ากัน**
(ถ้าค่าเท่ากัน ลำดับระหว่างกันไม่แน่นอน → ใส่ tie-breaker ใน ORDER BY เช่น `, id`)

### Pattern สำคัญ
1. **Top-N ต่อกลุ่ม** — `WHERE rn <= N`
2. **Deduplicate** — เก็บแถวล่าสุดของแต่ละ key: `PARTITION BY key ORDER BY updated_at DESC` แล้ว `WHERE rn = 1`
""",
  [E("สินค้าราคาสูงสุด 2 อันดับในแต่ละหมวด", """WITH ranked AS (
  SELECT category_id, name, price,
         ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY price DESC, id) AS rn
  FROM products
  WHERE category_id IS NOT NULL
)
SELECT category_id, rn, name, price
FROM ranked
WHERE rn <= 2
ORDER BY category_id, rn;""", ["นับลำดับใหม่ทุกหมวด", "`id` เป็น tie-breaker เมื่อราคาเท่ากัน", "กรอง rn ใน query นอก"]),
   E("เงินเดือนปัจจุบันจากประวัติ (dedupe)", """SELECT employee_id, amount, effective_from
FROM (
  SELECT employee_id, amount, effective_from,
         ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY effective_from DESC) AS rn
  FROM salaries
) s
WHERE rn = 1
ORDER BY employee_id
LIMIT 8;""", ["แถวล่าสุดของแต่ละพนักงานได้ rn = 1"], db="hr")],
  [M("ไม่มี tie-breaker", "ROW_NUMBER() OVER (ORDER BY price DESC)", "ROW_NUMBER() OVER (ORDER BY price DESC, id)",
     "สินค้าราคาเท่ากันจะสลับอันดับกันได้ในแต่ละครั้งที่รัน")],
  ["rank", "dense-rank", "window-functions"]),

L("rank", "RANK() — อันดับแบบมีช่องว่าง",
  "จัดอันดับโดยค่าที่เท่ากันได้อันดับเดียวกัน และอันดับถัดไปถูกข้าม",
  ["ใช้ RANK จัดอันดับ", "เข้าใจ gap หลังค่าที่เสมอกัน"],
  """
`RANK()` ให้แถวที่ค่าเท่ากันได้ **อันดับเดียวกัน** แล้ว **ข้าม** อันดับถัดไปตามจำนวนที่เสมอ — เหมือนการแข่งกีฬา

| คะแนน | ROW_NUMBER | RANK | DENSE_RANK |
|---|---|---|---|
| 100 | 1 | 1 | 1 |
| 90 | 2 | 2 | 2 |
| 90 | 3 | 2 | 2 |
| 80 | 4 | **4** | **3** |
""",
  [E("จัดอันดับประเทศตามยอดขายเพลง", """SELECT billing_country, SUM(total) AS revenue,
       RANK() OVER (ORDER BY SUM(total) DESC) AS rnk
FROM invoices
GROUP BY billing_country
ORDER BY rnk;""", ["window function ใช้ร่วมกับ GROUP BY ได้ โดยทำงานหลังการจัดกลุ่ม", "`ORDER BY SUM(total)` ภายใน OVER"], db="music_store"),
   E("เปรียบเทียบ ROW_NUMBER / RANK / DENSE_RANK", """SELECT name, price,
       ROW_NUMBER() OVER (ORDER BY price DESC) AS row_number,
       RANK()       OVER (ORDER BY price DESC) AS rank,
       DENSE_RANK() OVER (ORDER BY price DESC) AS dense_rank
FROM products
WHERE price BETWEEN 600 AND 1300
ORDER BY price DESC;""", ["ดูแถวที่ราคาเท่ากันเพื่อเห็นความต่างของทั้งสามฟังก์ชัน"])],
  [M("ใช้ RANK แล้ว WHERE rnk = 2 คาดว่าได้เสมอ", "WHERE rnk = 2", "WHERE dense_rnk = 2",
     "ถ้ามีสองแถวเสมอที่อันดับ 1 จะไม่มีอันดับ 2 เลย")],
  ["dense-rank", "row-number"]),

L("dense-rank", "DENSE_RANK() — อันดับแบบไม่มีช่องว่าง",
  "จัดอันดับแบบต่อเนื่อง เหมาะกับโจทย์ 'ค่าสูงสุดอันดับที่ N'",
  ["ใช้ DENSE_RANK", "แก้โจทย์ Nth highest"],
  """
`DENSE_RANK()` ค่าที่เท่ากันได้อันดับเดียวกันเหมือน RANK แต่อันดับถัดไป **ไม่ข้าม** (1, 2, 2, 3)

โจทย์สัมภาษณ์คลาสสิก: **"หาเงินเดือนที่สูงเป็นอันดับ 2 (ไม่นับซ้ำ)"**
```sql
SELECT DISTINCT amount FROM (
  SELECT amount, DENSE_RANK() OVER (ORDER BY amount DESC) AS dr FROM salaries WHERE effective_to IS NULL
) t WHERE dr = 2;
```
""",
  [E("3 ระดับราคาสูงสุดในแต่ละหมวด (รวมราคาที่เท่ากัน)", """SELECT * FROM (
  SELECT category_id, name, price,
         DENSE_RANK() OVER (PARTITION BY category_id ORDER BY price DESC) AS price_rank
  FROM products
  WHERE category_id IN (9, 10, 13)
) t
WHERE price_rank <= 3
ORDER BY category_id, price_rank;""", ["ถ้าราคาเท่ากัน ทั้งสองสินค้าได้อันดับเดียวกันและไม่มีอันดับหาย"])],
  [M("ใช้ LIMIT/OFFSET หาอันดับ 2", "ORDER BY amount DESC LIMIT 1 OFFSET 1", "DENSE_RANK() ... WHERE dr = 2",
     "ถ้าอันดับ 1 มีสองคน OFFSET 1 จะได้ค่าอันดับ 1 ซ้ำ")],
  ["rank", "partition-by"]),

L("partition-by", "PARTITION BY — แบ่งหน้าต่างเป็นกลุ่ม",
  "แบ่งการคำนวณ window function ตามกลุ่ม เช่นต่อแผนก ต่อลูกค้า ต่อเดือน",
  ["ใช้ PARTITION BY กับ aggregate และ ranking", "คำนวณสัดส่วนต่อกลุ่ม (% of total)", "PARTITION หลายคอลัมน์"],
  """
`PARTITION BY` คล้าย GROUP BY แต่ **ไม่ยุบแถว** — window function จะ "รีเซ็ต" เมื่อเปลี่ยนกลุ่ม

ตัวอย่างการใช้งาน
- สัดส่วนยอดขายสินค้าในหมวดของตัวเอง: `revenue / SUM(revenue) OVER (PARTITION BY category)`
- ยอดสะสมต่อลูกค้า: `SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date)`
- ลำดับครั้งที่ซื้อของลูกค้าแต่ละคน: `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date)`
""",
  [E("ส่วนแบ่งรายได้ของสินค้าภายในหมวด", """WITH product_rev AS (
  SELECT p.category_id, p.name, SUM(oi.unit_price * oi.quantity) AS revenue
  FROM order_items oi JOIN products p ON p.id = oi.product_id
  WHERE p.category_id IN (6, 7)
  GROUP BY p.category_id, p.name
)
SELECT category_id, name, revenue,
       ROUND(100 * revenue / SUM(revenue) OVER (PARTITION BY category_id), 1) AS pct_of_category
FROM product_rev
ORDER BY category_id, revenue DESC;""", ["`SUM(revenue) OVER (PARTITION BY category_id)` = รายได้รวมของหมวด แสดงทุกแถว",
                                         "หารเพื่อได้เปอร์เซ็นต์"]),
   E("ครั้งที่ซื้อของลูกค้า (purchase sequence)", """SELECT customer_id, id AS order_id, order_date,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) AS nth_order
FROM orders
WHERE customer_id <= 3
ORDER BY customer_id, order_date;""", ["ลำดับเริ่มนับ 1 ใหม่เมื่อเปลี่ยนลูกค้า"])],
  [M("ลืม PARTITION แล้วได้ค่ารวมทั้งตาราง", "SUM(revenue) OVER ()", "SUM(revenue) OVER (PARTITION BY category_id)",
     "OVER () ว่างคือหน้าต่างเดียวทั้งตาราง")],
  ["window-functions", "group-by"]),

L("lag-lead", "LAG() และ LEAD() — มองแถวก่อนหน้า/ถัดไป",
  "เปรียบเทียบกับงวดก่อน (MoM, YoY), หาระยะห่างระหว่างเหตุการณ์",
  ["ใช้ LAG/LEAD ดึงค่าจากแถวข้างเคียง", "คำนวณการเติบโต Month-over-Month", "คำนวณช่วงห่างระหว่างการซื้อ"],
  """
```sql
LAG(expr, offset = 1, default = NULL) OVER (PARTITION BY ... ORDER BY ...)
LEAD(expr, offset = 1, default = NULL) OVER (...)
```
- `LAG` = ค่าของแถว **ก่อนหน้า**, `LEAD` = แถว **ถัดไป** ตามลำดับใน OVER
- แถวแรกไม่มีแถวก่อนหน้า → ได้ NULL (หรือค่า default)

**Growth %** = `(current - previous) / previous * 100` — ระวังหารด้วย 0: ใช้ `NULLIF(previous, 0)`
""",
  [E("การเติบโตรายเดือน (MoM)", """WITH monthly AS (
  SELECT DATE_TRUNC('month', order_date)::date AS month, COUNT(*) AS orders
  FROM orders
  GROUP BY 1
)
SELECT month, orders,
       LAG(orders) OVER (ORDER BY month) AS prev_month,
       ROUND(100.0 * (orders - LAG(orders) OVER (ORDER BY month)) / NULLIF(LAG(orders) OVER (ORDER BY month), 0), 1) AS mom_pct
FROM monthly
ORDER BY month
LIMIT 12;""", ["`LAG(orders)` ดึงจำนวนของเดือนก่อน", "`NULLIF(x, 0)` ป้องกัน division by zero"]),
   E("ระยะห่าง (วัน) ระหว่างคำสั่งซื้อของลูกค้า", """SELECT customer_id, order_date,
       LEAD(order_date) OVER (PARTITION BY customer_id ORDER BY order_date) AS next_order,
       LEAD(order_date) OVER (PARTITION BY customer_id ORDER BY order_date)::date - order_date::date AS days_to_next
FROM orders
WHERE customer_id = 5
ORDER BY order_date;""", ["`LEAD` ดูคำสั่งซื้อถัดไปของลูกค้าคนเดียวกัน", "ลบ date ได้จำนวนวัน"])],
  [M("ลืม PARTITION BY", "LAG(order_date) OVER (ORDER BY order_date)", "LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date)",
     "จะได้คำสั่งซื้อก่อนหน้าของ *ลูกค้าคนอื่น*")],
  ["window-functions", "date-functions"]),

L("exists", "EXISTS และ NOT EXISTS — ตรวจว่ามีแถวที่เกี่ยวข้องหรือไม่",
  "semi-join และ anti-join ที่ปลอดภัยจากปัญหา NULL และมักเร็วกว่า IN",
  ["ใช้ EXISTS หา 'มีอย่างน้อยหนึ่ง'", "ใช้ NOT EXISTS หา 'ไม่มีเลย'", "เปรียบเทียบกับ IN / LEFT JOIN"],
  """
```sql
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
```
- คืน TRUE ถ้า subquery มี **อย่างน้อย 1 แถว** — ไม่สนว่า SELECT อะไร (นิยมเขียน `SELECT 1`)
- หยุดค้นหาเมื่อเจอแถวแรก (short-circuit)
- **ไม่ทำให้แถวซ้ำ** ต่างจาก JOIN
- `NOT EXISTS` **ไม่มีปัญหา NULL** แบบ `NOT IN` → เป็นวิธีที่แนะนำสำหรับ anti-join
""",
  [E("ลูกค้าที่ไม่เคยสั่งซื้อ (NOT EXISTS)", """SELECT c.id, c.first_name, c.last_name, c.created_at
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
ORDER BY c.id;""", ["correlated subquery ตรวจทีละลูกค้า", "ได้ลูกค้าที่ไม่มีคำสั่งซื้อเลย"]),
   E("พนักงานที่เป็นหัวหน้าคน", """SELECT e.id, e.first_name, e.last_name
FROM employees e
WHERE EXISTS (SELECT 1 FROM employees r WHERE r.manager_id = e.id)
ORDER BY e.id;""", ["มีลูกน้องอย่างน้อย 1 คน → เป็นหัวหน้า", "ไม่ซ้ำแม้มีลูกน้องหลายคน"], db="hr")],
  [M("ใช้ NOT IN กับคอลัมน์ที่มี NULL", "WHERE e.id NOT IN (SELECT manager_id FROM employees)",
     "WHERE NOT EXISTS (SELECT 1 FROM employees r WHERE r.manager_id = e.id)", "NOT IN ได้ 0 แถวเพราะมี NULL")],
  ["in", "left-join", "correlated-subqueries"]),

L("advanced-join", "Advanced JOIN — CROSS JOIN, Non-equi JOIN, LATERAL",
  "JOIN ที่ไม่ใช่แค่ key = key: ผลคูณคาร์ทีเซียน, JOIN ด้วยช่วง, และ LATERAL สำหรับ Top-N ต่อแถว",
  ["ใช้ CROSS JOIN สร้างทุกคู่", "JOIN ด้วยเงื่อนไขช่วง (non-equi)", "ใช้ JOIN LATERAL"],
  """
### CROSS JOIN
ทุกแถว × ทุกแถว — ใช้สร้าง "ตารางโครง" เช่น ทุกเดือน × ทุกหมวด แล้ว LEFT JOIN ยอดขาย เพื่อให้เดือนที่ไม่มียอดแสดงเป็น 0

### Non-equi JOIN
เงื่อนไขไม่ใช่ `=` เช่นจับคู่เงินเดือนกับช่วงของตำแหน่ง `s.amount BETWEEN p.min_salary AND p.max_salary`
หรือหาเงินเดือนที่มีผล ณ วันที่หนึ่ง `d >= s.effective_from AND (s.effective_to IS NULL OR d < s.effective_to)`

### LATERAL
subquery ใน FROM ที่ **อ้างถึงตารางก่อนหน้าได้** — เหมือน for-each:
```sql
FROM customers c
CROSS JOIN LATERAL (SELECT ... FROM orders o WHERE o.customer_id = c.id ORDER BY order_date DESC LIMIT 3) last3
```
""",
  [E("ตารางโครง: ทุกเดือน × วิธีชำระเงิน (รวมช่องที่เป็น 0)", """WITH months AS (
  SELECT generate_series('2025-10-01'::date, '2025-12-01'::date, interval '1 month')::date AS month
), methods AS (
  SELECT DISTINCT method FROM payments
)
SELECT m.month, me.method, COUNT(p.id) AS payments
FROM months m
CROSS JOIN methods me
LEFT JOIN payments p ON p.method = me.method AND DATE_TRUNC('month', p.payment_date)::date = m.month
GROUP BY m.month, me.method
ORDER BY m.month, me.method;""", ["`generate_series` สร้างรายการเดือน", "CROSS JOIN ได้ทุกคู่ เดือน × วิธีชำระ",
                                   "LEFT JOIN ข้อมูลจริง — คู่ที่ไม่มีข้อมูลได้ 0"]),
   E("ตรวจเงินเดือนที่อยู่นอกช่วงของตำแหน่ง (non-equi)", """SELECT e.first_name, p.title, s.amount, p.min_salary, p.max_salary
FROM employees e
JOIN positions p ON p.id = e.position_id
JOIN salaries s ON s.employee_id = e.id AND s.effective_to IS NULL
WHERE s.amount NOT BETWEEN p.min_salary AND p.max_salary
ORDER BY p.title;""", ["เปรียบเทียบกับช่วง ไม่ใช่ค่าเท่ากัน", "ได้รายการผิดปกติที่ HR ควรตรวจสอบ"], db="hr"),
   E("LATERAL: 2 คำสั่งซื้อล่าสุดของลูกค้า 3 คนแรก", """SELECT c.id, c.first_name, last2.order_id, last2.order_date
FROM customers c
CROSS JOIN LATERAL (
  SELECT o.id AS order_id, o.order_date FROM orders o
  WHERE o.customer_id = c.id ORDER BY o.order_date DESC LIMIT 2
) AS last2
WHERE c.id <= 3
ORDER BY c.id, last2.order_date DESC;""", ["subquery ใน LATERAL อ้าง `c.id` ได้", "LIMIT 2 ทำงานแยกต่อลูกค้า"])],
  [M("CROSS JOIN ตารางใหญ่โดยไม่ตั้งใจ", "FROM orders, order_items", "FROM orders o JOIN order_items oi ON oi.order_id = o.id",
     "comma ใน FROM คือ CROSS JOIN: 900 × 1666 แถว")],
  ["inner-join", "advanced-techniques"]),

L("advanced-techniques", "Advanced Query Techniques — เทคนิคที่ใช้ในงานจริง",
  "GROUPING SETS/ROLLUP, conditional aggregation, gaps & islands, cohort และการเขียน query ที่อ่านง่าย",
  ["สร้าง subtotal ด้วย ROLLUP", "แก้ปัญหา gaps & islands", "จัดโครงสร้าง query วิเคราะห์หลายขั้นด้วย CTE"],
  """
### 1) ROLLUP / GROUPING SETS — subtotal ใน query เดียว
`GROUP BY ROLLUP (year, status)` ได้ยอดต่อ (ปี, สถานะ) + ยอดรวมต่อปี + ยอดรวมทั้งหมด
แถว subtotal มีค่า NULL ในคอลัมน์ที่ถูกรวม — ใช้ `GROUPING(col)` แยกว่าเป็น subtotal หรือ NULL จริง

### 2) Gaps & Islands
หาช่วงต่อเนื่อง เช่น "วันที่ลูกค้าซื้อติดกัน": `day - ROW_NUMBER() OVER (ORDER BY day)` จะคงที่ภายในช่วงต่อเนื่องเดียวกัน → GROUP BY ค่านั้น

### 3) Cohort analysis
กลุ่มลูกค้าตามเดือนที่ซื้อครั้งแรก แล้วดูว่าซื้อซ้ำในเดือนต่อ ๆ ไปเท่าไร — ใช้ `MIN() OVER (PARTITION BY customer)` + DATE_TRUNC

### หลักการเขียน query ซับซ้อน
1. แตกเป็น CTE ทีละขั้น ตั้งชื่อสื่อความหมาย
2. ตรวจผลทีละ CTE (`SELECT * FROM step1 LIMIT 10`)
3. ตรวจ **grain** (1 แถว = อะไร) ทุกขั้น เพื่อป้องกัน JOIN ทำแถวซ้ำ
""",
  [E("ROLLUP: ยอดชำระตามปีและวิธี พร้อม subtotal", """SELECT CASE WHEN GROUPING(EXTRACT(YEAR FROM payment_date)) = 1 THEN 'ALL' ELSE EXTRACT(YEAR FROM payment_date)::text END AS year,
       CASE WHEN GROUPING(method) = 1 THEN 'ALL' ELSE method END AS method,
       SUM(amount) AS total
FROM payments
GROUP BY ROLLUP (EXTRACT(YEAR FROM payment_date), method)
ORDER BY 1, 2;""", ["ROLLUP สร้างแถวสรุประดับปี และระดับทั้งหมด", "`GROUPING()` = 1 เมื่อแถวนั้นเป็นแถวสรุป"]),
   E("Cohort: ลูกค้าตามเดือนแรกที่ซื้อ (2025 H2)", """WITH first_order AS (
  SELECT customer_id, DATE_TRUNC('month', MIN(order_date))::date AS cohort_month
  FROM orders
  GROUP BY customer_id
)
SELECT cohort_month, COUNT(*) AS new_customers
FROM first_order
WHERE cohort_month >= '2025-07-01'
GROUP BY cohort_month
ORDER BY cohort_month;""", ["หาเดือนแรกที่ลูกค้าแต่ละคนซื้อ", "นับลูกค้าใหม่ต่อ cohort"])],
  [M("JOIN สองตาราง 1:N พร้อมกันแล้ว SUM", "FROM orders o JOIN order_items oi ... JOIN payments p ... SUM(p.amount)",
     "สรุปแต่ละตารางใน CTE ของตัวเองก่อน แล้วค่อย JOIN", "แถวคูณกัน (fan-out) ทำให้ยอดเงินเกินจริง")],
  ["cte", "window-functions", "query-optimization"]),
]
