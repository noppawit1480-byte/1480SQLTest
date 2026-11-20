"use client";

import { Discussion } from "@/components/Discussion";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  AlertTriangle, ArrowLeft, ArrowRight, Bookmark, BookmarkCheck, CheckCircle2, Dumbbell, Play, Target,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { LessonDetail, LessonExample } from "@/lib/types";
import { useAuth, useToast } from "@/components/providers";
import { Markdown, SqlBlock } from "@/components/Markdown";
import { DataTable } from "@/components/ResultView";
import { Badge, Button, ButtonLink, Card, cx, DifficultyBadge, ErrorState, Spinner } from "@/components/ui";

function playgroundHref(ex: LessonExample) {
  const p = new URLSearchParams({ db: ex.db, sql: ex.sql });
  if (ex.writable) p.set("mode", "writable");
  return `/playground?${p.toString()}`;
}

function Example({ ex, n }: { ex: LessonExample; n: number }) {
  const r = ex.result;
  return (
    <div className="rounded-lg border border-line bg-surface" data-testid="lesson-example">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <h3 className="text-sm font-semibold">ตัวอย่างที่ {n}: {ex.title}</h3>
        <div className="flex items-center gap-2">
          <Badge>DB: {ex.db}</Badge>
          {ex.writable && <Badge className="!text-warn">Writable sandbox</Badge>}
          <ButtonLink href={playgroundHref(ex)} variant="primary" className="!h-7 !px-2.5 !text-xs"><Play className="size-3" /> Try it</ButtonLink>
        </div>
      </div>
      <div className="space-y-3 p-4">
        <SqlBlock code={ex.sql} />
        <div>
          <div className="mb-1 text-xs font-semibold text-muted">อธิบายทีละส่วน</div>
          <ol className="list-decimal space-y-0.5 pl-5 text-sm">
            {ex.explain.map((e, i) => <li key={i}><Markdown>{e}</Markdown></li>)}
          </ol>
        </div>
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-muted">
            ผลลัพธ์จริงจาก PostgreSQL
            {r.row_count !== undefined && <span className="font-normal">({r.row_count} แถว{r.truncated ? ", แสดงบางส่วน" : ""} · {r.exec_ms} ms)</span>}
          </div>
          {r.error ? (
            <div className="rounded-md border border-bad/30 bg-bad-soft/30 p-3 font-mono text-xs">
              <span className="font-sans font-semibold text-bad">ERROR</span> {r.error.message}
              {r.error.detail && <div className="mt-1 text-muted">DETAIL: {r.error.detail}</div>}
              {r.commands.length > 0 && <div className="mt-1 font-sans text-muted">ก่อนเกิด error: {r.commands.join(" · ")}</div>}
            </div>
          ) : r.columns?.length ? <DataTable columns={r.columns} rows={r.rows ?? []} maxHeight="18rem" />
            : <div className="rounded-md border border-line p-2 font-mono text-xs">{r.commands.join(" · ")}</div>}
          {r.commands.length > 1 && !r.error && <div className="mt-1 text-[11px] text-muted">คำสั่งที่รัน: {r.commands.join(" · ")}</div>}
        </div>
      </div>
    </div>
  );
}

