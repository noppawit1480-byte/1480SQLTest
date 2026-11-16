from app.content import advanced, beginner, intermediate, professional
from app.content.model import CourseDef

COURSES = [
    CourseDef("beginner", "SQL สำหรับผู้เริ่มต้น", "beginner",
              "เริ่มจากศูนย์: ฐานข้อมูลคืออะไร, SELECT, การกรอง เรียง จำกัดผลลัพธ์ และการจัดการค่า NULL",
              beginner.LESSONS),
    CourseDef("intermediate", "SQL ระดับกลาง", "intermediate",
              "สรุปข้อมูลด้วย Aggregate และ GROUP BY, รวมตารางด้วย JOIN ทุกแบบ, CASE WHEN และฟังก์ชันข้อความ/วันที่",
              intermediate.LESSONS),
    CourseDef("advanced", "SQL ขั้นสูง", "advanced",
              "Subquery, CTE, Recursive CTE, Window Functions และเทคนิคการเขียน query วิเคราะห์ข้อมูลที่ใช้ในงานจริง",
              advanced.LESSONS),
    CourseDef("professional", "Professional & Database Design", "professional",
              "DDL/DML, Constraints, Normalization, Transactions, Indexes, EXPLAIN และการออกแบบฐานข้อมูล",
              professional.LESSONS),
]

SAMPLE_DATABASES = [
    ("ecommerce", "E-Commerce", "ร้านค้าออนไลน์: ลูกค้า สินค้า หมวดหมู่ (มีหมวดย่อย) คำสั่งซื้อ รายการสินค้า และการชำระเงิน ปี 2024–2025"),
    ("hr", "HR Management", "ระบบบุคคล: แผนก ตำแหน่ง พนักงาน (มีสายบังคับบัญชา) และประวัติเงินเดือน"),
    ("banking", "Banking", "ธนาคาร: ลูกค้า บัญชี ธุรกรรม (ยอดบวก/ลบ) และสินเชื่อ"),
    ("hospital", "Hospital", "โรงพยาบาล: ผู้ป่วย แพทย์ นัดหมาย และการรักษา"),
    ("music_store", "Music Store", "ร้านขายเพลงดิจิทัล: ศิลปิน อัลบั้ม เพลง เพลย์ลิสต์ ใบแจ้งหนี้ และรายการขาย"),
]
