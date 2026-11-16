"""Real-World Projects: a business brief + a sequence of tasks. Each task is an auto-checked exercise
(expected results computed by executing the solution at seed time)."""
from app.content.model import ExerciseDef as X
from app.content.model import ProjectDef as P

VALID = "o.status IN ('paid', 'shipped', 'delivered')"
NET = "oi.unit_price * oi.quantity - COALESCE(oi.discount, 0)"

SALES = P(
    "sales-analysis", "Sales Analysis — ทบทวนยอดขายปี 2025", "Data Analyst",
    "สรุปยอดขายรายเดือน สินค้าขายดี รายได้ตามหมวดหมู่หลัก และการเติบโตเทียบปีก่อน ให้ผู้บริหาร",
    f"""
**สถานการณ์:** คุณเป็น Data Analyst ของร้านค้าออนไลน์ CEO จะประชุมวางแผนปี 2026 และขอ **Sales Review ปี 2025**

**นิยามที่ทีม Finance ตกลงกันแล้ว (ต้องใช้ตามนี้ทุกข้อ)**
- *ยอดขายสุทธิ (net revenue)* ของรายการ = `unit_price * quantity - ส่วนลด` (ส่วนลด NULL = 0)
- นับเฉพาะคำสั่งซื้อที่ status เป็น `paid`, `shipped`, `delivered` (ไม่นับ `pending` และ `cancelled`)
- ปีอ้างอิงจาก `orders.order_date`

```sql
-- เงื่อนไขที่ใช้ซ้ำได้
{VALID}
```
""",
    ["ยอดขายสุทธิรายเดือนปี 2025", "Top 5 สินค้าตามยอดขาย", "ยอดขายตามหมวดหมู่ระดับบนสุด", "การเติบโต YoY"],
    "ecommerce", "hard", [
    X("PJ-SALES-1", "ยอดขายสุทธิรายเดือน 2025", "แสดง **month** (`DATE_TRUNC('month', order_date)::date`) และ **net_revenue** ของทุกเดือนในปี 2025 เรียงตามเดือน",
      "hard", "Analytics", "ecommerce",
      f"""SELECT DATE_TRUNC('month', o.order_date)::date AS month, SUM({NET}) AS net_revenue
FROM orders o JOIN order_items oi ON oi.order_id = o.id
WHERE {VALID} AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
GROUP BY 1 ORDER BY 1;""",
      ["ยอดขายอยู่ใน order_items แต่สถานะและวันที่อยู่ใน orders", "JOIN แล้วกรองตามนิยามใน brief", "SUM(unit_price * quantity - COALESCE(discount, 0)) + GROUP BY DATE_TRUNC"],
      "ข้อนี้คือ 'fact table' ของรายงาน — ตรวจให้ grain ถูก (1 แถว = 1 เดือน) ก่อนไปข้อถัดไป", order_matters=True, project="sales-analysis"),
    X("PJ-SALES-2", "Top 5 สินค้าปี 2025", "แสดง **product**, **units** (จำนวนชิ้น), **net_revenue** ของสินค้า 5 อันดับแรกตาม net_revenue ปี 2025 (มากไปน้อย)",
      "hard", "Analytics", "ecommerce",
      f"""SELECT p.name AS product, SUM(oi.quantity) AS units, SUM({NET}) AS net_revenue
FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id
WHERE {VALID} AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
GROUP BY p.id, p.name ORDER BY net_revenue DESC LIMIT 5;""",
      ["ต้องการชื่อสินค้า — JOIN products", "GROUP BY สินค้า แล้วเรียงตามยอด", "ORDER BY net_revenue DESC LIMIT 5"],
      "จัดกลุ่มด้วย p.id ด้วยเสมอ — สินค้าชื่อซ้ำกันได้ในโลกจริง", order_matters=True, project="sales-analysis"),
    X("PJ-SALES-3", "ยอดขายตามหมวดหมู่ระดับบนสุด", """หมวดหมู่มีหลายระดับ (เช่น Wireless Earbuds → Audio → Electronics) ผู้บริหารต้องการดูที่ **หมวดระดับบนสุด** เท่านั้น
แสดง **category** (ชื่อหมวดบนสุด) และ **net_revenue** ปี 2025 (ไม่นับสินค้าที่ไม่มีหมวด)""",
      "expert", "Analytics", "ecommerce",
      f"""WITH RECURSIVE tree AS (
  SELECT id, id AS root_id FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, t.root_id FROM categories c JOIN tree t ON c.parent_id = t.id
)
SELECT r.name AS category, SUM({NET}) AS net_revenue
FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id
JOIN tree t ON t.id = p.category_id JOIN categories r ON r.id = t.root_id
WHERE {VALID} AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
GROUP BY r.name;""",
      ["ต้อง map ทุกหมวดไปยังหมวดบนสุดของมันก่อน", "Recursive CTE: anchor = หมวดที่ parent_id IS NULL, ส่งต่อ root_id ลงไปทุกระดับ", "WITH RECURSIVE tree AS (SELECT id, id AS root_id ... UNION ALL SELECT c.id, t.root_id ...)"],
      "สร้าง mapping table (id → root_id) ด้วย recursive CTE แล้ว JOIN — ใช้ได้ทุกความลึกของลำดับชั้น", project="sales-analysis"),
    X("PJ-SALES-4", "การเติบโตเทียบปีก่อน (YoY)", "แสดงแถวเดียว: **revenue_2024**, **revenue_2025**, **growth_pct** (= (2025−2024)/2024×100 ปัด 1 ตำแหน่ง)",
      "hard", "Analytics", "ecommerce",
      f"""WITH y AS (
  SELECT SUM({NET}) FILTER (WHERE o.order_date >= '2024-01-01' AND o.order_date < '2025-01-01') AS r24,
         SUM({NET}) FILTER (WHERE o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01') AS r25
  FROM orders o JOIN order_items oi ON oi.order_id = o.id WHERE {VALID})
SELECT r24 AS revenue_2024, r25 AS revenue_2025, ROUND(100 * (r25 - r24) / r24, 1) AS growth_pct FROM y;""",
      ["คำนวณสองปีใน query เดียวด้วย conditional aggregation", "SUM(...) FILTER (WHERE ปี = ...)", "ROUND(100 * (r25 - r24) / r24, 1)"],
      "FILTER ทำ pivot หลายช่วงเวลาได้ในการสแกนครั้งเดียว", project="sales-analysis"),
])

