"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, Gauge, Info, Lightbulb, MessageSquare, Send, ShieldAlert, Sparkles, Wrench, Zap } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { AssistantAnswer, AssistantFinding, AssistantStatus, ExecError } from "@/lib/types";
import { Markdown, SqlBlock } from "./Markdown";
import { useAuth } from "./providers";
import { Button, cx, EmptyState, Spinner } from "./ui";

type Mode = "explain" | "review" | "optimize" | "explain_error" | "fix";

const SEVERITY: Record<AssistantFinding["severity"], { label: string; cls: string; icon: typeof Info }> = {
  danger: { label: "ร้ายแรง", cls: "border-bad/40 bg-bad-soft/30", icon: ShieldAlert },
  warning: { label: "ควรแก้", cls: "border-warn/40 bg-warn-soft/30", icon: AlertTriangle },
  perf: { label: "ประสิทธิภาพ", cls: "border-brand/40 bg-brand-soft/30", icon: Gauge },
  info: { label: "แนะนำ", cls: "border-line bg-surface-2", icon: Info },
};

export function AnswerView({ a, onUseSql }: { a: AssistantAnswer; onUseSql?: (sql: string) => void }) {
  return (
    <div className="space-y-3 text-sm" data-testid="assistant-answer">
      <div className="flex items-start gap-2 rounded-md bg-surface-2 px-3 py-2">
        <Bot className="mt-0.5 size-4 shrink-0 text-brand" />
        <span>{a.summary}</span>
      </div>
      {a.findings.length > 0 && (
        <ul className="space-y-2" data-testid="assistant-findings">
          {a.findings.map((f) => {
            const s = SEVERITY[f.severity];
            return (
              <li key={f.code} className={cx("rounded-md border p-3", s.cls)}>
                <div className="flex items-center gap-1.5 font-semibold"><s.icon className="size-4" /> {f.title}
                  <span className="ml-auto text-[10px] font-normal uppercase text-muted">{s.label}</span></div>
                <div className="mt-1"><Markdown>{f.body_md}</Markdown></div>
                {f.suggestion_sql && (
                  <div className="mt-1">
                    <SqlBlock code={f.suggestion_sql} />
                    {onUseSql && <button className="mt-1 text-xs text-brand hover:underline" onClick={() => onUseSql(f.suggestion_sql!)}>คัดลอกไปที่ editor</button>}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {a.sections.map((s, i) => (
        <section key={i} className="rounded-md border border-line p-3">
          <h4 className="mb-1 font-semibold">{s.title}</h4>
          <Markdown>{s.body_md}</Markdown>
          {s.sql && <SqlBlock code={s.sql} className="mt-2" />}
        </section>
      ))}
      {a.plan && (
        <section className="rounded-md border border-line p-3">
          <h4 className="mb-1 font-semibold">Execution plan (EXPLAIN)</h4>
          <div className="overflow-x-auto font-mono text-xs">
            {a.plan.map((p, i) => (
              <div key={i} style={{ paddingLeft: p.depth * 16 }} className="whitespace-nowrap py-0.5">
                <span className="text-brand">→ {p.node}</span>{p.relation && <> on <b>{p.relation}</b></>}{p.index && <> using {p.index}</>}
                <span className="text-muted"> (rows={p.rows}, cost={p.cost})</span>
                {p.filter && <span className="text-muted"> · {p.filter}</span>}
              </div>
            ))}
          </div>
        </section>
      )}
      {a.ai_md && (
        <section className="rounded-md border border-brand/40 p-3" data-testid="assistant-ai">
          <h4 className="mb-1 flex items-center gap-1.5 font-semibold text-brand"><Sparkles className="size-4" /> คำอธิบายเพิ่มเติมจาก AI</h4>
          <Markdown>{a.ai_md}</Markdown>
          <p className="mt-2 text-[11px] text-muted">AI อาจผิดพลาดได้ — ผลตรวจคำตอบมาจากการรันบนฐานข้อมูลจริงเสมอ</p>
        </section>
      )}
    </div>
  );
}

export function TutorChat({ dbKey, exerciseCode, compact }: { dbKey?: string; exerciseCode?: string; compact?: boolean }) {
  const { user } = useAuth();
  const status = useApi<AssistantStatus>("/assistant/status");
  const [msgs, setMsgs] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [msgs]);

  if (!user) return <EmptyState title="เข้าสู่ระบบเพื่อคุยกับ SQL Tutor" action={<Link className="text-sm text-brand underline" href="/login?next=/assistant">เข้าสู่ระบบ</Link>} />;
  if (status.loading) return <Spinner />;
  if (!status.data?.ai_available) {
    return <EmptyState icon={<MessageSquare className="size-8" />} title="SQL Tutor (AI) ยังไม่เปิดใช้งานบนเซิร์ฟเวอร์นี้"
      description="ผู้ดูแลระบบต้องตั้งค่า AI provider ก่อน — ระหว่างนี้ใช้ Explain / Review / Optimize / Fix แบบวิเคราะห์อัตโนมัติได้เต็มที่" />;
  }
  async function send() {
    const q = text.trim();
    if (!q) return;
    const next = [...msgs, { role: "user" as const, content: q }];
    setMsgs(next); setText(""); setBusy(true); setErr(null);
    try {
      const r = await api.post<{ reply_md: string }>("/assistant/tutor", { messages: next, db_key: dbKey, exercise_code: exerciseCode });
      setMsgs([...next, { role: "assistant", content: r.reply_md }]);
    } catch (e) {
      setErr((e as ApiError).message);
      setMsgs(msgs);
      setText(q);
    } finally { setBusy(false); }
  }
  return (
    <div className={cx("flex flex-col", compact ? "h-full" : "h-[32rem]")}>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto scrollbar-thin p-1">
        {msgs.length === 0 && (
          <div className="text-sm text-muted">
            ถามอะไรก็ได้เกี่ยวกับ SQL{dbKey ? ` และฐานข้อมูล ${dbKey}` : ""} เช่น <i>“ทำไม COUNT(*) กับ COUNT(col) ได้ไม่เท่ากัน”</i>
            {exerciseCode && <p className="mt-1 text-warn">โหมดแบบฝึกหัด: Tutor จะให้คำใบ้ ไม่เฉลยคำตอบ</p>}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={cx("rounded-lg px-3 py-2 text-sm", m.role === "user" ? "ml-8 bg-brand-soft/60" : "mr-4 border border-line bg-surface")}>
            {m.role === "assistant" ? <Markdown>{m.content}</Markdown> : <p className="whitespace-pre-wrap">{m.content}</p>}
          </div>
        ))}
        {busy && <Spinner label="Tutor กำลังคิด..." />}
        <div ref={end} />
      </div>
      {err && <p className="mb-1 text-xs text-bad" role="alert">{err}</p>}
      <form className="flex gap-2 border-t border-line pt-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={4000} aria-label="ข้อความถึง Tutor"
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="พิมพ์คำถาม (Enter เพื่อส่ง, Shift+Enter ขึ้นบรรทัด)" className="flex-1 resize-none rounded-md border border-line bg-bg p-2 text-sm" />
        <Button type="submit" variant="primary" loading={busy} aria-label="ส่ง"><Send className="size-4" /></Button>
      </form>
    </div>
  );
}

/** Assistant panel used next to an editor (Playground, exercises). */
export function AssistantPanel({ sql, dbKey, lastError, exerciseCode, onUseSql }: {
  sql: string; dbKey: string; lastError?: ExecError | null; exerciseCode?: string; onUseSql?: (sql: string) => void;
}) {
  const { user } = useAuth();
  const status = useApi<AssistantStatus>("/assistant/status");
  const [tab, setTab] = useState<"analyze" | "chat">("analyze");
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [busy, setBusy] = useState<Mode | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [useAi, setUseAi] = useState(false);
  const aiReady = !!status.data?.ai_available && !!user;

  async function run(mode: Mode) {
    if (!sql.split("\n").some((l) => l.trim() && !l.trim().startsWith("--"))) { setErr("พิมพ์ SQL ใน editor ก่อน"); return; }
    setBusy(mode); setErr(null);
    try {
      const error = mode === "explain_error" || mode === "fix" ? lastError ?? null : null;
      setAnswer(await api.post<AssistantAnswer>("/assistant/analyze",
        { mode, sql, db_key: dbKey, error, exercise_code: exerciseCode, use_ai: useAi && aiReady }));
    } catch (e) { setErr((e as ApiError).message); }
    finally { setBusy(null); }
  }

  const buttons: { mode: Mode; label: string; icon: typeof Info; hint: string }[] = [
    { mode: "explain", label: "Explain", icon: Lightbulb, hint: "อธิบาย SQL ทีละส่วนตามลำดับการทำงานจริง" },
    { mode: "explain_error", label: "Explain Error", icon: AlertTriangle, hint: "อธิบายสาเหตุของ error ล่าสุด" },
    { mode: "fix", label: exerciseCode ? "ช่วยหาจุดผิด" : "Fix", icon: Wrench, hint: "แนวทางแก้ไข" },
    { mode: "review", label: "Review", icon: ShieldAlert, hint: "ตรวจคุณภาพและกับดักที่พบบ่อย" },
    { mode: "optimize", label: "Optimize", icon: Zap, hint: "วิเคราะห์ execution plan" },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="assistant-panel">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <div className="flex overflow-hidden rounded-md border border-line text-xs" role="tablist">
          <button role="tab" aria-selected={tab === "analyze"} onClick={() => setTab("analyze")}
            className={cx("px-2 py-1", tab === "analyze" ? "bg-brand-soft text-brand" : "text-muted")}>วิเคราะห์ SQL</button>
          <button role="tab" aria-selected={tab === "chat"} onClick={() => setTab("chat")}
            className={cx("border-l border-line px-2 py-1", tab === "chat" ? "bg-brand-soft text-brand" : "text-muted")}>ถาม Tutor</button>
        </div>
        {tab === "analyze" && buttons.map((b) => (
          <Button key={b.mode} size="sm" onClick={() => run(b.mode)} loading={busy === b.mode} title={b.hint}
            disabled={b.mode === "explain_error" && !lastError} data-testid={`assist-${b.mode}`}>
            {busy !== b.mode && <b.icon className="size-3.5" />} {b.label}
          </Button>
        ))}
        {tab === "analyze" && (
          <label className={cx("ml-auto flex items-center gap-1 text-xs", aiReady ? "" : "text-muted")}
            title={aiReady ? "เพิ่มคำอธิบายจาก AI" : status.data?.ai_available ? "เข้าสู่ระบบเพื่อใช้ AI" : "เซิร์ฟเวอร์นี้ยังไม่ได้ตั้งค่า AI"}>
            <input type="checkbox" checked={useAi && aiReady} disabled={!aiReady} onChange={(e) => setUseAi(e.target.checked)} />
            <Sparkles className="size-3.5" /> AI เสริม
          </label>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        {tab === "chat" ? <TutorChat dbKey={dbKey} exerciseCode={exerciseCode} compact />
          : err ? <p className="text-sm text-bad" role="alert">{err}</p>
          : busy ? <Spinner label="กำลังวิเคราะห์..." />
          : answer ? <AnswerView a={answer} onUseSql={onUseSql} />
          : <EmptyState icon={<Bot className="size-8" />} title="SQL Learning Assistant"
              description={`เลือกโหมดด้านบนเพื่อวิเคราะห์ SQL ใน editor${exerciseCode ? " — ในแบบฝึกหัด ผู้ช่วยจะชี้แนวทาง ไม่เฉลยคำตอบ" : ""}`} />}
      </div>
    </div>
  );
}
