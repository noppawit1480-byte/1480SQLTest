"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock, Flag, Lightbulb, Play, Send, Trophy, XCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { ChallengeSessionView, DatabaseDetail, ExecutionResult } from "@/lib/types";
import { useToast } from "@/components/providers";
import { Markdown, SqlBlock } from "@/components/Markdown";
import { DataTable, ResultView } from "@/components/ResultView";
import { SqlEditor } from "@/components/SqlEditor";
import { Badge, Button, Card, cx, DifficultyBadge, ErrorState, ProgressBar, Spinner } from "@/components/ui";

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const KIND: Record<string, string> = { timed: "Timed Challenge", random: "Random Challenge", interview: "Mock Interview" };

function Report({ s }: { s: ChallengeSessionView }) {
  const r = s.report!;
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4" data-testid="challenge-report">
      <Card title={<span className="flex items-center gap-2"><Trophy className="size-5 text-warn" /> สรุปผล {KIND[s.kind]} · {s.status === "expired" ? "หมดเวลา" : "จบแล้ว"}</span>}>
        <div className="grid gap-3 sm:grid-cols-3 text-center">
          <div><div className="text-3xl font-bold">{r.score}</div><div className="text-xs text-muted">คะแนน (สูงสุด {r.max_score})</div></div>
          <div><div className="text-3xl font-bold">{r.solved}/{r.total}</div><div className="text-xs text-muted">ตอบถูก</div></div>
          <div><div className="text-3xl font-bold">{fmt(r.seconds_used)}</div><div className="text-xs text-muted">เวลาที่ใช้</div></div>
        </div>
      </Card>
      {r.rubric && (
        <Card title={<span>Interview Rubric · <span className={r.rubric.passed ? "text-ok" : "text-bad"} data-testid="rubric-overall">{r.rubric.overall}/100 {r.rubric.passed ? "ผ่าน" : "ยังไม่ผ่าน (เกณฑ์ 70)"}</span></span>}>
          <ul className="space-y-3">{r.rubric.criteria.map((c) => (
            <li key={c.name}><div className="flex justify-between text-sm"><span className="font-medium">{c.name} <span className="text-xs text-muted">(น้ำหนัก {c.weight}%)</span></span><span>{c.score}/100</span></div>
              <ProgressBar value={c.score} className="mt-1" /><p className="mt-0.5 text-xs text-muted">{c.note}</p></li>))}</ul>
          <p className="mt-3 text-xs text-muted">Rubric นี้คำนวณจากข้อมูลที่วัดได้ (ความถูกต้อง จำนวนครั้งที่ส่ง hint เวลา และความยาวคำอธิบาย) — ไม่ได้ประเมินคุณภาพเนื้อหาคำอธิบายด้วย AI</p>
        </Card>)}
      <Card title="รายข้อ">
        <table className="w-full text-sm"><thead className="text-left text-xs text-muted"><tr><th>ข้อ</th><th>ผล</th><th>ส่ง</th><th>hint</th><th>เวลา</th><th className="text-right">คะแนน</th></tr></thead>
          <tbody>{r.items.map((i) => (
            <tr key={i.position} className="border-t border-line align-top">
              <td className="py-1.5"><Link className="hover:underline" href={`/practice/${i.code}`}>{i.code} · {i.title}</Link>
                {i.approach_text && <p className="mt-1 whitespace-pre-wrap text-xs text-muted">“{i.approach_text}”</p>}</td>
              <td>{i.solved ? <CheckCircle2 className="size-4 text-ok" /> : <XCircle className="size-4 text-bad" />}</td>
              <td>{i.attempts}</td><td>{i.hints_used}</td><td>{i.seconds_to_solve != null ? fmt(i.seconds_to_solve) : "–"}</td><td className="text-right font-semibold">{i.points}</td>
            </tr>))}</tbody></table>
        <p className="mt-2 text-xs text-muted">เฉลยของแต่ละข้อเปิดดูได้ในหน้าโจทย์ (กดชื่อข้อ) หลังจบ challenge</p>
      </Card>
      <div className="flex gap-2"><Link href="/challenges" className="text-sm text-brand underline">เริ่ม challenge ใหม่</Link><Link href="/leaderboard" className="text-sm text-brand underline">ดู Leaderboard</Link></div>
    </div>
  );
}

