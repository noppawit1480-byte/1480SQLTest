"use client";

import { AlertTriangle, Database, Search } from "lucide-react";
import type { Plan, PlanNode } from "@/lib/types";
import { cx } from "./ui";

/** Visual EXPLAIN tree: one card per node, indented by depth, with a cost/time bar relative to the root. */
function NodeCard({ n, max, depth, metric }: { n: PlanNode; max: number; depth: number; metric: "time_ms" | "est_cost" }) {
  const value = (n[metric] as number | null | undefined) ?? 0;
  const pct = max ? Math.min(100, (100 * value) / max) : 0;
  const scan = /Seq Scan|^SCAN$/.test(n.label);
  return (
    <li>
      <div className={cx("rounded-md border bg-surface p-2 text-xs", scan ? "border-warn/50" : n.index ? "border-ok/50" : "border-line")}
        style={{ marginLeft: depth * 18 }} data-testid="plan-node">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          {scan ? <Database className="size-3.5 text-warn" /> : n.index ? <Search className="size-3.5 text-ok" /> : null}
          <b className="text-[13px]">{n.label}</b>
          {n.relation && <span>on <b>{n.relation}</b>{n.alias && n.alias !== n.relation && <span className="text-muted"> ({n.alias})</span>}</span>}
          {n.index && <span className="text-ok">using {n.index}</span>}
          <span className="ml-auto flex gap-3 tabular-nums text-muted">
            {n.est_rows != null && <span title="rows ที่ planner คาดการณ์">est {n.est_rows.toLocaleString()} rows</span>}
            {n.actual_rows != null && <span title="rows จริง × loops">actual {(n.actual_rows * (n.loops ?? 1)).toLocaleString()}</span>}
            {n.est_cost != null && <span>cost {n.est_cost.toLocaleString()}</span>}
            {n.time_ms != null && <span>{n.time_ms.toFixed(2)} ms</span>}
          </span>
        </div>
        {n.detail.length > 0 && <div className="mt-1 space-y-0.5 font-mono text-[11px] text-muted">{n.detail.map((d, i) => <div key={i} className="break-all">{d}</div>)}</div>}
        {n.misestimate && (
          <div className="mt-1 flex items-center gap-1 text-[11px] text-warn"><AlertTriangle className="size-3" />
            planner ประมาณจำนวนแถวคลาดเคลื่อน ~{n.misestimate}× — สถิติอาจเก่า (ANALYZE) หรือเงื่อนไขซับซ้อน</div>
        )}
        {max > 0 && (
          <div className="mt-1.5 h-1.5 rounded-full bg-surface-2" aria-label={`${metric === "time_ms" ? "เวลา" : "cost"} ${pct.toFixed(0)}% ของทั้งหมด`}>
            <div className={cx("h-full rounded-full", pct > 60 ? "bg-bad" : pct > 25 ? "bg-warn" : "bg-brand")} style={{ width: `${Math.max(pct, 1)}%` }} />
          </div>
        )}
      </div>
      {n.children.length > 0 && <ul className="mt-1 space-y-1">{n.children.map((c) => <NodeCard key={c.id} n={c} max={max} depth={depth + 1} metric={metric} />)}</ul>}
    </li>
  );
}

export function PlanTree({ plan }: { plan: Plan }) {
  const metric = plan.analyzed ? "time_ms" : "est_cost";
  const max = (plan.root[metric] as number | null) ?? 0;
  return (
    <div className="space-y-2" data-testid="plan-tree">
      <div className="flex flex-wrap gap-3 text-xs text-muted">
        <span>engine: <b>{plan.engine}</b></span>
        {plan.total_cost != null && <span>total cost: <b>{plan.total_cost.toLocaleString()}</b></span>}
        {plan.planning_ms != null && <span>planning: <b>{plan.planning_ms.toFixed(2)} ms</b></span>}
        {plan.execution_ms != null && <span>execution: <b>{plan.execution_ms.toFixed(2)} ms</b></span>}
        <span>{plan.analyzed ? "แถบ = สัดส่วนเวลาจริง" : plan.engine === "postgresql" ? "แถบ = สัดส่วน cost โดยประมาณ" : "SQLite EXPLAIN QUERY PLAN (ไม่มี cost)"}</span>
      </div>
      <ul className="space-y-1">
        {plan.engine === "sqlite" && plan.root.label === "QUERY PLAN"
          ? plan.root.children.map((c) => <NodeCard key={c.id} n={c} max={0} depth={0} metric={metric} />)
          : <NodeCard n={plan.root} max={max} depth={0} metric={metric} />}
      </ul>
    </div>
  );
}
