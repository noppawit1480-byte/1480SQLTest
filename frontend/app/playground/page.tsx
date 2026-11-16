"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { format } from "sql-formatter";
import {
  Bookmark, Bot, Database, Eraser, History, Lock, PanelLeft, Play, RotateCcw, Save, Trash2, Unlock, Wand2,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DatabaseDetail, DatabaseSummary, ExecutionResult, HistoryItem, Mode, SavedQuery } from "@/lib/types";
import { useAuth, useToast } from "@/components/providers";
import { AssistantPanel } from "@/components/AssistantPanel";
import { ResultView } from "@/components/ResultView";
import { SchemaExplorer } from "@/components/SchemaExplorer";
import { SqlEditor } from "@/components/SqlEditor";
import { Button, cx, EmptyState, ErrorState, Skeleton, Spinner } from "@/components/ui";

const DEFAULT_SQL: Record<string, string> = {
  ecommerce: "-- ลองรัน query แรกของคุณ (Ctrl/⌘ + Enter)\nSELECT id, first_name, last_name, city\nFROM customers\nORDER BY id\nLIMIT 10;",
  hr: "SELECT e.first_name, e.last_name, d.name AS department\nFROM employees e\nLEFT JOIN departments d ON d.id = e.department_id\nLIMIT 10;",
  banking: "SELECT account_type, status, COUNT(*) AS accounts, SUM(balance) AS total_balance\nFROM accounts\nGROUP BY account_type, status\nORDER BY account_type;",
  hospital: "SELECT d.specialty, COUNT(*) AS appointments\nFROM appointments a\nJOIN doctors d ON d.id = a.doctor_id\nGROUP BY d.specialty\nORDER BY appointments DESC;",
  music_store: "SELECT t.genre, COUNT(*) AS tracks, ROUND(AVG(t.milliseconds) / 60000.0, 2) AS avg_minutes\nFROM tracks t\nGROUP BY t.genre\nORDER BY tracks DESC;",
};

type Panel = "results" | "history" | "saved" | "assistant";

