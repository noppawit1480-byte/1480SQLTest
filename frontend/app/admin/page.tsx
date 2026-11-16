"use client";

import Link from "next/link";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Database, Pencil, Plus, RefreshCw, Shield, Trophy, Users } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { Difficulty } from "@/lib/types";
import { AdminGuard } from "@/components/AdminGuard";
import { useAuth, useTheme, useToast } from "@/components/providers";
import { Badge, Button, ButtonLink, Card, cx, DifficultyBadge, ErrorState, PageHeader, Spinner, StatCard } from "@/components/ui";

interface Stats {
  users: { total: number; new_7d: number; active_today: number; active_7d: number };
  submissions: { total: number; correct: number; accuracy: number | null };
  lessons_completed: number;
  content: { lessons: number; exercises: number; projects: number; custom: number };
  hardest_exercises: { code: string; title: string; attempts: number; correct: number; learners: number; success_rate: number }[];
  daily: { date: string; submissions: number; signups: number }[];
  assistant_7d: { provider: string; requests: number; input_tokens: number; output_tokens: number }[];
}
interface AdminUser { id: number; email: string; display_name: string; role: string; is_active: boolean; created_at: string; last_active: string | null; points: number; solved: number }
interface AdminCourse { id: number; slug: string; title: string; level: string; description: string; lessons: { id: number; slug: string; title: string; is_custom: boolean; admin_edited: boolean }[] }
interface AdminExercise { id: number; code: string; title: string; difficulty: Difficulty; category: string; points: number; sample_db: string; check_type: string; lesson_slug: string | null; project_slug: string | null; is_custom: boolean; admin_edited: boolean }
interface AdminProject { id: number; slug: string; title: string; role: string; summary: string; brief_md: string; deliverables: string[]; sample_db: string; difficulty: Difficulty; tasks: number; is_custom: boolean; admin_edited: boolean }
interface AdminAch { key: string; title: string; description: string; icon: string; earned_by: number }
interface AdminDb { key: string; name: string; description: string; engine: string; tables: number; rows: number; exercises: number }

const TABS = [["overview", "ภาพรวม"], ["users", "ผู้ใช้"], ["lessons", "บทเรียน"], ["exercises", "โจทย์"], ["projects", "Projects"],
  ["achievements", "Achievements"], ["databases", "ฐานข้อมูล"]] as const;
type Tab = (typeof TABS)[number][0];

function EditBadges({ custom, edited }: { custom: boolean; edited: boolean }) {
  return <>{custom && <Badge className="!text-brand">custom</Badge>}{!custom && edited && <Badge className="!text-warn">แก้ไขแล้ว</Badge>}</>;
}

