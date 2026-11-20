"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Copy, Download, FileUp, FolderOpen, Plus, Rocket, Save, Shapes, Trash2, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseSummary, Design, DesignColumn, Engine } from "@/lib/types";
import { EngineSelect } from "@/components/EngineSelect";
import { Mermaid } from "@/components/Mermaid";
import { useAuth, useToast } from "@/components/providers";
import { SqlBlock } from "@/components/Markdown";
import { DataTable } from "@/components/ResultView";
import { Badge, Button, Card, cx, EmptyState, PageHeader, Spinner } from "@/components/ui";

const TYPES = ["integer", "bigint", "smallint", "numeric(10,2)", "real", "text", "varchar(100)", "varchar(255)", "boolean", "date", "timestamp", "timestamptz", "jsonb", "uuid"];
const STARTER: Design = {
  tables: [
    { name: "customers", columns: [{ name: "id", type: "integer", pk: true, identity: true }, { name: "name", type: "varchar(100)", not_null: true }, { name: "email", type: "text", not_null: true, unique: true }] },
    { name: "orders", columns: [{ name: "id", type: "integer", pk: true, identity: true }, { name: "customer_id", type: "integer", not_null: true }, { name: "created_at", type: "timestamptz", not_null: true, default: "now()" }] },
  ],
  relations: [{ from_table: "orders", from_column: "customer_id", to_table: "customers", to_column: "id", on_delete: "restrict" }],
};
const inp = "rounded border border-line bg-surface px-1.5 py-1 text-xs";
interface DdlRes { issues: { level: string; message: string }[]; mermaid: string; ddl: Record<string, string> | null }

