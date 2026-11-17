"use client";

import Link from "next/link";
import { useState } from "react";
import { Medal } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { useAuth, useToast } from "@/components/providers";
import { Card, cx, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";

interface Entry { rank: number; user_id: number; display_name: string; score: number; count: number }
interface Board { board: string; period: string; entries: Entry[]; me: Entry | null; me_hidden: boolean }

export default function LeaderboardPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [board, setBoard] = useState<"points" | "challenges">("points");
  const [period, setPeriod] = useState<"week" | "all">("all");
  const lb = useApi<Board>(`/leaderboard?board=${board}&period=${period}`);
  const [hidden, setHidden] = useState<boolean | null>(null);
  const meHidden = hidden ?? lb.data?.me_hidden ?? false;
  const seg = (on: boolean) => cx("rounded px-3 py-1 text-sm", on ? "bg-brand text-brand-fg" : "text-muted hover:bg-surface-2");

  async function toggle(show: boolean) {
    setHidden(!show);
    try { await api.patch("/me/settings", { show_on_leaderboard: show }); toast.push("ok", show ? "แสดงชื่อใน Leaderboard แล้ว" : "ซ่อนชื่อจาก Leaderboard แล้ว"); lb.reload(); }
    catch (e) { setHidden(show); toast.push("err", (e as ApiError).message); }
  }

  return (
    <>
      <PageHeader title="Leaderboard" description="อันดับจากคะแนนโจทย์ที่ทำถูก (นับครั้งแรกของแต่ละข้อ) หรือคะแนนรวมจาก Challenges · แสดง 20 อันดับแรก" />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex gap-1 rounded-md border border-line p-0.5" role="tablist" aria-label="ประเภท">
          <button role="tab" aria-selected={board === "points"} className={seg(board === "points")} onClick={() => setBoard("points")}>คะแนนแบบฝึกหัด</button>
          <button role="tab" aria-selected={board === "challenges"} className={seg(board === "challenges")} onClick={() => setBoard("challenges")} data-testid="board-challenges">Challenges</button>
        </div>
        <div className="flex gap-1 rounded-md border border-line p-0.5" role="tablist" aria-label="ช่วงเวลา">
          <button role="tab" aria-selected={period === "week"} className={seg(period === "week")} onClick={() => setPeriod("week")}>7 วันล่าสุด</button>
          <button role="tab" aria-selected={period === "all"} className={seg(period === "all")} onClick={() => setPeriod("all")}>ทั้งหมด</button>
        </div>
      </div>
      {lb.loading ? <Spinner /> : lb.error ? <ErrorState message={lb.error.message} onRetry={lb.reload} /> : (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <Card>
            {!lb.data!.entries.length ? <EmptyState title="ยังไม่มีอันดับในช่วงนี้" /> : (
              <table className="w-full text-sm" data-testid="leaderboard">
                <thead className="text-left text-xs text-muted"><tr><th className="w-14">อันดับ</th><th>ผู้เรียน</th><th className="text-right">{board === "points" ? "ข้อที่ทำถูก" : "จำนวนรอบ"}</th><th className="text-right">คะแนน</th></tr></thead>
                <tbody>{lb.data!.entries.map((e) => (
                  <tr key={e.user_id} className={cx("border-t border-line", user?.id === e.user_id && "bg-brand-soft/40 font-medium")}>
                    <td className="py-2">{e.rank <= 3 ? <Medal className={cx("size-4", ["text-warn", "text-muted", "text-orange-600"][e.rank - 1])} aria-label={`อันดับ ${e.rank}`} /> : e.rank}</td>
                    <td>{e.display_name}{user?.id === e.user_id && " (คุณ)"}</td><td className="text-right">{e.count}</td><td className="text-right font-semibold">{e.score.toLocaleString()}</td>
                  </tr>))}</tbody>
              </table>)}
          </Card>
          <Card title="ของฉัน">
            {!user ? <p className="text-sm"><Link className="text-brand underline" href="/login?next=/leaderboard">เข้าสู่ระบบ</Link> เพื่อดูอันดับของคุณ</p> : (
              <div className="space-y-3 text-sm">
                {lb.data!.me && !meHidden ? <p>อันดับ <b>#{lb.data!.me.rank}</b> · {lb.data!.me.score.toLocaleString()} คะแนน</p>
                  : <p className="text-muted">{meHidden ? "คุณซ่อนชื่อจาก Leaderboard อยู่" : "ยังไม่มีคะแนนในช่วงนี้"}</p>}
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={!meHidden} onChange={(e) => toggle(e.target.checked)} data-testid="lb-optin" />
                  แสดงชื่อของฉันใน Leaderboard</label>
                <p className="text-xs text-muted">แสดงเฉพาะชื่อที่แสดง (display name) ไม่แสดงอีเมล</p>
              </div>)}
          </Card>
        </div>
      )}
    </>
  );
}
