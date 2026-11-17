"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Dice5, Mic, Timer } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { ChallengeSessionView } from "@/lib/types";
import { useAuth, useToast } from "@/components/providers";
import { Badge, Button, Card, cx, EmptyState, PageHeader, Spinner } from "@/components/ui";

type Kind = "timed" | "random" | "interview";
const MODES: { kind: Kind; title: string; icon: typeof Timer; desc: string; count: [number, number, number]; minutes: [number, number, number] }[] = [
  { kind: "timed", title: "Timed Challenge", icon: Timer, desc: "ทำหลายข้อแข่งกับเวลา ยิ่งเสร็จเร็วยิ่งได้คะแนนเพิ่ม (สูงสุด ×1.5)", count: [3, 10, 5], minutes: [5, 60, 20] },
  { kind: "random", title: "Random Challenge", icon: Dice5, desc: "สุ่มโจทย์ 1 ข้อตามระดับที่เลือก — เหมาะกับการฝึกประจำวัน", count: [1, 1, 1], minutes: [5, 30, 15] },
  { kind: "interview", title: "Mock Interview", icon: Mic, desc: "โจทย์สไตล์สัมภาษณ์งาน Data/Backend พร้อมอธิบายแนวคิด และรายงานผลตาม rubric", count: [2, 5, 3], minutes: [15, 90, 45] },
];
interface HistoryRow { id: number; kind: Kind; status: string; score: number; started_at: string; remaining_seconds: number; solved: number; total: number }
const STATUS: Record<string, string> = { active: "กำลังทำ", finished: "จบแล้ว", expired: "หมดเวลา" };

export default function ChallengesPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [kind, setKind] = useState<Kind>("timed");
  const mode = MODES.find((m) => m.kind === kind)!;
  const [count, setCount] = useState(5);
  const [minutes, setMinutes] = useState(20);
  const [difficulty, setDifficulty] = useState("");
  const [busy, setBusy] = useState(false);
  const hist = useApi<HistoryRow[]>(user ? "/challenges" : null);

  function pick(k: Kind) {
    const m = MODES.find((x) => x.kind === k)!;
    setKind(k); setCount(m.count[2]); setMinutes(m.minutes[2]);
  }
  async function start() {
    setBusy(true);
    try {
      const s = await api.post<ChallengeSessionView>("/challenges", { kind, count, minutes, difficulty: kind === "interview" ? null : difficulty || null });
      router.push(`/challenges/${s.id}`);
    } catch (e) { toast.push("err", (e as ApiError).message); setBusy(false); }
  }

  if (!ready) return <Spinner />;
  return (
    <>
      <PageHeader title="Challenges & Mock Interview" description="ฝึกทำโจทย์ภายใต้เวลาจำกัด — เวลาและคะแนนตรวจสอบที่เซิร์ฟเวอร์ ส่งคำตอบหลังหมดเวลาจะไม่ถูกนับ"
        actions={<Link href="/leaderboard" className="text-sm text-brand underline">Leaderboard</Link>} />
      {!user ? (
        <EmptyState title="เข้าสู่ระบบเพื่อเริ่ม challenge" description="คะแนนและประวัติจะถูกบันทึกในบัญชีของคุณ" action={<Link href="/login?next=/challenges" className="text-brand underline">เข้าสู่ระบบ</Link>} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              {MODES.map((m) => (
                <button key={m.kind} onClick={() => pick(m.kind)} data-testid={`mode-${m.kind}`}
                  className={cx("rounded-lg border p-4 text-left transition", kind === m.kind ? "border-brand bg-brand-soft/40" : "border-line hover:bg-surface-2")}>
                  <m.icon className="mb-2 size-5 text-brand" /><div className="font-semibold">{m.title}</div><p className="mt-1 text-xs text-muted">{m.desc}</p>
                </button>
              ))}
            </div>
            <Card title={`ตั้งค่า: ${mode.title}`}>
              <div className="flex flex-wrap items-end gap-4 text-sm">
                {mode.count[0] !== mode.count[1] && (
                  <label className="flex flex-col gap-1">จำนวนข้อ ({mode.count[0]}–{mode.count[1]})
                    <input type="number" min={mode.count[0]} max={mode.count[1]} value={count} onChange={(e) => setCount(Number(e.target.value))} className="w-24 rounded-md border border-line bg-surface px-2 py-1" /></label>)}
                <label className="flex flex-col gap-1">เวลา (นาที, {mode.minutes[0]}–{mode.minutes[1]})
                  <input type="number" min={mode.minutes[0]} max={mode.minutes[1]} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} className="w-24 rounded-md border border-line bg-surface px-2 py-1" /></label>
                {kind !== "interview" && (
                  <label className="flex flex-col gap-1">ระดับ
                    <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1">
                      <option value="">ทุกระดับ</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option><option value="expert">Expert</option></select></label>)}
                <Button variant="primary" onClick={start} loading={busy} data-testid="start-challenge">เริ่มเลย</Button>
              </div>
              <p className="mt-3 text-xs text-muted">คะแนนต่อข้อ = คะแนนโจทย์ × (1 + 0.5 × สัดส่วนเวลาที่เหลือ) × 0.9<sup>จำนวน hint</sup> × (ลด 10% ต่อการส่งผิด, ต่ำสุด 50%) · เปิดได้พร้อมกันไม่เกิน 3 รายการ
                {kind === "interview" ? " · Mock Interview ใช้ชุดโจทย์สัมภาษณ์แยกจากแบบฝึกหัดทั่วไป" : " · ใช้เฉพาะโจทย์ประเภท SELECT"}</p>
            </Card>
          </div>
          <Card title="ประวัติของฉัน">
            {hist.loading ? <Spinner /> : !hist.data?.length ? <p className="text-sm text-muted">ยังไม่มีประวัติ</p> : (
              <ul className="divide-y divide-line text-sm" data-testid="challenge-history">
                {hist.data.map((h) => (
                  <li key={h.id}><Link href={`/challenges/${h.id}`} className="flex items-center justify-between gap-2 py-2 hover:text-brand">
                    <span><span className="font-medium">{MODES.find((m) => m.kind === h.kind)?.title}</span>
                      <span className="block text-xs text-muted">{new Date(h.started_at).toLocaleString("th-TH")} · ถูก {h.solved}/{h.total}</span></span>
                    <span className="text-right"><Badge className={h.status === "active" ? "!text-brand" : ""}>{STATUS[h.status]}</Badge>
                      <span className="block text-xs font-semibold">{h.score} pts</span></span>
                  </Link></li>))}
              </ul>)}
          </Card>
        </div>
      )}
    </>
  );
}
