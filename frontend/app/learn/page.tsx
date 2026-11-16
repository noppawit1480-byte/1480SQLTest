"use client";

import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { CourseSummary } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { ErrorState, PageHeader, ProgressBar, Skeleton } from "@/components/ui";

const LEVEL_TH: Record<string, string> = { beginner: "Level 1 · Beginner", intermediate: "Level 2 · Intermediate", advanced: "Level 3 · Advanced", professional: "Level 4 · Professional" };

export default function LearnPage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<CourseSummary[]>("/courses");
  return (
    <>
      <PageHeader title="หลักสูตร SQL" description="4 ระดับ 62 บทเรียน — เริ่มจากระดับไหนก็ได้ ทุกตัวอย่างรันจริงบน PostgreSQL" />
      {loading ? <div className="grid gap-4 md:grid-cols-2">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-44" />)}</div>
        : error ? <ErrorState message={error.message} onRetry={reload} />
        : (
          <div className="grid gap-4 md:grid-cols-2">
            {data!.map((c) => (
              <Link key={c.slug} href={`/learn/${c.slug}`} className="group flex flex-col rounded-lg border border-line bg-surface p-5 transition hover:border-brand">
                <div className="text-xs font-semibold uppercase tracking-wide text-brand">{LEVEL_TH[c.level] ?? c.level}</div>
                <h2 className="mt-1 text-lg font-bold">{c.title}</h2>
                <p className="mt-1 flex-1 text-sm text-muted">{c.description}</p>
                <div className="mt-4 flex items-center gap-3 text-sm">
                  <BookOpen className="size-4 text-muted" />
                  <span className="text-muted">{c.lesson_count} บทเรียน</span>
                  {user && <span className="ml-auto tabular-nums text-muted">{c.completed}/{c.lesson_count}</span>}
                  <ArrowRight className="size-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-brand" />
                </div>
                {user && <ProgressBar value={c.percent} className="mt-2" label={`ความคืบหน้า ${c.title}`} />}
              </Link>
            ))}
          </div>
        )}
    </>
  );
}
