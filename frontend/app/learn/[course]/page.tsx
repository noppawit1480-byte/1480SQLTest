"use client";

import Link from "next/link";
import { use } from "react";
import { CheckCircle2, Circle, CircleDot, Dumbbell } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { CourseDetail } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { ButtonLink, ErrorState, PageHeader, ProgressBar, Spinner } from "@/components/ui";

export default function CoursePage({ params }: { params: Promise<{ course: string }> }) {
  const { course } = use(params);
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<CourseDetail>(`/courses/${course}`);
  if (loading) return <Spinner />;
  if (error || !data) return <ErrorState message={error?.message ?? "ไม่พบหลักสูตร"} onRetry={reload} />;
  const next = data.lessons.find((l) => l.status !== "completed") ?? data.lessons[0];
  return (
    <>
      <nav className="mb-2 text-sm text-muted"><Link href="/learn" className="hover:underline">หลักสูตร</Link> / {data.title}</nav>
      <PageHeader title={data.title} description={data.description}
        actions={next && <ButtonLink variant="primary" href={`/learn/${course}/${next.slug}`}>{data.completed ? "เรียนต่อ" : "เริ่มเรียน"}: {next.title.split("—")[0]}</ButtonLink>} />
      {user && (
        <div className="mb-6 flex items-center gap-3 text-sm">
          <ProgressBar value={data.percent} className="max-w-md" label="ความคืบหน้าหลักสูตร" />
          <span className="tabular-nums text-muted">{data.completed}/{data.lessons.length} บท ({data.percent}%)</span>
        </div>
      )}
      <h2 className="mb-2 text-sm font-semibold text-muted">Table of Contents</h2>
      <ol className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface" data-testid="toc">
        {data.lessons.map((l, i) => (
          <li key={l.slug}>
            <Link href={`/learn/${course}/${l.slug}`} className="flex items-start gap-3 px-4 py-3 hover:bg-surface-2">
              {l.status === "completed" ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-ok" aria-label="เรียนจบแล้ว" />
                : l.status === "in_progress" ? <CircleDot className="mt-0.5 size-5 shrink-0 text-warn" aria-label="กำลังเรียน" />
                : <Circle className="mt-0.5 size-5 shrink-0 text-line" aria-label="ยังไม่เริ่ม" />}
              <span className="w-6 shrink-0 pt-0.5 text-right font-mono text-xs text-muted">{i + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{l.title}</span>
                <span className="block text-xs text-muted">{l.summary}</span>
              </span>
              {l.has_exercise && <Dumbbell className="mt-0.5 size-4 shrink-0 text-muted" aria-label="มีแบบฝึกหัดท้ายบท" />}
            </Link>
          </li>
        ))}
      </ol>
    </>
  );
}
