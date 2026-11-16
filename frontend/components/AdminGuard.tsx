"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ShieldX } from "lucide-react";
import { useAuth } from "./providers";
import { EmptyState, Spinner } from "./ui";

/** UX guard only — every /api/admin route is enforced server-side by RBAC. */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <Spinner />;
  if (!user) return <EmptyState title="กรุณาเข้าสู่ระบบ" action={<Link className="text-brand underline" href="/login?next=/admin">เข้าสู่ระบบ</Link>} />;
  if (user.role !== "admin") return <EmptyState icon={<ShieldX className="size-8" />} title="ไม่มีสิทธิ์เข้าถึง" description="หน้านี้สำหรับผู้ดูแลระบบเท่านั้น" />;
  return <>{children}</>;
}
