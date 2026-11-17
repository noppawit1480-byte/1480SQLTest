"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { FlaskConical, Gauge } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseSummary, Plan, PlanSummary } from "@/lib/types";
import { PlanTree } from "@/components/PlanTree";
import { useAuth, useToast } from "@/components/providers";
import { SqlEditor } from "@/components/SqlEditor";
import { Button, Card, cx, EmptyState, PageHeader, Spinner, StatCard } from "@/components/ui";

interface LabRes { ok: boolean; error?: string; before: Plan; after: Plan; summary_before: PlanSummary; summary_after: PlanSummary;
  new_indexes_used: string[]; speedup: number | null; verdict: string; note: string }

const EXAMPLES = [
  { db: "saas", sql: "SELECT * FROM events\nWHERE properties->>'device' = 'ios'\n  AND occurred_at >= '2025-12-01';", idx: "CREATE INDEX ON events ((properties->>'device'), occurred_at);" },
  { db: "ecommerce", sql: "SELECT id, order_date FROM orders\nWHERE status = 'cancelled'\nORDER BY order_date DESC;", idx: "CREATE INDEX ON orders (status, order_date DESC);" },
  { db: "banking", sql: "SELECT * FROM transactions\nWHERE txn_type = 'fee' AND amount < -50;", idx: "CREATE INDEX ON transactions (txn_type);" },
];

function Lab() {
  const params = useSearchParams();
  const { user } = useAuth();
  const toast = useToast();
  const dbs = useApi<DatabaseSummary[]>("/databases");
  const [dbKey, setDbKey] = useState(params.get("db") ?? EXAMPLES[0].db);
  const [sql, setSql] = useState(params.get("sql") || EXAMPLES[0].sql);
  const [idx, setIdx] = useState(EXAMPLES[0].idx);
  const [res, setRes] = useState<LabRes | null>(null);
  const [busy, setBusy] = useState(false);

  async function runLab() {
    setBusy(true);
    try {
      const r = await api.post<LabRes>("/plans/index-lab", { db_key: dbKey, sql, index_sql: idx });
      if (!r.ok) toast.push("err", r.error ?? "ทดลองไม่สำเร็จ");
      setRes(r.ok ? r : null);
    } catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHeader title={<span className="flex items-center gap-2"><Gauge className="size-6 text-brand" /> Optimization Lab — Index Simulator</span>}
        description="วัดผล query → สร้าง index ที่เสนอ → วัดผลอีกครั้ง บนสำเนาฐานข้อมูลชั่วคราว แล้วเทียบ execution plan ก่อน/หลัง (EXPLAIN ANALYZE จริง)" />
      <div className="mb-3 flex flex-wrap gap-2 text-xs">ตัวอย่าง:
        {EXAMPLES.map((e, i) => <button key={i} className="rounded border border-line px-2 py-0.5 hover:border-brand" onClick={() => { setDbKey(e.db); setSql(e.sql); setIdx(e.idx); setRes(null); }}>{e.db}: {e.idx.slice(13, 60)}</button>)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Query (SELECT)" action={<select value={dbKey} onChange={(e) => setDbKey(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1 text-sm" aria-label="ฐานข้อมูล">
          {dbs.data?.filter((d) => d.key !== "blank").map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}</select>}>
          <div className="h-40"><SqlEditor value={sql} onChange={setSql} /></div>
        </Card>
        <Card title="Index ที่เสนอ (CREATE INDEX สูงสุด 3 คำสั่ง)" action={
          user ? <Button variant="primary" size="sm" onClick={runLab} loading={busy} data-testid="lab-run"><FlaskConical className="size-3.5" /> ทดลอง</Button>
            : <Link href="/login?next=/optimize" className="text-sm text-brand underline">เข้าสู่ระบบเพื่อทดลอง</Link>}>
          <div className="h-40"><SqlEditor value={idx} onChange={setIdx} validate={false} /></div>
        </Card>
      </div>
      {busy && <Spinner label="กำลังสร้างสำเนา วัดผล สร้าง index และวัดผลอีกครั้ง..." />}
      {!busy && !res && <EmptyState title="ยังไม่ได้ทดลอง" description="เลือกตัวอย่างหรือเขียน query และ index ของคุณเอง แล้วกด ทดลอง" />}
      {res && !busy && (
        <div className="mt-4 space-y-4" data-testid="lab-result">
          <div className={cx("rounded-md border px-3 py-2 text-sm", res.new_indexes_used.length ? "border-ok/40 bg-ok-soft/40" : "border-warn/40 bg-warn-soft/40")}>
            <b>{res.verdict}</b><div className="text-xs text-muted">{res.note}</div></div>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="เวลา ก่อน" value={`${res.summary_before.execution_ms?.toFixed(2)} ms`} />
            <StatCard label="เวลา หลัง" value={`${res.summary_after.execution_ms?.toFixed(2)} ms`} sub={res.speedup ? `${res.speedup}× เร็วขึ้น` : undefined} />
            <StatCard label="cost ก่อน → หลัง" value={`${Math.round(res.summary_before.total_cost ?? 0)} → ${Math.round(res.summary_after.total_cost ?? 0)}`} />
            <StatCard label="Seq Scan ก่อน → หลัง" value={`${res.summary_before.seq_scans.length} → ${res.summary_after.seq_scans.length}`} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="แผนก่อนสร้าง index"><PlanTree plan={res.before} /></Card>
            <Card title="แผนหลังสร้าง index"><PlanTree plan={res.after} /></Card>
          </div>
        </div>
      )}
    </>
  );
}

export default function OptimizePage() { return <Suspense fallback={<Spinner />}><Lab /></Suspense>; }
