"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { format } from "sql-formatter";
import {
  ArrowLeft, ArrowRight, BookOpen, CheckCircle2, Eye, Lightbulb, Play, Send, Wand2, XCircle,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseDetail, ExecutionResult, ExerciseDetail, SubmitResult } from "@/lib/types";
import { useAuth, useToast } from "@/components/providers";
import { Markdown, SqlBlock } from "@/components/Markdown";
import { AssistantPanel } from "@/components/AssistantPanel";
import { DataTable, ResultView } from "@/components/ResultView";
import { SchemaExplorer } from "@/components/SchemaExplorer";
import { SqlEditor } from "@/components/SqlEditor";
import { Discussion } from "@/components/Discussion";
import { Badge, Button, ButtonLink, cx, DifficultyBadge, ErrorState, Spinner } from "@/components/ui";

const HINT_LABELS = ["Hint 1: คำใบ้เบื้องต้น", "Hint 2: แนวทางการแก้", "Hint 3: SQL Keywords ที่ควรใช้"];

export default function ExercisePage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const { user } = useAuth();
  const toast = useToast();
  const ex = useApi<ExerciseDetail>(`/exercises/${code}`);
  const schema = useApi<DatabaseDetail>(ex.data ? `/databases/${ex.data.sample_db}` : null);
  const [sql, setSql] = useState("");
  const [hints, setHints] = useState(0);
  const [solution, setSolution] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<ExecutionResult | null>(null);
  const [submit, setSubmit] = useState<SubmitResult | null>(null);
  const [busy, setBusy] = useState<"run" | "submit" | null>(null);
  const [leftTab, setLeftTab] = useState<"task" | "schema" | "discuss">("task");
  const [bottom, setBottom] = useState<"result" | "assistant">("result");

  useEffect(() => {
    setSql(localStorage.getItem(`ex:${code}`) ?? `-- ${code}: เขียนคำตอบของคุณที่นี่\n`);
    setHints(0); setSolution(null); setRunResult(null); setSubmit(null); setLeftTab("task"); setBottom("result");
  }, [code]);
  useEffect(() => {
    const id = window.setTimeout(() => localStorage.setItem(`ex:${code}`, sql), 400);
    return () => window.clearTimeout(id);
  }, [sql, code]);

  const run = useCallback(async () => {
    setBusy("run"); setSubmit(null); setBottom("result");
    try {
      setRunResult(await api.post<ExecutionResult>(`/exercises/${code}/run`, { sql }));
    } catch (e) {
      toast.push("err", (e as ApiError).message);
    } finally { setBusy(null); }
  }, [code, sql, toast]);

  async function doSubmit() {
    if (!user) { toast.push("err", "เข้าสู่ระบบเพื่อส่งคำตอบและบันทึกคะแนน"); return; }
    setBusy("submit"); setBottom("result");
    try {
      const r = await api.post<SubmitResult>(`/exercises/${code}/submit`, { sql });
      setSubmit(r); setRunResult(r.execution);
      toast.awards(r.new_achievements);
      if (r.correct) ex.setData(ex.data ? { ...ex.data, status: "solved", attempts: ex.data.attempts + 1 } : null);
    } catch (e) {
      toast.push("err", (e as ApiError).message);
    } finally { setBusy(null); }
  }

  async function showSolution() {
    if (!confirm("ดูเฉลยตอนนี้? แนะนำให้ลองใช้ Hint ทั้ง 3 ระดับก่อน")) return;
    const r = await api.get<{ solution_sql: string }>(`/exercises/${code}/solution`);
    setSolution(r.solution_sql);
  }

  const errorMarker = useMemo(() => runResult?.error?.line
    ? { line: runResult.error.line, column: runResult.error.column ?? 1, message: runResult.error.message } : null, [runResult]);

  if (ex.loading) return <Spinner />;
  if (ex.error || !ex.data) return <div className="p-6"><ErrorState message={ex.error?.message ?? "ไม่พบโจทย์"} onRetry={ex.reload} /></div>;
  const e = ex.data;
  const needsLogin = e.check_type === "dml" && !user;

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      {/* Left: problem */}
      <section className="flex min-h-0 flex-col border-line bg-surface lg:w-[42%] lg:border-r max-lg:max-h-[45%]">
        <div className="flex items-center gap-1 border-b border-line px-3 pt-1 text-xs" role="tablist">
          {(["task", "schema", "discuss"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={leftTab === t} onClick={() => setLeftTab(t)}
              className={cx("border-b-2 px-2.5 py-1.5", leftTab === t ? "border-brand font-medium" : "border-transparent text-muted")}>
              {t === "task" ? "โจทย์" : t === "discuss" ? "สนทนา" : `Schema: ${e.sample_db}`}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-4">
          {leftTab === "discuss" ? (
            <Discussion targetType="exercise" targetKey={e.code} />
          ) : leftTab === "schema" ? (
            schema.data ? <SchemaExplorer tables={schema.data.tables} /> : <Spinner />
          ) : (
            <>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-muted">{e.code}</span>
                <DifficultyBadge d={e.difficulty} /><Badge>{e.category}</Badge><Badge>{e.points} pts</Badge>
                <Badge>DB: {e.sample_db}</Badge>
                {e.check_type === "dml" && <Badge className="!text-warn">DML/DDL — ตรวจบนสำเนาฐานข้อมูลใหม่</Badge>}
                {e.status === "solved" && <span className="flex items-center gap-1 text-xs font-medium text-ok"><CheckCircle2 className="size-3.5" /> ทำถูกแล้ว</span>}
              </div>
              {e.project && (
                <Link href={`/projects/${e.project.slug}`} className="mb-1 block text-xs font-medium text-brand hover:underline">
                  Project: {e.project.title} · งานที่ {e.project.task_no}/{e.project.task_count}
                </Link>
              )}
              <h1 className="text-xl font-bold" data-testid="exercise-title">{e.title}</h1>
              <div className="mt-2"><Markdown>{e.description_md}</Markdown></div>
              {e.order_matters && <p className="mt-2 text-xs text-warn">⚠ โจทย์นี้ตรวจลำดับของแถวด้วย</p>}

              <h2 className="mt-5 mb-2 text-sm font-semibold">Expected Result <span className="font-normal text-muted">({e.expected.row_count} แถว{e.expected.row_count > e.expected.rows.length ? `, แสดง ${e.expected.rows.length} แถวแรก` : ""})</span></h2>
              <DataTable columns={e.expected.columns} rows={e.expected.rows} maxHeight="16rem" />

              <div className="mt-5 space-y-2">
                {e.hints.map((h, i) => i < hints ? (
                  <div key={i} className="rounded-md border border-warn/30 bg-warn-soft/40 p-3 text-sm" data-testid={`hint-${i + 1}`}>
                    <div className="mb-0.5 text-xs font-semibold text-warn">{HINT_LABELS[i]}</div>{h}
                  </div>
                ) : null)}
                <div className="flex flex-wrap gap-2">
                  {hints < 3 && <Button size="sm" onClick={() => setHints((h) => h + 1)} data-testid="hint-btn"><Lightbulb className="size-3.5" /> {HINT_LABELS[hints].split(":")[0]}</Button>}
                  {!solution && <Button size="sm" variant="ghost" onClick={showSolution}><Eye className="size-3.5" /> Show Solution</Button>}
                  {e.lesson && <ButtonLink href={`/learn/${e.lesson.course_slug}/${e.lesson.slug}`} variant="ghost" className="!h-8 !px-2.5 !text-xs"><BookOpen className="size-3.5" /> บทเรียน: {e.lesson.title}</ButtonLink>}
                </div>
                {solution && (
                  <div>
                    <div className="mb-1 flex items-center justify-between text-xs font-semibold">เฉลยตัวอย่าง
                      <button className="text-brand hover:underline" onClick={() => setSql(solution)}>ใส่ใน editor</button></div>
                    <SqlBlock code={solution} />
                  </div>
                )}
              </div>
            </>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-line px-3 py-2 text-sm">
          {e.prev ? <Link href={`/practice/${e.prev}`} className="flex items-center gap-1 text-muted hover:text-fg"><ArrowLeft className="size-4" /> {e.prev}</Link> : <span />}
          <Link href={e.project ? `/projects/${e.project.slug}` : "/practice"} className="text-xs text-muted hover:text-fg">{e.project ? "กลับไปที่โปรเจกต์" : "รายการโจทย์"}</Link>
          {e.next ? <Link href={`/practice/${e.next}`} className="flex items-center gap-1 text-muted hover:text-fg" data-testid="next-exercise">{e.next} <ArrowRight className="size-4" /></Link> : <span />}
        </div>
      </section>

      {/* Right: editor + feedback */}
      <section className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-surface px-2 py-1.5">
          <Button size="sm" onClick={run} loading={busy === "run"} disabled={needsLogin} data-testid="run-btn"><Play className="size-3.5" /> Run</Button>
          <Button size="sm" variant="primary" onClick={doSubmit} loading={busy === "submit"} data-testid="submit-btn"><Send className="size-3.5" /> Submit</Button>
          <Button size="sm" variant="ghost" onClick={() => { try { setSql(format(sql, { language: "postgresql", keywordCase: "upper" })); } catch { toast.push("err", "จัดรูปแบบไม่ได้"); } }}>
            <Wand2 className="size-3.5" /> Format
          </Button>
          {needsLogin && <span className="text-xs text-warn">โจทย์ DML/DDL ต้อง <Link className="underline" href={`/login?next=/practice/${code}`}>เข้าสู่ระบบ</Link> ก่อน</span>}
          {!user && !needsLogin && <span className="text-xs text-muted">Run ได้เลย · <Link className="underline" href={`/login?next=/practice/${code}`}>เข้าสู่ระบบ</Link> เพื่อ Submit</span>}
          {e.attempts > 0 && <span className="ml-auto text-xs text-muted">ส่งแล้ว {e.attempts} ครั้ง</span>}
        </div>
        <div className="min-h-[160px] flex-1 border-b border-line">
          <SqlEditor value={sql} onChange={setSql} onRun={run} schema={schema.data?.tables} errorMarker={errorMarker} />
        </div>
        <div className="flex min-h-0 flex-1 flex-col bg-surface">
          <div className="flex gap-1 border-b border-line px-2 pt-1 text-xs" role="tablist">
            {(["result", "assistant"] as const).map((t) => (
              <button key={t} role="tab" aria-selected={bottom === t} onClick={() => setBottom(t)}
                className={cx("border-b-2 px-2.5 py-1.5", bottom === t ? "border-brand font-medium" : "border-transparent text-muted")}>
                {t === "result" ? "ผลลัพธ์ / ผลตรวจ" : "Assistant"}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-3">
            {bottom === "assistant" ? (
              <AssistantPanel sql={sql} dbKey={e.sample_db} lastError={runResult?.error ?? null} exerciseCode={e.code} />
            ) : (
              <>
                {submit && <Feedback r={submit} onUse={(s) => setSql(s)} />}
                <ResultView result={runResult} running={busy !== null} emptyHint="Run เพื่อดูผลลัพธ์ของคุณ หรือ Submit เพื่อตรวจคำตอบ" />
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function Feedback({ r, onUse }: { r: SubmitResult; onUse: (s: string) => void }) {
  const d = r.details as { missing_rows?: unknown[][]; unexpected_rows?: unknown[][] };
  return (
    <div className={cx("mb-3 rounded-lg border p-4", r.correct ? "border-ok/40 bg-ok-soft/40" : "border-bad/40 bg-bad-soft/30")} data-testid="feedback" role="status">
      <div className="flex items-center gap-2 text-base font-bold">
        {r.correct ? <CheckCircle2 className="size-5 text-ok" /> : <XCircle className="size-5 text-bad" />}
        <span data-testid="verdict">{r.correct ? "Correct" : "Incorrect"}</span>
        {r.points_awarded > 0 && <span className="rounded bg-ok px-1.5 py-0.5 text-xs text-white">+{r.points_awarded} pts</span>}
      </div>
      <p className="mt-1 text-sm">{r.message}</p>
      {!r.correct && (d.missing_rows?.length || d.unexpected_rows?.length) ? (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {!!d.missing_rows?.length && <div><div className="mb-1 text-xs font-semibold">แถวที่คาดหวังแต่ไม่พบ (ตัวอย่าง)</div>
            <DataTable columns={r.expected.columns} rows={d.missing_rows} maxHeight="10rem" /></div>}
          {!!d.unexpected_rows?.length && <div><div className="mb-1 text-xs font-semibold">แถวที่เกินมา/ไม่ถูกต้อง (ตัวอย่าง)</div>
            <DataTable columns={r.actual?.columns ?? r.expected.columns} rows={d.unexpected_rows} maxHeight="10rem" /></div>}
        </div>
      ) : null}
      {!r.correct && r.actual && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-semibold">เปรียบเทียบผลลัพธ์ทั้งหมด (ของคุณ {r.actual.rows.length} แถว vs คาดหวัง {r.expected.row_count} แถว)</summary>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            <div><div className="mb-1 text-xs text-muted">ผลลัพธ์ของคุณ</div><DataTable columns={r.actual.columns} rows={r.actual.rows} maxHeight="14rem" /></div>
            <div><div className="mb-1 text-xs text-muted">ผลลัพธ์ที่คาดหวัง</div><DataTable columns={r.expected.columns} rows={r.expected.rows} maxHeight="14rem" /></div>
          </div>
        </details>
      )}
      <div className="mt-3 border-t border-line pt-3 text-sm">
        <div className="mb-1 text-xs font-semibold">คำอธิบาย</div>
        <Markdown>{r.explanation_md}</Markdown>
        <div className="mt-2 mb-1 flex items-center justify-between text-xs font-semibold">เฉลยตัวอย่าง (เขียนต่างได้ ขอให้ผลเหมือนกัน)
          <button className="font-normal text-brand hover:underline" onClick={() => onUse(r.solution_sql)}>ใส่ใน editor</button></div>
        <SqlBlock code={r.solution_sql} />
      </div>
    </div>
  );
}
