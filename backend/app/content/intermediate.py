from app.content.model import Example as E
from app.content.model import LessonDef as L
from app.content.model import Mistake as M

LESSONS = [
L("aggregate-functions", "Aggregate Functions — สรุปข้อมูลหลายแถวเป็นค่าเดียว",
  "ภาพรวมของฟังก์ชันสรุปผล COUNT, SUM, AVG, MIN, MAX และพฤติกรรมกับ NULL",
  ["อธิบายความต่างระหว่างฟังก์ชันปกติกับ aggregate", "ใช้ aggregate หลายตัวใน query เดียว",
   "เข้าใจว่า aggregate ข้าม NULL"],
  """
**Aggregate function** รับค่าจาก **หลายแถว** แล้วคืนค่า **เดียว** — ต่างจากฟังก์ชันปกติ (เช่น `UPPER`) ที่ทำทีละแถว

| ฟังก์ชัน | คืนค่า | NULL |
|---|---|---|
| `COUNT(*)` | จำนวนแถว | นับทุกแถว |
| `COUNT(col)` | จำนวนค่าที่ไม่ใช่ NULL | ข้าม |
| `SUM(col)` | ผลรวม | ข้าม (ถ้าทั้งหมดเป็น NULL ได้ NULL) |
| `AVG(col)` | ค่าเฉลี่ย | ข้าม |
| `MIN/MAX(col)` | ค่าน้อยสุด/มากสุด | ข้าม |

- เมื่อไม่มี `GROUP BY` ทั้งตารางคือ 1 กลุ่ม → ได้ 1 แถว
- ห้ามผสมคอลัมน์ปกติกับ aggregate โดยไม่ GROUP BY: `SELECT name, MAX(price)` ❌
- `FILTER (WHERE ...)` (PostgreSQL) ทำ aggregate แบบมีเงื่อนไข: `COUNT(*) FILTER (WHERE status = 'cancelled')`
""",
  [E("สรุปภาพรวมสินค้า", """SELECT COUNT(*) AS products,
       MIN(price) AS cheapest,
       MAX(price) AS most_expensive,
       ROUND(AVG(price), 2) AS avg_price,
       SUM(stock) AS total_stock
FROM products;""", ["ทุกฟังก์ชันทำงานบนทั้งตาราง → ผลลัพธ์ 1 แถว", "`ROUND(x, 2)` ปัดทศนิยม 2 ตำแหน่ง"]),
   E("Aggregate แบบมีเงื่อนไขด้วย FILTER", """SELECT COUNT(*) AS all_orders,
       COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'cancelled') / COUNT(*), 2) AS cancel_rate_pct
FROM orders;""", ["`FILTER (WHERE ...)` นับเฉพาะแถวที่ตรงเงื่อนไข", "`100.0 *` ทำให้หารแบบทศนิยม ไม่ใช่หารจำนวนเต็ม"])],
  [M("ผสมคอลัมน์ปกติกับ aggregate", "SELECT name, MAX(price) FROM products;",
     "SELECT name, price FROM products ORDER BY price DESC LIMIT 1;",
     "error: column \"products.name\" must appear in the GROUP BY clause or be used in an aggregate function"),
   M("หารจำนวนเต็มได้ 0", "SELECT 1 / 3;", "SELECT 1.0 / 3;", "integer / integer ใน PostgreSQL ตัดเศษทิ้ง")],
  ["count", "group-by", "having"]),

L("count", "COUNT() — นับจำนวน",
  "นับแถว นับค่าที่ไม่ใช่ NULL และนับค่าไม่ซ้ำ",
  ["เลือกใช้ COUNT(*), COUNT(col), COUNT(DISTINCT col) ได้ถูกต้อง", "นับแบบมีเงื่อนไข"],
  """
| รูปแบบ | ความหมาย |
|---|---|
| `COUNT(*)` | จำนวนแถวทั้งหมด |
| `COUNT(col)` | จำนวนแถวที่ col ไม่เป็น NULL |
| `COUNT(DISTINCT col)` | จำนวนค่าไม่ซ้ำ (ไม่รวม NULL) |

คำถามธุรกิจ: *"มีลูกค้ากี่คนที่เคยสั่งซื้อ?"* → `COUNT(DISTINCT customer_id) FROM orders` (ไม่ใช่ `COUNT(*)` ซึ่งนับจำนวนคำสั่งซื้อ)
""",
  [E("นับลูกค้า 3 แบบ", """SELECT COUNT(*) AS rows_total,
       COUNT(city) AS rows_with_city,
       COUNT(DISTINCT city) AS distinct_cities
FROM customers;""", ["สังเกตว่า 3 ค่าต่างกันเพราะ NULL และค่าซ้ำ"]),
   E("ลูกค้าที่เคยสั่งซื้อ", "SELECT COUNT(DISTINCT customer_id) AS buying_customers FROM orders;",
     ["ลูกค้า 1 คนมีหลายคำสั่งซื้อ จึงต้องใช้ DISTINCT"])],
  [M("นับลูกค้าจากตาราง orders ด้วย COUNT(*)", "SELECT COUNT(*) FROM orders;", "SELECT COUNT(DISTINCT customer_id) FROM orders;",
     "COUNT(*) นับคำสั่งซื้อ ไม่ใช่จำนวนคน")],
  ["aggregate-functions", "distinct", "null"]),

L("sum", "SUM() — หาผลรวม",
  "หาผลรวมของคอลัมน์และนิพจน์ เช่นยอดขาย = ราคา × จำนวน − ส่วนลด",
  ["หาผลรวมของคอลัมน์", "หาผลรวมของนิพจน์คำนวณ", "จัดการ NULL ในการคำนวณยอดเงิน"],
  """
`SUM(expression)` บวกค่าทุกแถว (ข้าม NULL)

ยอดขายจริงของแต่ละรายการ = `unit_price * quantity - COALESCE(discount, 0)`
ต้องใช้ `COALESCE` เพราะถ้า `discount` เป็น NULL ทั้งนิพจน์จะกลายเป็น NULL แล้วถูก SUM ข้ามไป → **ยอดขายหายโดยไม่มี error!**

> ใช้ `numeric` กับเงินเสมอ ผลรวมจะแม่นยำทุกสตางค์
""",
  [E("ยอดขายรวมจากรายการสินค้า", """SELECT SUM(unit_price * quantity) AS gross_sales,
       SUM(COALESCE(discount, 0)) AS total_discount,
       SUM(unit_price * quantity - COALESCE(discount, 0)) AS net_sales
FROM order_items;""", ["คำนวณต่อแถวก่อน แล้ว SUM รวมทั้งตาราง", "`COALESCE(discount, 0)` แปลง NULL เป็น 0"]),
   E("ผลของลืม COALESCE", """SELECT SUM(unit_price * quantity - discount) AS wrong_net,
       SUM(unit_price * quantity - COALESCE(discount, 0)) AS correct_net
FROM order_items;""", ["`wrong_net` รวมเฉพาะแถวที่มีส่วนลด จึงน้อยกว่าความจริงมาก"])],
  [M("ลืม NULL ในนิพจน์", "SUM(unit_price * quantity - discount)", "SUM(unit_price * quantity - COALESCE(discount, 0))",
     "แถวที่ discount เป็น NULL ทั้งนิพจน์เป็น NULL")],
  ["avg", "group-by", "null"]),

L("avg", "AVG() — ค่าเฉลี่ย",
  "หาค่าเฉลี่ย ปัดทศนิยม และเข้าใจผลของ NULL ต่อค่าเฉลี่ย",
  ["หาค่าเฉลี่ยด้วย AVG", "ปัดเศษด้วย ROUND", "เข้าใจว่า AVG ข้าม NULL"],
  """
`AVG(col)` = `SUM(col) / COUNT(col)` — **ไม่ใช่** `/ COUNT(*)`

ตัวอย่าง: ค่าคอมมิชชันเฉลี่ย `AVG(commission_pct)` คิดเฉพาะพนักงานที่มีค่าคอมฯ (ฝ่ายขาย)
ถ้าต้องการถือว่าคนที่ไม่มีคือ 0 ให้ใช้ `AVG(COALESCE(commission_pct, 0))`

- `AVG` ของ integer ได้ผลเป็น numeric ทศนิยมยาว → ใช้ `ROUND(AVG(x), 2)`
- ค่าเฉลี่ยไวต่อค่าผิดปกติ (outlier) — งานวิเคราะห์จริงมักดู **median** ด้วย: `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)`
""",
  [E("AVG ข้าม NULL", """SELECT ROUND(AVG(commission_pct), 4) AS avg_of_sales_staff,
       ROUND(AVG(COALESCE(commission_pct, 0)), 4) AS avg_of_everyone
FROM employees;""", ["ค่าแรกเฉลี่ยเฉพาะคนที่มีค่าคอมฯ", "ค่าที่สองเฉลี่ยทุกคนโดยนับคนที่ไม่มีเป็น 0"], db="hr"),
   E("ค่าเฉลี่ยและมัธยฐานของมูลค่าใบแจ้งหนี้", """SELECT ROUND(AVG(total), 2) AS avg_total,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total) AS median_total
FROM invoices;""", ["`PERCENTILE_CONT(0.5)` คือค่ามัธยฐาน"], db="music_store")],
  [M("คิดว่า AVG นับแถว NULL", "AVG(commission_pct) -- 'เฉลี่ยทุกคน'", "AVG(COALESCE(commission_pct, 0))",
     "AVG ข้าม NULL ผลจึงสูงกว่าที่คาด")],
  ["sum", "min-max", "group-by"]),

L("min-max", "MIN() และ MAX() — ค่าน้อยสุดและมากสุด",
  "หาค่าต่ำสุด/สูงสุดของตัวเลข วันที่ และข้อความ",
  ["ใช้ MIN/MAX กับตัวเลข วันที่ ข้อความ", "รู้ว่าการหา 'แถว' ที่มีค่าสูงสุดต้องใช้วิธีอื่น"],
  """
- `MIN/MAX` ใช้ได้กับทุก type ที่เรียงลำดับได้: ตัวเลข, วันที่ (`MIN(order_date)` = คำสั่งซื้อแรก), ข้อความ (ตามลำดับตัวอักษร)
- ได้ **ค่า** ไม่ใช่ **แถว** — ถ้าอยากรู้ว่า *สินค้าไหน* แพงสุด ใช้ `ORDER BY price DESC LIMIT 1`
  หรือ subquery `WHERE price = (SELECT MAX(price) FROM products)` (ซึ่งรองรับกรณีเสมอกันหลายตัว)
""",
  [E("ช่วงเวลาของข้อมูลคำสั่งซื้อ", """SELECT MIN(order_date) AS first_order, MAX(order_date) AS last_order,
       MAX(order_date) - MIN(order_date) AS span
FROM orders;""", ["ลบ timestamp ได้ผลเป็น interval"]),
   E("สินค้าที่แพงที่สุด (ทุกตัวที่เสมอกัน)", """SELECT name, price
FROM products
WHERE price = (SELECT MAX(price) FROM products);""", ["subquery หาค่าสูงสุดก่อน แล้วเลือกทุกแถวที่ราคาเท่านั้น"])],
  [M("เลือกชื่อคู่กับ MAX", "SELECT name, MAX(price) FROM products;", "SELECT name, price FROM products WHERE price = (SELECT MAX(price) FROM products);",
     "SQL ไม่รู้ว่า name ไหนคู่กับ MAX")],
  ["aggregate-functions", "subqueries"]),

L("group-by", "GROUP BY — สรุปผลตามกลุ่ม",
  "แบ่งแถวเป็นกลุ่มแล้วคำนวณ aggregate ต่อกลุ่ม เช่นยอดขายต่อเดือน ลูกค้าต่อเมือง",
  ["จัดกลุ่มข้อมูลด้วย GROUP BY", "จัดกลุ่มหลายคอลัมน์", "เข้าใจกฎคอลัมน์ใน SELECT เมื่อมี GROUP BY"],
  """
```sql
SELECT group_col, AGG(x)
FROM t
GROUP BY group_col;
```
1. FROM/WHERE ได้ชุดแถว
2. GROUP BY แบ่งแถวที่มีค่า group_col เท่ากันเป็นกลุ่มเดียว (NULL รวมเป็นกลุ่มเดียว)
3. aggregate ทำงานต่อกลุ่ม → ได้ 1 แถวต่อกลุ่ม

**กฎ:** ทุกคอลัมน์ใน SELECT ต้องอยู่ใน GROUP BY หรืออยู่ใน aggregate
(ยกเว้นคอลัมน์ที่ขึ้นกับ primary key ที่ group แล้ว — PostgreSQL อนุญาต)

จัดกลุ่มด้วยนิพจน์ได้ เช่น `GROUP BY DATE_TRUNC('month', order_date)`
""",
  [E("จำนวนลูกค้าต่อเมือง", """SELECT city, COUNT(*) AS customers
FROM customers
GROUP BY city
ORDER BY customers DESC;""", ["แต่ละเมืองกลายเป็น 1 แถว", "NULL เป็นกลุ่มหนึ่ง", "เรียงด้วย alias ได้เพราะ ORDER BY ทำงานหลัง SELECT"]),
   E("จำนวนคำสั่งซื้อต่อปีและสถานะ", """SELECT EXTRACT(YEAR FROM order_date) AS year, status, COUNT(*) AS orders
FROM orders
GROUP BY EXTRACT(YEAR FROM order_date), status
ORDER BY year, status;""", ["จัดกลุ่ม 2 ระดับ: ปี × สถานะ", "`EXTRACT(YEAR FROM ...)` ดึงปีจากวันที่"])],
  [M("ลืมใส่คอลัมน์ใน GROUP BY", "SELECT city, country, COUNT(*) FROM customers GROUP BY city;",
     "SELECT city, country, COUNT(*) FROM customers GROUP BY city, country;", "country ต้องอยู่ใน GROUP BY"),
   M("ใช้ WHERE กรองผล aggregate", "SELECT city, COUNT(*) FROM customers WHERE COUNT(*) > 5 GROUP BY city;",
     "SELECT city, COUNT(*) FROM customers GROUP BY city HAVING COUNT(*) > 5;", "aggregate ใช้ใน WHERE ไม่ได้ → ใช้ HAVING")],
  ["having", "aggregate-functions", "date-functions"]),

L("having", "HAVING — กรองกลุ่ม",
  "กรองผลลัพธ์หลังจากจัดกลุ่ม และความต่างระหว่าง WHERE กับ HAVING",
  ["กรองกลุ่มด้วย HAVING", "เลือกใช้ WHERE หรือ HAVING ได้ถูก", "ใช้ทั้งสองอย่างใน query เดียว"],
  """
| | WHERE | HAVING |
|---|---|---|
| ทำงานเมื่อ | **ก่อน** GROUP BY | **หลัง** GROUP BY |
| กรองอะไร | แถว | กลุ่ม |
| ใช้ aggregate ได้ | ❌ | ✅ |

**หลักปฏิบัติ:** เงื่อนไขที่ไม่เกี่ยวกับ aggregate ให้ใส่ใน WHERE เสมอ — กรองแถวออกก่อนทำให้เร็วกว่า
""",
  [E("ลูกค้าที่สั่งซื้อ (ไม่นับยกเลิก) ตั้งแต่ 10 ครั้ง", """SELECT customer_id, COUNT(*) AS orders
FROM orders
WHERE status <> 'cancelled'
GROUP BY customer_id
HAVING COUNT(*) >= 10
ORDER BY orders DESC;""", ["WHERE ตัดคำสั่งซื้อที่ยกเลิกก่อนจัดกลุ่ม", "HAVING เก็บเฉพาะกลุ่มที่มี ≥ 10 คำสั่งซื้อ"])],
  [M("ใส่เงื่อนไขธรรมดาใน HAVING", "GROUP BY customer_id HAVING customer_id > 100", "WHERE customer_id > 100 GROUP BY customer_id",
     "ได้ผลเหมือนกันแต่ช้ากว่า และอ่านยากกว่า")],
  ["group-by", "aggregate-functions"]),

L("inner-join", "INNER JOIN — รวมตารางที่มีข้อมูลตรงกัน",
  "เชื่อมข้อมูลจากหลายตารางด้วย key และ JOIN มากกว่า 2 ตาราง",
  ["JOIN 2 ตารางด้วย ON", "JOIN หลายตาราง", "เข้าใจว่า INNER JOIN ตัดแถวที่ไม่มีคู่"],
  """
```sql
SELECT o.id, c.first_name
FROM orders o
INNER JOIN customers c ON c.id = o.customer_id;
```
INNER JOIN (หรือเขียนแค่ `JOIN`) จับคู่แถวจากสองตารางที่ **เงื่อนไข ON เป็นจริง** — แถวที่ไม่มีคู่จะ **หายไป**

```
customers            orders               INNER JOIN
id | name            id | customer_id     name | order
1  | Anan    ─────── 10 | 1               Anan | 10
2  | Pim     ─────── 11 | 2               Pim  | 11
3  | Krit             (ไม่มี order)        (Krit หายไป)
```

### เคล็ดลับ
- ตั้ง alias ให้ทุกตาราง และอ้างคอลัมน์ด้วย alias เสมอ
- **ความสัมพันธ์ 1:N ทำให้แถวเพิ่ม** — ลูกค้า 1 คน JOIN กับ 10 คำสั่งซื้อได้ 10 แถว
- JOIN หลายตาราง: ต่อทีละคู่ตามเส้นทาง FK เช่น `order_items → orders → customers` และ `order_items → products → categories`
""",
  [E("คำสั่งซื้อพร้อมชื่อลูกค้า", """SELECT o.id AS order_id, o.order_date, c.first_name || ' ' || c.last_name AS customer
FROM orders o
JOIN customers c ON c.id = o.customer_id
ORDER BY o.order_date DESC
LIMIT 5;""", ["`ON c.id = o.customer_id` คือเงื่อนไขจับคู่ตาม FK"]),
   E("JOIN 4 ตาราง: ยอดขายต่อหมวดหมู่", """SELECT cat.name AS category, SUM(oi.unit_price * oi.quantity) AS revenue
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN products p ON p.id = oi.product_id
JOIN categories cat ON cat.id = p.category_id
WHERE o.status <> 'cancelled'
GROUP BY cat.name
ORDER BY revenue DESC;""", ["order_items → orders เพื่อกรองสถานะ", "order_items → products → categories เพื่อได้ชื่อหมวด",
                             "สินค้าที่ไม่มีหมวด (category_id NULL) หายไปเพราะ INNER JOIN"])],
  [M("ลืมเงื่อนไข ON (Cartesian product)", "SELECT * FROM orders, customers;", "SELECT * FROM orders o JOIN customers c ON c.id = o.customer_id;",
     "ทุกแถวคูณทุกแถว: 900 × 150 = 135,000 แถว"),
   M("ไม่ระบุตารางของคอลัมน์ที่ชื่อซ้ำ", "SELECT id FROM orders o JOIN customers c ON c.id = o.customer_id;",
     "SELECT o.id FROM orders o JOIN customers c ON c.id = o.customer_id;", "error: column reference \"id\" is ambiguous")],
  ["left-join", "self-join", "foreign-key"]),

L("left-join", "LEFT JOIN — เก็บทุกแถวของตารางซ้าย",
  "รวมตารางโดยไม่ทิ้งแถวฝั่งซ้ายที่ไม่มีคู่ และใช้หา 'สิ่งที่ไม่มี' (anti-join)",
  ["ใช้ LEFT JOIN เก็บแถวที่ไม่มีคู่", "หาแถวที่ไม่มีความสัมพันธ์ด้วย IS NULL", "วางเงื่อนไขใน ON vs WHERE ให้ถูก"],
  """
LEFT JOIN คืน **ทุกแถวของตารางซ้าย** — ถ้าไม่มีคู่ฝั่งขวา คอลัมน์ฝั่งขวาจะเป็น `NULL`

### Pattern: หาสิ่งที่ "ไม่มี" (anti-join)
```sql
SELECT c.* FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.id IS NULL;     -- ลูกค้าที่ไม่เคยสั่งซื้อ
```

### ⚠️ ON vs WHERE
- เงื่อนไขของตาราง **ขวา** ใส่ใน `ON` → ยังเก็บแถวซ้ายไว้
- ถ้าใส่ใน `WHERE` → แถวที่ฝั่งขวาเป็น NULL ถูกตัด → กลายเป็น INNER JOIN โดยไม่รู้ตัว

### ⚠️ COUNT กับ LEFT JOIN
`COUNT(*)` นับแถวที่ไม่มีคู่เป็น 1 → ใช้ `COUNT(o.id)` เพื่อได้ 0
""",
  [E("จำนวนคำสั่งซื้อของลูกค้าทุกคน (รวมคนที่ไม่เคยซื้อ)", """SELECT c.id, c.first_name, COUNT(o.id) AS orders
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.first_name
ORDER BY orders, c.id
LIMIT 10;""", ["ลูกค้าที่ไม่มี order ได้ orders = 0 เพราะ `COUNT(o.id)` ไม่นับ NULL"]),
   E("สินค้าที่ไม่เคยขายได้", """SELECT p.id, p.name
FROM products p
LEFT JOIN order_items oi ON oi.product_id = p.id
WHERE oi.id IS NULL;""", ["`WHERE oi.id IS NULL` เก็บเฉพาะสินค้าที่ไม่มีรายการขายเลย"])],
  [M("กรองตารางขวาใน WHERE", "LEFT JOIN orders o ON o.customer_id = c.id WHERE o.status = 'paid'",
     "LEFT JOIN orders o ON o.customer_id = c.id AND o.status = 'paid'", "ลูกค้าที่ไม่มี order 'paid' จะหายไปทั้งหมด"),
   M("ใช้ COUNT(*) กับ LEFT JOIN", "COUNT(*)", "COUNT(o.id)", "ลูกค้าที่ไม่มี order จะได้ 1 แทน 0")],
  ["inner-join", "right-join", "exists"]),

L("right-join", "RIGHT JOIN — เก็บทุกแถวของตารางขวา",
  "RIGHT JOIN คือ LEFT JOIN กลับด้าน และทำไมในทางปฏิบัติจึงนิยมเขียนเป็น LEFT JOIN",
  ["อธิบาย RIGHT JOIN", "แปลง RIGHT JOIN เป็น LEFT JOIN ได้"],
  """
`A RIGHT JOIN B` = `B LEFT JOIN A` — เก็บทุกแถวของตาราง **ขวา**

ทีมส่วนใหญ่ใช้ **LEFT JOIN อย่างเดียว** เพราะอ่านจากบนลงล่างได้เป็นธรรมชาติ ("เริ่มจากตารางหลัก แล้วต่อข้อมูลเสริม")
แต่ควรอ่าน RIGHT JOIN ออกเพราะเจอในโค้ดเก่าและข้อสอบสัมภาษณ์
""",
  [E("แผนกทุกแผนกพร้อมจำนวนพนักงาน (RIGHT JOIN)", """SELECT d.name AS department, COUNT(e.id) AS employees
FROM employees e
RIGHT JOIN departments d ON d.id = e.department_id
GROUP BY d.name
ORDER BY employees;""", ["departments อยู่ขวา → ทุกแผนกถูกเก็บ รวมแผนก Research ที่ไม่มีพนักงาน"], db="hr"),
   E("เขียนแบบ LEFT JOIN ได้ผลเดียวกัน", """SELECT d.name AS department, COUNT(e.id) AS employees
FROM departments d
LEFT JOIN employees e ON e.department_id = d.id
GROUP BY d.name
ORDER BY employees;""", ["สลับตำแหน่งตารางแล้วเปลี่ยนเป็น LEFT JOIN"], db="hr")],
  [M("สับสนว่าตารางไหนคือ 'ขวา'", "FROM departments d RIGHT JOIN employees e ...", "FROM employees e RIGHT JOIN departments d ...",
     "ตารางขวาคือตารางที่อยู่หลังคำว่า JOIN")],
  ["left-join", "full-outer-join"]),

L("full-outer-join", "FULL OUTER JOIN — เก็บทุกแถวทั้งสองฝั่ง",
  "รวมทุกแถวจากทั้งสองตาราง ใช้ตรวจสอบความสอดคล้องของข้อมูล (data reconciliation)",
  ["ใช้ FULL OUTER JOIN", "หาแถวที่ไม่มีคู่จากทั้งสองฝั่งในคราวเดียว"],
  """
FULL OUTER JOIN = LEFT + RIGHT — เก็บทุกแถวของทั้งสองตาราง ฝั่งที่ไม่มีคู่จะเป็น NULL

Use case ในงานจริง: **กระทบยอด (reconciliation)** เช่น เปรียบเทียบรายการจากระบบ A กับระบบ B
- มีทั้งสองฝั่ง → ตรงกัน
- มีแต่ซ้าย → ขาดในระบบ B
- มีแต่ขวา → ขาดในระบบ A
""",
  [E("พนักงานกับแผนก — ใครไม่มีแผนก และแผนกไหนไม่มีคน", """SELECT e.first_name, e.last_name, d.name AS department
FROM employees e
FULL OUTER JOIN departments d ON d.id = e.department_id
WHERE e.id IS NULL OR d.id IS NULL;""", ["พนักงานที่ department_id เป็น NULL → department เป็น NULL",
                                          "แผนก Research ที่ไม่มีพนักงาน → ชื่อพนักงานเป็น NULL"], db="hr")],
  [M("ใช้ FULL JOIN เมื่อต้องการแค่ฝั่งเดียว", "FULL OUTER JOIN", "LEFT JOIN", "ได้แถวเกินมาและอ่านยาก")],
  ["left-join", "right-join", "union"]),

L("self-join", "SELF JOIN — JOIN ตารางกับตัวเอง",
  "ใช้กับข้อมูลลำดับชั้น เช่นพนักงาน–หัวหน้า หรือหมวดหมู่–หมวดแม่",
  ["JOIN ตารางเดียวกันด้วย alias ต่างกัน", "แสดงความสัมพันธ์ลำดับชั้น 1 ระดับ", "เปรียบเทียบแถวในตารางเดียวกัน"],
  """
Self join ไม่ใช่คำสั่งพิเศษ — คือการ JOIN ตารางเดิมโดยตั้ง **alias สองชื่อ** ให้เหมือนเป็นสองตาราง

```sql
SELECT e.first_name AS employee, m.first_name AS manager
FROM employees e
LEFT JOIN employees m ON m.id = e.manager_id;
```
- `e` = บทบาท "ลูกน้อง", `m` = บทบาท "หัวหน้า"
- ใช้ LEFT JOIN เพื่อไม่ให้ CEO (manager_id = NULL) หายไป
- ถ้าลำดับชั้นหลายระดับ (หัวหน้าของหัวหน้า...) ใช้ **Recursive CTE**
""",
  [E("พนักงานพร้อมชื่อหัวหน้า", """SELECT e.id, e.first_name || ' ' || e.last_name AS employee,
       m.first_name || ' ' || m.last_name AS manager
FROM employees e
LEFT JOIN employees m ON m.id = e.manager_id
ORDER BY e.id
LIMIT 10;""", ["`m.id = e.manager_id` จับคู่ลูกน้องกับหัวหน้า", "แถวแรก (CEO) มี manager เป็น NULL"], db="hr"),
   E("หมวดหมู่ย่อยพร้อมหมวดแม่", """SELECT child.name AS category, parent.name AS parent_category
FROM categories child
LEFT JOIN categories parent ON parent.id = child.parent_id
ORDER BY parent.name NULLS FIRST, child.name;""", ["หมวดระดับบนสุดไม่มีหมวดแม่"])],
  [M("ใช้ INNER JOIN แล้ว CEO หาย", "JOIN employees m ON m.id = e.manager_id", "LEFT JOIN employees m ON m.id = e.manager_id",
     "คนที่ไม่มีหัวหน้าไม่มีคู่ จึงหายไป")],
  ["inner-join", "recursive-cte"]),

L("union", "UNION และ UNION ALL — รวมผลลัพธ์แนวตั้ง",
  "ต่อผลลัพธ์ของหลาย query เข้าด้วยกัน พร้อมรู้จัก INTERSECT และ EXCEPT",
  ["ใช้ UNION / UNION ALL", "เข้าใจเงื่อนไขจำนวนคอลัมน์และชนิดข้อมูล", "ใช้ INTERSECT / EXCEPT"],
  """
JOIN ต่อตาราง **แนวนอน** (เพิ่มคอลัมน์), UNION ต่อ **แนวตั้ง** (เพิ่มแถว)

| ตัวดำเนินการ | ผล |
|---|---|
| `UNION` | รวม + **ตัดแถวซ้ำ** (ต้อง sort/hash → ช้ากว่า) |
| `UNION ALL` | รวมทั้งหมด **เก็บแถวซ้ำ** (เร็วกว่า) |
| `INTERSECT` | เฉพาะแถวที่มีในทั้งสอง |
| `EXCEPT` | แถวใน query แรกที่ไม่มีใน query ที่สอง |

**กฎ:** จำนวนคอลัมน์ต้องเท่ากัน, ชนิดข้อมูลเข้ากันได้, ชื่อคอลัมน์มาจาก query แรก, `ORDER BY` ใส่ได้ครั้งเดียวท้ายสุด
""",
  [E("รายชื่อเมืองจากลูกค้าและจากที่อยู่จัดส่ง", """SELECT city FROM customers WHERE city IS NOT NULL
UNION
SELECT shipping_city FROM orders WHERE shipping_city IS NOT NULL
ORDER BY city;""", ["UNION ตัดเมืองที่ซ้ำให้เหลือเมืองละ 1 แถว"]),
   E("รวม 'กิจกรรม' จากสองตารางพร้อมป้ายกำกับ", """SELECT 'order' AS activity, id, order_date AS at FROM orders WHERE order_date >= '2025-12-28'
UNION ALL
SELECT 'payment', id, payment_date FROM payments WHERE payment_date >= '2025-12-28'
ORDER BY at;""", ["ค่าคงที่ 'order'/'payment' บอกที่มาของแต่ละแถว", "UNION ALL เพราะไม่ต้องการตัดซ้ำ"]),
   E("EXCEPT — ลูกค้าที่ไม่เคยสั่งซื้อ", """SELECT id FROM customers
EXCEPT
SELECT customer_id FROM orders
ORDER BY id;""", ["ได้ id ที่มีใน customers แต่ไม่มีใน orders"])],
  [M("ใช้ UNION เมื่อไม่ต้องตัดซ้ำ", "SELECT ... UNION SELECT ...", "SELECT ... UNION ALL SELECT ...",
     "UNION ต้องเรียง/แฮชเพื่อตัดซ้ำ ช้ากว่าและอาจทำข้อมูลที่ซ้ำโดยชอบธรรมหาย"),
   M("จำนวนคอลัมน์ไม่เท่ากัน", "SELECT id, city FROM customers UNION SELECT id FROM orders", "SELECT id, city FROM customers UNION SELECT id, shipping_city FROM orders",
     "each UNION query must have the same number of columns")],
  ["full-outer-join", "exists"]),

L("case-when", "CASE WHEN — ตรรกะเงื่อนไขใน SQL",
  "สร้างคอลัมน์ตามเงื่อนไข จัดหมวดหมู่ข้อมูล และทำ pivot ด้วย conditional aggregation",
  ["เขียน searched CASE และ simple CASE", "ใช้ CASE จัดกลุ่มข้อมูล (bucketing)", "ใช้ CASE ภายใน aggregate"],
  """
```sql
CASE
  WHEN condition1 THEN result1
  WHEN condition2 THEN result2
  ELSE default_result      -- ถ้าไม่ใส่ ELSE จะได้ NULL
END
```
- ประเมิน **ตามลำดับ** และหยุดที่ WHEN แรกที่เป็นจริง → ใส่เงื่อนไขที่เจาะจงที่สุดก่อน
- Simple CASE: `CASE status WHEN 'paid' THEN 'จ่ายแล้ว' ... END`
- ใช้ได้ทุกที่ที่ใส่ expression ได้: SELECT, WHERE, ORDER BY, GROUP BY และในฟังก์ชัน aggregate

### Conditional aggregation (pivot)
```sql
SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END)
```
""",
  [E("จัดระดับราคาสินค้า", """SELECT name, price,
       CASE
         WHEN price >= 20000 THEN 'Premium'
         WHEN price >= 3000  THEN 'Mid-range'
         ELSE 'Budget'
       END AS price_tier
FROM products
ORDER BY price DESC
LIMIT 10;""", ["ตรวจจากราคาสูงลงต่ำ เงื่อนไขแรกที่จริงชนะ"]),
   E("Pivot: จำนวนคำสั่งซื้อแต่ละสถานะต่อปี", """SELECT EXTRACT(YEAR FROM order_date) AS year,
       SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) AS delivered,
       SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
       SUM(CASE WHEN status IN ('pending','paid','shipped') THEN 1 ELSE 0 END) AS in_progress
FROM orders
GROUP BY 1
ORDER BY 1;""", ["แต่ละ CASE กลายเป็นคอลัมน์หนึ่ง", "`GROUP BY 1` = จัดกลุ่มตามคอลัมน์ที่ 1 ใน SELECT"])],
  [M("เรียงเงื่อนไขผิด", "WHEN price >= 3000 THEN 'Mid' WHEN price >= 20000 THEN 'Premium'",
     "WHEN price >= 20000 THEN 'Premium' WHEN price >= 3000 THEN 'Mid'", "สินค้า 30,000 จะตกเป็น Mid เพราะเงื่อนไขแรกจริงก่อน"),
   M("ลืม ELSE", "CASE WHEN price > 1000 THEN 'high' END", "CASE WHEN price > 1000 THEN 'high' ELSE 'low' END",
     "แถวที่ไม่ตรงเงื่อนไขได้ NULL")],
  ["group-by", "aggregate-functions"]),

L("string-functions", "String Functions — จัดการข้อความ",
  "ฟังก์ชันข้อความที่ใช้บ่อย: UPPER/LOWER, TRIM, LENGTH, SUBSTRING, REPLACE, CONCAT, SPLIT_PART และการทำความสะอาดข้อมูล",
  ["แปลงตัวพิมพ์และตัดช่องว่าง", "ตัด/ค้นหา/แทนที่ข้อความ", "ทำความสะอาดข้อมูลที่สะกดไม่สม่ำเสมอ"],
  """
| ฟังก์ชัน | ตัวอย่าง | ผล |
|---|---|---|
| `UPPER / LOWER / INITCAP` | `INITCAP('bangkok')` | Bangkok |
| `TRIM / LTRIM / RTRIM` | `TRIM('  a ')` | a |
| `LENGTH` | `LENGTH('SQL')` | 3 |
| `SUBSTRING(s FROM i FOR n)` / `LEFT / RIGHT` | `LEFT('Bangkok', 3)` | Ban |
| `POSITION(sub IN s)` | `POSITION('@' IN 'a@b.com')` | 2 |
| `REPLACE(s, from, to)` | `REPLACE('a-b', '-', '/')` | a/b |
| `CONCAT(a, b, ...)` / `||` | `CONCAT('A', NULL, 'B')` | AB |
| `SPLIT_PART(s, delim, n)` | `SPLIT_PART('a@b.com', '@', 2)` | b.com |
| `LPAD / RPAD` | `LPAD('7', 3, '0')` | 007 |

> `CONCAT` ข้าม NULL แต่ `||` กับ NULL ได้ NULL

**Data cleaning:** `INITCAP(TRIM(city))` ทำให้ `'bangkok'` และ `'Bangkok'` กลายเป็นค่าเดียวกัน
""",
  [E("โดเมนอีเมลของลูกค้า", """SELECT SPLIT_PART(email, '@', 2) AS domain, COUNT(*) AS customers
FROM customers
GROUP BY 1
ORDER BY customers DESC;""", ["`SPLIT_PART(email, '@', 2)` เอาส่วนหลัง @"]),
   E("ทำความสะอาดชื่อเมืองก่อนนับ", """SELECT INITCAP(TRIM(city)) AS clean_city, COUNT(*) AS customers
FROM customers
WHERE city IS NOT NULL
GROUP BY 1
ORDER BY customers DESC
LIMIT 5;""", ["`bangkok` และ `Bangkok` ถูกรวมเป็นกลุ่มเดียวแล้ว"]),
   E("สร้างรหัสสินค้า", """SELECT id, name, 'P-' || LPAD(id::text, 4, '0') AS sku, UPPER(LEFT(name, 3)) AS short
FROM products
ORDER BY id
LIMIT 5;""", ["`id::text` แปลงตัวเลขเป็นข้อความ", "`LPAD(..., 4, '0')` เติม 0 ข้างหน้าให้ครบ 4 หลัก"])],
  [M("ใช้ || กับค่าที่อาจเป็น NULL", "first_name || ' ' || middle_name || ' ' || last_name",
     "CONCAT_WS(' ', first_name, middle_name, last_name)", "ถ้ามีค่า NULL ทั้งข้อความกลายเป็น NULL")],
  ["like", "date-functions"]),

L("date-functions", "Date Functions — วันที่และเวลา",
  "ดึงส่วนของวันที่, ตัดรอบเดือน, คำนวณช่วงเวลา และจัดรูปแบบวันที่",
  ["ใช้ EXTRACT และ DATE_TRUNC", "คำนวณด้วย INTERVAL และ AGE", "จัดรูปแบบด้วย TO_CHAR"],
  """
| ฟังก์ชัน | ใช้ทำอะไร | ตัวอย่าง |
|---|---|---|
| `CURRENT_DATE`, `NOW()` | วันที่/เวลาปัจจุบัน | |
| `EXTRACT(field FROM d)` | ดึงปี เดือน วัน ชั่วโมง วันในสัปดาห์ (`DOW`: 0=อาทิตย์) | `EXTRACT(MONTH FROM order_date)` |
| `DATE_TRUNC('month', d)` | ปัดลงเป็นต้นเดือน — **ดีที่สุดสำหรับ group รายเดือน** | 2025-03-17 → 2025-03-01 |
| `d + INTERVAL '30 days'` | บวก/ลบช่วงเวลา | |
| `d2 - d1` | ผลต่าง (date−date = จำนวนวัน, timestamp−timestamp = interval) | |
| `AGE(d2, d1)` | ผลต่างแบบปี/เดือน/วัน | `AGE(birth_date)` |
| `TO_CHAR(d, 'YYYY-MM')` | จัดรูปแบบเป็นข้อความ | 2025-03 |
| `d::date` | ตัดเวลาทิ้ง | |

> ข้อมูลตัวอย่างอยู่ในช่วง ปี 2024–2025 — ระวังการใช้ `CURRENT_DATE` ในโจทย์ เพราะผลจะเปลี่ยนตามวันที่จริง
""",
  [E("ยอดคำสั่งซื้อรายเดือน (ปี 2025)", """SELECT DATE_TRUNC('month', order_date)::date AS month, COUNT(*) AS orders
FROM orders
WHERE order_date >= '2025-01-01' AND order_date < '2026-01-01'
GROUP BY 1
ORDER BY 1;""", ["`DATE_TRUNC('month', ...)` ทำให้ทุกวันในเดือนมีค่าเดียวกัน", "`::date` ตัดส่วนเวลาออกเพื่อให้อ่านง่าย"]),
   E("วันในสัปดาห์ที่มีคำสั่งซื้อมากที่สุด", """SELECT TO_CHAR(order_date, 'Day') AS weekday, EXTRACT(ISODOW FROM order_date) AS dow, COUNT(*) AS orders
FROM orders
GROUP BY 1, 2
ORDER BY dow;""", ["`ISODOW`: จันทร์=1 … อาทิตย์=7"]),
   E("อายุผู้ป่วย ณ วันนัด", """SELECT a.id, p.full_name, a.scheduled_at::date AS visit_date,
       EXTRACT(YEAR FROM AGE(a.scheduled_at, p.birth_date)) AS age_at_visit
FROM appointments a
JOIN patients p ON p.id = a.patient_id
ORDER BY a.id
LIMIT 5;""", ["`AGE(a, b)` คืน interval แบบ ปี-เดือน-วัน", "`EXTRACT(YEAR FROM ...)` ดึงเฉพาะจำนวนปี"], db="hospital")],
  [M("group ด้วย EXTRACT(MONTH) อย่างเดียว", "GROUP BY EXTRACT(MONTH FROM order_date)", "GROUP BY DATE_TRUNC('month', order_date)",
     "มกราคม 2024 กับ มกราคม 2025 จะถูกรวมเป็นกลุ่มเดียวกัน")],
  ["between", "group-by", "lag-lead"]),
]
