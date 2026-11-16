"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, Info, Rows3 } from "lucide-react";
import type { ColumnInfo, ExecutionResult } from "@/lib/types";
import { cx, EmptyState, Spinner } from "./ui";

const NUMERIC = new Set(["int2", "int4", "int8", "numeric", "float4", "float8", "money", "oid"]);

function Cell({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <span className="italic text-muted">NULL</span>;
  if (typeof v === "boolean") return <span className="text-brand">{v ? "true" : "false"}</span>;
  if (typeof v === "object") return <span>{JSON.stringify(v)}</span>;
  return <span>{String(v)}</span>;
}

export function DataTable({ columns, rows, maxHeight = "100%", className, highlightRows }: {
  columns: ColumnInfo[]; rows: unknown[][]; maxHeight?: string; className?: string; highlightRows?: Set<number>;
}) {
  if (!columns.length) return null;
  return (
    <div className={cx("overflow-auto scrollbar-thin rounded-md border border-line", className)} style={{ maxHeight }}>
      <table className="w-full border-collapse font-mono text-[12.5px]" data-testid="result-table">
        <thead className="sticky top-0 z-10 bg-surface-2">
          <tr>
            <th className="w-10 border-b border-line px-2 py-1.5 text-right text-[11px] font-normal text-muted">#</th>
            {columns.map((c, i) => (
              <th key={i} className="whitespace-nowrap border-b border-l border-line px-3 py-1.5 text-left">
                <div className="font-semibold">{c.name}</div>
                <div className="text-[10px] font-normal text-muted">{c.type}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={cx("odd:bg-surface even:bg-bg hover:bg-brand-soft/30", highlightRows?.has(i) && "!bg-bad-soft/50")}>
              <td className="border-b border-line px-2 py-1 text-right text-[11px] text-muted">{i + 1}</td>
              {r.map((v, j) => (
                <td key={j} className={cx("max-w-[28rem] truncate whitespace-nowrap border-b border-l border-line px-3 py-1",
                  NUMERIC.has(columns[j]?.type) && "text-right tabular-nums")} title={v === null ? "NULL" : String(v)}>
                  <Cell v={v} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ErrorBox({ result }: { result: ExecutionResult }) {
  const e = result.error!;
  const title = { timeout: "Query หมดเวลา", limit: "เกินขีดจำกัด", permission: "ไม่มีสิทธิ์", internal: "ระบบขัดข้อง", sql: "SQL Error" }[e.kind];
  return (
    <div className="rounded-md border border-bad/40 bg-bad-soft/40 p-3 text-sm" role="alert" data-testid="sql-error">
      <div className="flex items-center gap-2 font-semibold text-bad">
        <AlertTriangle className="size-4" /> {title}
        {e.sqlstate && <span className="font-mono text-xs font-normal text-muted">SQLSTATE {e.sqlstate}</span>}
        {e.line && <span className="font-mono text-xs font-normal text-muted">บรรทัด {e.line}, คอลัมน์ {e.column}</span>}
      </div>
      <p className="mt-1.5 whitespace-pre-wrap font-mono text-[13px]">{e.message}</p>
      {e.detail && <p className="mt-1 text-xs text-muted">DETAIL: {e.detail}</p>}
      {e.hint && <p className="mt-1 text-xs text-muted">HINT: {e.hint}</p>}
      {result.result_sets.length > 0 && (
        <p className="mt-2 text-xs text-muted">คำสั่งก่อนหน้าที่สำเร็จ: {result.result_sets.map((r) => r.command).join(" · ")}</p>
      )}
    </div>
  );
}

export function ResultView({ result, running, emptyHint = "กด Run (Ctrl/⌘ + Enter) เพื่อรัน SQL" }: {
  result: ExecutionResult | null; running: boolean; emptyHint?: string;
}) {
  const [tab, setTab] = useState<number | null>(null);
  if (running) return <Spinner label="กำลังรัน query..." />;
  if (!result) return <EmptyState title="ยังไม่มีผลลัพธ์" description={emptyHint} icon={<Rows3 className="size-8" />} />;

  const withRows = result.result_sets.filter((r) => r.columns.length);
  const activeIdx = tab !== null && tab < result.result_sets.length ? tab
    : (withRows.length ? result.result_sets.indexOf(withRows[withRows.length - 1]) : result.result_sets.length - 1);
  const active = result.result_sets[activeIdx];

  return (
    <div className="flex h-full min-h-0 flex-col gap-2" data-testid="result-view">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {result.ok ? (
          <span className="flex items-center gap-1 font-medium text-ok" data-testid="exec-status"><CheckCircle2 className="size-3.5" /> สำเร็จ</span>
        ) : (
          <span className="flex items-center gap-1 font-medium text-bad" data-testid="exec-status"><AlertTriangle className="size-3.5" /> ล้มเหลว</span>
        )}
        {active?.columns.length ? (
          <span className="flex items-center gap-1 text-muted" data-testid="row-count"><Rows3 className="size-3.5" /> {active.row_count.toLocaleString()} แถว{active.truncated && " (ตัดที่ขีดจำกัด)"}</span>
        ) : null}
        <span className="flex items-center gap-1 text-muted"><Clock className="size-3.5" /> {result.exec_ms} ms</span>
        <span className="text-muted">{result.statements} คำสั่ง</span>
      </div>
      {result.result_sets.length > 1 && (
        <div className="flex flex-wrap gap-1" role="tablist">
          {result.result_sets.map((r, i) => (
            <button key={i} role="tab" aria-selected={i === activeIdx} onClick={() => setTab(i)}
              className={cx("rounded border px-2 py-0.5 font-mono text-[11px]", i === activeIdx ? "border-brand bg-brand-soft text-brand" : "border-line text-muted hover:bg-surface-2")}>
              {i + 1}. {r.command || "OK"}
            </button>
          ))}
        </div>
      )}
      {result.notices.length > 0 && (
        <div className="flex items-start gap-1.5 rounded border border-line bg-surface-2 px-2 py-1 text-xs text-muted">
          <Info className="mt-0.5 size-3.5" /> {result.notices.join(" · ")}
        </div>
      )}
      {!result.ok && <ErrorBox result={result} />}
      {active && (active.columns.length ? (
        active.rows.length ? <DataTable columns={active.columns} rows={active.rows} className="min-h-0 flex-1" />
          : <div className="rounded-md border border-line p-4 text-center text-sm text-muted">Query สำเร็จ แต่ไม่มีแถวที่ตรงเงื่อนไข (0 แถว)
              <DataTable columns={active.columns} rows={[]} className="mt-2" /></div>
      ) : result.ok ? (
        <div className="rounded-md border border-line p-4 font-mono text-sm">{active.command || "OK"}</div>
      ) : null)}
    </div>
  );
}
