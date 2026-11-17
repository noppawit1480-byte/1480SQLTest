"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  BookOpen, Bot, Database, Gauge, Languages, Shapes, Shield, Dumbbell, Timer, Trophy, FolderKanban, LayoutDashboard, LogIn, LogOut, Menu, Moon, Sun, Terminal, User, X,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth, useTheme } from "./providers";
import { cx } from "./ui";

const NAV: { href: string; label: string; icon: typeof BookOpen; auth?: boolean; admin?: boolean; badge?: string }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, auth: true },
  { href: "/learn", label: "บทเรียน", icon: BookOpen },
  { href: "/playground", label: "Playground", icon: Terminal },
  { href: "/practice", label: "แบบฝึกหัด", icon: Dumbbell },
  { href: "/assistant", label: "Assistant", icon: Bot },
  { href: "/databases", label: "Databases", icon: Database },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/challenges", label: "Challenges", icon: Timer },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { href: "/designer", label: "DB Designer", icon: Shapes },
  { href: "/optimize", label: "Optimization", icon: Gauge },
  { href: "/dialects", label: "SQL Dialects", icon: Languages },
  { href: "/profile", label: "โปรไฟล์", icon: User, auth: true },
  { href: "/admin", label: "Admin", icon: Shield, auth: true, admin: true },
];

const FULL_BLEED = ["/playground", "/practice/", "/assistant/practice/", "/challenges/"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, ready, setUser } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const isLanding = pathname === "/" || pathname === "/login" || pathname === "/register";
  const fullBleed = FULL_BLEED.some((p) => pathname.startsWith(p) && pathname !== "/practice");

  async function logout() {
    await api.post("/auth/logout").catch(() => undefined);
    setUser(null);
    router.push("/");
  }

  const nav = (
    <nav className="flex flex-col gap-0.5 p-3" aria-label="เมนูหลัก">
      {NAV.filter((n) => (!n.auth || user) && (!n.admin || user?.role === "admin")).map((n) => {
        const active = pathname === n.href || pathname.startsWith(n.href + "/");
        return (
          <Link key={n.href} href={n.href} onClick={() => setOpen(false)}
            className={cx("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition",
              active ? "bg-brand-soft font-medium text-brand" : "text-muted hover:bg-surface-2 hover:text-fg")}>
            <n.icon className="size-4" aria-hidden />
            <span className="flex-1">{n.label}</span>
            {n.badge && <span className="rounded bg-surface-2 px-1 text-[10px] text-muted">{n.badge}</span>}
          </Link>
        );
      })}
    </nav>
  );

  const topActions = (
    <div className="flex items-center gap-1.5">
      <button onClick={toggle} className="rounded-md p-2 text-muted hover:bg-surface-2 hover:text-fg"
        aria-label={theme === "dark" ? "เปลี่ยนเป็นโหมดสว่าง" : "เปลี่ยนเป็นโหมดมืด"}>
        {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </button>
      {ready && (user ? (
        <div className="flex items-center gap-2">
          <Link href="/profile" className="hidden items-center gap-2 rounded-md px-2 py-1 text-sm hover:bg-surface-2 sm:flex">
            <span className="grid size-7 place-items-center rounded-full bg-brand text-xs font-bold text-brand-fg">
              {user.display_name.slice(0, 1).toUpperCase()}
            </span>
            <span className="max-w-32 truncate">{user.display_name}</span>
          </Link>
          <button onClick={logout} className="rounded-md p-2 text-muted hover:bg-surface-2 hover:text-fg" aria-label="ออกจากระบบ" title="ออกจากระบบ">
            <LogOut className="size-4" />
          </button>
        </div>
      ) : (
        <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="flex items-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg">
          <LogIn className="size-4" /> เข้าสู่ระบบ
        </Link>
      ))}
    </div>
  );

  const logo = (
    <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
      <span className="grid size-7 place-items-center rounded-md bg-brand font-mono text-xs text-brand-fg">SQ</span>
      <span>SQLab</span>
    </Link>
  );

  if (isLanding) {
    return (
      <div className="min-h-full">
        <header className="sticky top-0 z-30 border-b border-line bg-bg/80 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">{logo}{topActions}</div>
        </header>
        {children}
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line bg-surface md:flex">
        <div className="flex h-14 items-center border-b border-line px-4">{logo}</div>
        {nav}
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-line bg-surface">
            <div className="flex h-14 items-center justify-between border-b border-line px-4">
              {logo}
              <button onClick={() => setOpen(false)} aria-label="ปิดเมนู" className="p-1"><X className="size-5" /></button>
            </div>
            {nav}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-3 md:px-5">
          <button className="rounded-md p-2 md:hidden" onClick={() => setOpen(true)} aria-label="เปิดเมนู"><Menu className="size-5" /></button>
          <div className="hidden text-sm text-muted md:block" />
          {topActions}
        </header>
        <main className={cx("min-h-0 flex-1", fullBleed ? "overflow-hidden" : "overflow-y-auto")}>
          {fullBleed ? children : <div className="mx-auto max-w-6xl px-4 py-6 md:px-8">{children}</div>}
        </main>
      </div>
    </div>
  );
}