export default function ChallengeRunner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const toast = useToast();
  const sess = useApi<ChallengeSessionView>(`/challenges/${id}`);
  const s = sess.data;
  const [pos, setPos] = useState(0);
  const [sqls, setSqls] = useState<Record<number, string>>({});
  const [approach, setApproach] = useState<Record<number, string>>({});
  const [left, setLeft] = useState(0);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [verdict, setVerdict] = useState<{ correct: boolean; message: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const item = s?.items[pos];
  const schema = useApi<DatabaseDetail>(item ? `/databases/${item.sample_db}` : null);

  useEffect(() => {
    if (!s) return;
    const end = Date.now() + s.remaining_seconds * 1000;
    setLeft(s.remaining_seconds);
    if (s.status !== "active") return;
    const t = window.setInterval(() => {
      const l = Math.max(0, Math.round((end - Date.now()) / 1000));
      setLeft(l);
      if (l === 0) { window.clearInterval(t); sess.reload(); }
    }, 1000);
    return () => window.clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s?.id, s?.status, s?.remaining_seconds]);
  useEffect(() => {
    if (!s) return;
    setSqls((m) => Object.fromEntries(s.items.map((i) => [i.position, m[i.position] ?? i.last_sql ?? `-- ${i.code}\n`])));
    setApproach((m) => Object.fromEntries(s.items.map((i) => [i.position, m[i.position] ?? i.approach_text ?? ""])));
  }, [s]);
  useEffect(() => { setResult(null); setVerdict(null); }, [pos]);

  const sql = sqls[pos] ?? "";
  const run = useCallback(async () => {
    if (!item) return;
    setBusy("run"); setVerdict(null);
    try { setResult(await api.post<ExecutionResult>(`/exercises/${item.code}/run`, { sql })); }
    catch (e) { toast.push("err", (e as ApiError).message); } finally { setBusy(null); }
  }, [item, sql, toast]);

  async function submit() {
    if (!s || !item) return;
    setBusy("submit");
    try {
      const r = await api.post<{ correct: boolean; message: string; points_awarded: number; execution: ExecutionResult; session_status: string; new_achievements: string[] }>(
        `/challenges/${s.id}/items/${pos}/submit`, { sql, approach: s.kind === "interview" ? approach[pos] ?? "" : null });
      setResult(r.execution); setVerdict({ correct: r.correct, message: r.correct ? `ถูกต้อง! +${r.points_awarded} คะแนน` : r.message });
      toast.awards(r.new_achievements);
      if (r.correct) {
        const next = s.items.findIndex((i) => !i.solved && i.position !== pos);
        await sess.reload();
        if (r.session_status === "active" && next >= 0) window.setTimeout(() => setPos(next), 900);
      } else sess.setData({ ...s, items: s.items.map((i) => (i.position === pos ? { ...i, attempts: i.attempts + 1 } : i)) });
    } catch (e) { toast.push("err", (e as ApiError).message); sess.reload(); } finally { setBusy(null); }
  }
  async function hint() {
    if (!s || !item || !confirm("ใช้ hint? คะแนนข้อนี้จะลดลง 10%")) return;
    try { await api.post(`/challenges/${s.id}/items/${pos}/hint`); sess.reload(); } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function saveApproach() {
    if (!s) return;
    try { await api.post(`/challenges/${s.id}/items/${pos}/approach`, { sql: "-", approach: approach[pos] ?? "" }); toast.push("ok", "บันทึกคำอธิบายแล้ว"); }
    catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function finish() {
    if (!s || !confirm("จบ challenge ตอนนี้? ข้อที่ยังไม่ถูกจะได้ 0 คะแนน")) return;
    if (s.kind === "interview" && approach[pos]) await saveApproach();
    try { const r = await api.post<ChallengeSessionView & { new_achievements: string[] }>(`/challenges/${s.id}/finish`); toast.awards(r.new_achievements); sess.setData(r); }
    catch (e) { toast.push("err", (e as ApiError).message); }
  }
  const errorMarker = useMemo(() => result?.error?.line ? { line: result.error.line, column: result.error.column ?? 1, message: result.error.message } : null, [result]);

  if (sess.loading && !s) return <Spinner />;
  if (sess.error || !s) return <div className="p-6"><ErrorState message={sess.error?.message ?? "ไม่พบ challenge"} onRetry={sess.reload} /></div>;
  if (s.status !== "active") return <Report s={s} />;
  const it = item!;
  const low = left <= 60;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-surface px-3 py-2">
        <span className="font-semibold">{KIND[s.kind]}</span>
        <div className="flex gap-1" role="tablist">{s.items.map((i) => (
          <button key={i.position} role="tab" aria-selected={pos === i.position} onClick={() => setPos(i.position)}
            className={cx("flex size-7 items-center justify-center rounded text-xs font-medium", pos === i.position ? "bg-brand text-brand-fg" : i.solved ? "bg-ok-soft text-ok" : "bg-surface-2")}>
            {i.solved ? "✓" : i.position + 1}</button>))}</div>
        <span className={cx("ml-auto flex items-center gap-1 font-mono text-lg tabular-nums", low && "text-bad")} data-testid="timer" aria-live="polite"><Clock className="size-4" /> {fmt(left)}</span>
        <Badge>{s.score} pts</Badge>
        <Button size="sm" variant="ghost" onClick={finish} data-testid="finish-challenge"><Flag className="size-3.5" /> จบ</Button>
      </div>
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <section className="min-h-0 overflow-y-auto scrollbar-thin border-line bg-surface p-4 lg:w-[42%] lg:border-r max-lg:max-h-[45%]">
          <div className="mb-2 flex flex-wrap items-center gap-2"><DifficultyBadge d={it.difficulty} /><Badge>{it.points} pts</Badge><Badge>DB: {it.sample_db}</Badge>
            {it.attempts > 0 && <Badge>ส่งแล้ว {it.attempts} ครั้ง</Badge>}</div>
          <h1 className="text-lg font-bold" data-testid="challenge-item-title">{it.title}</h1>
          <div className="mt-2"><Markdown>{it.description_md}</Markdown></div>
          {it.order_matters && <p className="mt-2 text-xs text-warn">⚠ ตรวจลำดับของแถวด้วย</p>}
          <h2 className="mt-4 mb-1 text-sm font-semibold">Expected Result <span className="font-normal text-muted">({it.expected.row_count} แถว, แสดง {it.expected.rows.length} แถวแรก)</span></h2>
          <DataTable columns={it.expected.columns} rows={it.expected.rows} maxHeight="12rem" />
          <div className="mt-4 space-y-2">
            {it.hints.map((h, k) => <div key={k} className="rounded-md border border-warn/30 bg-warn-soft/40 p-2 text-sm">Hint {k + 1}: {h}</div>)}
            {!it.solved && it.hints.length < it.hints_total && <Button size="sm" onClick={hint}><Lightbulb className="size-3.5" /> ขอ hint (−10%)</Button>}
          </div>
          {s.kind === "interview" && (
            <div className="mt-4">
              <label className="text-sm font-semibold" htmlFor="approach">อธิบายแนวคิดของคุณ (เหมือนพูดกับผู้สัมภาษณ์)</label>
              <textarea id="approach" value={approach[pos] ?? ""} onChange={(e) => setApproach({ ...approach, [pos]: e.target.value })} rows={5} maxLength={4000}
                placeholder="เช่น: เริ่มจาก JOIN ตาราง… ใช้ GROUP BY เพราะ… ระวัง NULL ตรง… ถ้าข้อมูลใหญ่ควรมี index ที่…"
                className="mt-1 w-full rounded-md border border-line bg-surface p-2 text-sm" data-testid="approach" />
              <div className="flex items-center justify-between text-xs text-muted"><span>{(approach[pos] ?? "").trim().length} ตัวอักษร (rubric นับเมื่อ ≥ 40)</span>
                <button className="text-brand" onClick={saveApproach}>บันทึกคำอธิบาย</button></div>
            </div>)}
          {schema.data && (
            <details className="mt-4 text-xs"><summary className="cursor-pointer font-semibold">ตารางใน {it.sample_db}</summary>
              <ul className="mt-1 space-y-0.5 font-mono">{schema.data.tables.map((t) => <li key={t.name}>{t.name}({t.columns.map((c) => c.name).join(", ")})</li>)}</ul></details>)}
        </section>
        <section className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-[200px] flex-1">
            <SqlEditor value={sql} onChange={(v) => setSqls({ ...sqls, [pos]: v })} onRun={run} schema={schema.data?.tables} errorMarker={errorMarker} readOnly={it.solved} />
          </div>
          <div className="flex items-center gap-2 border-y border-line bg-surface px-3 py-2">
            <Button size="sm" onClick={run} loading={busy === "run"} disabled={!!busy}><Play className="size-3.5" /> Run</Button>
            <Button size="sm" variant="primary" onClick={submit} loading={busy === "submit"} disabled={!!busy || it.solved} data-testid="challenge-submit"><Send className="size-3.5" /> Submit</Button>
            {verdict && <span className={cx("text-sm font-medium", verdict.correct ? "text-ok" : "text-bad")} data-testid="challenge-verdict">{verdict.message}</span>}
            {it.solved && !verdict && <span className="text-sm text-ok">ข้อนี้ถูกแล้ว (+{it.points_awarded})</span>}
          </div>
          <div className="h-[38%] min-h-[140px] overflow-auto"><ResultView result={result} running={busy !== null} emptyHint="Run เพื่อดูผลลัพธ์ หรือ Submit เพื่อตรวจคำตอบ" /></div>
        </section>
      </div>
    </div>
  );
}