CUSTOMER = P(
    "customer-analysis", "Customer Analysis — เข้าใจลูกค้าเพื่อแคมเปญ CRM", "CRM Analyst",
    "หาลูกค้าที่ใช้จ่ายสูงสุด อัตราการกลับมาซื้อซ้ำ ลูกค้าที่หายไป และแบ่งกลุ่มลูกค้า",
    f"""
**สถานการณ์:** ทีม Marketing จะทำแคมเปญ CRM ไตรมาสหน้า และต้องการข้อมูลเพื่อเลือกกลุ่มเป้าหมาย

**นิยาม**
- *คำสั่งซื้อที่นับ* = status `paid`, `shipped`, `delivered`
- *ยอดใช้จ่าย (spend)* = ผลรวม `unit_price * quantity - ส่วนลด` ของคำสั่งซื้อที่นับ
- วันอ้างอิงของรายงาน = **2025-12-31**
""",
    ["Top 10 ลูกค้าตาม Lifetime Value", "Repeat purchase rate", "ลูกค้าที่หายไป (dormant)", "Customer segments"],
    "ecommerce", "hard", [
    X("PJ-CUST-1", "Top 10 Lifetime Value", "แสดง **customer_id**, **customer** (`first_name || ' ' || last_name`), **orders** (จำนวนคำสั่งซื้อที่นับ), **lifetime_value** ของ 10 อันดับแรก (มากไปน้อย)",
      "hard", "Analytics", "ecommerce",
      f"""SELECT c.id AS customer_id, c.first_name || ' ' || c.last_name AS customer, COUNT(DISTINCT o.id) AS orders, SUM({NET}) AS lifetime_value
FROM customers c JOIN orders o ON o.customer_id = c.id JOIN order_items oi ON oi.order_id = o.id
WHERE {VALID} GROUP BY c.id ORDER BY lifetime_value DESC LIMIT 10;""",
      ["JOIN ถึง order_items ทำให้ 1 คำสั่งซื้อมีหลายแถว", "นับคำสั่งซื้อด้วย COUNT(DISTINCT o.id)", "GROUP BY c.id ORDER BY lifetime_value DESC LIMIT 10"],
      "COUNT(*) หลัง JOIN order_items จะนับ 'รายการสินค้า' ไม่ใช่คำสั่งซื้อ — กับดัก fan-out ที่พบบ่อย", order_matters=True, project="customer-analysis"),
    X("PJ-CUST-2", "อัตราการซื้อซ้ำ", "แสดงแถวเดียว: **buyers** (ลูกค้าที่มีคำสั่งซื้อที่นับ ≥ 1), **repeat_buyers** (≥ 2), **repeat_rate** (%, ปัด 1 ตำแหน่ง)",
      "hard", "Analytics", "ecommerce",
      f"""WITH per AS (SELECT o.customer_id, COUNT(*) AS n FROM orders o WHERE {VALID} GROUP BY o.customer_id)
SELECT COUNT(*) AS buyers, COUNT(*) FILTER (WHERE n >= 2) AS repeat_buyers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE n >= 2) / COUNT(*), 1) AS repeat_rate FROM per;""",
      ["นับจำนวนคำสั่งซื้อต่อคนก่อน", "แล้วสรุปจากผลนั้นอีกชั้น", "COUNT(*) FILTER (WHERE n >= 2)"],
      "aggregate ซ้อน aggregate: สรุปต่อคนใน CTE แล้วสรุปทั้งหมดอีกครั้ง", project="customer-analysis"),
    X("PJ-CUST-3", "ลูกค้าที่หายไป", "ลูกค้าที่เคยมีคำสั่งซื้อที่นับ แต่ครั้งล่าสุดก่อน **2025-06-01** แสดง **customer_id**, **last_order** (`::date`), **days_since** (= `'2025-12-31'::date - last_order`)",
      "hard", "Analytics", "ecommerce",
      f"""SELECT o.customer_id, MAX(o.order_date)::date AS last_order, '2025-12-31'::date - MAX(o.order_date)::date AS days_since
FROM orders o WHERE {VALID} GROUP BY o.customer_id HAVING MAX(o.order_date) < '2025-06-01';""",
      ["หาวันที่ซื้อครั้งล่าสุดของแต่ละคน", "กรองกลุ่มด้วย HAVING", "date − date ได้จำนวนวัน"],
      "ใช้วันอ้างอิงคงที่แทน CURRENT_DATE เพื่อให้รายงานทำซ้ำได้ (reproducible)", project="customer-analysis"),
    X("PJ-CUST-4", "แบ่งกลุ่มลูกค้าตามยอดใช้จ่าย", "จัดลูกค้าที่มีคำสั่งซื้อที่นับเป็น **segment**: `VIP` (spend ≥ 50000), `Regular` (≥ 10000), `Occasional` (ที่เหลือ) แสดง segment, **customers**, **total_spend**",
      "expert", "Analytics", "ecommerce",
      f"""WITH spend AS (SELECT o.customer_id, SUM({NET}) AS s FROM orders o JOIN order_items oi ON oi.order_id = o.id WHERE {VALID} GROUP BY o.customer_id)
SELECT CASE WHEN s >= 50000 THEN 'VIP' WHEN s >= 10000 THEN 'Regular' ELSE 'Occasional' END AS segment,
       COUNT(*) AS customers, SUM(s) AS total_spend
FROM spend GROUP BY 1;""",
      ["ยอดใช้จ่ายต่อคนก่อน (CTE)", "CASE WHEN จากเกณฑ์สูงลงต่ำ", "GROUP BY segment"],
      "segment ที่ได้นำไปทำแคมเปญต่างกัน: VIP = loyalty program, Occasional = กระตุ้นซื้อซ้ำ", project="customer-analysis"),
])

