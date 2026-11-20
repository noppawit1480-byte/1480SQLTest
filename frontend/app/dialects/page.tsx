"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, GitCompare, Play, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseSummary, DialectFeature, ExecutionResult } from "@/lib/types";
import { useToast } from "@/components/providers";
import { ResultView } from "@/components/ResultView";
import { SqlEditor } from "@/components/SqlEditor";
import { Button, Card, cx, PageHeader, Spinner } from "@/components/ui";

interface CompareRes {
  postgresql: ExecutionResult; sqlite: ExecutionResult;
  comparison: { same: boolean | null; message: string; details: Record<string, unknown> };
  features: DialectFeature[];
}

function FeatureTable({ features, title }: { features: DialectFeature[]; title: string }) {
  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="dialect-table">
          <thead className="text-left text-xs text-muted"><tr><th className="py-1 pr-3">เรื่อง</th><th className="pr-3">PostgreSQL</th><th className="pr-3">SQLite</th><th className="pr-3">MySQL*</th><th>SQL Server*</th></tr></thead>
          <tbody>{features.map((f) => (
            <tr key={f.key} className="border-t border-line align-top">
              <td className="py-1.5 pr-3 font-medium">{f.title}{f.note && <div className="text-[11px] font-normal text-muted">{f.note}</div>}</td>
              {[f.postgresql, f.sqlite, f.mysql, f.sqlserver].map((v, i) => <td key={i} className="pr-3 font-mono text-xs">{v}</td>)}
            </tr>))}</tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted">* MySQL และ SQL Server เป็นข้อมูลอ้างอิงสำหรับเรียนรู้ — แพลตฟอร์มนี้รัน SQL จริงบน PostgreSQL และ SQLite</p>
    </Card>
  );
}

function Dialects() {
  const params = useSearchParams();
  const toast = useToast();
  const dbs = useApi<DatabaseSummary[]>("/databases");
  const ref = useApi<{ features: DialectFeature[] }>("/dialects/reference");
  const [dbKey, setDbKey] = useState(params.get("db") ?? "ecommerce");
  const [sql, setSql] = useState(params.get("sql") || "SELECT DATE_TRUNC('month', order_date)::date AS month, COUNT(*) AS orders\nFROM orders\nGROUP BY 1\nORDER BY 1\nLIMIT 5;");
  const [res, setRes] = useState<CompareRes | null>(null);
  const [busy, setBusy] = useState(false);

  async function compare() {
    setBusy(true);
    try { setRes(await api.post<CompareRes>("/dialects/compare", { sql, db_key: dbKey })); }
    catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  return (
    <>
      <PageHeader title={<span className="flex items-center gap-2"><GitCompare className="size-6 text-brand" /> SQL Dialect Comparison</span>}
        description="รัน SQL เดียวกันบน PostgreSQL และ SQLite (ข้อมูลชุดเดียวกัน) แล้วเทียบผลลัพธ์ — พร้อมคำอธิบายความต่างของแต่ละ dialect" />
      <Card title="SQL" action={<div className="flex items-center gap-2">
        <select value={dbKey} onChange={(e) => setDbKey(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1 text-sm" aria-label="ฐานข้อมูล">
          {dbs.data?.filter((d) => d.key !== "blank").map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}</select>
        <Button variant="primary" size="sm" onClick={compare} loading={busy} data-testid="compare-btn"><Play className="size-3.5" /> เทียบ</Button></div>}>
        <div className="h-48"><SqlEditor value={sql} onChange={setSql} onRun={compare} validate={false} /></div>
      </Card>
      {busy && <Spinner />}
      {res && !busy && (
        <div className="mt-4 space-y-4">
          <div className={cx("flex items-center gap-2 rounded-md border px-3 py-2 text-sm", res.comparison.same ? "border-ok/40 bg-ok-soft/40" : "border-warn/40 bg-warn-soft/40")} data-testid="compare-verdict">
            {res.comparison.same ? <CheckCircle2 className="size-4 text-ok" /> : <XCircle className="size-4 text-warn" />} {res.comparison.message}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="PostgreSQL 16"><div className="max-h-96 overflow-auto"><ResultView result={res.postgresql} running={false} /></div></Card>
            <Card title="SQLite 3"><div className="max-h-96 overflow-auto"><ResultView result={res.sqlite} running={false} /></div></Card>
          </div>
          {res.features.length > 0 && <FeatureTable features={res.features} title="สิ่งที่ query นี้ใช้ และวิธีเขียนในแต่ละ dialect" />}
        </div>
      )}
      <div className="mt-6">{ref.data && <FeatureTable features={ref.data.features} title="ตารางเทียบ dialect ทั้งหมด" />}</div>
    </>
  );
}

export default function DialectsPage() { return <Suspense fallback={<Spinner />}><Dialects /></Suspense>; }
