"use client";

import Link from "next/link";
import { Briefcase, CheckCircle2, Database } from "lucide-react";
import { useApi } from "@/lib/hooks";
import type { ProjectSummary } from "@/lib/types";
import { useAuth } from "@/components/providers";
import { Badge, DifficultyBadge, ErrorState, PageHeader, ProgressBar, Skeleton } from "@/components/ui";

export default function ProjectsPage() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<ProjectSummary[]>("/projects");
  return (
    <>
      <PageHeader title="Real-World Projects" description="รับบทนักวิเคราะห์ในสถานการณ์ธุรกิจจริง: อ่าน brief แล้วทำงานทีละขั้น — ทุกงานตรวจอัตโนมัติจากผลลัพธ์ SQL" />
      {loading ? <div className="grid gap-4 md:grid-cols-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-44" />)}</div>
        : error ? <ErrorState message={error.message} onRetry={reload} />
        : (
          <div className="grid gap-4 md:grid-cols-2" data-testid="project-list">
            {data!.map((p) => (
              <Link key={p.slug} href={`/projects/${p.slug}`} className="flex flex-col rounded-lg border border-line bg-surface p-5 transition hover:border-brand">
                <div className="flex items-center gap-2 text-xs text-muted">
                  <Briefcase className="size-3.5" /> {p.role}
                  <span className="ml-auto flex items-center gap-1.5"><Badge><Database className="size-3" /> {p.sample_db}</Badge><DifficultyBadge d={p.difficulty} /></span>
                </div>
                <h2 className="mt-2 font-bold">{p.title}</h2>
                <p className="mt-1 flex-1 text-sm text-muted">{p.summary}</p>
                <div className="mt-4 flex items-center gap-2 text-sm">
                  {p.completed && <CheckCircle2 className="size-4 text-ok" aria-label="เสร็จแล้ว" />}
                  <span className="text-muted">{p.tasks} งาน</span>
                  {user && <span className="ml-auto tabular-nums text-muted">{p.solved}/{p.tasks}</span>}
                </div>
                {user && <ProgressBar value={(100 * p.solved) / Math.max(1, p.tasks)} className="mt-2" label={`ความคืบหน้า ${p.title}`} />}
              </Link>
            ))}
          </div>
        )}
    </>
  );
}