function Playground() {
  const params = useSearchParams();
  const { user } = useAuth();
  const toast = useToast();
  const [dbKey, setDbKey] = useState(params.get("db") ?? "ecommerce");
  const [mode, setMode] = useState<Mode>(params.get("mode") === "writable" ? "writable" : "readonly");
  const [sql, setSql] = useState<string>(params.get("sql") ?? "");
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [running, setRunning] = useState(false);
  const [panel, setPanel] = useState<Panel>("results");
  const [showExplorer, setShowExplorer] = useState(true);

  const effectiveMode: Mode = mode === "writable" && user ? "writable" : "readonly";
  const dbs = useApi<DatabaseSummary[]>("/databases");
  const detail = useApi<DatabaseDetail>(`/databases/${dbKey}?mode=${effectiveMode}`);

  // restore draft per database (unless a query came from a lesson link)
  useEffect(() => {
    if (params.get("sql")) return;
    const saved = typeof window !== "undefined" ? localStorage.getItem(`pg:${dbKey}`) : null;
    setSql(saved ?? DEFAULT_SQL[dbKey] ?? "SELECT 1;");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dbKey]);
  useEffect(() => {
    const id = window.setTimeout(() => localStorage.setItem(`pg:${dbKey}`, sql), 400);
    return () => window.clearTimeout(id);
  }, [sql, dbKey]);

  const run = useCallback(async (text?: string) => {
    const q = text ?? sql;
    setRunning(true);
    setPanel("results");
    try {
      const r = await api.post<ExecutionResult>("/playground/execute", { db_key: dbKey, mode: effectiveMode, sql: q });
      setResult(r);
      toast.awards(r.new_achievements);
      if (effectiveMode === "writable" && r.ok) detail.reload();
    } catch (e) {
      const err = e as ApiError;
      setResult({ ok: false, result_sets: [], exec_ms: 0, statements: 0, notices: [],
        error: { message: err.message, sqlstate: null, detail: null, hint: null, line: null, column: null, statement_index: null, kind: "internal" } });
    } finally {
      setRunning(false);
    }
  }, [sql, dbKey, effectiveMode, toast, detail]);

  async function preview(table: string) {
    setRunning(true);
    setPanel("results");
    try {
      setResult(await api.get<ExecutionResult>(`/databases/${dbKey}/tables/${table}/preview?mode=${effectiveMode}`));
    } catch (e) {
      toast.push("err", (e as ApiError).message);
    } finally {
      setRunning(false);
    }
  }

  function doFormat() {
    try {
      setSql(format(sql, { language: "postgresql", keywordCase: "upper", tabWidth: 2 }));
    } catch {
      toast.push("err", "จัดรูปแบบไม่ได้ — ตรวจสอบ syntax ก่อน");
    }
  }

  async function resetDb() {
    if (!confirm(`รีเซ็ตฐานข้อมูล ${dbKey} (Writable sandbox ของคุณ) กลับเป็นค่าเริ่มต้น? การเปลี่ยนแปลงทั้งหมดจะหายไป`)) return;
    try {
      const r = await api.post<{ message: string }>("/playground/reset", { db_key: dbKey });
      toast.push("ok", r.message);
      detail.reload();
      setResult(null);
    } catch (e) {
      toast.push("err", (e as ApiError).message);
    }
  }

  async function saveQuery() {
    const title = prompt("ตั้งชื่อ query นี้", sql.split("\n").find((l) => l.trim() && !l.startsWith("--"))?.slice(0, 60) ?? "My query");
    if (!title) return;
    try {
      await api.post("/saved-queries", { title, db_key: dbKey, sql });
      toast.push("ok", "บันทึก query แล้ว");
      setPanel("saved");
    } catch (e) {
      toast.push("err", (e as ApiError).message);
    }
  }

  const errorMarker = useMemo(() => result?.error?.line
    ? { line: result.error.line, column: result.error.column ?? 1, message: result.error.message } : null, [result]);

  return (
    <div className="flex h-full min-h-0">
      {/* Pane 1: Database Explorer */}
      <aside className={cx("w-64 shrink-0 flex-col border-r border-line bg-surface", showExplorer ? "hidden lg:flex" : "hidden")}>
        <div className="space-y-2 border-b border-line p-3">
          <label className="text-[11px] font-semibold uppercase tracking-wide text-muted" htmlFor="db-select">Database</label>
          <select id="db-select" value={dbKey} onChange={(e) => { setDbKey(e.target.value); setResult(null); }}
            className="w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm" data-testid="db-select">
            {(dbs.data ?? [{ key: dbKey, name: dbKey }]).map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}
          </select>
          <div className="flex items-center justify-between text-xs">
            <Link href={`/databases/${dbKey}`} className="text-brand hover:underline">ER Diagram & คำอธิบาย →</Link>
            <span className="text-muted">PostgreSQL 16</span>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-2">
          {detail.loading && !detail.data ? <div className="space-y-2 p-1">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-5" />)}</div>
            : detail.error ? <ErrorState message={detail.error.message} onRetry={detail.reload} />
            : <SchemaExplorer tables={detail.data?.tables ?? []} onPreview={preview} onInsert={(t) => setSql((s) => s + (s.endsWith(" ") || s.endsWith("\n") ? "" : " ") + t)} />}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-surface px-2 py-1.5">
          <button onClick={() => setShowExplorer((v) => !v)} className="hidden rounded p-1.5 text-muted hover:bg-surface-2 lg:block" aria-label="แสดง/ซ่อน Database Explorer">
            <PanelLeft className="size-4" />
          </button>
          <select value={dbKey} onChange={(e) => { setDbKey(e.target.value); setResult(null); }} aria-label="เลือกฐานข้อมูล"
            className="rounded-md border border-line bg-surface px-2 py-1 text-sm lg:hidden">
            {(dbs.data ?? []).map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}
          </select>
          <Button variant="primary" size="sm" onClick={() => run()} loading={running} data-testid="run-btn" title="Ctrl/⌘ + Enter">
            {!running && <Play className="size-3.5" />} Run
          </Button>
          <Button size="sm" onClick={doFormat} title="Format SQL"><Wand2 className="size-3.5" /> Format</Button>
          <Button size="sm" onClick={() => { setSql(""); setResult(null); }} title="ล้าง editor"><Eraser className="size-3.5" /> Clear</Button>
          {user && <Button size="sm" onClick={saveQuery}><Save className="size-3.5" /> Save</Button>}
          <div className="ml-auto flex items-center gap-1.5">
            <div className="flex overflow-hidden rounded-md border border-line text-xs" role="radiogroup" aria-label="โหมดฐานข้อมูล">
              <button role="radio" aria-checked={effectiveMode === "readonly"} onClick={() => setMode("readonly")}
                className={cx("flex items-center gap-1 px-2 py-1", effectiveMode === "readonly" ? "bg-brand-soft text-brand" : "text-muted hover:bg-surface-2")}>
                <Lock className="size-3" /> Read-only
              </button>
              <button role="radio" aria-checked={effectiveMode === "writable"} data-testid="mode-writable"
                onClick={() => user ? setMode("writable") : toast.push("err", "เข้าสู่ระบบเพื่อใช้ Writable sandbox ส่วนตัว")}
                className={cx("flex items-center gap-1 border-l border-line px-2 py-1", effectiveMode === "writable" ? "bg-warn-soft text-warn" : "text-muted hover:bg-surface-2")}
                title={user ? "ฐานข้อมูลส่วนตัว แก้ไขได้ (INSERT/UPDATE/DDL)" : "ต้องเข้าสู่ระบบ"}>
                <Unlock className="size-3" /> Writable
              </button>
            </div>
            {effectiveMode === "writable" && (
              <Button size="sm" variant="ghost" onClick={resetDb} title="รีเซ็ตฐานข้อมูลส่วนตัว" data-testid="reset-btn"><RotateCcw className="size-3.5" /> Reset</Button>
            )}
          </div>
        </div>

        {/* Pane 2: Editor */}
        <div className="min-h-[180px] flex-[1.1] border-b border-line">
          <SqlEditor value={sql} onChange={setSql} onRun={() => run()} schema={detail.data?.tables} errorMarker={errorMarker} />
        </div>

        {/* Pane 3: Results / History / Saved */}
        <div className="flex min-h-0 flex-1 flex-col bg-surface">
          <div className="flex items-center gap-1 border-b border-line px-2 pt-1 text-xs" role="tablist">
            {([["results", "ผลลัพธ์", Database], ["assistant", "Assistant", Bot], ["history", "History", History], ["saved", "Saved", Bookmark]] as const).map(([k, label, Icon]) => (
              <button key={k} role="tab" aria-selected={panel === k} onClick={() => setPanel(k)}
                className={cx("flex items-center gap-1 border-b-2 px-2.5 py-1.5", panel === k ? "border-brand font-medium text-fg" : "border-transparent text-muted hover:text-fg")}>
                <Icon className="size-3.5" /> {label}
              </button>
            ))}
            <span className={cx("ml-auto rounded px-1.5 py-0.5 text-[10px]", effectiveMode === "writable" ? "bg-warn-soft text-warn" : "bg-surface-2 text-muted")}>
              {effectiveMode === "writable" ? `Writable sandbox: u_${user?.id}_${dbKey}` : `Read-only: ${dbKey}`}
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-auto scrollbar-thin p-3">
            {panel === "results" && <ResultView result={result} running={running} />}
            {panel === "assistant" && <AssistantPanel sql={sql} dbKey={dbKey} lastError={result?.error ?? null} onUseSql={(s) => setSql(s)} />}
            {panel === "history" && <HistoryPanel onPick={(h) => { setDbKey(h.db_key); setSql(h.sql); setPanel("results"); }} />}
            {panel === "saved" && <SavedPanel onPick={(q) => { setDbKey(q.db_key); setSql(q.sql); setPanel("results"); }} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function LoginNeeded({ what }: { what: string }) {
  return <EmptyState title={`เข้าสู่ระบบเพื่อดู${what}`} description="ระบบจะบันทึกทุก query ที่คุณรันโดยอัตโนมัติ"
    action={<Link className="text-sm text-brand underline" href="/login?next=/playground">เข้าสู่ระบบ</Link>} />;
}

function HistoryPanel({ onPick }: { onPick: (h: HistoryItem) => void }) {
  const { user } = useAuth();
  const h = useApi<HistoryItem[]>(user ? "/playground/history" : null);
  if (!user) return <LoginNeeded what=" Query History" />;
  if (h.loading) return <Spinner />;
  if (h.error) return <ErrorState message={h.error.message} onRetry={h.reload} />;
  if (!h.data?.length) return <EmptyState title="ยังไม่มีประวัติ" description="query ที่คุณรันจะแสดงที่นี่" />;
  return (
    <div>
      <div className="mb-2 flex justify-end">
        <Button size="sm" variant="ghost" onClick={async () => { if (confirm("ล้างประวัติทั้งหมด?")) { await api.del("/playground/history"); h.reload(); } }}>
          <Trash2 className="size-3.5" /> ล้างประวัติ
        </Button>
      </div>
      <ul className="divide-y divide-line rounded-md border border-line">
        {h.data.map((it) => (
          <li key={it.id}>
            <button onClick={() => onPick(it)} className="flex w-full items-start gap-3 px-3 py-2 text-left hover:bg-surface-2">
              <span className={cx("mt-1 size-2 shrink-0 rounded-full", it.success ? "bg-ok" : "bg-bad")} aria-label={it.success ? "สำเร็จ" : "ล้มเหลว"} />
              <code className="line-clamp-2 flex-1 whitespace-pre-wrap font-mono text-xs">{it.sql}</code>
              <span className="shrink-0 text-right text-[11px] text-muted">{it.db_key}{it.mode === "writable" && " ✎"}<br />
                {new Date(it.created_at).toLocaleString("th-TH")}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SavedPanel({ onPick }: { onPick: (q: SavedQuery) => void }) {
  const { user } = useAuth();
  const s = useApi<SavedQuery[]>(user ? "/saved-queries" : null);
  if (!user) return <LoginNeeded what=" Saved Queries" />;
  if (s.loading) return <Spinner />;
  if (s.error) return <ErrorState message={s.error.message} onRetry={s.reload} />;
  if (!s.data?.length) return <EmptyState title="ยังไม่มี query ที่บันทึกไว้" description="กดปุ่ม Save บนแถบเครื่องมือเพื่อบันทึก query" />;
  return (
    <ul className="divide-y divide-line rounded-md border border-line">
      {s.data.map((q) => (
        <li key={q.id} className="flex items-start gap-2 px-3 py-2 hover:bg-surface-2">
          <button onClick={() => onPick(q)} className="min-w-0 flex-1 text-left">
            <div className="text-sm font-medium">{q.title} <span className="text-[11px] font-normal text-muted">· {q.db_key}</span></div>
            <code className="line-clamp-1 font-mono text-xs text-muted">{q.sql}</code>
          </button>
          <button onClick={async () => { await api.del(`/saved-queries/${q.id}`); s.reload(); }} className="rounded p-1 text-muted hover:text-bad" aria-label={`ลบ ${q.title}`}>
            <Trash2 className="size-3.5" />
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function PlaygroundPage() {
  return <Suspense fallback={<Spinner />}><Playground /></Suspense>;
}
