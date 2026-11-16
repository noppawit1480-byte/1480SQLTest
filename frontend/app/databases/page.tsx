"use client";

import Link from "next/link";
import { Database, Table2 } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { DatabaseSummary } from "@/lib/types";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui";

export default function DatabasesPage() {
  const { data, error, loading, reload } = useApi<DatabaseSummary[]>("/databases");
  return (
    <>
      <PageHeader title="Sample Databases" description="ฐานข้อมูลจำลอง 5 โดเมนธุรกิจ พร้อม PK/FK, ข้อมูลกรณีพิเศษ (NULL, ค่าซ้ำ, ข้อมูลไม่มีความสัมพันธ์) และ ER Diagram" />
      {loading ? <div className="grid gap-4 md:grid-cols-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-40" />)}</div>
        : error ? <ErrorState message={error.message} onRetry={reload} />
        : (
          <div className="grid gap-4 md:grid-cols-2">
            {data!.map((d) => (
              <div key={d.key} className="flex flex-col rounded-lg border border-line bg-surface p-5">
                <div className="flex items-center gap-2"><Database className="size-5 text-brand" /><h2 className="font-bold">{d.name}</h2>
                  <span className="ml-auto font-mono text-xs text-muted">{d.key} · {d.engine}</span></div>
                <p className="mt-1 text-sm text-muted">{d.description}</p>
                <ul className="mt-3 flex flex-wrap gap-1.5">
                  {d.tables.map((t) => <li key={t.name} className="flex items-center gap-1 rounded border border-line px-1.5 py-0.5 font-mono text-xs"><Table2 className="size-3 text-muted" />{t.name}<span className="text-muted">({t.rows})</span></li>)}
                </ul>
                <div className="mt-4 flex gap-3 text-sm">
                  <Link href={`/databases/${d.key}`} className="text-brand hover:underline">ER Diagram & คำอธิบาย</Link>
                  <Link href={`/playground?db=${d.key}`} className="text-brand hover:underline">เปิดใน Playground</Link>
                </div>
              </div>
            ))}
          </div>
        )}
    </>
  );
}