PRODUCT = P(
    "product-analysis", "Product Analysis — สินค้าไหนควรลงทุนต่อ", "Product / Merchandising Analyst",
    "สินค้าขายดี หมวดที่ทำกำไรสูงสุด สินค้าที่ยอดตก และความเสี่ยงสต็อกไม่พอ",
    f"""
**สถานการณ์:** ทีมจัดซื้อกำลังวางแผนสั่งสินค้าและปรับพอร์ตสินค้าปี 2026

**นิยาม**
- คำสั่งซื้อที่นับ = status `paid`, `shipped`, `delivered`
- *กำไรขั้นต้น (gross profit)* = `(unit_price − products.cost) × quantity − ส่วนลด`
- *margin %* = gross profit ÷ net revenue × 100
""",
    ["Top 5 สินค้าตามจำนวนชิ้น", "กำไรและ margin ตามหมวด", "สินค้ายอดตก H1 → H2", "ความเสี่ยงสต็อก"],
    "ecommerce", "hard", [
    X("PJ-PROD-1", "สินค้าขายดีตามจำนวนชิ้น", "แสดง **product**, **units** ของสินค้า 5 อันดับแรกตามจำนวนชิ้นที่ขาย (ทุกปี) ถ้าเท่ากันเรียงชื่อ A→Z",
      "hard", "Analytics", "ecommerce",
      f"""SELECT p.name AS product, SUM(oi.quantity) AS units
FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id
WHERE {VALID} GROUP BY p.id, p.name ORDER BY units DESC, product LIMIT 5;""",
      ["นับจำนวนชิ้น ไม่ใช่จำนวนรายการ", "SUM(quantity)", "ORDER BY units DESC, product LIMIT 5"],
      "ขายดีด้วยจำนวนชิ้น ≠ ขายดีด้วยรายได้ — สินค้าราคาถูกมักชนะในมุมนี้", order_matters=True, project="product-analysis"),
    X("PJ-PROD-2", "กำไรและ margin ตามหมวด", "แสดง **category** (ชื่อหมวดของสินค้าโดยตรง), **gross_profit**, **margin_pct** (ปัด 1 ตำแหน่ง) เรียงกำไรมากไปน้อย (ไม่นับสินค้าไม่มีหมวด)",
      "expert", "Analytics", "ecommerce",
      f"""SELECT c.name AS category, SUM((oi.unit_price - p.cost) * oi.quantity - COALESCE(oi.discount, 0)) AS gross_profit,
       ROUND(100 * SUM((oi.unit_price - p.cost) * oi.quantity - COALESCE(oi.discount, 0)) / SUM({NET}), 1) AS margin_pct
FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id JOIN categories c ON c.id = p.category_id
WHERE {VALID} GROUP BY c.id, c.name ORDER BY gross_profit DESC;""",
      ["ต้นทุนอยู่ที่ products.cost", "margin = กำไร / ยอดขายสุทธิ", "ROUND(100 * SUM(profit) / SUM(net), 1)"],
      "อัตราส่วนต้องคำนวณจาก SUM/SUM ไม่ใช่ AVG ของอัตราส่วนรายแถว", order_matters=True, project="product-analysis"),
    X("PJ-PROD-3", "สินค้าที่ยอดตก", "เทียบจำนวนชิ้นที่ขายครึ่งปีแรก 2025 (ม.ค.–มิ.ย.) กับครึ่งปีหลัง (ก.ค.–ธ.ค.) แสดง **product**, **h1_units**, **h2_units** เฉพาะสินค้าที่ h2 < h1",
      "hard", "Analytics", "ecommerce",
      f"""SELECT p.name AS product,
       COALESCE(SUM(oi.quantity) FILTER (WHERE o.order_date < '2025-07-01'), 0) AS h1_units,
       COALESCE(SUM(oi.quantity) FILTER (WHERE o.order_date >= '2025-07-01'), 0) AS h2_units
FROM orders o JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id
WHERE {VALID} AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01'
GROUP BY p.id, p.name
HAVING COALESCE(SUM(oi.quantity) FILTER (WHERE o.order_date >= '2025-07-01'), 0)
     < COALESCE(SUM(oi.quantity) FILTER (WHERE o.order_date < '2025-07-01'), 0);""",
      ["สองช่วงเวลาใน query เดียว", "SUM(...) FILTER (WHERE ...) และระวัง NULL เมื่อช่วงใดไม่มียอด", "COALESCE(..., 0) + HAVING h2 < h1"],
      "ถ้าไม่ COALESCE สินค้าที่ไม่มียอดครึ่งหลังเลย (NULL) จะหลุดจากการเปรียบเทียบ ทั้งที่ยอดตกหนักที่สุด", project="product-analysis"),
    X("PJ-PROD-4", "ความเสี่ยงสต็อก (months of cover)", """ทีมจัดซื้อต้องการรายการสินค้าที่ต้องสั่งเพิ่มก่อน: คำนวณ *months of cover* = `stock ÷ ยอดขายเฉลี่ยต่อเดือนปี 2025` (units ÷ 12)
แสดง **product**, **stock**, **avg_monthly_units** (ปัด 1), **months_of_cover** (ปัด 1) เฉพาะสินค้า `is_active` ที่ months_of_cover **น้อยกว่า 12** เรียง months_of_cover น้อยไปมาก""",
      "hard", "Analytics", "ecommerce",
      f"""WITH u AS (
  SELECT oi.product_id, SUM(oi.quantity) / 12.0 AS m
  FROM orders o JOIN order_items oi ON oi.order_id = o.id
  WHERE {VALID} AND o.order_date >= '2025-01-01' AND o.order_date < '2026-01-01' GROUP BY oi.product_id)
SELECT p.name AS product, p.stock, ROUND(u.m, 1) AS avg_monthly_units, ROUND(p.stock / u.m, 1) AS months_of_cover
FROM products p JOIN u ON u.product_id = p.id
WHERE p.is_active AND p.stock / u.m < 12
ORDER BY months_of_cover;""",
      ["คำนวณยอดเฉลี่ยต่อเดือนต่อสินค้าใน CTE ก่อน", "หาร 12.0 เพื่อให้เป็นทศนิยม แล้ว stock ÷ ค่านั้น", "WHERE p.is_active AND p.stock / u.m < 12 ORDER BY months_of_cover"],
      "months of cover เปรียบเทียบสต็อกกับอัตราการขาย (run rate) — พื้นฐานของการวางแผนสั่งซื้อ", order_matters=True, project="product-analysis"),
])

