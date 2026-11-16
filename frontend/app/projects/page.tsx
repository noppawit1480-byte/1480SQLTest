import Link from "next/link";
import { Construction } from "lucide-react";

export const metadata = { title: "Real-World Projects" };

const PROJECTS = [
  ["Sales Analysis", "ยอดขายรายเดือน สินค้าขายดี รายได้ตามหมวดหมู่", "EX-X001"],
  ["Customer Analysis", "ลูกค้าที่ใช้จ่ายสูงสุด ลูกค้าประจำ ลูกค้าที่หายไป", "EX-X002"],
  ["Product Analysis", "สินค้าขายดี/กำไรสูงสุด เปรียบเทียบยอดขาย", "EX-X003"],
  ["Employee Analysis", "เงินเดือนตามแผนก ผู้มีรายได้สูงสุดในแต่ละแผนก", "EX-X004"],
  ["Financial Analysis", "รายรับ–รายจ่าย ธุรกรรม และสรุปยอดตามช่วงเวลา", "EX-X005"],
];

// Phase 2 feature — this page states its status honestly instead of showing non-working buttons.
export default function ProjectsPage() {
  return (
    <>
      <div className="mb-6 flex items-start gap-3 rounded-lg border border-warn/40 bg-warn-soft/40 p-4">
        <Construction className="mt-0.5 size-5 shrink-0 text-warn" />
        <div>
          <h1 className="text-lg font-bold">Real-World Projects — กำลังพัฒนาใน Phase 2</h1>
          <p className="mt-1 text-sm">โปรเจกต์แบบหลายขั้นตอนพร้อมสถานการณ์ธุรกิจ (business brief) และเกณฑ์การประเมินจะเปิดใน Phase 2
            ระหว่างนี้ ฝึกโจทย์ระดับ <b>Expert</b> ที่ออกแบบจากสถานการณ์เดียวกันได้แล้ว และตรวจคำตอบอัตโนมัติจริง</p>
        </div>
      </div>
      <ul className="grid gap-3 md:grid-cols-2">
        {PROJECTS.map(([title, desc, code]) => (
          <li key={title} className="rounded-lg border border-line bg-surface p-4">
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-1 text-sm text-muted">{desc}</p>
            <Link href={`/practice/${code}`} className="mt-3 inline-block text-sm text-brand hover:underline">ฝึกโจทย์ Expert ที่เกี่ยวข้อง ({code}) →</Link>
          </li>
        ))}
      </ul>
    </>
  );
}
