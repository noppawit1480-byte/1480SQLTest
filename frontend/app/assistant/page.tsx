"use client";

import Link from "next/link";
import { useState } from "react";
import { Bot, CheckCircle2, Sparkles, Target, Wand2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { AssistantStatus, DatabaseSummary, Difficulty, GeneratedPractice } from "@/lib/types";
import { TutorChat } from "@/components/AssistantPanel";
import { useAuth, useToast } from "@/components/providers";
import { Badge, Button, Card, DifficultyBadge, EmptyState, PageHeader, ProgressBar, Spinner } from "@/components/ui";

interface Recs { weak_categories: { category: string; solved: number; total: number; next: { code: string; title: string; difficulty: Difficulty }[] }[] }

export default function AssistantPage() {
  const { user } = useAuth();
  const toast = useToast();
  const status = useApi<AssistantStatus>("/assistant/status");
  const recs = useApi<Recs>(user ? "/assistant/recommendations" : null);
  const gen = useApi<GeneratedPractice[]>(user ? "/assistant/generated" : null);
  const dbs = useApi<DatabaseSummary[]>("/databases");
  const [dbKey, setDbKey] = useState("ecommerce");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [busy, setBusy] = useState(false);
  const ai = !!status.data?.ai_available;

  async function generate() {
    if (topic.trim().length < 2) { toast.push("err", "ระบุหัวข้อที่อยากฝึก เช่น LEFT JOIN, Window Functions"); return; }
    setBusy(true);
    try {
      const g = await api.post<GeneratedPractice>("/assistant/generate", { db_key: dbKey, topic, difficulty });
      toast.push("ok", `สร้างโจทย์ "${g.title}" แล้ว`);
      gen.reload();
    } catch (e) { toast.push("err", (e as ApiError).message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title={<span className="flex items-center gap-2"><Bot className="size-6 text-brand" /> SQL Learning Assistant</span>}
        description="ผู้ช่วยเรียน SQL: วิเคราะห์ SQL อัตโนมัติด้วย parser ของ PostgreSQL (ใช้ได้เสมอ) + AI Tutor และโจทย์ฝึกที่สร้างเฉพาะคุณ (เมื่อเซิร์ฟเวอร์เปิดใช้ AI)" />
      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <Badge>Explain · Explain Error · Fix · Review · Optimize — ใช้ได้ใน Playground และหน้าแบบฝึกหัด (แท็บ Assistant)</Badge>
        {status.data && (ai
          ? <Badge className="!text-ok"><Sparkles className="size-3" /> AI: {status.data.provider} · {status.data.model}</Badge>
          : <Badge>AI: ยังไม่ได้ตั้งค่าบนเซิร์ฟเวอร์</Badge>)}
      </div>
      {!user ? (
        <EmptyState title="เข้าสู่ระบบเพื่อรับคำแนะนำเฉพาะตัว" action={<Link className="text-sm text-brand underline" href="/login?next=/assistant">เข้าสู่ระบบ</Link>} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={<span className="flex items-center gap-1.5"><Target className="size-4" /> ควรฝึกอะไรต่อ (จากผลการทำโจทย์จริงของคุณ)</span>}>
            {recs.loading ? <Spinner /> : !recs.data?.weak_categories.length ? <EmptyState title="ทำโจทย์ครบทุกหมวดแล้ว 🎉" /> : (
              <ul className="space-y-4" data-testid="recommendations">
                {recs.data.weak_categories.map((c) => (
                  <li key={c.category}>
                    <div className="mb-1 flex justify-between text-sm"><b>{c.category}</b><span className="text-muted">{c.solved}/{c.total}</span></div>
                    <ProgressBar value={(100 * c.solved) / c.total} label={c.category} />
                    <ul className="mt-2 space-y-1">
                      {c.next.map((x) => (
                        <li key={x.code}><Link href={`/practice/${x.code}`} className="flex items-center gap-2 text-sm hover:text-brand">
                          <span className="font-mono text-xs text-muted">{x.code}</span><span className="flex-1">{x.title}</span><DifficultyBadge d={x.difficulty} /></Link></li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title={<span className="flex items-center gap-1.5"><Bot className="size-4" /> SQL Tutor</span>}>
            <TutorChat dbKey={dbKey} />
          </Card>
          <Card className="lg:col-span-2" title={<span className="flex items-center gap-1.5"><Wand2 className="size-4" /> สร้างโจทย์ฝึกเพิ่ม (AI)</span>}>
            {!ai ? <p className="text-sm text-muted">ฟีเจอร์นี้ต้องเปิดใช้ AI บนเซิร์ฟเวอร์ — ระหว่างนี้ฝึกจากคำแนะนำด้านบนหรือ <Link href="/practice" className="text-brand underline">คลังโจทย์ 70 ข้อ</Link></p> : (
              <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); generate(); }}>
                <label className="text-sm">ฐานข้อมูล<br />
                  <select value={dbKey} onChange={(e) => setDbKey(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1.5">
                    {dbs.data?.map((d) => <option key={d.key} value={d.key}>{d.name}</option>)}
                  </select></label>
                <label className="min-w-56 flex-1 text-sm">หัวข้อที่อยากฝึก<br />
                  <input value={topic} onChange={(e) => setTopic(e.target.value)} maxLength={80} placeholder="เช่น LEFT JOIN, HAVING, ROW_NUMBER"
                    className="w-full rounded-md border border-line bg-surface px-2 py-1.5" /></label>
                <label className="text-sm">ระดับ<br />
                  <select value={difficulty} onChange={(e) => setDifficulty(e.target.value as typeof difficulty)} className="rounded-md border border-line bg-surface px-2 py-1.5">
                    <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                  </select></label>
                <Button type="submit" variant="primary" loading={busy}><Sparkles className="size-4" /> สร้างโจทย์</Button>
              </form>
            )}
            <p className="mt-2 text-xs text-muted">ทุกโจทย์ที่ AI สร้างจะถูกตรวจโดยการรันเฉลยบนฐานข้อมูลจริงก่อนส่งให้คุณ — ผลลัพธ์ที่คาดหวังมาจากฐานข้อมูล ไม่ใช่จาก AI (โจทย์ฝึกส่วนตัว ไม่นับคะแนน)</p>
            {gen.data && gen.data.length > 0 && (
              <ul className="mt-4 divide-y divide-line rounded-md border border-line" data-testid="generated-list">
                {gen.data.map((g) => (
                  <li key={g.id}><Link href={`/assistant/practice/${g.id}`} className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-surface-2">
                    {g.solved ? <CheckCircle2 className="size-4 text-ok" /> : <Sparkles className="size-4 text-muted" />}
                    <span className="flex-1">{g.title}</span><Badge>{g.topic}</Badge><Badge>{g.db_key}</Badge></Link></li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