EMPLOYEE = P(
    "employee-analysis", "Employee Analysis — รายงานโครงสร้างค่าตอบแทน", "HR / People Analyst",
    "เงินเดือนตามแผนก ขนาดทีมของหัวหน้า การเติบโตของเงินเดือน และอายุงาน",
    """
**สถานการณ์:** ฝ่าย HR เตรียมทบทวนค่าตอบแทนประจำปี และต้องการภาพรวมก่อนประชุมคณะกรรมการ

**นิยาม**
- *เงินเดือนปัจจุบัน* = แถวใน `salaries` ที่ `effective_to IS NULL`
- นับเฉพาะพนักงาน `is_active = true` เว้นแต่โจทย์ระบุอื่น
- วันอ้างอิง = **2025-12-31**
""",
    ["สรุปเงินเดือนตามแผนก", "Span of control ของหัวหน้า", "Top 10 การเติบโตของเงินเดือน", "อายุงาน"],
    "hr", "hard", [
    X("PJ-EMP-1", "สรุปเงินเดือนตามแผนก", "แสดง **department**, **employees**, **avg_salary** (ปัด 2), **min_salary**, **max_salary** ของเงินเดือนปัจจุบัน พนักงาน active ที่มีแผนก",
      "hard", "Analytics", "hr",
      """SELECT d.name AS department, COUNT(*) AS employees, ROUND(AVG(s.amount), 2) AS avg_salary, MIN(s.amount) AS min_salary, MAX(s.amount) AS max_salary
FROM employees e JOIN departments d ON d.id = e.department_id JOIN salaries s ON s.employee_id = e.id AND s.effective_to IS NULL
WHERE e.is_active GROUP BY d.id, d.name;""",
      ["JOIN 3 ตาราง และเลือกเฉพาะเงินเดือนปัจจุบัน", "effective_to IS NULL ใส่ใน ON หรือ WHERE ก็ได้", "GROUP BY แผนก + AVG/MIN/MAX"],
      "ประวัติเงินเดือนมีหลายแถวต่อคน — ลืมกรองเงินเดือนปัจจุบันจะนับคนซ้ำ", project="employee-analysis"),
    X("PJ-EMP-2", "Span of control", "แสดง **manager** (`first_name || ' ' || last_name`) และ **direct_reports** (ลูกน้องโดยตรงทุกสถานะ) เฉพาะหัวหน้าที่มีลูกน้องตั้งแต่ 3 คน",
      "hard", "JOIN", "hr",
      """SELECT m.first_name || ' ' || m.last_name AS manager, COUNT(*) AS direct_reports
FROM employees e JOIN employees m ON m.id = e.manager_id GROUP BY m.id, m.first_name, m.last_name HAVING COUNT(*) >= 3;""",
      ["หัวหน้าอยู่ในตารางเดียวกัน", "Self join แล้วนับต่อหัวหน้า", "GROUP BY m.id ... HAVING COUNT(*) >= 3"],
      "span of control ที่กว้างเกินไปเป็นสัญญาณภาระงานหัวหน้า", project="employee-analysis"),
    X("PJ-EMP-3", "Top 10 การเติบโตของเงินเดือน", "พนักงานที่มีประวัติเงินเดือน ≥ 2 แถว แสดง **employee_id**, **first_amount**, **current_amount**, **growth_pct** (ปัด 1) เรียง growth_pct มากไปน้อย ถ้าเท่ากันเรียง employee_id น้อยไปมาก เอา 10 แถว",
      "expert", "Window Functions", "hr",
      """WITH r AS (
  SELECT employee_id, amount,
         ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY effective_from) AS first_rn,
         ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY effective_from DESC) AS last_rn,
         COUNT(*) OVER (PARTITION BY employee_id) AS n
  FROM salaries)
SELECT f.employee_id, f.amount AS first_amount, l.amount AS current_amount, ROUND(100 * (l.amount - f.amount) / f.amount, 1) AS growth_pct
FROM r f JOIN r l ON l.employee_id = f.employee_id AND l.last_rn = 1
WHERE f.first_rn = 1 AND f.n >= 2
ORDER BY growth_pct DESC, f.employee_id LIMIT 10;""",
      ["ต้องได้เงินเดือนแรกและล่าสุดของแต่ละคน", "ROW_NUMBER() สองทิศทาง หรือ FIRST_VALUE/LAST_VALUE", "COUNT(*) OVER (PARTITION BY employee_id) >= 2"],
      "ใช้ window function หาแถวแรก/แถวสุดท้ายต่อกลุ่ม แล้ว self-join ผลลัพธ์", order_matters=True, project="employee-analysis"),
    X("PJ-EMP-4", "อายุงาน", "พนักงาน active จัดกลุ่มอายุงาน ณ 2025-12-31 เป็น **tenure**: `0-2y` (< 2 ปี), `2-5y` (< 5 ปี), `5y+` แสดง tenure, **employees**, **avg_salary** (เงินเดือนปัจจุบัน ปัด 2)",
      "hard", "CASE", "hr",
      """SELECT CASE WHEN AGE('2025-12-31'::date, e.hire_date) < INTERVAL '2 years' THEN '0-2y'
            WHEN AGE('2025-12-31'::date, e.hire_date) < INTERVAL '5 years' THEN '2-5y' ELSE '5y+' END AS tenure,
       COUNT(*) AS employees, ROUND(AVG(s.amount), 2) AS avg_salary
FROM employees e JOIN salaries s ON s.employee_id = e.id AND s.effective_to IS NULL
WHERE e.is_active GROUP BY 1;""",
      ["คำนวณอายุงานด้วย AGE หรือการลบวันที่", "CASE WHEN จัดกลุ่ม", "AGE('2025-12-31'::date, hire_date) < INTERVAL '2 years'"],
      "AGE คืน interval ที่เปรียบเทียบกับ INTERVAL ได้โดยตรง", project="employee-analysis"),
])