function DesignerTab() {
  const { user } = useAuth();
  const toast = useToast();
  const [design, setDesign] = useState<Design>(STARTER);
  const [name, setName] = useState("My design");
  const [id, setId] = useState<number | null>(null);
  const [check, setCheck] = useState<DdlRes | null>(null);
  const [dialect, setDialect] = useState("postgresql");
  const [engine, setEngine] = useState<Engine>("postgresql");
  const [applied, setApplied] = useState<string | null>(null);
  const mine = useApi<{ id: number; name: string; design: Design }[]>(user ? "/designs" : null);
  const dbs = useApi<DatabaseSummary[]>("/databases");

  useEffect(() => {
    const t = window.setTimeout(() => { api.post<DdlRes>("/designs/ddl", design).then(setCheck).catch(() => undefined); }, 400);
    return () => window.clearTimeout(t);
  }, [design]);

  const errors = check?.issues.filter((i) => i.level === "error") ?? [];
  const setTable = (ti: number, patch: Partial<Design["tables"][number]>) =>
    setDesign({ ...design, tables: design.tables.map((t, i) => (i === ti ? { ...t, ...patch } : t)) });
  const setCol = (ti: number, ci: number, patch: Partial<DesignColumn>) =>
    setTable(ti, { columns: design.tables[ti].columns.map((c, i) => (i === ci ? { ...c, ...patch } : c)) });
  const renameTable = (ti: number, nn: string) => {
    const old = design.tables[ti].name;
    setDesign({ tables: design.tables.map((t, i) => (i === ti ? { ...t, name: nn } : t)),
      relations: design.relations.map((r) => ({ ...r, from_table: r.from_table === old ? nn : r.from_table, to_table: r.to_table === old ? nn : r.to_table })) });
  };
  const colsOf = (t: string) => design.tables.find((x) => x.name === t)?.columns.map((c) => c.name) ?? [];

  async function save() {
    try {
      const r = id ? await api.put<{ id: number }>(`/designs/${id}`, { name, design }) : await api.post<{ id: number }>("/designs", { name, design });
      setId(r.id); toast.push("ok", "บันทึกแบบแล้ว"); mine.reload();
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function apply() {
    if (!id) { toast.push("err", "บันทึกแบบก่อน"); return; }
    if (!confirm("สร้างตารางตามแบบนี้ในฐานข้อมูล blank (Writable sandbox ของคุณ)? ข้อมูลเดิมใน blank จะถูกล้าง")) return;
    try {
      await api.put(`/designs/${id}`, { name, design });
      const r = await api.post<{ ok: boolean; message?: string; error?: string }>(`/designs/${id}/apply`, { engine });
      if (r.ok) { setApplied(r.message ?? "สำเร็จ"); toast.push("ok", "สร้างตารางแล้ว"); } else toast.push("err", r.error ?? "ไม่สำเร็จ");
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function loadFromDb(key: string) {
    try { setDesign(await api.get<Design>(`/designs/from-db/${key}`)); setName(`${key} (reverse-engineered)`); setId(null); }
    catch (e) { toast.push("err", (e as ApiError).message); }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm" aria-label="ชื่อแบบ" />
        {user ? <Button size="sm" onClick={save} data-testid="save-design"><Save className="size-3.5" /> {id ? "บันทึก" : "บันทึกเป็นแบบใหม่"}</Button>
          : <Link href="/login?next=/designer" className="text-sm text-brand underline">เข้าสู่ระบบเพื่อบันทึก</Link>}
        <Button size="sm" variant="ghost" onClick={() => { setDesign({ tables: [], relations: [] }); setId(null); setName("New design"); }}>เริ่มใหม่</Button>
        <select onChange={(e) => e.target.value && loadFromDb(e.target.value)} value="" className="rounded-md border border-line bg-surface px-2 py-1 text-sm" aria-label="โหลดจากฐานข้อมูลตัวอย่าง">
          <option value="">โหลดโครงสร้างจาก DB ตัวอย่าง…</option>
          {dbs.data?.filter((d) => d.key !== "blank").map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}
        </select>
        {mine.data && mine.data.length > 0 && (
          <select onChange={(e) => { const d = mine.data!.find((x) => x.id === Number(e.target.value)); if (d) { setDesign(d.design); setName(d.name); setId(d.id); } }}
            value="" className="rounded-md border border-line bg-surface px-2 py-1 text-sm" aria-label="แบบของฉัน">
            <option value="">แบบของฉัน ({mine.data.length})…</option>
            {mine.data.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
        {id && <Button size="sm" variant="ghost" onClick={async () => { if (confirm("ลบแบบนี้?")) { await api.del(`/designs/${id}`); setId(null); mine.reload(); } }}><Trash2 className="size-3.5" /></Button>}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-3">
          {design.tables.map((t, ti) => (
            <Card key={ti} title={<input value={t.name} onChange={(e) => renameTable(ti, e.target.value)} className={cx(inp, "font-mono text-sm font-semibold")} aria-label="ชื่อตาราง" />}
              action={<button onClick={() => setDesign({ tables: design.tables.filter((_, i) => i !== ti), relations: design.relations.filter((r) => r.from_table !== t.name && r.to_table !== t.name) })} aria-label={`ลบตาราง ${t.name}`} className="text-muted hover:text-bad"><Trash2 className="size-4" /></button>}>
              <table className="w-full text-xs" data-testid="design-table">
                <thead className="text-left text-muted"><tr><th>คอลัมน์</th><th>ชนิด</th><th title="Primary key">PK</th><th title="NOT NULL">NN</th><th title="UNIQUE">UQ</th><th title="identity (auto increment)">ID</th><th>default</th><th /></tr></thead>
                <tbody>{t.columns.map((c, ci) => (
                  <tr key={ci}>
                    <td><input className={cx(inp, "w-28 font-mono")} value={c.name} onChange={(e) => setCol(ti, ci, { name: e.target.value })} aria-label="ชื่อคอลัมน์" /></td>
                    <td><input list="types" className={cx(inp, "w-28 font-mono")} value={c.type} onChange={(e) => setCol(ti, ci, { type: e.target.value })} aria-label="ชนิดข้อมูล" /></td>
                    {(["pk", "not_null", "unique", "identity"] as const).map((k) => <td key={k}><input type="checkbox" checked={!!c[k]} onChange={(e) => setCol(ti, ci, { [k]: e.target.checked })} aria-label={k} /></td>)}
                    <td><input className={cx(inp, "w-20 font-mono")} value={c.default ?? ""} onChange={(e) => setCol(ti, ci, { default: e.target.value || null })} aria-label="default" /></td>
                    <td><button onClick={() => setTable(ti, { columns: t.columns.filter((_, i) => i !== ci) })} aria-label="ลบคอลัมน์" className="text-muted hover:text-bad"><XCircle className="size-3.5" /></button></td>
                  </tr>))}</tbody>
              </table>
              <button className="mt-2 text-xs text-brand" onClick={() => setTable(ti, { columns: [...t.columns, { name: `column_${t.columns.length + 1}`, type: "text" }] })}>+ เพิ่มคอลัมน์</button>
            </Card>
          ))}
          <Button size="sm" onClick={() => setDesign({ ...design, tables: [...design.tables, { name: `table_${design.tables.length + 1}s`, columns: [{ name: "id", type: "integer", pk: true, identity: true }] }] })} data-testid="add-table">
            <Plus className="size-3.5" /> เพิ่มตาราง</Button>
          <Card title="ความสัมพันธ์ (Foreign keys)" action={<button className="text-xs text-brand" onClick={() => design.tables.length && setDesign({ ...design, relations: [...design.relations, { from_table: design.tables[0].name, from_column: design.tables[0].columns[0]?.name ?? "", to_table: design.tables[0].name, to_column: "id", on_delete: "no action" }] })}>+ เพิ่ม</button>}>
            {design.relations.length === 0 ? <p className="text-xs text-muted">ยังไม่มีความสัมพันธ์</p> : (
              <ul className="space-y-1 text-xs">{design.relations.map((r, ri) => {
                const up = (p: Partial<typeof r>) => setDesign({ ...design, relations: design.relations.map((x, i) => (i === ri ? { ...x, ...p } : x)) });
                return (
                  <li key={ri} className="flex flex-wrap items-center gap-1">
                    <select className={inp} value={r.from_table} onChange={(e) => up({ from_table: e.target.value })} aria-label="ตารางลูก">{design.tables.map((t) => <option key={t.name}>{t.name}</option>)}</select>.
                    <select className={inp} value={r.from_column} onChange={(e) => up({ from_column: e.target.value })} aria-label="คอลัมน์ FK">{colsOf(r.from_table).map((c) => <option key={c}>{c}</option>)}</select>→
                    <select className={inp} value={r.to_table} onChange={(e) => up({ to_table: e.target.value })} aria-label="ตารางแม่">{design.tables.map((t) => <option key={t.name}>{t.name}</option>)}</select>.
                    <select className={inp} value={r.to_column} onChange={(e) => up({ to_column: e.target.value })} aria-label="คอลัมน์อ้างอิง">{colsOf(r.to_table).map((c) => <option key={c}>{c}</option>)}</select>
                    <select className={inp} value={r.on_delete ?? "no action"} onChange={(e) => up({ on_delete: e.target.value })} aria-label="on delete">{["no action", "restrict", "cascade", "set null"].map((o) => <option key={o}>{o}</option>)}</select>
                    <button onClick={() => setDesign({ ...design, relations: design.relations.filter((_, i) => i !== ri) })} aria-label="ลบความสัมพันธ์" className="text-muted hover:text-bad"><XCircle className="size-3.5" /></button>
                  </li>);
              })}</ul>)}
          </Card>
          <datalist id="types">{TYPES.map((t) => <option key={t} value={t} />)}</datalist>
        </div>
        <div className="space-y-3">
          {check && check.issues.length > 0 && (
            <ul className="space-y-1 text-xs" data-testid="design-issues">{check.issues.map((i, k) => (
              <li key={k} className={cx("flex items-start gap-1 rounded px-2 py-1", i.level === "error" ? "bg-bad-soft/40 text-bad" : "bg-warn-soft/40")}>
                <AlertTriangle className="mt-0.5 size-3 shrink-0" />{i.message}</li>))}</ul>)}
          <Card title="ER Diagram (อัปเดตอัตโนมัติ)">{check?.mermaid && design.tables.length ? <Mermaid chart={check.mermaid} /> : <EmptyState title="เพิ่มตารางเพื่อดู ER Diagram" />}</Card>
          <Card title="DDL" action={<div className="flex gap-1 text-xs">{["postgresql", "sqlite", "mysql"].map((d) => (
            <button key={d} onClick={() => setDialect(d)} className={cx("rounded px-2 py-0.5", dialect === d ? "bg-brand-soft text-brand" : "text-muted")}>{d}</button>))}</div>}>
            {check?.ddl ? (
              <>
                <SqlBlock code={check.ddl[dialect]} />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="ghost" onClick={() => { navigator.clipboard.writeText(check.ddl![dialect]); toast.push("ok", "คัดลอกแล้ว"); }}><Copy className="size-3.5" /> คัดลอก</Button>
                  {user && (<>
                    <EngineSelect value={engine} onChange={setEngine} className={inp} aria-label="engine" data-testid="apply-engine" />
                    <Button size="sm" variant="primary" onClick={apply} data-testid="apply-design"><Rocket className="size-3.5" /> สร้างใน Writable sandbox</Button>
                  </>)}
                </div>
                {applied && <p className="mt-2 text-sm text-ok" data-testid="apply-result">{applied} · <Link className="underline" href={`/playground?db=blank&mode=writable&engine=${engine}`}>เปิด Playground</Link></p>}
              </>
            ) : <p className="text-sm text-muted">{errors.length ? `แก้ข้อผิดพลาด ${errors.length} รายการก่อน จึงจะสร้าง DDL ได้` : "กำลังตรวจสอบ..."}</p>}
          </Card>
        </div>
      </div>
    </div>
  );
}

interface Preview { columns: { name: string; type: string; nulls: number; sample: string[] }[]; row_count: number; sample: string[][] }

function CsvTab() {
  const { user } = useAuth();
  const toast = useToast();
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [delimiter, setDelimiter] = useState(",");
  const [header, setHeader] = useState(true);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [types, setTypes] = useState<string[]>([]);
  const [table, setTable] = useState("imported");
  const [engine, setEngine] = useState<Engine>("postgresql");
  const [replace, setReplace] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const cols = useMemo(() => preview?.columns ?? [], [preview]);

  if (!user) return <EmptyState title="เข้าสู่ระบบเพื่อนำเข้า CSV" description="ข้อมูลจะถูกนำเข้าในฐานข้อมูลส่วนตัว (Writable sandbox) ของคุณ" action={<Link className="text-brand underline" href="/login?next=/designer">เข้าสู่ระบบ</Link>} />;
  async function doPreview(t = text) {
    try {
      const p = await api.post<Preview>("/csv/preview", { csv_text: t, delimiter, has_header: header });
      setPreview(p); setTypes(p.columns.map((c) => c.type)); setDone(null);
    } catch (e) { setPreview(null); toast.push("err", (e as ApiError).message); }
  }
  async function doImport() {
    try {
      const r = await api.post<{ message: string }>("/csv/import", { csv_text: text, delimiter, has_header: header, table_name: table, engine, replace, db_key: "blank",
        columns: cols.map((c, i) => ({ name: c.name, type: types[i] })) });
      setDone(r.message); toast.push("ok", "นำเข้าแล้ว");
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  return (
    <div className="space-y-4">
      <Card title="1. เลือกไฟล์ CSV (สูงสุด 5 MB / 50,000 แถว)">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-3 py-1.5 hover:bg-surface-2"><FileUp className="size-4" /> {fileName || "เลือกไฟล์"}
            <input type="file" accept=".csv,text/csv,.tsv,.txt" className="hidden" data-testid="csv-file" onChange={async (e) => {
              const f = e.target.files?.[0]; if (!f) return;
              if (f.size > 5 * 1024 * 1024) { toast.push("err", "ไฟล์ใหญ่เกิน 5 MB"); return; }
              const t = await f.text(); setText(t); setFileName(f.name);
              setTable(f.name.replace(/\.[^.]+$/, "").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^[^a-z_]+/, "t_") || "imported");
              doPreview(t);
            }} /></label>
          <label>ตัวคั่น <select value={delimiter} onChange={(e) => setDelimiter(e.target.value)} className={inp}><option value=",">,</option><option value=";">;</option><option value={"\t"}>tab</option><option value="|">|</option></select></label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={header} onChange={(e) => setHeader(e.target.checked)} /> แถวแรกเป็นหัวตาราง</label>
          {text && <Button size="sm" onClick={() => doPreview()}>ตรวจใหม่</Button>}
        </div>
      </Card>
      {preview && (
        <Card title={`2. ตรวจชนิดข้อมูล (${preview.row_count.toLocaleString()} แถว)`}>
          <table className="w-full text-xs" data-testid="csv-columns"><thead className="text-left text-muted"><tr><th>คอลัมน์</th><th>ชนิด (แก้ได้)</th><th>ค่าว่าง</th><th>ตัวอย่าง</th></tr></thead>
            <tbody>{cols.map((c, i) => (
              <tr key={c.name} className="border-t border-line"><td className="py-1 font-mono">{c.name}</td>
                <td><select className={inp} value={types[i]} onChange={(e) => setTypes(types.map((t, j) => (j === i ? e.target.value : t)))}>
                  {["integer", "bigint", "numeric", "boolean", "date", "timestamp", "text"].map((t) => <option key={t}>{t}</option>)}</select></td>
                <td>{c.nulls}</td><td className="font-mono text-muted">{c.sample.join(" · ")}</td></tr>))}</tbody></table>
          <div className="mt-3"><DataTable columns={cols.map((c, i) => ({ name: c.name, type: types[i] }))} rows={preview.sample} maxHeight="12rem" /></div>
        </Card>
      )}
      {preview && (
        <Card title="3. นำเข้า">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label>ชื่อตาราง <input value={table} onChange={(e) => setTable(e.target.value)} className={cx(inp, "font-mono")} data-testid="csv-table" /></label>
            <label>engine <EngineSelect value={engine} onChange={setEngine} className={inp} data-testid="csv-engine" /></label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} /> แทนที่ตารางเดิม</label>
            <Badge>ปลายทาง: ฐานข้อมูล blank (Writable sandbox)</Badge>
            <Button variant="primary" size="sm" onClick={doImport} data-testid="csv-import"><Download className="size-3.5" /> นำเข้า</Button>
          </div>
          {done && <p className="mt-2 text-sm text-ok" data-testid="csv-done">{done} · <Link className="underline" href={`/playground?db=blank&mode=writable&engine=${engine}&sql=${encodeURIComponent(`SELECT * FROM ${table} LIMIT 20;`)}`}>เปิดใน Playground</Link></p>}
        </Card>
      )}
    </div>
  );
}

export default function DesignerPage() {
  const [tab, setTab] = useState<"design" | "csv">("design");
  return (
    <>
      <PageHeader title={<span className="flex items-center gap-2"><Shapes className="size-6 text-brand" /> Database Design Playground</span>}
        description="ออกแบบตาราง ความสัมพันธ์ และ constraint ด้วย ER Diagram Builder — ตรวจแบบอัตโนมัติ สร้าง DDL 3 dialect และสร้างจริงในฐานข้อมูลส่วนตัว หรือนำเข้าข้อมูลจาก CSV" />
      <div className="mb-4 flex gap-1 border-b border-line" role="tablist">
        {([["design", "ER Diagram Builder", Shapes], ["csv", "นำเข้า CSV", FolderOpen]] as const).map(([k, label, Icon]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={cx("-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm", tab === k ? "border-brand font-medium" : "border-transparent text-muted")}><Icon className="size-4" /> {label}</button>
        ))}
      </div>
      {tab === "design" ? <DesignerTab /> : <CsvTab />}
    </>
  );
}
