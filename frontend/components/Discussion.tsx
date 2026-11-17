"use client";

import Link from "next/link";
import { useState } from "react";
import { EyeOff, Flag, MessageSquare, Pencil, ThumbsUp, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { DiscussionPost } from "@/lib/types";
import { Markdown } from "@/components/Markdown";
import { useAuth, useToast } from "@/components/providers";
import { Button, cx, Spinner } from "@/components/ui";

interface Thread { solved: boolean; can_see_spoilers: boolean; count: number; threads: DiscussionPost[] }

function Composer({ onSubmit, initial = "", spoilerDefault = false, showSpoiler, placeholder, compact }: {
  onSubmit: (body: string, spoiler: boolean) => Promise<boolean>; initial?: string; spoilerDefault?: boolean; showSpoiler: boolean; placeholder: string; compact?: boolean }) {
  const [body, setBody] = useState(initial);
  const [spoiler, setSpoiler] = useState(spoilerDefault);
  const [busy, setBusy] = useState(false);
  return (
    <form className="space-y-1.5" onSubmit={async (e) => { e.preventDefault(); setBusy(true); if (await onSubmit(body, spoiler)) setBody(""); setBusy(false); }}>
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={compact ? 2 : 3} maxLength={5000} placeholder={placeholder}
        className="w-full rounded-md border border-line bg-surface p-2 text-sm" aria-label={placeholder} data-testid="post-body" />
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {showSpoiler && <label className="flex items-center gap-1"><input type="checkbox" checked={spoiler} onChange={(e) => setSpoiler(e.target.checked)} /> มีเฉลย/แนวคำตอบ (spoiler)</label>}
        <span className="text-muted">รองรับ Markdown · โพสต์ที่มีบล็อก ```sql ในโจทย์จะถูกตั้งเป็น spoiler อัตโนมัติ</span>
        <Button size="sm" type="submit" loading={busy} disabled={body.trim().length < 2} className="ml-auto" data-testid="post-submit">โพสต์</Button>
      </div>
    </form>
  );
}

export function Discussion({ targetType, targetKey }: { targetType: "exercise" | "lesson"; targetKey: string }) {
  const { user } = useAuth();
  const toast = useToast();
  const [reveal, setReveal] = useState(false);
  const d = useApi<Thread>(`/discussions?target_type=${targetType}&target_key=${encodeURIComponent(targetKey)}&reveal_spoilers=${reveal}`);
  const [replyTo, setReplyTo] = useState<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const isEx = targetType === "exercise";

  async function create(body: string, spoiler: boolean, parent_id: number | null = null) {
    try {
      const r = await api.post<{ auto_spoiler: boolean }>("/discussions", { target_type: targetType, target_key: targetKey, body, is_spoiler: spoiler, parent_id });
      if (r.auto_spoiler) toast.push("ok", "โพสต์แล้ว — ตั้งเป็น spoiler อัตโนมัติเพราะมีโค้ด SQL");
      setReplyTo(null); d.reload(); return true;
    } catch (e) { toast.push("err", (e as ApiError).message); return false; }
  }
  async function act(fn: () => Promise<unknown>) { try { await fn(); d.reload(); } catch (e) { toast.push("err", (e as ApiError).message); } }

  function PostView({ p, reply }: { p: DiscussionPost; reply?: boolean }) {
    return (
      <div className={cx("text-sm", reply ? "ml-5 border-l-2 border-line pl-3 pt-2" : "")} data-testid="post">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span className="font-medium text-fg">{p.author}</span><span>{new Date(p.created_at).toLocaleString("th-TH")}</span>
          {p.edited && <span>(แก้ไขแล้ว)</span>}
          {p.is_spoiler && <span className="rounded bg-warn-soft px-1 text-warn">spoiler</span>}
          {p.is_hidden && <span className="rounded bg-bad-soft px-1 text-bad">ซ่อนโดยผู้ดูแล</span>}
        </div>
        {editing === p.id && p.body != null ? (
          <div className="mt-1"><Composer initial={p.body} spoilerDefault={p.is_spoiler} showSpoiler={isEx} placeholder="แก้ไขโพสต์" compact
            onSubmit={async (b, s) => { try { await api.patch(`/discussions/${p.id}`, { body: b, is_spoiler: s }); setEditing(null); d.reload(); return false; } catch (e) { toast.push("err", (e as ApiError).message); return false; } }} /></div>
        ) : p.body == null ? (
          <p className="mt-1 flex items-center gap-1 italic text-muted" data-testid="spoiler-locked"><EyeOff className="size-3.5" />
            {p.is_hidden ? "โพสต์นี้ถูกซ่อนโดยผู้ดูแล" : "ซ่อนไว้เพราะอาจเปิดเผยคำตอบ — ทำโจทย์ให้ถูกก่อน หรือกด “แสดง spoiler”"}</p>
        ) : <div className="prose-sm mt-1 [&_pre]:text-xs"><Markdown>{p.body}</Markdown></div>}
        <div className="mt-1 flex items-center gap-3 text-xs text-muted">
          <button disabled={!user || p.is_mine} onClick={() => act(() => api.post(`/discussions/${p.id}/vote`))} aria-label="โหวต"
            className={cx("flex items-center gap-1 disabled:opacity-60", p.voted && "text-brand")}><ThumbsUp className="size-3.5" /> {p.votes}</button>
          {user && !reply && <button onClick={() => setReplyTo(replyTo === p.id ? null : p.id)} className="hover:text-fg">ตอบกลับ</button>}
          {p.is_mine && p.body != null && <button onClick={() => setEditing(p.id)} aria-label="แก้ไข" className="hover:text-fg"><Pencil className="size-3.5" /></button>}
          {(p.is_mine || user?.role === "admin") && <button onClick={() => confirm("ลบโพสต์นี้ (รวมคำตอบกลับ)?") && act(() => api.del(`/discussions/${p.id}`))} aria-label="ลบ" className="hover:text-bad"><Trash2 className="size-3.5" /></button>}
          {user && !p.is_mine && <button onClick={() => { const r = prompt("เหตุผลที่รายงานโพสต์นี้ (อย่างน้อย 3 ตัวอักษร)"); if (r) act(async () => { await api.post(`/discussions/${p.id}/report`, { reason: r }); toast.push("ok", "ส่งรายงานแล้ว"); }); }}
            aria-label="รายงาน" className="hover:text-bad"><Flag className="size-3.5" /></button>}
        </div>
        {p.replies.map((r) => <PostView key={r.id} p={r} reply />)}
        {replyTo === p.id && <div className="ml-5 mt-2"><Composer showSpoiler={isEx} placeholder="เขียนคำตอบกลับ" compact onSubmit={(b, s) => create(b, s, p.id)} /></div>}
      </div>
    );
  }

  if (d.loading && !d.data) return <Spinner />;
  if (!d.data) return <p className="text-sm text-bad">{d.error?.message}</p>;
  const hasLocked = isEx && !d.data.can_see_spoilers && d.data.count > 0;
  return (
    <div className="space-y-4" data-testid="discussion">
      <div className="flex items-center gap-2 text-sm font-semibold"><MessageSquare className="size-4" /> การสนทนา ({d.data.count})
        {hasLocked && <button className="ml-auto text-xs font-normal text-brand" onClick={() => setReveal(true)} data-testid="reveal-spoilers">แสดง spoiler</button>}
        {isEx && d.data.solved && <span className="ml-auto text-xs font-normal text-ok">คุณทำข้อนี้ถูกแล้ว — เห็นทุกโพสต์</span>}
      </div>
      {user ? <Composer showSpoiler={isEx} placeholder={isEx ? "ถามคำถาม หรือแชร์แนวคิด (ไม่ควรเฉลยตรง ๆ)" : "ถามคำถามเกี่ยวกับบทเรียนนี้"} onSubmit={(b, s) => create(b, s)} />
        : <p className="text-sm text-muted"><Link href="/login" className="text-brand underline">เข้าสู่ระบบ</Link> เพื่อร่วมสนทนา</p>}
      {d.data.threads.length === 0 ? <p className="text-sm text-muted">ยังไม่มีการสนทนา — เริ่มเป็นคนแรก!</p>
        : <div className="space-y-4 divide-y divide-line">{d.data.threads.map((p) => <div key={p.id} className="pt-3 first:pt-0"><PostView p={p} /></div>)}</div>}
    </div>
  );
}