FINANCE = P(
    "financial-analysis", "Financial Analysis — รายงานกระแสเงินและสินเชื่อ", "Financial / Risk Analyst",
    "รายรับ-รายจ่ายรายเดือน ลูกค้าที่มียอดเงินฝากสูง ธุรกรรมขนาดใหญ่ และพอร์ตสินเชื่อ",
    """
**สถานการณ์:** ธนาคารต้องส่งรายงานภาพรวมให้ฝ่ายบริหารความเสี่ยงประจำปี 2025

**นิยาม**
- `transactions.amount` บวก = เงินเข้า (inflow), ลบ = เงินออก (outflow)
- บัญชีที่นับยอดคงเหลือ = `status = 'active'`
- สินเชื่อที่ *อนุมัติ* = status `approved` หรือ `paid_off`; อัตราอนุมัติไม่นับคำขอที่ยัง `pending`
""",
    ["Cash flow รายเดือน 2025", "Top 5 ลูกค้าตามยอดเงินฝาก", "ธุรกรรมถอนขนาดใหญ่", "พอร์ตสินเชื่อตามประเภท"],
    "banking", "hard", [
    X("PJ-FIN-1", "Cash flow รายเดือน 2025", "แสดง **month** (`::date`), **inflow**, **outflow**, **net** ของทุกเดือนในปี 2025 เรียงตามเดือน",
      "hard", "Analytics", "banking",
      """SELECT DATE_TRUNC('month', txn_at)::date AS month,
       SUM(amount) FILTER (WHERE amount > 0) AS inflow, SUM(amount) FILTER (WHERE amount < 0) AS outflow, SUM(amount) AS net
FROM transactions WHERE txn_at >= '2025-01-01' AND txn_at < '2026-01-01' GROUP BY 1 ORDER BY 1;""",
      ["แยกเงินเข้า/ออกตามเครื่องหมายของ amount", "SUM(...) FILTER (WHERE amount > 0)", "net = SUM(amount)"],
      "เก็บ amount แบบมีเครื่องหมายทำให้ net คำนวณได้ด้วย SUM เดียว", order_matters=True, project="financial-analysis"),
    X("PJ-FIN-2", "Top 5 ลูกค้าตามยอดเงินฝาก", "แสดง **customer** (full_name), **accounts** (จำนวนบัญชี active), **total_balance** ของ 5 อันดับแรก (มากไปน้อย)",
      "hard", "JOIN", "banking",
      """SELECT c.full_name AS customer, COUNT(*) AS accounts, SUM(a.balance) AS total_balance
FROM customers c JOIN accounts a ON a.customer_id = c.id WHERE a.status = 'active'
GROUP BY c.id, c.full_name ORDER BY total_balance DESC LIMIT 5;""",
      ["รวมยอดทุกบัญชี active ของลูกค้า", "GROUP BY ลูกค้า", "ORDER BY total_balance DESC LIMIT 5"],
      "ลูกค้ากลุ่มนี้คือ High Net Worth ที่ทีม Private Banking ดูแล", order_matters=True, project="financial-analysis"),
    X("PJ-FIN-3", "ธุรกรรมถอนขนาดใหญ่", "ธุรกรรมปี 2025 ที่ amount ≤ −20000 แสดง **txn_id**, **customer** (full_name), **account_no**, **amount**, **txn_at**",
      "hard", "JOIN", "banking",
      """SELECT t.id AS txn_id, c.full_name AS customer, a.account_no, t.amount, t.txn_at
FROM transactions t JOIN accounts a ON a.id = t.account_id JOIN customers c ON c.id = a.customer_id
WHERE t.amount <= -20000 AND t.txn_at >= '2025-01-01' AND t.txn_at < '2026-01-01';""",
      ["ต้องการข้อมูลจาก 3 ตาราง", "transactions → accounts → customers", "WHERE amount <= -20000 + ช่วงปี 2025"],
      "รายการแบบนี้ใช้ตรวจสอบธุรกรรมผิดปกติ (AML monitoring)", project="financial-analysis"),
    X("PJ-FIN-4", "พอร์ตสินเชื่อตามประเภท", "แสดง **loan_type**, **applications** (ทั้งหมด), **approved_principal** (ผลรวม principal ที่อนุมัติ), **approval_rate** (% อนุมัติ จากคำขอที่ไม่ใช่ pending ปัด 1)",
      "expert", "Analytics", "banking",
      """SELECT loan_type, COUNT(*) AS applications,
       COALESCE(SUM(principal) FILTER (WHERE status IN ('approved', 'paid_off')), 0) AS approved_principal,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status IN ('approved', 'paid_off')) / NULLIF(COUNT(*) FILTER (WHERE status <> 'pending'), 0), 1) AS approval_rate
FROM loans GROUP BY loan_type;""",
      ["นับหลายเงื่อนไขในกลุ่มเดียว", "ตัวหาร = คำขอที่ตัดสินแล้ว (ไม่ใช่ pending)", "COUNT(*) FILTER (...) / NULLIF(COUNT(*) FILTER (WHERE status <> 'pending'), 0)"],
      "ระวังตัวหาร: รวม pending จะทำให้อัตราอนุมัติต่ำกว่าความจริง", project="financial-analysis"),
])