function MiniBars({ data, k, label }: { data: Stats["daily"]; k: "submissions" | "signups"; label: string }) {
  const { theme } = useTheme();
  return (
    <div>
      <div className="mb-1 text-xs text-muted">{label} (14 วัน)</div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.map((d) => ({ ...d, day: d.date.slice(5) }))} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="day" tick={{ fontSize: 10, fill: "var(--muted)" }} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval="preserveStartEnd" />
            <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
            <Tooltip cursor={{ fill: "var(--surface-2)" }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", fontSize: 12, color: "var(--text)" }}
              formatter={(v) => [v as number, label]} />
            <Bar dataKey={k} fill={theme === "dark" ? "#3987e5" : "#2a78d6"} radius={[4, 4, 0, 0]} maxBarSize={16} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Overview() {
  const { data, error, loading, reload } = useApi<Stats>("/admin/stats");
  if (loading) return <Spinner />;
  if (error || !data) return <ErrorState message={error?.message ?? ""} onRetry={reload} />;
  const s = data;
  return (
    <div className="space-y-4" data-testid="admin-overview">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="ผู้ใช้ทั้งหมด" value={s.users.total} sub={`ใหม่ 7 วัน: ${s.users.new_7d}`} icon={<Users className="size-4" />} />
        <StatCard label="Active วันนี้ / 7 วัน" value={`${s.users.active_today} / ${s.users.active_7d}`} />
        <StatCard label="การส่งคำตอบ" value={s.submissions.total} sub={`ถูก ${s.submissions.accuracy ?? "—"}%`} />
        <StatCard label="บทเรียนที่เรียนจบ (รวม)" value={s.lessons_completed} sub={`${s.content.lessons} บท · ${s.content.exercises} โจทย์ · ${s.content.projects} projects`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="กิจกรรมรายวัน"><div className="grid gap-4 sm:grid-cols-2"><MiniBars data={s.daily} k="submissions" label="การส่งคำตอบ" /><MiniBars data={s.daily} k="signups" label="สมัครใหม่" /></div></Card>
        <Card title="โจทย์ที่ผู้เรียนติดมากที่สุด (≥ 3 ครั้ง)">
          {s.hardest_exercises.length ? (
            <table className="w-full text-sm"><thead className="text-left text-xs text-muted"><tr><th>โจทย์</th><th className="text-right">ส่ง</th><th className="text-right">ผู้เรียน</th><th className="text-right">สำเร็จ</th></tr></thead>
              <tbody>{s.hardest_exercises.map((h) => <tr key={h.code} className="border-t border-line"><td className="py-1"><span className="font-mono text-xs text-muted">{h.code}</span> {h.title}</td>
                <td className="text-right tabular-nums">{h.attempts}</td><td className="text-right tabular-nums">{h.learners}</td><td className="text-right tabular-nums">{h.success_rate}%</td></tr>)}</tbody></table>
          ) : <p className="text-sm text-muted">ยังมีข้อมูลไม่พอ</p>}
        </Card>
      </div>
      <Card title="การใช้ Assistant (7 วัน)">
        {s.assistant_7d.length ? <ul className="text-sm">{s.assistant_7d.map((a) => <li key={a.provider}><b>{a.provider}</b>: {a.requests} ครั้ง{a.provider !== "rules" && ` · tokens in ${a.input_tokens.toLocaleString()} / out ${a.output_tokens.toLocaleString()}`}</li>)}</ul>
          : <p className="text-sm text-muted">ยังไม่มีการใช้งาน</p>}
      </Card>
    </div>
  );
}

function UsersTab() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { data, loading, error, reload } = useApi<{ total: number; items: AdminUser[] }>(`/admin/users?q=${encodeURIComponent(query)}`);
  async function patch(u: AdminUser, body: Partial<AdminUser>) {
    try {
      await api.patch(`/admin/users/${u.id}`, body);
      toast.push("ok", "บันทึกแล้ว");
      reload();
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  return (
    <Card title={`ผู้ใช้ (${data?.total ?? "…"})`} action={
      <form onSubmit={(e) => { e.preventDefault(); setQuery(q); }} className="flex gap-1"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ค้นหาอีเมล/ชื่อ" className="rounded-md border border-line bg-surface px-2 py-1 text-sm" /><Button size="sm" type="submit">ค้นหา</Button></form>}>
      {loading ? <Spinner /> : error ? <ErrorState message={error.message} /> : (
        <div className="overflow-x-auto"><table className="w-full text-sm" data-testid="admin-users">
          <thead className="text-left text-xs text-muted"><tr><th className="py-1">ผู้ใช้</th><th>Role</th><th className="text-right">คะแนน</th><th className="text-right">โจทย์ถูก</th><th>ใช้งานล่าสุด</th><th /></tr></thead>
          <tbody>{data!.items.map((u) => (
            <tr key={u.id} className={cx("border-t border-line", !u.is_active && "opacity-50")}>
              <td className="py-1.5"><div className="font-medium">{u.display_name}</div><div className="text-xs text-muted">{u.email}</div></td>
              <td><select value={u.role} disabled={u.id === me?.id} onChange={(e) => patch(u, { role: e.target.value })} className="rounded border border-line bg-surface px-1 text-xs" aria-label={`role ของ ${u.email}`}>
                <option value="learner">learner</option><option value="admin">admin</option></select></td>
              <td className="text-right tabular-nums">{u.points}</td><td className="text-right tabular-nums">{u.solved}</td>
              <td className="text-xs text-muted">{u.last_active ?? "—"}</td>
              <td className="text-right">{u.id !== me?.id && <Button size="sm" variant={u.is_active ? "ghost" : "secondary"} onClick={() => patch(u, { is_active: !u.is_active })}>{u.is_active ? "ระงับ" : "เปิดใช้"}</Button>}</td>
            </tr>))}</tbody></table></div>
      )}
    </Card>
  );
}

function LessonsTab() {
  const { data, loading } = useApi<AdminCourse[]>("/admin/courses");
  if (loading || !data) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><ButtonLink href="/admin/lessons/new" variant="primary"><Plus className="size-4" /> บทเรียนใหม่</ButtonLink></div>
      {data.map((c) => (
        <Card key={c.id} title={`${c.title} (${c.lessons.length} บท)`}>
          <ol className="divide-y divide-line text-sm">{c.lessons.map((l, i) => (
            <li key={l.id} className="flex items-center gap-2 py-1.5"><span className="w-6 text-right text-xs text-muted">{i + 1}</span><span className="flex-1">{l.title}</span>
              <EditBadges custom={l.is_custom} edited={l.admin_edited} />
              <Link href={`/admin/lessons/${l.id}`} className="text-brand" aria-label={`แก้ไข ${l.title}`}><Pencil className="size-4" /></Link></li>))}</ol>
        </Card>
      ))}
    </div>
  );
}

function ExercisesTab() {
  const { data, loading } = useApi<AdminExercise[]>("/admin/exercises");
  const [f, setF] = useState("");
  if (loading || !data) return <Spinner />;
  const rows = data.filter((e) => !f || `${e.code} ${e.title} ${e.category} ${e.project_slug ?? ""}`.toLowerCase().includes(f.toLowerCase()));
  return (
    <Card title={`โจทย์ทั้งหมด (${data.length})`} action={<div className="flex gap-2"><input value={f} onChange={(e) => setF(e.target.value)} placeholder="กรอง" className="rounded-md border border-line bg-surface px-2 py-1 text-sm" />
      <ButtonLink href="/admin/exercises/new" variant="primary" className="!h-8"><Plus className="size-4" /> โจทย์ใหม่</ButtonLink></div>}>
      <table className="w-full text-sm" data-testid="admin-exercises"><tbody>{rows.map((e) => (
        <tr key={e.id} className="border-t border-line"><td className="w-24 py-1.5 font-mono text-xs text-muted">{e.code}</td><td>{e.title}</td>
          <td><DifficultyBadge d={e.difficulty} /></td><td className="text-xs text-muted">{e.project_slug ? `project: ${e.project_slug}` : e.category}</td>
          <td><EditBadges custom={e.is_custom} edited={e.admin_edited} /></td>
          <td className="text-right"><Link href={`/admin/exercises/${e.id}`} className="text-brand" aria-label={`แก้ไข ${e.code}`}><Pencil className="size-4" /></Link></td></tr>))}</tbody></table>
    </Card>
  );
}

function ProjectsTab() {
  const toast = useToast();
  const { data, loading, reload } = useApi<AdminProject[]>("/admin/projects");
  const [edit, setEdit] = useState<Partial<AdminProject> | null>(null);
  async function save() {
    if (!edit) return;
    const body = { slug: edit.slug, title: edit.title, role: edit.role, summary: edit.summary, brief_md: edit.brief_md,
      deliverables: edit.deliverables ?? [], sample_db: edit.sample_db, difficulty: edit.difficulty };
    try {
      if (edit.id) await api.put(`/admin/projects/${edit.id}`, body); else await api.post("/admin/projects", body);
      toast.push("ok", "บันทึกโปรเจกต์แล้ว"); setEdit(null); reload();
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function del(p: AdminProject) {
    if (!confirm(`ลบโปรเจกต์ ${p.title}? งานในโปรเจกต์จะถูกลบด้วย`)) return;
    try { await api.del(`/admin/projects/${p.id}`); reload(); } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  if (loading || !data) return <Spinner />;
  const inp = "w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm";
  return (
    <div className="space-y-4">
      {edit ? (
        <Card title={edit.id ? `แก้ไข ${edit.title}` : "โปรเจกต์ใหม่"}>
          <div className="grid gap-2 md:grid-cols-2">
            {(["slug", "title", "role", "sample_db"] as const).map((k) => <label key={k} className="text-xs">{k}<input className={inp} value={(edit[k] as string) ?? ""} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} /></label>)}
            <label className="text-xs">difficulty<select className={inp} value={edit.difficulty ?? "hard"} onChange={(e) => setEdit({ ...edit, difficulty: e.target.value as Difficulty })}>
              {["easy", "medium", "hard", "expert"].map((d) => <option key={d}>{d}</option>)}</select></label>
            <label className="text-xs md:col-span-2">summary<input className={inp} value={edit.summary ?? ""} onChange={(e) => setEdit({ ...edit, summary: e.target.value })} /></label>
            <label className="text-xs md:col-span-2">business brief (markdown)<textarea rows={8} className={cx(inp, "font-mono")} value={edit.brief_md ?? ""} onChange={(e) => setEdit({ ...edit, brief_md: e.target.value })} /></label>
            <label className="text-xs md:col-span-2">deliverables (บรรทัดละรายการ)<textarea rows={3} className={inp} value={(edit.deliverables ?? []).join("\n")} onChange={(e) => setEdit({ ...edit, deliverables: e.target.value.split("\n").filter(Boolean) })} /></label>
          </div>
          <div className="mt-3 flex gap-2"><Button variant="primary" onClick={save}>บันทึก</Button><Button onClick={() => setEdit(null)}>ยกเลิก</Button></div>
          <p className="mt-2 text-xs text-muted">เพิ่มงาน (tasks) ของโปรเจกต์ได้ที่แท็บ “โจทย์” โดยเลือก project</p>
        </Card>
      ) : <div className="flex justify-end"><Button variant="primary" onClick={() => setEdit({ difficulty: "hard", sample_db: "ecommerce" })}><Plus className="size-4" /> โปรเจกต์ใหม่</Button></div>}
      <Card title="Projects">
        <ul className="divide-y divide-line text-sm">{data.map((p) => (
          <li key={p.id} className="flex items-center gap-2 py-2"><span className="flex-1"><b>{p.title}</b> <span className="text-xs text-muted">· {p.sample_db} · {p.tasks} งาน</span></span>
            <EditBadges custom={p.is_custom} edited={p.admin_edited} />
            <Button size="sm" variant="ghost" onClick={() => setEdit(p)}><Pencil className="size-3.5" /></Button>
            {p.is_custom && <Button size="sm" variant="ghost" onClick={() => del(p)}>ลบ</Button>}</li>))}</ul>
      </Card>
    </div>
  );
}

function AchievementsTab() {
  const toast = useToast();
  const { data, loading, reload } = useApi<AdminAch[]>("/admin/achievements");
  const [edit, setEdit] = useState<AdminAch | null>(null);
  if (loading || !data) return <Spinner />;
  return (
    <Card title={<span className="flex items-center gap-1.5"><Trophy className="size-4" /> Achievements</span>}>
      <p className="mb-2 text-xs text-muted">เงื่อนไขการได้รับกำหนดในโค้ด (services/progress.py) — แก้ไขชื่อ คำอธิบาย และไอคอนได้ที่นี่</p>
      <ul className="divide-y divide-line text-sm">{data.map((a) => edit?.key === a.key ? (
        <li key={a.key} className="grid gap-2 py-2 md:grid-cols-4">
          <input className="rounded border border-line bg-surface px-2 py-1" value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} aria-label="title" />
          <input className="rounded border border-line bg-surface px-2 py-1 md:col-span-2" value={edit.description} onChange={(e) => setEdit({ ...edit, description: e.target.value })} aria-label="description" />
          <div className="flex gap-1"><input className="w-24 rounded border border-line bg-surface px-2 py-1" value={edit.icon} onChange={(e) => setEdit({ ...edit, icon: e.target.value })} aria-label="icon" />
            <Button size="sm" variant="primary" onClick={async () => { try { await api.put(`/admin/achievements/${a.key}`, edit); setEdit(null); reload(); } catch (e) { toast.push("err", (e as ApiError).message); } }}>บันทึก</Button></div>
        </li>) : (
        <li key={a.key} className="flex items-center gap-2 py-2"><span className="flex-1"><b>{a.title}</b> <span className="text-xs text-muted">— {a.description}</span></span>
          <Badge>{a.earned_by} คนได้รับ</Badge><Button size="sm" variant="ghost" onClick={() => setEdit(a)}><Pencil className="size-3.5" /></Button></li>))}</ul>
    </Card>
  );
}

function DatabasesTab() {
  const toast = useToast();
  const { data, loading, reload } = useApi<AdminDb[]>("/admin/databases");
  const [busy, setBusy] = useState<string | null>(null);
  async function rebuild(d: AdminDb) {
    if (!confirm(`สร้างฐานข้อมูล ${d.key} (template + read-only) ใหม่จากไฟล์ seed และคำนวณ expected result ของ ${d.exercises} โจทย์ใหม่? (Writable sandbox ของผู้เรียนไม่ถูกแตะ)`)) return;
    setBusy(d.key);
    try {
      const r = await api.post<{ ok: boolean; recomputed_failures: { code: string; error: string }[] }>(`/admin/databases/${d.key}/rebuild`);
      toast.push(r.ok ? "ok" : "err", r.ok ? `สร้าง ${d.key} ใหม่เรียบร้อย` : `โจทย์ที่คำนวณใหม่ไม่ผ่าน: ${r.recomputed_failures.map((f) => f.code).join(", ")}`);
      reload();
    } catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(null); }
  }
  if (loading || !data) return <Spinner />;
  return (
    <Card title={<span className="flex items-center gap-1.5"><Database className="size-4" /> Sample Databases</span>}>
      <table className="w-full text-sm"><thead className="text-left text-xs text-muted"><tr><th>Key</th><th>ชื่อ</th><th className="text-right">ตาราง</th><th className="text-right">แถว</th><th className="text-right">โจทย์</th><th /></tr></thead>
        <tbody>{data.map((d) => <tr key={d.key} className="border-t border-line"><td className="py-1.5 font-mono">{d.key}</td><td>{d.name}</td><td className="text-right tabular-nums">{d.tables}</td>
          <td className="text-right tabular-nums">{d.rows.toLocaleString()}</td><td className="text-right tabular-nums">{d.exercises}</td>
          <td className="text-right"><Button size="sm" onClick={() => rebuild(d)} loading={busy === d.key}><RefreshCw className="size-3.5" /> Rebuild</Button></td></tr>)}</tbody></table>
    </Card>
  );
}

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("overview");
  return (
    <AdminGuard>
      <PageHeader title={<span className="flex items-center gap-2"><Shield className="size-6 text-brand" /> Admin Panel</span>}
        description="จัดการเนื้อหา ผู้ใช้ และฐานข้อมูลของแพลตฟอร์ม — ทุกการบันทึกเนื้อหาถูกตรวจโดยการรัน SQL จริงบน sandbox" />
      <div className="mb-4 flex flex-wrap gap-1 border-b border-line" role="tablist">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cx("-mb-px border-b-2 px-3 py-2 text-sm", tab === k ? "border-brand font-medium" : "border-transparent text-muted hover:text-fg")}>{label}</button>
        ))}
      </div>
      {tab === "overview" && <Overview />}
      {tab === "users" && <UsersTab />}
      {tab === "lessons" && <LessonsTab />}
      {tab === "exercises" && <ExercisesTab />}
      {tab === "projects" && <ProjectsTab />}
      {tab === "achievements" && <AchievementsTab />}
      {tab === "databases" && <DatabasesTab />}
    </AdminGuard>
  );
}
