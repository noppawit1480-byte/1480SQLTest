"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { ExamplePreview } from "@/lib/types";
import { AdminGuard } from "@/components/AdminGuard";
import { Markdown } from "@/components/Markdown";
import { useToast } from "@/components/providers";
import { DataTable } from "@/components/ResultView";
import { Button, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";

interface Example { title: string; sql: string; explain: string[]; db: string; writable: boolean; result?: ExamplePreview }
interface Mistake { title: string; wrong: string; right: string; why: string }
interface L {
  id?: number; course_slug: string; slug: string; title: string; summary: string; objectives: string[]; content_md: string;
  examples: Example[]; common_mistakes: Mistake[]; related_slugs: string[]; sample_db: string | null; is_custom?: boolean; admin_edited?: boolean;
}
const EMPTY: L = { course_slug: "beginner", slug: "", title: "", summary: "", objectives: [], content_md: "", examples: [], common_mistakes: [], related_slugs: [], sample_db: "ecommerce" };
const inp = "w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm";

function Editor({ id }: { id: string }) {
  const router = useRouter();
  const toast = useToast();
  const isNew = id === "new";
  const existing = useApi<L>(isNew ? null : `/admin/lessons/${id}`);
  const [l, setL] = useState<L>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [previewMd, setPreviewMd] = useState(false);
  useEffect(() => { if (existing.data) setL(existing.data); }, [existing.data]);
  if (!isNew && existing.loading) return <Spinner />;
  if (!isNew && existing.error) return <ErrorState message={existing.error.message} />;
  const set = <K extends keyof L>(k: K, v: L[K]) => setL({ ...l, [k]: v });
  const setEx = (i: number, patch: Partial<Example>) => set("examples", l.examples.map((e, j) => (j === i ? { ...e, ...patch, result: undefined } : e)));

  async function save() {
    setBusy(true);
    const body = { ...l, id: undefined, is_custom: undefined, admin_edited: undefined,
      examples: l.examples.map(({ result: _r, ...e }) => e) };
    try {
      const r = isNew ? await api.post<L>("/admin/lessons", body) : await api.put<L>(`/admin/lessons/${id}`, body);
      toast.push("ok", "บันทึกแล้ว — ผลลัพธ์ตัวอย่างคำนวณใหม่จากการรันจริง");
      if (isNew) router.replace(`/admin/lessons/${r.id}`); else setL(r);
    } catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  async function revert() {
    if (!confirm("คืนบทเรียนนี้เป็นเวอร์ชันใน repository (มีผลเมื่อรัน seed ครั้งถัดไป)?")) return;
    try { const r = await api.post<{ message: string }>(`/admin/lessons/${id}/revert`); toast.push("ok", r.message); existing.reload(); }
    catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function del() {
    if (!confirm("ลบบทเรียนนี้?")) return;
    try { await api.del(`/admin/lessons/${id}`); router.push("/admin"); } catch (e) { toast.push("err", (e as ApiError).message); }
  }

  return (
    <>
      <nav className="mb-2 text-sm text-muted"><Link href="/admin" className="hover:underline">Admin</Link> / บทเรียน</nav>
      <PageHeader title={isNew ? "บทเรียนใหม่" : `แก้ไข: ${l.title}`} actions={<div className="flex gap-2">
        {!isNew && !l.is_custom && l.admin_edited && <Button onClick={revert}><RotateCcw className="size-4" /> คืนค่าจาก repository</Button>}
        {!isNew && l.is_custom && <Button variant="ghost" onClick={del}><Trash2 className="size-4" /></Button>}
        <Button variant="primary" onClick={save} loading={busy}><Save className="size-4" /> บันทึก</Button></div>} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="ข้อมูลบทเรียน">
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="text-xs">หลักสูตร<select className={inp} value={l.course_slug} onChange={(e) => set("course_slug", e.target.value)}>{["beginner", "intermediate", "advanced", "professional"].map((c) => <option key={c}>{c}</option>)}</select></label>
            <label className="text-xs">slug<input className={inp} value={l.slug} onChange={(e) => set("slug", e.target.value)} /></label>
            <label className="text-xs sm:col-span-2">ชื่อบทเรียน<input className={inp} value={l.title} onChange={(e) => set("title", e.target.value)} /></label>
            <label className="text-xs sm:col-span-2">คำอธิบายสั้น<input className={inp} value={l.summary} onChange={(e) => set("summary", e.target.value)} /></label>
            <label className="text-xs sm:col-span-2">วัตถุประสงค์ (บรรทัดละข้อ)<textarea rows={3} className={inp} value={l.objectives.join("\n")} onChange={(e) => set("objectives", e.target.value.split("\n"))} /></label>
            <label className="text-xs sm:col-span-2">บทเรียนที่เกี่ยวข้อง (slug คั่นด้วย comma)<input className={inp} value={l.related_slugs.join(", ")} onChange={(e) => set("related_slugs", e.target.value.split(",").map((x) => x.trim()).filter(Boolean))} /></label>
          </div>
        </Card>
        <Card title="เนื้อหา (markdown)" action={<button className="text-xs text-brand" onClick={() => setPreviewMd(!previewMd)}>{previewMd ? "แก้ไข" : "พรีวิว"}</button>}>
          {previewMd ? <Markdown>{l.content_md}</Markdown> : <textarea rows={14} className={`${inp} font-mono`} value={l.content_md} onChange={(e) => set("content_md", e.target.value)} />}
        </Card>
      </div>
      <Card className="mt-4" title={`ตัวอย่าง SQL (${l.examples.length}) — ผลลัพธ์คำนวณจากการรันจริงตอนบันทึก`}
        action={<Button size="sm" onClick={() => set("examples", [...l.examples, { title: "", sql: "", explain: [], db: l.sample_db ?? "ecommerce", writable: false }])}><Plus className="size-3.5" /> เพิ่ม</Button>}>
        <div className="space-y-4">{l.examples.map((ex, i) => (
          <div key={i} className="rounded-md border border-line p-3">
            <div className="grid gap-2 sm:grid-cols-4">
              <input className={`${inp} sm:col-span-2`} placeholder="ชื่อตัวอย่าง" value={ex.title} onChange={(e) => setEx(i, { title: e.target.value })} />
              <input className={inp} placeholder="db" value={ex.db} onChange={(e) => setEx(i, { db: e.target.value })} />
              <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={ex.writable} onChange={(e) => setEx(i, { writable: e.target.checked })} /> writable (DDL/DML)
                <button className="ml-auto text-bad" onClick={() => set("examples", l.examples.filter((_, j) => j !== i))} aria-label="ลบตัวอย่าง"><Trash2 className="size-4" /></button></label>
              <textarea rows={4} className={`${inp} font-mono sm:col-span-2`} value={ex.sql} onChange={(e) => setEx(i, { sql: e.target.value })} aria-label="SQL" />
              <textarea rows={4} className={`${inp} sm:col-span-2`} placeholder="คำอธิบายทีละส่วน (บรรทัดละข้อ)" value={ex.explain.join("\n")} onChange={(e) => setEx(i, { explain: e.target.value.split("\n") })} />
            </div>
            {ex.result && (ex.result.error ? <p className="mt-2 text-xs text-bad">ERROR: {ex.result.error.message}</p>
              : ex.result.columns ? <DataTable columns={ex.result.columns} rows={ex.result.rows ?? []} maxHeight="10rem" className="mt-2" /> : null)}
          </div>))}</div>
      </Card>
      <Card className="mt-4" title="ข้อผิดพลาดที่พบบ่อย" action={<Button size="sm" onClick={() => set("common_mistakes", [...l.common_mistakes, { title: "", wrong: "", right: "", why: "" }])}><Plus className="size-3.5" /> เพิ่ม</Button>}>
        <div className="space-y-3">{l.common_mistakes.map((m, i) => {
          const up = (p: Partial<Mistake>) => set("common_mistakes", l.common_mistakes.map((x, j) => (j === i ? { ...x, ...p } : x)));
          return (
            <div key={i} className="grid gap-2 rounded-md border border-line p-3 sm:grid-cols-2">
              <input className={`${inp} sm:col-span-2`} placeholder="หัวข้อ" value={m.title} onChange={(e) => up({ title: e.target.value })} />
              <textarea rows={2} className={`${inp} font-mono`} placeholder="✗ ผิด" value={m.wrong} onChange={(e) => up({ wrong: e.target.value })} />
              <textarea rows={2} className={`${inp} font-mono`} placeholder="✓ ถูก" value={m.right} onChange={(e) => up({ right: e.target.value })} />
              <input className={`${inp} sm:col-span-2`} placeholder="เหตุผล" value={m.why} onChange={(e) => up({ why: e.target.value })} />
            </div>);
        })}</div>
      </Card>
    </>
  );
}

export default function AdminLessonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <AdminGuard><Editor id={id} /></AdminGuard>;
}