SAAS = P(
    "saas-metrics", "SaaS Metrics — MRR, Retention และการใช้งานผลิตภัณฑ์", "Product / Growth Analyst",
    "MRR ตามแพ็กเกจ, MRR รายเดือน, MAU, trial conversion และการวิเคราะห์ event JSONB",
    """
**สถานการณ์:** บริษัท SaaS กำลังเตรียมระดมทุน นักลงทุนขอ **SaaS metrics** มาตรฐาน (ฐานข้อมูล `saas` — ชุดข้อมูลขั้นสูง)

**นิยาม**
- *subscription ที่ใช้งานอยู่ ณ วันที่ D* = `started_at <= D` และ (`ended_at IS NULL` หรือ `ended_at > D`) และ `status <> 'trial'`
- *MRR* = ผลรวม `subscriptions.mrr` ของ subscription ที่ใช้งานอยู่
- *Active user ในเดือน* = ผู้ใช้ที่มี event อย่างน้อย 1 ครั้งในเดือนนั้น
- `events.properties` เป็น **JSONB** — อ่านค่าด้วย `properties->>'key'`
""",
    ["MRR ปัจจุบันตามแพ็กเกจ", "MRR สิ้นเดือนปี 2025", "MAU ครึ่งปีหลัง 2025", "Trial conversion", "ความนิยมของรายงาน (JSONB)"],
    "saas", "expert", [
    X("PJ-SAAS-1", "MRR ปัจจุบันตามแพ็กเกจ", "จาก subscription ที่ `ended_at IS NULL` และ `status = 'active'` แสดง **plan**, **companies**, **mrr** เรียง mrr มากไปน้อย",
      "hard", "Analytics", "saas",
      """SELECT p.name AS plan, COUNT(*) AS companies, SUM(s.mrr) AS mrr
FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE s.ended_at IS NULL AND s.status = 'active'
GROUP BY p.id, p.name ORDER BY mrr DESC;""",
      ["subscription ปัจจุบันคือแถวที่ยังไม่สิ้นสุด", "JOIN plans เพื่อเอาชื่อ", "GROUP BY plan ORDER BY mrr DESC"],
      "สังเกตแพ็กเกจ Legacy ที่ปิดขายแล้วแต่ยังมีรายได้ — ข้อมูลจริงมักเป็นแบบนี้", order_matters=True, project="saas-metrics"),
    X("PJ-SAAS-2", "MRR ณ สิ้นเดือน ปี 2025", "แสดง **month_end** (วันสุดท้ายของแต่ละเดือนปี 2025, ชนิด date) และ **mrr** ตามนิยามใน brief เรียงตามเดือน",
      "expert", "Analytics", "saas",
      """WITH m AS (SELECT (generate_series('2025-02-01'::date, '2026-01-01'::date, interval '1 month') - interval '1 day')::date AS month_end)
SELECT m.month_end, COALESCE(SUM(s.mrr), 0) AS mrr
FROM m LEFT JOIN subscriptions s ON s.started_at <= m.month_end AND (s.ended_at IS NULL OR s.ended_at > m.month_end) AND s.status <> 'trial'
GROUP BY m.month_end ORDER BY m.month_end;""",
      ["สร้างรายการวันสิ้นเดือนก่อน (generate_series)", "JOIN subscription ด้วยเงื่อนไขช่วงเวลา (non-equi join)", "วันสิ้นเดือน = วันแรกของเดือนถัดไป − 1 วัน"],
      "MRR ณ จุดเวลาใช้ non-equi join ระหว่าง 'ปฏิทิน' กับช่วงอายุ subscription", order_matters=True, project="saas-metrics"),
    X("PJ-SAAS-3", "Monthly Active Users ก.ค.–ธ.ค. 2025", "แสดง **month** (`::date`) และ **mau** (ผู้ใช้ไม่ซ้ำที่มี event) ของเดือน ก.ค.–ธ.ค. 2025 เรียงตามเดือน",
      "hard", "Analytics", "saas",
      """SELECT DATE_TRUNC('month', occurred_at)::date AS month, COUNT(DISTINCT user_id) AS mau
FROM events WHERE occurred_at >= '2025-07-01' AND occurred_at < '2026-01-01' GROUP BY 1 ORDER BY 1;""",
      ["นับผู้ใช้ ไม่ใช่นับ event", "COUNT(DISTINCT user_id)", "GROUP BY DATE_TRUNC('month', occurred_at)"],
      "ตาราง event ใหญ่ — การกรองด้วยช่วงเวลาบนคอลัมน์ดิบทำให้ใช้ index (event_type, occurred_at) / (user_id, occurred_at) ได้", order_matters=True, project="saas-metrics"),
    X("PJ-SAAS-4", "Trial conversion rate", "แสดงแถวเดียว: **trials** (บริษัทที่มี subscription status `trial`), **converted** (บริษัทเหล่านั้นที่มี subscription ที่ไม่ใช่ trial ด้วย), **conversion_rate** (% ปัด 1)",
      "expert", "Subquery", "saas",
      """WITH t AS (SELECT DISTINCT company_id FROM subscriptions WHERE status = 'trial')
SELECT COUNT(*) AS trials,
       COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM subscriptions s WHERE s.company_id = t.company_id AND s.status <> 'trial')) AS converted,
       ROUND(100.0 * COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM subscriptions s WHERE s.company_id = t.company_id AND s.status <> 'trial')) / COUNT(*), 1) AS conversion_rate
FROM t;""",
      ["หาบริษัทที่เคย trial ก่อน", "ตรวจว่ามี subscription แบบจ่ายเงินหรือไม่ด้วย EXISTS", "COUNT(*) FILTER (WHERE EXISTS (...))"],
      "EXISTS ภายใน FILTER ทำ semi-join แบบมีเงื่อนไขได้ในการสรุปครั้งเดียว", project="saas-metrics"),
    X("PJ-SAAS-5", "ความนิยมของรายงาน (JSONB)", "จาก event `create_report` ปี 2025 แสดง **report_type** (`properties->>'report_type'`), **reports**, **avg_duration_ms** (ค่าเฉลี่ยของ `properties->>'duration_ms'` เป็นตัวเลข ปัดเป็นจำนวนเต็ม)",
      "expert", "Analytics", "saas",
      """SELECT properties->>'report_type' AS report_type, COUNT(*) AS reports, ROUND(AVG((properties->>'duration_ms')::int)) AS avg_duration_ms
FROM events WHERE event_type = 'create_report' AND occurred_at >= '2025-01-01' AND occurred_at < '2026-01-01'
GROUP BY 1;""",
      ["อ่านค่าจาก JSONB ด้วยตัวดำเนินการ ->>", "->> คืนข้อความ ต้อง cast เป็นตัวเลขก่อน AVG", "(properties->>'duration_ms')::int"],
      "`->` คืน jsonb, `->>` คืน text — ต้อง cast ก่อนคำนวณ", project="saas-metrics"),
])

PROJECTS = [SALES, CUSTOMER, PRODUCT, EMPLOYEE, FINANCE, SAAS]
