"use client";

import Link from "next/link";
import { use } from "react";
import { Briefcase, CheckCircle2, Circle, CircleDot, ClipboardList, Database, Trophy } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { ProjectDetail } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { Markdown } from "@/components/Markdown";
import { Badge, ButtonLink, Card, DifficultyBadge, ErrorState, PageHeader, ProgressBar, Spinner } from "@/components/ui";

export default function ProjectPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<ProjectDetail>(`/projects/${slug}`);
  if (loading) return <Spinner />;
  if (error || !data) return <ErrorState message={error?.message ?? "ไม่พบโปรเจกต์"} onRetry={reload} />;
  const p = data;
  const next = p.tasks.find((t) => t.status !== "solved") ?? p.tasks[0];
  return (
    <>
      <nav className="mb-2 text-sm text-muted"><Link href="/projects" className="hover:underline">Projects</Link> / {p.title}</nav>
      <PageHeader title={p.title} description={p.summary}
        actions={next && <ButtonLink variant="primary" href={`/practice/${next.code}`}>{p.solved ? "ทำต่อ" : "เริ่มโปรเจกต์"}: งานที่ {p.tasks.indexOf(next) + 1}</ButtonLink>} />
      <div className="mb-5 flex flex-wrap items-center gap-2 text-sm">
        <Badge><Briefcase className="size-3" /> บทบาท: {p.role}</Badge>
        <Badge><Database className="size-3" /> {p.sample_db}</Badge>
        <DifficultyBadge d={p.difficulty} />
        {p.completed && <span className="flex items-center gap-1 font-medium text-ok" data-testid="project-complete"><Trophy className="size-4" /> โปรเจกต์สำเร็จ!</span>}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card title="Business Brief"><Markdown>{p.brief_md}</Markdown></Card>
          <Card title={<span className="flex items-center gap-1.5"><ClipboardList className="size-4" /> งานที่ต้องส่ง</span>}>
            <ol className="divide-y divide-line" data-testid="project-tasks">
              {p.tasks.map((t, i) => (
                <li key={t.code}>
                  <Link href={`/practice/${t.code}`} className="flex items-center gap-3 py-3 hover:text-brand">
                    {t.status === "solved" ? <CheckCircle2 className="size-5 shrink-0 text-ok" aria-label="เสร็จแล้ว" />
                      : t.status === "attempted" ? <CircleDot className="size-5 shrink-0 text-warn" aria-label="ทำแล้วยังไม่ถูก" />
                      : <Circle className="size-5 shrink-0 text-line" aria-label="ยังไม่ทำ" />}
                    <span className="w-14 shrink-0 text-xs text-muted">งานที่ {i + 1}</span>
                    <span className="flex-1 text-sm font-medium">{t.title}</span>
                    <DifficultyBadge d={t.difficulty} />
                    <span className="w-12 text-right text-xs text-muted">{t.points} pts</span>
                  </Link>
                </li>
              ))}
            </ol>
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="เกณฑ์การประเมิน">
            <ul className="space-y-1.5 text-sm">
              <li>✔ ทุกงานตรวจอัตโนมัติจาก <b>ผลลัพธ์</b> ที่รันบนฐานข้อมูลจริง</li>
              <li>✔ ต้องใช้ <b>นิยามใน brief</b> ให้ตรง (เช่น สถานะคำสั่งซื้อที่นับ)</li>
              <li>✔ โปรเจกต์สำเร็จเมื่อผ่าน <b>ครบทุกงาน</b> → Achievement <i>Real-World Analyst</i></li>
            </ul>
            {user ? (
              <div className="mt-4">
                <div className="mb-1 flex justify-between text-xs"><span>{p.solved}/{p.tasks.length} งาน</span><span>{p.points_earned}/{p.points_total} pts</span></div>
                <ProgressBar value={(100 * p.solved) / Math.max(1, p.tasks.length)} label="ความคืบหน้าโปรเจกต์" />
              </div>
            ) : <p className="mt-3 text-xs text-muted"><Link className="text-brand underline" href={`/login?next=/projects/${slug}`}>เข้าสู่ระบบ</Link> เพื่อบันทึกความคืบหน้า</p>}
          </Card>
          <Card title="ผลลัพธ์ที่ต้องส่งมอบ">
            <ul className="list-disc space-y-1 pl-5 text-sm">{p.deliverables.map((d) => <li key={d}>{d}</li>)}</ul>
          </Card>
        </div>
      </div>
    </>
  );
}
