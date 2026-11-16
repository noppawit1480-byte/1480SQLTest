"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { CheckCircle2, FlaskConical, Save, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { ColumnInfo, DatabaseSummary } from "@/lib/types";
import { AdminGuard } from "@/components/AdminGuard";
import { useToast } from "@/components/providers";
import { DataTable } from "@/components/ResultView";
import { Button, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";

interface Ex {
  id?: number; code: string; title: string; description_md: string; difficulty: string; category: string; points?: number | null;
  sample_db: string; check_type: "select" | "dml"; solution_sql: string; check_sql: string | null; order_matters: boolean;
  check_column_names: boolean; hints: string[]; explanation_md: string; lesson_slug: string | null; project_slug: string | null;
  is_custom?: boolean; expected?: { columns: ColumnInfo[]; rows: unknown[][]; row_count: number };
}
const EMPTY: Ex = { code: "", title: "", description_md: "", difficulty: "easy", category: "SELECT", sample_db: "ecommerce", check_type: "select",
  solution_sql: "", check_sql: null, order_matters: false, check_column_names: true, hints: ["", "", ""], explanation_md: "", lesson_slug: null, project_slug: null };
const inp = "w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm";

function Editor({ id }: { id: string }) {
  const router = useRouter();
  const toast = useToast();
  const isNew = id === "new";
  const existing = useApi<Ex>(isNew ? null : `/admin/exercises/${id}`);
  const dbs = useApi<DatabaseSummary[]>("/databases");
  const projects = useApi<{ slug: string; title: string }[]>("/admin/projects");
  const [ex, setEx] = useState<Ex>(EMPTY);
  const [preview, setPreview] = useState<Ex["expected"] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (existing.data) { setEx({ ...existing.data, hints: [...existing.data.hints] }); setPreview(existing.data.expected ?? null); } }, [existing.data]);
  if (!isNew && existing.loading) return <Spinner />;
  if (!isNew && existing.error) return <ErrorState message={existing.error.message} />;

  const set = <K extends keyof Ex>(k: K, v: Ex[K]) => setEx({ ...ex, [k]: v });
  const body = () => ({ ...ex, id: undefined, is_custom: undefined, expected: undefined, points: ex.points || null,
    check_sql: ex.check_type === "dml" ? ex.check_sql : null, lesson_slug: ex.lesson_slug || null, project_slug: ex.project_slug || null });

  async function validate() {
    setBusy(true);
    try { setPreview(await api.post<Ex["expected"]>("/admin/exercises/validate", body())); toast.push("ok", "เฉลยรันผ่าน"); }
    catch (e) { setPreview(null); toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  async function save() {
    setBusy(true);
    try {
      const r = isNew ? await api.post<Ex>("/admin/exercises", body()) : await api.put<Ex>(`/admin/exercises/${id}`, body());
      toast.push("ok", "บันทึกแล้ว — expected result คำนวณจากการรันเฉลยจริง");
      if (isNew) router.replace(`/admin/exercises/${r.id}`); else setPreview(r.expected ?? null);
    } catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  async function del() {
    if (!confirm(`ลบโจทย์ ${ex.code}?`)) return;
    try { await api.del(`/admin/exercises/${id}`); router.push("/admin"); } catch (e) { toast.push("err", (e as ApiError).message); }
  }

  return (
    <>
      <nav className="mb-2 text-sm text-muted"><Link href="/admin" className="hover:underline">Admin</Link> / โจทย์</nav>
      <PageHeader title={isNew ? "โจทย์ใหม่" : `แก้ไข ${ex.code}`} actions={<div className="flex gap-2">
        <Button onClick={validate} loading={busy}><FlaskConical className="size-4" /> ทดสอบเฉลย</Button>
        <Button variant="primary" onClick={save} loading={busy} data-testid="save-exercise"><Save className="size-4" /> บันทึก</Button>
        {!isNew && ex.is_custom && <Button variant="ghost" onClick={del}><Trash2 className="size-4" /></Button>}</div>} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="ข้อมูลโจทย์">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="text-xs">รหัส (เช่น EX-C001)<input className={inp} value={ex.code} onChange={(e) => set("code", e.target.value.toUpperCase())} disabled={!isNew && !ex.is_custom} /></label>
            <label className="text-xs">หมวด<input className={inp} value={ex.category} onChange={(e) => set("category", e.target.value)} /></label>
            <label className="text-xs sm:col-span-2">ชื่อโจทย์<input className={inp} value={ex.title} onChange={(e) => set("title", e.target.value)} /></label>
            <label className="text-xs">ระดับ<select className={inp} value={ex.difficulty} onChange={(e) => set("difficulty", e.target.value)}>{["easy", "medium", "hard", "expert"].map((d) => <option key={d}>{d}</option>)}</select></label>
            <label className="text-xs">คะแนน (ว่าง = ตามระดับ)<input type="number" className={inp} value={ex.points ?? ""} onChange={(e) => set("points", e.target.value ? Number(e.target.value) : null)} /></label>
            <label className="text-xs">ฐานข้อมูล<select className={inp} value={ex.sample_db} onChange={(e) => set("sample_db", e.target.value)}>{dbs.data?.map((d) => <option key={d.key} value={d.key}>{d.key}</option>)}</select></label>
            <label className="text-xs">ประเภทการตรวจ<select className={inp} value={ex.check_type} onChange={(e) => set("check_type", e.target.value as Ex["check_type"])}><option value="select">select (เทียบผล SELECT)</option><option value="dml">dml (รันบนสำเนาแล้วตรวจด้วย check_sql)</option></select></label>
            <label className="text-xs">บทเรียน (slug, ไม่บังคับ)<input className={inp} value={ex.lesson_slug ?? ""} onChange={(e) => set("lesson_slug", e.target.value)} /></label>
            <label className="text-xs">Project (ไม่บังคับ)<select className={inp} value={ex.project_slug ?? ""} onChange={(e) => set("project_slug", e.target.value)}><option value="">— ไม่ใช่งานในโปรเจกต์ —</option>{projects.data?.map((p) => <option key={p.slug} value={p.slug}>{p.title}</option>)}</select></label>
            <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={ex.order_matters} onChange={(e) => set("order_matters", e.target.checked)} /> ตรวจลำดับแถว</label>
            <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={ex.check_column_names} onChange={(e) => set("check_column_names", e.target.checked)} /> ตรวจชื่อคอลัมน์</label>
            <label className="text-xs sm:col-span-2">รายละเอียดโจทย์ (markdown)<textarea rows={5} className={inp} value={ex.description_md} onChange={(e) => set("description_md", e.target.value)} /></label>
          </div>
        </Card>
        <Card title="เฉลย ตัวตรวจ และคำใบ้">
          <div className="space-y-2">
            <label className="block text-xs">solution_sql<textarea rows={6} className={`${inp} font-mono`} value={ex.solution_sql} onChange={(e) => set("solution_sql", e.target.value)} data-testid="solution-sql" /></label>
            {ex.check_type === "dml" && <label className="block text-xs">check_sql (query ที่ใช้ตรวจสภาพข้อมูลหลังรันคำตอบ)<textarea rows={3} className={`${inp} font-mono`} value={ex.check_sql ?? ""} onChange={(e) => set("check_sql", e.target.value)} /></label>}
            {[0, 1, 2].map((i) => <label key={i} className="block text-xs">Hint {i + 1}<input className={inp} value={ex.hints[i]} onChange={(e) => { const h = [...ex.hints]; h[i] = e.target.value; set("hints", h); }} /></label>)}
            <label className="block text-xs">คำอธิบายเฉลย (markdown)<textarea rows={3} className={inp} value={ex.explanation_md} onChange={(e) => set("explanation_md", e.target.value)} /></label>
          </div>
        </Card>
      </div>
      <Card className="mt-4" title={<span className="flex items-center gap-1.5">{preview && <CheckCircle2 className="size-4 text-ok" />} Expected result {preview && `(${preview.row_count} แถว — จากการรันเฉลยจริง)`}</span>}>
        {preview ? <DataTable columns={preview.columns} rows={preview.rows} maxHeight="18rem" /> : <p className="text-sm text-muted">กด “ทดสอบเฉลย” เพื่อรันบน sandbox และดูผลลัพธ์ที่คาดหวัง</p>}
      </Card>
    </>
  );
}

export default function AdminExercisePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <AdminGuard><Editor id={id} /></AdminGuard>;
}
