"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  Award, BookOpen, Briefcase, Crown, CheckCircle2, Clock, Dumbbell, Flame, GraduationCap, Hammer, Layers, Link2, Lock, PanelsTopLeft,
  Play, Sprout, Target, Trophy, XCircle,
} from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { Dashboard } from "@/lib/types";
import { useAuth, useTheme } from "@/components/providers";
import { ButtonLink, Card, cx, DifficultyBadge, EmptyState, ErrorState, PageHeader, ProgressBar, Skeleton, StatCard } from "@/components/ui";

const ICONS: Record<string, typeof Award> = {
  play: Play, check: CheckCircle2, sprout: Sprout, graduation: GraduationCap, link: Link2, layers: Layers,
  window: PanelsTopLeft, hammer: Hammer, flame: Flame, trophy: Trophy, briefcase: Briefcase, crown: Crown,
};
// Categorical slots 1–2 of the validated reference palette (light / dark steps).
const SERIES = { light: { correct: "#2a78d6", wrong: "#eb6834" }, dark: { correct: "#3987e5", wrong: "#d95926" } };

function fmtDuration(s: number) {
  const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
  return h ? `${h} ชม. ${m} นาที` : `${m} นาที`;
}

function ActivityChart({ data }: { data: Dashboard["activity"] }) {
  const { theme } = useTheme();
  const [asTable, setAsTable] = useState(false);
  const c = SERIES[theme];
  const rows = useMemo(() => data.map((d) => ({ ...d, label: d.date.slice(5), wrong: d.submissions - d.correct })), [data]);
  const empty = data.every((d) => d.submissions === 0);
  return (
    <Card title="พัฒนาการ 30 วันล่าสุด (การส่งคำตอบต่อวัน)" action={
      <button className="text-xs text-brand hover:underline" onClick={() => setAsTable((v) => !v)}>{asTable ? "ดูเป็นกราฟ" : "ดูเป็นตาราง"}</button>}>
      {empty ? (
        <EmptyState title="ยังไม่มีการส่งคำตอบใน 30 วันที่ผ่านมา" description="ทำแบบฝึกหัดแล้วกราฟจะแสดงพัฒนาการของคุณที่นี่"
          action={<ButtonLink href="/practice" variant="primary">เริ่มทำแบบฝึกหัด</ButtonLink>} />
      ) : asTable ? (
        <div className="max-h-64 overflow-auto text-sm">
          <table className="w-full"><thead className="text-left text-xs text-muted"><tr><th>วันที่</th><th className="text-right">ส่ง</th><th className="text-right">ถูก</th><th className="text-right">นาทีที่เรียน</th></tr></thead>
            <tbody>{data.filter((d) => d.submissions || d.minutes).map((d) => <tr key={d.date} className="border-t border-line"><td>{d.date}</td><td className="text-right tabular-nums">{d.submissions}</td><td className="text-right tabular-nums">{d.correct}</td><td className="text-right tabular-nums">{d.minutes}</td></tr>)}</tbody></table>
        </div>
      ) : (
        <div className="h-64" data-testid="activity-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -20 }} barCategoryGap="20%">
              <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="0" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval="preserveStartEnd" minTickGap={16} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: "var(--surface-2)" }}
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 6, fontSize: 12, color: "var(--text)" }}
                labelStyle={{ color: "var(--text)", fontWeight: 600 }} itemStyle={{ color: "var(--text)" }}
                formatter={(v, name) => [v as number, name === "correct" ? "ถูก" : "ไม่ถูก"]} labelFormatter={(l) => `วันที่ ${l}`} />
              <Legend formatter={(v) => <span style={{ color: "var(--text)", fontSize: 12 }}>{v === "correct" ? "ถูก" : "ไม่ถูก"}</span>} iconType="square" iconSize={10} />
              <Bar dataKey="correct" stackId="s" fill={c.correct} stroke="var(--surface)" strokeWidth={2} maxBarSize={18} />
              <Bar dataKey="wrong" stackId="s" fill={c.wrong} stroke="var(--surface)" strokeWidth={2} radius={[4, 4, 0, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

export default function DashboardPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const { data, error, loading, reload } = useApi<Dashboard>(user ? "/dashboard" : null);

  useEffect(() => { if (ready && !user) router.replace("/login?next=/dashboard"); }, [ready, user, router]);

  if (!ready || loading || (!data && !error)) return (
    <div className="space-y-4"><Skeleton className="h-8 w-64" /><div className="grid grid-cols-2 gap-3 lg:grid-cols-5">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-24" />)}</div><Skeleton className="h-72" /></div>
  );
  if (error || !data) return <ErrorState message={error?.message ?? "โหลดข้อมูลไม่สำเร็จ"} onRetry={reload} />;
  const d = data;
  const lv = d.level;
  const lvPct = lv.next_threshold ? (100 * (lv.points - lv.current_threshold)) / (lv.next_threshold - lv.current_threshold) : 100;

  return (
    <>
      <PageHeader title={`สวัสดี, ${user!.display_name}`} description="ภาพรวมการเรียนรู้ของคุณ — คำนวณจากการใช้งานจริงทั้งหมด"
        actions={d.current_lesson && <ButtonLink variant="primary" href={`/learn/${d.current_lesson.course_slug}/${d.current_lesson.slug}`}><BookOpen className="size-4" /> เรียนต่อ: {d.current_lesson.title.split("—")[0]}</ButtonLink>} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6" data-testid="stats">
        <StatCard label="บทเรียนที่เรียนจบ" value={`${d.lessons.completed}/${d.lessons.total}`} icon={<BookOpen className="size-4" />} />
        <StatCard label="โจทย์ที่ทำสำเร็จ" value={`${d.exercises.solved}/${d.exercises.total}`} icon={<Dumbbell className="size-4" />} />
        <StatCard label="Projects สำเร็จ" value={`${d.projects.completed}/${d.projects.total}`} sub={`${d.projects.tasks_solved}/${d.projects.tasks_total} งาน`} icon={<Briefcase className="size-4" />} />
        <StatCard label="อัตราตอบถูก" value={d.submissions.accuracy === null ? "—" : `${d.submissions.accuracy}%`}
          sub={`${d.submissions.correct} ถูก จาก ${d.submissions.total} ครั้ง`} icon={<Target className="size-4" />} />
        <StatCard label="Learning Streak" value={<span className="flex items-center gap-1">{d.streak} <Flame className={cx("size-5", d.streak ? "text-warn" : "text-muted")} /></span>}
          sub="วันต่อเนื่อง" icon={<Flame className="size-4" />} />
        <StatCard label="เวลาเรียนรวม" value={fmtDuration(d.learning_seconds)} icon={<Clock className="size-4" />} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card title="ระดับความสามารถ SQL" className="lg:col-span-1">
          <div className="flex items-baseline gap-2"><span className="text-2xl font-bold text-brand" data-testid="level-name">{lv.name}</span>
            <span className="text-sm text-muted">{lv.points} คะแนน</span></div>
          <ProgressBar value={lvPct} className="mt-3" label="ความคืบหน้าสู่ระดับถัดไป" />
          <p className="mt-1.5 text-xs text-muted">{lv.next_name ? `อีก ${lv.next_threshold! - lv.points} คะแนนถึงระดับ ${lv.next_name}` : "ระดับสูงสุดแล้ว!"}</p>
          <p className="mt-3 text-xs text-muted">คะแนนได้จากโจทย์ที่ทำถูก: Easy 10 · Medium 20 · Hard 30 · Expert 50</p>
        </Card>
        <div className="lg:col-span-2"><ActivityChart data={d.activity} /></div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="ความคืบหน้าแต่ละหลักสูตร">
          <ul className="space-y-3">
            {d.courses.map((c) => (
              <li key={c.slug}>
                <Link href={`/learn/${c.slug}`} className="group block">
                  <div className="mb-1 flex justify-between text-sm"><span className="group-hover:text-brand">{c.title}</span><span className="tabular-nums text-muted">{c.completed}/{c.total}</span></div>
                  <ProgressBar value={c.percent} label={c.title} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Skill Progress (โจทย์ที่ทำถูกตามหมวด)">
          <ul className="grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
            {d.skills.map((s) => (
              <li key={s.category}>
                <div className="mb-1 flex justify-between text-xs"><span>{s.category}</span><span className="tabular-nums text-muted">{s.solved}/{s.total}</span></div>
                <ProgressBar value={s.percent} label={s.category} />
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card title="โจทย์ที่ทำล่าสุด" action={<Link href="/practice" className="text-xs text-brand hover:underline">ดูทั้งหมด</Link>}>
          {d.recent_exercises.length ? (
            <ul className="divide-y divide-line">
              {d.recent_exercises.map((r, i) => (
                <li key={i}><Link href={`/practice/${r.code}`} className="flex items-center gap-2 py-2 text-sm hover:text-brand">
                  {r.is_correct ? <CheckCircle2 className="size-4 text-ok" aria-label="ถูก" /> : <XCircle className="size-4 text-bad" aria-label="ไม่ถูก" />}
                  <span className="font-mono text-xs text-muted">{r.code}</span><span className="flex-1 truncate">{r.title}</span><DifficultyBadge d={r.difficulty} />
                </Link></li>
              ))}
            </ul>
          ) : <EmptyState title="ยังไม่เคยส่งคำตอบ" action={<ButtonLink href="/practice/EX-E001" variant="primary">ลองโจทย์แรก</ButtonLink>} />}
        </Card>
        <Card title="Achievements & Badges">
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="achievements">
            {d.achievements.map((a) => {
              const Icon = ICONS[a.icon] ?? Award;
              return (
                <li key={a.key} title={a.description} className={cx("flex flex-col items-center rounded-md border p-2 text-center",
                  a.earned_at ? "border-brand/40 bg-brand-soft/40" : "border-line opacity-60")}>
                  {a.earned_at ? <Icon className="size-6 text-brand" /> : <Lock className="size-6 text-muted" />}
                  <span className="mt-1 text-xs font-medium">{a.title}</span>
                  <span className="text-[10px] text-muted">{a.earned_at ? new Date(a.earned_at).toLocaleDateString("th-TH") : a.description}</span>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </>
  );
}
