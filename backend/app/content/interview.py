"""Mock SQL interview question bank — classic questions asked in Data Analyst / Data Engineer interviews."""
from app.content.model import ExerciseDef as X

QUESTIONS = [
X("IV-01", "เงินเดือนสูงสุดอันดับ 3", "หาเงินเดือนปัจจุบัน (`effective_to IS NULL`) ที่สูงเป็นอันดับ **3** แบบไม่นับค่าซ้ำ ในคอลัมน์ **amount** (ถ้าไม่มีให้ได้ 0 แถว)",
  "hard", "Interview", "hr",
  "SELECT DISTINCT amount FROM (SELECT amount, DENSE_RANK() OVER (ORDER BY amount DESC) AS r FROM salaries WHERE effective_to IS NULL) t WHERE r = 3;",
  ["ค่าที่เท่ากันต้องได้อันดับเดียวกัน", "DENSE_RANK หรือ subquery แบบ OFFSET บนค่า DISTINCT", "DENSE_RANK() OVER (ORDER BY amount DESC) แล้วกรอง = 3"],
  "คำถามคลาสสิก: N-th highest — DENSE_RANK ถูกต้องเมื่อมีค่าซ้ำ ส่วน `ORDER BY ... LIMIT 1 OFFSET 2` ผิดถ้าไม่ DISTINCT ก่อน", interview=True),
X("IV-02", "หาข้อมูลซ้ำ", "ลูกค้าที่ชื่อและนามสกุลซ้ำกัน แสดง **first_name**, **last_name**, **n** (จำนวนคน) เฉพาะที่มีมากกว่า 1 คน",
  "medium", "Interview", "ecommerce",
  "SELECT first_name, last_name, COUNT(*) AS n FROM customers GROUP BY first_name, last_name HAVING COUNT(*) > 1;",
  ["จัดกลุ่มด้วยคอลัมน์ที่ใช้ระบุ 'ซ้ำ'", "นับในกลุ่มแล้วกรองกลุ่ม", "GROUP BY first_name, last_name HAVING COUNT(*) > 1"],
  "การหาข้อมูลซ้ำ = GROUP BY คีย์ที่สนใจ + HAVING COUNT(*) > 1", interview=True),
X("IV-03", "พนักงานที่เข้างานก่อนหัวหน้า", "แสดง **employee_id**, **employee_hired**, **manager_hired** ของพนักงานที่ `hire_date` เก่ากว่าหัวหน้าโดยตรงของตัวเอง",
  "medium", "Interview", "hr",
  """SELECT e.id AS employee_id, e.hire_date AS employee_hired, m.hire_date AS manager_hired
FROM employees e JOIN employees m ON m.id = e.manager_id
WHERE e.hire_date < m.hire_date;""",
  ["ต้องเปรียบเทียบแถวของพนักงานกับแถวของหัวหน้าในตารางเดียวกัน", "self join ผ่าน manager_id", "employees e JOIN employees m ON m.id = e.manager_id WHERE e.hire_date < m.hire_date"],
  "Self join เพื่อเปรียบเทียบแถวในตารางเดียวกัน — ตั้ง alias ให้ชัดว่าฝั่งไหนคือพนักงาน ฝั่งไหนคือหัวหน้า", interview=True),
X("IV-04", "แผนกที่ไม่มีพนักงาน", "แสดง **department** (ชื่อแผนก) ที่ไม่มีพนักงานเลย", "easy", "Interview", "hr",
  "SELECT d.name AS department FROM departments d WHERE NOT EXISTS (SELECT 1 FROM employees e WHERE e.department_id = d.id);",
  ["หาสิ่งที่ 'ไม่มี' ความสัมพันธ์", "NOT EXISTS หรือ LEFT JOIN … IS NULL", "WHERE NOT EXISTS (SELECT 1 FROM employees e WHERE e.department_id = d.id)"],
  "Anti-join — NOT EXISTS ปลอดภัยกว่า NOT IN เมื่อมี NULL (employees.department_id มี NULL!)", interview=True),
X("IV-05", "Top 2 สินค้าต่อหมวด", "สินค้า 2 อันดับแรกของแต่ละหมวด (`category_id`) ตามรายได้รวม `unit_price * quantity` จากทุกคำสั่งซื้อ (ถ้าเท่ากันให้ product id น้อยกว่าก่อน) แสดง **category_id**, **product_id**, **revenue**",
  "hard", "Interview", "ecommerce",
  """WITH r AS (SELECT p.category_id, p.id AS product_id, SUM(oi.unit_price * oi.quantity) AS revenue
  FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.category_id IS NOT NULL GROUP BY p.category_id, p.id),
k AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY revenue DESC, product_id) AS rn FROM r)
SELECT category_id, product_id, revenue FROM k WHERE rn <= 2;""",
  ["สรุปรายได้ต่อสินค้าก่อน", "จัดอันดับภายในหมวด", "ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY revenue DESC, product_id) <= 2"],
  "Top-N per group: aggregate → window ranking → filter ใน query นอก", interview=True),
X("IV-06", "ลูกค้าที่ซื้อทั้งปี 2024 และ 2025", "แสดง **customer_id** ของลูกค้าที่มีคำสั่งซื้อทั้งในปี 2024 และปี 2025", "medium", "Interview", "ecommerce",
  """SELECT customer_id FROM orders WHERE order_date >= '2024-01-01' AND order_date < '2025-01-01'
INTERSECT
SELECT customer_id FROM orders WHERE order_date >= '2025-01-01' AND order_date < '2026-01-01';""",
  ["ต้องมีทั้งสองเงื่อนไขในระดับลูกค้า ไม่ใช่ระดับแถว", "INTERSECT หรือ GROUP BY + HAVING COUNT(DISTINCT ปี) = 2", "SELECT … 2024 INTERSECT SELECT … 2025"],
  "WHERE ปี = 2024 AND ปี = 2025 ใช้ไม่ได้ (แถวเดียวเป็นสองปีไม่ได้) — ต้องคิดระดับกลุ่ม", interview=True),
X("IV-07", "ยอดชำระสะสมรายวัน ธันวาคม 2025", "แสดง **day** (`payment_date::date`), **amount** (ยอดชำระรวมของวัน), **running_total** สำหรับเดือนธันวาคม 2025 เรียงตามวัน",
  "hard", "Interview", "ecommerce",
  """WITH d AS (SELECT payment_date::date AS day, SUM(amount) AS amount FROM payments
  WHERE payment_date >= '2025-12-01' AND payment_date < '2026-01-01' GROUP BY 1)
SELECT day, amount, SUM(amount) OVER (ORDER BY day) AS running_total FROM d ORDER BY day;""",
  ["สรุปรายวันก่อน", "window SUM แบบมี ORDER BY", "SUM(amount) OVER (ORDER BY day)"],
  "Running total คือคำถามยอดนิยม — ต้อง aggregate ก่อนแล้วค่อยสะสม", order_matters=True, interview=True),
X("IV-08", "ลูกค้าใหม่รายเดือนและการเปลี่ยนแปลง", "จาก `customers.created_at` ปี 2025 แสดง **month** (`::date`), **new_customers**, **change** (= เดือนนี้ − เดือนก่อน, เดือนแรกเป็น NULL) เรียงตามเดือน",
  "hard", "Interview", "ecommerce",
  """WITH m AS (SELECT DATE_TRUNC('month', created_at)::date AS month, COUNT(*) AS new_customers FROM customers
  WHERE created_at >= '2025-01-01' AND created_at < '2026-01-01' GROUP BY 1)
SELECT month, new_customers, new_customers - LAG(new_customers) OVER (ORDER BY month) AS change FROM m ORDER BY month;""",
  ["นับรายเดือนก่อน", "ดึงค่าเดือนก่อนหน้าด้วย window function", "new_customers - LAG(new_customers) OVER (ORDER BY month)"],
  "LAG เปรียบเทียบกับแถวก่อนหน้า — แถวแรกไม่มีค่าก่อนหน้าจึงเป็น NULL", order_matters=True, interview=True),
X("IV-09", "มัธยฐานยอดคงเหลือตามประเภทบัญชี", "แสดง **account_type** และ **median_balance** (มัธยฐานของ balance บัญชีที่ active)", "medium", "Interview", "banking",
  "SELECT account_type, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY balance) AS median_balance FROM accounts WHERE status = 'active' GROUP BY account_type;",
  ["ค่าเฉลี่ยไม่ใช่มัธยฐาน", "ordered-set aggregate", "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY balance)"],
  "มัธยฐานทนต่อ outlier กว่าค่าเฉลี่ย — ใน PostgreSQL ใช้ PERCENTILE_CONT", interview=True),
X("IV-10", "Pivot สถานะนัดหมายตามปี", "hospital: แสดง **year**, **completed**, **cancelled**, **no_show** (จำนวนนัดของแต่ละสถานะ) ต่อปีของ `scheduled_at` เรียงตามปี",
  "medium", "Interview", "hospital",
  """SELECT EXTRACT(YEAR FROM scheduled_at)::int AS year,
  COUNT(*) FILTER (WHERE status = 'completed') AS completed,
  COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
  COUNT(*) FILTER (WHERE status = 'no_show') AS no_show
FROM appointments GROUP BY 1 ORDER BY 1;""",
  ["แต่ละสถานะเป็นหนึ่งคอลัมน์", "conditional aggregation", "COUNT(*) FILTER (WHERE status = …) หรือ SUM(CASE WHEN …)"],
  "Pivot ด้วย conditional aggregation ทำได้ทุก engine (FILTER หรือ CASE)", order_matters=True, interview=True),
]
