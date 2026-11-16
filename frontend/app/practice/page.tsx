"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CheckCircle2, Circle, CircleDot, PenLine } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { Difficulty, ExerciseSummary } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { Badge, cx, DifficultyBadge, EmptyState, ErrorState, PageHeader, ProgressBar, Skeleton } from "@/components/ui";

const LEVELS: { key: Difficulty | "all"; label: string }[] = [
  { key: "all", label: "ทั้งหมด" }, { key: "easy", label: "Easy" }, { key: "medium", label: "Medium" },
  { key: "hard", label: "Hard" }, { key: "expert", label: "Expert" },
];

export default function PracticePage() {
  const { user } = useAuth();
  const [level, setLevel] = useState<Difficulty | "all">("all");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useApi<{ categories: string[]; items: ExerciseSummary[] }>("/exercises");

  const items = useMemo(() => (data?.items ?? []).filter((e) =>
    (level === "all" || e.difficulty === level) && (!category || e.category === category) && (!status || e.status === status)), [data, level, category, status]);
  const solved = data?.items.filter((e) => e.status === "solved").length ?? 0;

  return (
    <>
      <PageHeader title="แบบฝึกหัด SQL" description="ตรวจคำตอบจากผลลัพธ์การรันจริงบน PostgreSQL — เขียน SQL แบบไหนก็ได้ ขอแค่ผลลัพธ์ถูกต้อง"
        actions={user && data ? (
          <div className="w-56 text-right text-sm">
            <div className="mb-1 text-muted">ทำสำเร็จ {solved}/{data.items.length}</div>
            <ProgressBar value={(100 * solved) / Math.max(1, data.items.length)} label="ความคืบหน้าแบบฝึกหัด" />
          </div>
        ) : null} />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-md border border-line" role="tablist" aria-label="ระดับความยาก">
          {LEVELS.map((l) => (
            <button key={l.key} role="tab" aria-selected={level === l.key} onClick={() => setLevel(l.key)}
              className={cx("px-3 py-1.5 text-sm", level === l.key ? "bg-brand text-brand-fg" : "bg-surface hover:bg-surface-2")}>{l.label}</button>
          ))}
        </div>
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="หมวดหมู่"
          className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm">
          <option value="">ทุกหมวด</option>
          {data?.categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {user && (
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="สถานะ"
            className="rounded-md border border-line bg-surface px-2 py-1.5 text-sm">
            <option value="">ทุกสถานะ</option><option value="new">ยังไม่ทำ</option>
            <option value="attempted">ทำแล้วยังไม่ถูก</option><option value="solved">ทำถูกแล้ว</option>
          </select>
        )}
      </div>

      {loading ? <div className="space-y-2">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
        : error ? <ErrorState message={error.message} onRetry={reload} />
        : !items.length ? <EmptyState title="ไม่พบโจทย์ตามตัวกรอง" description="ลองเปลี่ยนระดับหรือหมวดหมู่" />
        : (
          <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface" data-testid="exercise-list">
            {items.map((e) => (
              <li key={e.code}>
                <Link href={`/practice/${e.code}`} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2">
                  {e.status === "solved" ? <CheckCircle2 className="size-5 shrink-0 text-ok" aria-label="ทำถูกแล้ว" />
                    : e.status === "attempted" ? <CircleDot className="size-5 shrink-0 text-warn" aria-label="ทำแล้วยังไม่ถูก" />
                    : <Circle className="size-5 shrink-0 text-line" aria-label="ยังไม่ทำ" />}
                  <span className="w-16 shrink-0 font-mono text-xs text-muted">{e.code}</span>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{e.title}</span>
                  <span className="hidden gap-1.5 sm:flex">
                    {e.check_type === "dml" && <Badge><PenLine className="size-3" /> DML/DDL</Badge>}
                    <Badge>{e.category}</Badge><Badge>{e.sample_db}</Badge>
                  </span>
                  <DifficultyBadge d={e.difficulty} />
                  <span className="w-12 text-right text-xs tabular-nums text-muted">{e.points} pts</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
