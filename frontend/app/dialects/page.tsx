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

type Eng = "postgresql" | "sqlite" | "mysql";
type CompareRes = Partial<Record<Eng, ExecutionResult>> & {
  engines: Eng[];
  comparison: { same: boolean | null; message: string; details: Record<string, unknown>;
    engines: Partial<Record<Eng, { same: boolean | null; message: string }>> };
  features: DialectFeature[];
};
const TITLE: Record<Eng, string> = { postgresql: "PostgreSQL 16", sqlite: "SQLite 3", mysql: "MySQL 8.4" };

function FeatureTable({ features, title, executable }: { features: DialectFeature[]; title: string; executable: string[] }) {
  const mysqlRuns = executable.includes("mysql");
  return (
    <Card title={title}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="dialect-table">
          <thead className="text-left text-xs text-muted"><tr><th className="py-1 pr-3">เรื่อง</th><th className="pr-3">PostgreSQL</th><th className="pr-3">SQLite</th><th className="pr-3">MySQL{mysqlRuns ? "" : "*"}</th><th>SQL Server*</th></tr></thead>
          <tbody>{features.map((f) => (
            <tr key={f.key} className="border-t border-line align-top">
              <td className="py-1.5 pr-3 font-medium">{f.title}{f.note && <div className="text-[11px] font-normal text-muted">{f.note}</div>}</td>
              {[f.postgresql, f.sqlite, f.mysql, f.sqlserver].map((v, i) => <td key={i} className="pr-3 font-mono text-xs">{v}</td>)}
            </tr>))}</tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-muted">* {mysqlRuns ? "SQL Server เป็นข้อมูลอ้างอิงสำหรับเรียนรู้ — แพลตฟอร์มนี้รัน SQL จริงบน PostgreSQL, SQLite และ MySQL"
        : "MySQL และ SQL Server เป็นข้อมูลอ้างอิงสำหรับเรียนรู้ — เซิร์ฟเวอร์นี้รัน SQL จริงบน PostgreSQL และ SQLite (ผู้ดูแลระบบยังไม่ได้เปิด MySQL)"}</p>
    </Card>
  );
}

function Dialects() {
  const params = useSearchParams();
  const toast = useToast();
  const dbs = useApi<DatabaseSummary[]>("/databases");
  const ref = useApi<{ features: DialectFeature[]; executable: string[] }>("/dialects/reference");
  const executable = ref.data?.executable ?? ["postgresql", "sqlite"];
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
        description={`รัน SQL เดียวกันบน ${executable.map((e) => TITLE[e as Eng]?.split(" ")[0] ?? e).join(", ")} (ข้อมูลชุดเดียวกัน) แล้วเทียบผลลัพธ์กับ PostgreSQL — พร้อมคำอธิบายความต่างของแต่ละ dialect`} />
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
          <div className={cx("grid gap-4", res.engines.length > 2 ? "xl:grid-cols-3" : "lg:grid-cols-2")}>
            {res.engines.map((e) => {
              const c = res.comparison.engines?.[e];
              return (
                <Card key={e} title={<span className="flex items-center gap-2">{TITLE[e]}
                  {e === "postgresql" ? <span className="text-xs font-normal text-muted">(อ้างอิง)</span>
                    : c && <span className={cx("text-xs font-normal", c.same ? "text-ok" : "text-warn")} data-testid={`verdict-${e}`}>{c.same ? "ตรงกับ PostgreSQL ✔" : c.same === false ? "ต่างจาก PostgreSQL" : "รันไม่สำเร็จ"}</span>}</span>}>
                  <div className="max-h-96 overflow-auto" data-testid={`result-${e}`}>{res[e] && <ResultView result={res[e]!} running={false} />}</div>
                </Card>);
            })}
          </div>
          {res.features.length > 0 && <FeatureTable features={res.features} executable={executable} title="สิ่งที่ query นี้ใช้ และวิธีเขียนในแต่ละ dialect" />}
        </div>
      )}
      <div className="mt-6">{ref.data && <FeatureTable features={ref.data.features} executable={executable} title="ตารางเทียบ dialect ทั้งหมด" />}</div>
    </>
  );
}

export default function DialectsPage() { return <Suspense fallback={<Spinner />}><Dialects /></Suspense>; }
