"use client";

import Link from "next/link";
import { use, useState } from "react";
import { Eye, KeyRound, Link2, Terminal } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseDetail, ExecutionResult } from "@/lib/types";
import { Mermaid } from "@/components/Mermaid";
import { ResultView } from "@/components/ResultView";
import { Button, ButtonLink, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";

export default function DatabaseDetailPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = use(params);
  const { data, error, loading, reload } = useApi<DatabaseDetail>(`/databases/${key}`);
  const [preview, setPreview] = useState<{ table: string; result: ExecutionResult | null; error?: string } | null>(null);

  async function load(table: string) {
    setPreview({ table, result: null });
    try { setPreview({ table, result: await api.get<ExecutionResult>(`/databases/${key}/tables/${table}/preview`) }); }
    catch (e) { setPreview({ table, result: null, error: (e as ApiError).message }); }
  }

  if (loading) return <Spinner />;
  if (error || !data) return <ErrorState message={error?.message ?? "ไม่พบฐานข้อมูล"} onRetry={reload} />;
  return (
    <>
      <nav className="mb-2 text-sm text-muted"><Link href="/databases" className="hover:underline">Databases</Link> / {data.name}</nav>
      <PageHeader title={data.name} description={data.description}
        actions={<ButtonLink variant="primary" href={`/playground?db=${key}`}><Terminal className="size-4" /> เปิดใน Playground</ButtonLink>} />
      <Card title="ER Diagram (สร้างจากโครงสร้างจริงในฐานข้อมูล)"><Mermaid chart={data.er_mermaid} /></Card>

      <h2 className="mt-8 mb-3 text-lg font-bold">ตารางและคอลัมน์</h2>
      <div className="space-y-4">
        {data.tables.map((t) => (
          <Card key={t.name} title={<span className="font-mono">{t.name} <span className="font-sans text-xs font-normal text-muted">· {t.row_estimate} แถว</span></span>}
            action={<Button size="sm" onClick={() => load(t.name)}><Eye className="size-3.5" /> Preview Data</Button>}>
            {t.comment && <p className="mb-3 text-sm text-muted">{t.comment}</p>}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted"><tr><th className="py-1 pr-3">Column</th><th className="pr-3">Type</th><th className="pr-3">Null</th><th className="pr-3">Key</th><th>คำอธิบาย</th></tr></thead>
                <tbody>
                  {t.columns.map((c) => (
                    <tr key={c.name} className="border-t border-line">
                      <td className="py-1.5 pr-3 font-mono">{c.name}</td>
                      <td className="pr-3 font-mono text-xs text-muted">{c.type}</td>
                      <td className="pr-3 text-xs">{c.nullable ? "YES" : "NO"}</td>
                      <td className="pr-3 text-xs">
                        {c.is_pk && <span className="mr-1 inline-flex items-center gap-0.5 text-warn"><KeyRound className="size-3" />PK</span>}
                        {c.fk && <span className="inline-flex items-center gap-0.5 text-brand"><Link2 className="size-3" />FK → {c.fk}</span>}
                      </td>
                      <td className="text-xs text-muted">{c.comment}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview?.table === t.name && (
              <div className="mt-3 max-h-96">
                {preview.error ? <ErrorState message={preview.error} /> : <ResultView result={preview.result} running={!preview.result} />}
              </div>
            )}
          </Card>
        ))}
      </div>
      <p className="mt-6 text-sm text-muted">ต้องการคืนค่าฐานข้อมูลหลังทดลอง INSERT/UPDATE/DELETE? ใช้ปุ่ม <b>Reset</b> ในโหมด Writable ของ Playground — ฐานข้อมูลแบบ Read-only ไม่มีวันถูกแก้ไข</p>
    </>
  );
}
