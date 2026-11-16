"use client";

import Link from "next/link";
import { use, useState } from "react";
import { CheckCircle2, Eye, Lightbulb, Play, Send, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseDetail, ExecutionResult, GeneratedPractice } from "@/lib/types";
import { useToast } from "@/components/providers";
import { Markdown, SqlBlock } from "@/components/Markdown";
import { DataTable, ResultView } from "@/components/ResultView";
import { SqlEditor } from "@/components/SqlEditor";
import { Badge, Button, cx, ErrorState, Spinner } from "@/components/ui";

interface GenSubmit { correct: boolean; message: string; details: { missing_rows?: unknown[][]; unexpected_rows?: unknown[][] }; execution: ExecutionResult; solution_sql: string | null }

export default function GeneratedPracticePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const toast = useToast();
  const g = useApi<GeneratedPractice>(`/assistant/generated/${id}`);
  const schema = useApi<DatabaseDetail>(g.data ? `/databases/${g.data.db_key}` : null);
  const [sql, setSql] = useState("-- เขียนคำตอบที่นี่\n");
  const [hints, setHints] = useState(0);
  const [res, setRes] = useState<ExecutionResult | null>(null);
  const [fb, setFb] = useState<GenSubmit | null>(null);
  const [sol, setSol] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (g.loading) return <Spinner />;
  if (g.error || !g.data) return <ErrorState message={g.error?.message ?? "ไม่พบโจทย์"} onRetry={g.reload} />;
  const p = g.data;

  async function run() {
    setBusy(true); setFb(null);
    try { setRes(await api.post<ExecutionResult>(`/assistant/generated/${id}/run`, { sql })); }
    catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  async function submit() {
    setBusy(true);
    try { const r = await api.post<GenSubmit>(`/assistant/generated/${id}/submit`, { sql }); setFb(r); setRes(r.execution); }
    catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(false); }
  }
  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <section className="overflow-y-auto border-line bg-surface p-4 lg:w-[42%] lg:border-r max-lg:max-h-[45%]">
        <Link href="/assistant" className="text-xs text-brand hover:underline">← SQL Learning Assistant</Link>
        <div className="mt-2 flex flex-wrap gap-1.5"><Badge>โจทย์ฝึกจาก AI</Badge><Badge>{p.topic}</Badge><Badge>DB: {p.db_key}</Badge>
          {p.solved && <span className="flex items-center gap-1 text-xs text-ok"><CheckCircle2 className="size-3.5" /> ทำถูกแล้ว</span>}</div>
        <h1 className="mt-2 text-xl font-bold">{p.title}</h1>
        <div className="mt-2"><Markdown>{p.description_md}</Markdown></div>
        <h2 className="mt-4 mb-2 text-sm font-semibold">Expected Result ({p.expected.row_count} แถว)</h2>
        <DataTable columns={p.expected.columns} rows={p.expected.rows} maxHeight="14rem" />
        <div className="mt-4 space-y-2">
          {p.hints.slice(0, hints).map((h, i) => <div key={i} className="rounded-md border border-warn/30 bg-warn-soft/40 p-2 text-sm"><b className="text-xs text-warn">Hint {i + 1}</b><br />{h}</div>)}
          <div className="flex gap-2">
            {hints < p.hints.length && <Button size="sm" onClick={() => setHints(hints + 1)}><Lightbulb className="size-3.5" /> Hint {hints + 1}</Button>}
            {!sol && <Button size="sm" variant="ghost" onClick={async () => setSol((await api.get<{ solution_sql: string }>(`/assistant/generated/${id}/solution`)).solution_sql)}><Eye className="size-3.5" /> Show Solution</Button>}
          </div>
          {sol && <SqlBlock code={sol} />}
        </div>
      </section>
      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex gap-1.5 border-b border-line bg-surface px-2 py-1.5">
          <Button size="sm" onClick={run} loading={busy}><Play className="size-3.5" /> Run</Button>
          <Button size="sm" variant="primary" onClick={submit} loading={busy}><Send className="size-3.5" /> Submit</Button>
        </div>
        <div className="min-h-[160px] flex-1 border-b border-line"><SqlEditor value={sql} onChange={setSql} onRun={run} schema={schema.data?.tables} /></div>
        <div className="min-h-0 flex-1 overflow-y-auto bg-surface p-3">
          {fb && (
            <div className={cx("mb-3 rounded-lg border p-3", fb.correct ? "border-ok/40 bg-ok-soft/40" : "border-bad/40 bg-bad-soft/30")}>
              <div className="flex items-center gap-2 font-bold">{fb.correct ? <CheckCircle2 className="size-5 text-ok" /> : <XCircle className="size-5 text-bad" />}{fb.correct ? "Correct" : "Incorrect"}</div>
              <p className="mt-1 text-sm">{fb.message}</p>
              {fb.solution_sql && <SqlBlock code={fb.solution_sql} className="mt-2" />}
            </div>
          )}
          <ResultView result={res} running={busy} />
        </div>
      </section>
    </div>
  );
}