export default function LessonPage({ params }: { params: Promise<{ course: string; lesson: string }> }) {
  const { lesson: slug } = use(params);
  const { user } = useAuth();
  const toast = useToast();
  const { data, error, loading, reload, setData } = useApi<LessonDetail>(`/lessons/${slug}`);
  const [note, setNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);

  useEffect(() => { if (data) setNote(data.note); }, [data]);

  // Opening a lesson marks it "in progress" for signed-in users (never downgrades a completed lesson).
  useEffect(() => {
    if (user && data && data.status === "not_started") {
      api.post(`/lessons/${slug}/progress`, { status: "in_progress" }).then(() => setData({ ...data, status: "in_progress" })).catch(() => undefined);
    }
  }, [user, data, slug, setData]);

  if (loading) return <Spinner />;
  if (error || !data) return <ErrorState message={error?.message ?? "ไม่พบบทเรียน"} onRetry={reload} />;
  const l = data;

  async function complete() {
    try {
      const r = await api.post<{ status: string; new_achievements: string[] }>(`/lessons/${slug}/progress`, { status: "completed" });
      setData({ ...l, status: "completed" });
      toast.push("ok", "บันทึกว่าเรียนจบบทนี้แล้ว");
      toast.awards(r.new_achievements);
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function toggleBookmark() {
    try {
      if (l.bookmarked) await api.del(`/lessons/${slug}/bookmark`); else await api.put(`/lessons/${slug}/bookmark`);
      setData({ ...l, bookmarked: !l.bookmarked });
    } catch (e) { toast.push("err", (e as ApiError).message); }
  }
  async function saveNote() {
    setSavingNote(true);
    try { await api.put(`/lessons/${slug}/note`, { body: note }); toast.push("ok", "บันทึกโน้ตแล้ว"); }
    catch (e) { toast.push("err", (e as ApiError).message); }
    finally { setSavingNote(false); }
  }

  return (
    <div className="flex gap-8">
      <article className="min-w-0 flex-1">
        <nav className="mb-3 text-sm text-muted">
          <Link href="/learn" className="hover:underline">หลักสูตร</Link> / <Link href={`/learn/${l.course.slug}`} className="hover:underline">{l.course.title}</Link>
        </nav>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-brand">บทที่ {l.position + 1} · {l.course.level}</div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight" data-testid="lesson-title">{l.title}</h1>
            <p className="mt-1 text-muted">{l.summary}</p>
          </div>
          {user && (
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={toggleBookmark} aria-pressed={l.bookmarked}>
                {l.bookmarked ? <BookmarkCheck className="size-4 text-brand" /> : <Bookmark className="size-4" />} {l.bookmarked ? "Bookmarked" : "Bookmark"}
              </Button>
            </div>
          )}
        </div>

        <Card className="mt-5" title={<span className="flex items-center gap-1.5"><Target className="size-4 text-brand" /> วัตถุประสงค์การเรียนรู้</span>}>
          <ul className="list-disc space-y-1 pl-5 text-sm">{l.objectives.map((o, i) => <li key={i}>{o}</li>)}</ul>
        </Card>

        <div className="mt-6"><Markdown>{l.content_md}</Markdown></div>

        <h2 className="mt-8 mb-3 text-lg font-bold">ตัวอย่าง SQL</h2>
        <div className="space-y-4">{l.examples.map((ex, i) => <Example key={i} ex={ex} n={i + 1} />)}</div>

        {l.common_mistakes.length > 0 && (
          <>
            <h2 className="mt-8 mb-3 flex items-center gap-2 text-lg font-bold"><AlertTriangle className="size-5 text-warn" /> ข้อผิดพลาดที่พบบ่อย</h2>
            <div className="space-y-3">
              {l.common_mistakes.map((m, i) => (
                <div key={i} className="rounded-lg border border-line bg-surface p-4">
                  <div className="font-medium">{m.title}</div>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    <div><div className="mb-1 text-xs font-semibold text-bad">✗ ผิด</div><SqlBlock code={m.wrong} className="!border-bad/30" /></div>
                    <div><div className="mb-1 text-xs font-semibold text-ok">✓ ถูก</div><SqlBlock code={m.right} className="!border-ok/30" /></div>
                  </div>
                  <p className="mt-2 text-sm text-muted">{m.why}</p>
                </div>
              ))}
            </div>
          </>
        )}

        <h2 className="mt-8 mb-3 flex items-center gap-2 text-lg font-bold"><Dumbbell className="size-5 text-brand" /> แบบฝึกหัดท้ายบท</h2>
        <div className="space-y-2">
          {l.exercises.map((x) => (
            <Link key={x.code} href={`/practice/${x.code}`} className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3 hover:border-brand">
              <span className="font-mono text-xs text-muted">{x.code}</span>
              <span className="flex-1 text-sm font-medium">{x.title}</span>
              <DifficultyBadge d={x.difficulty} />
              <ArrowRight className="size-4 text-muted" />
            </Link>
          ))}
        </div>

        {user && (
          <Card className="mt-8" title="โน้ตส่วนตัว" action={<Button size="sm" onClick={saveNote} loading={savingNote}>บันทึกโน้ต</Button>}>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} maxLength={10000} aria-label="โน้ตส่วนตัว"
              placeholder="จดสิ่งที่ได้เรียนรู้ หรือ query ที่อยากจำ..." className="w-full resize-y rounded-md border border-line bg-bg p-2 text-sm" />
          </Card>
        )}

        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
          {l.prev ? <ButtonLink href={`/learn/${l.prev.course_slug}/${l.prev.slug}`}><ArrowLeft className="size-4" /> {l.prev.title.split("—")[0]}</ButtonLink> : <span />}
          {user ? (
            l.status === "completed" ? <span className="flex items-center gap-1.5 text-sm font-medium text-ok"><CheckCircle2 className="size-4" /> เรียนจบแล้ว</span>
              : <Button variant="success" onClick={complete} data-testid="complete-btn"><CheckCircle2 className="size-4" /> ทำเครื่องหมายว่าเรียนจบ</Button>
          ) : <Link href={`/login?next=/learn/${l.course.slug}/${slug}`} className="text-sm text-brand underline">เข้าสู่ระบบเพื่อบันทึกความคืบหน้า</Link>}
          {l.next ? <ButtonLink href={`/learn/${l.next.course_slug}/${l.next.slug}`} variant="primary" className="max-w-xs">
            <span className="truncate">{l.next.title.split("—")[0]}</span> <ArrowRight className="size-4" /></ButtonLink> : <span />}
        </div>

        {l.related.length > 0 && (
          <div className="mt-6">
            <h2 className="mb-2 text-sm font-semibold text-muted">บทเรียนที่เกี่ยวข้อง</h2>
            <div className="flex flex-wrap gap-2">
              {l.related.map((r) => <Link key={r.slug} href={`/learn/${r.course_slug}/${r.slug}`} className="rounded-full border border-line bg-surface px-3 py-1 text-sm hover:border-brand">{r.title.split("—")[0]}</Link>)}
            </div>
          </div>
        )}

        <div className="mt-10 border-t border-line pt-6"><Discussion targetType="lesson" targetKey={slug} /></div>
      </article>

      <aside className="sticky top-0 hidden w-60 shrink-0 self-start xl:block">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">{l.course.title}</div>
        <ol className="mt-2 space-y-0.5 border-l border-line">
          {l.course.lessons.map((x, i) => (
            <li key={x.slug}>
              <Link href={`/learn/${l.course.slug}/${x.slug}`}
                className={cx("-ml-px block border-l-2 py-1 pl-3 text-[13px]", x.slug === slug ? "border-brand font-medium text-brand" : "border-transparent text-muted hover:text-fg")}>
                {i + 1}. {x.title.split("—")[0]}
              </Link>
            </li>
          ))}
        </ol>
      </aside>
    </div>
  );
}
