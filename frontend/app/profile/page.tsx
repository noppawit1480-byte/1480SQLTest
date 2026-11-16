"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Bookmark, NotebookPen } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { Dashboard, SavedQuery } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { Card, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";

interface Library {
  bookmarks: { slug: string; title: string; course_slug: string; created_at: string }[];
  notes: { slug: string; title: string; course_slug: string; body: string; updated_at: string }[];
}

export default function ProfilePage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const lib = useApi<Library>(user ? "/me/library" : null);
  const dash = useApi<Dashboard>(user ? "/dashboard" : null);
  const saved = useApi<SavedQuery[]>(user ? "/saved-queries" : null);
  useEffect(() => { if (ready && !user) router.replace("/login?next=/profile"); }, [ready, user, router]);
  if (!user || lib.loading || dash.loading) return <Spinner />;
  if (lib.error) return <ErrorState message={lib.error.message} onRetry={lib.reload} />;

  return (
    <>
      <PageHeader title={user.display_name} description={`${user.email} · สมาชิกตั้งแต่ ${user.created_at ? new Date(user.created_at).toLocaleDateString("th-TH") : "-"}${user.role === "admin" ? " · Admin" : ""}`} />
      {dash.data && (
        <p className="mb-6 text-sm">ระดับ <b className="text-brand">{dash.data.level.name}</b> · {dash.data.level.points} คะแนน ·
          Achievements {dash.data.achievements.filter((a) => a.earned_at).length}/{dash.data.achievements.length} · <Link href="/dashboard" className="text-brand underline">ดู Dashboard</Link></p>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={<span className="flex items-center gap-1.5"><Bookmark className="size-4" /> Bookmarks</span>}>
          {lib.data?.bookmarks.length ? (
            <ul className="divide-y divide-line">{lib.data.bookmarks.map((b) => <li key={b.slug}><Link className="block py-2 text-sm hover:text-brand" href={`/learn/${b.course_slug}/${b.slug}`}>{b.title}</Link></li>)}</ul>
          ) : <EmptyState title="ยังไม่มีบทเรียนที่ Bookmark" description="กดปุ่ม Bookmark ในหน้าบทเรียนเพื่อเก็บไว้อ่านภายหลัง" />}
        </Card>
        <Card title={<span className="flex items-center gap-1.5"><NotebookPen className="size-4" /> Personal Notes</span>}>
          {lib.data?.notes.length ? (
            <ul className="divide-y divide-line">{lib.data.notes.map((n) => (
              <li key={n.slug} className="py-2"><Link className="text-sm font-medium hover:text-brand" href={`/learn/${n.course_slug}/${n.slug}`}>{n.title}</Link>
                <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-xs text-muted">{n.body}</p></li>))}</ul>
          ) : <EmptyState title="ยังไม่มีโน้ต" description="เขียนโน้ตส่วนตัวได้ที่ท้ายทุกบทเรียน" />}
        </Card>
        <Card title="Saved Queries" className="lg:col-span-2">
          {saved.data?.length ? (
            <ul className="divide-y divide-line">{saved.data.map((q) => (
              <li key={q.id} className="py-2"><Link className="text-sm font-medium hover:text-brand" href={`/playground?db=${q.db_key}&sql=${encodeURIComponent(q.sql)}`}>{q.title}</Link>
                <span className="ml-2 text-xs text-muted">{q.db_key}</span><code className="mt-0.5 line-clamp-1 block font-mono text-xs text-muted">{q.sql}</code></li>))}</ul>
          ) : <EmptyState title="ยังไม่มี query ที่บันทึกไว้" description="กด Save ใน Playground เพื่อเก็บ query" />}
        </Card>
      </div>
    </>
  );
}
