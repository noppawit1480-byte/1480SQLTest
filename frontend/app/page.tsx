import Link from "next/link";
import { BarChart3, BookOpen, CheckCircle2, Dumbbell, FlaskConical, ShieldCheck, Terminal } from "lucide-react";

const STEPS = [
  { icon: BookOpen, title: "LEARN", desc: "62 บทเรียน 4 ระดับ อธิบายภาษาไทย พร้อมตัวอย่างที่รันจริง" },
  { icon: FlaskConical, title: "EXPERIMENT", desc: "SQL Playground บน PostgreSQL จริง 5 ฐานข้อมูลธุรกิจ" },
  { icon: Dumbbell, title: "PRACTICE", desc: "70 โจทย์ Easy → Expert ตรวจคำตอบจากผลลัพธ์จริง" },
  { icon: BarChart3, title: "ANALYZE", desc: "วิเคราะห์ยอดขาย ลูกค้า การเงิน ด้วย Window Functions & CTE" },
  { icon: CheckCircle2, title: "APPLY", desc: "DDL/DML, Transactions, Index และการออกแบบฐานข้อมูล" },
];

export default function Landing() {
  return (
    <main>
      <section className="mx-auto max-w-6xl px-4 pt-16 pb-12 text-center">
        <p className="text-sm font-semibold text-brand">SQL Learning & Practice Platform</p>
        <h1 className="mx-auto mt-3 max-w-3xl text-4xl font-bold tracking-tight md:text-5xl">เรียน SQL จากศูนย์ จนใช้ทำงานจริงได้</h1>
        <p className="mx-auto mt-4 max-w-2xl text-muted">เขียนและรัน SQL บนฐานข้อมูล PostgreSQL จริงผ่านเบราว์เซอร์ ไม่ต้องติดตั้งอะไร
          ระบบตรวจคำตอบจากผลลัพธ์ — เขียนแบบไหนก็ได้ ขอแค่ถูกต้อง</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/learn" className="rounded-md bg-brand px-5 py-2.5 font-medium text-brand-fg">เริ่มเรียนฟรี</Link>
          <Link href="/playground" className="flex items-center gap-2 rounded-md border border-line bg-surface px-5 py-2.5 font-medium"><Terminal className="size-4" /> ลอง Playground</Link>
        </div>
        <div className="mx-auto mt-10 max-w-2xl overflow-hidden rounded-lg border border-line bg-surface text-left shadow-sm">
          <div className="flex gap-1.5 border-b border-line px-3 py-2"><span className="size-2.5 rounded-full bg-bad/60" /><span className="size-2.5 rounded-full bg-warn/60" /><span className="size-2.5 rounded-full bg-ok/60" /></div>
          <pre className="p-4 font-mono text-[13px] leading-relaxed"><span className="sql-kw">SELECT</span> c.city, <span className="sql-fn">COUNT</span>(*) <span className="sql-kw">AS</span> orders,{"\n"}       <span className="sql-fn">RANK</span>() <span className="sql-kw">OVER</span> (<span className="sql-kw">ORDER BY</span> <span className="sql-fn">COUNT</span>(*) <span className="sql-kw">DESC</span>) <span className="sql-kw">AS</span> rnk{"\n"}<span className="sql-kw">FROM</span> orders o <span className="sql-kw">JOIN</span> customers c <span className="sql-kw">ON</span> c.id = o.customer_id{"\n"}<span className="sql-kw">GROUP BY</span> c.city;</pre>
        </div>
      </section>
      <section className="mx-auto grid max-w-6xl gap-3 px-4 pb-16 sm:grid-cols-2 lg:grid-cols-5">
        {STEPS.map((s) => (
          <div key={s.title} className="rounded-lg border border-line bg-surface p-4">
            <s.icon className="size-5 text-brand" />
            <h2 className="mt-2 text-sm font-bold tracking-wide">{s.title}</h2>
            <p className="mt-1 text-sm text-muted">{s.desc}</p>
          </div>
        ))}
      </section>
      <section className="border-t border-line bg-surface py-8">
        <p className="mx-auto flex max-w-6xl items-center justify-center gap-2 px-4 text-center text-sm text-muted">
          <ShieldCheck className="size-4 text-ok" /> ทุก query รันใน Sandbox แยกจากระบบหลัก จำกัดสิทธิ์ เวลา และจำนวนแถว — ทดลองได้อย่างปลอดภัย
        </p>
      </section>
    </main>
  );
}
