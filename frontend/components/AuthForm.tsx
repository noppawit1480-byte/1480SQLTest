"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { useAuth } from "./providers";
import { Button } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const raw = params.get("next") ?? "/dashboard";
  const next = raw.startsWith("/") && !raw.startsWith("//") ? raw : "/dashboard"; // no open redirects

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    if (mode === "register" && password.length < 8) { setErr("รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร"); return; }
    setBusy(true);
    try {
      const u = mode === "login"
        ? await api.post<User>("/auth/login", { email, password })
        : await api.post<User>("/auth/register", { email, password, display_name: name });
      setUser(u);
      router.push(next);
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  const input = "w-full rounded-md border border-line bg-surface px-3 py-2 text-sm focus:border-brand focus:outline-none";
  return (
    <main className="mx-auto flex max-w-sm flex-col px-4 py-16">
      <h1 className="text-2xl font-bold">{mode === "login" ? "เข้าสู่ระบบ" : "สมัครสมาชิก"}</h1>
      <p className="mt-1 text-sm text-muted">{mode === "login" ? "บันทึกความคืบหน้า คะแนน และ Writable sandbox ของคุณ" : "ฟรี — เริ่มเรียน SQL ได้ทันที"}</p>
      <form onSubmit={submit} className="mt-6 space-y-3" noValidate>
        {mode === "register" && (
          <div><label htmlFor="name" className="mb-1 block text-sm">ชื่อที่แสดง</label>
            <input id="name" className={input} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoComplete="nickname" /></div>
        )}
        <div><label htmlFor="email" className="mb-1 block text-sm">อีเมล</label>
          <input id="email" type="email" className={input} value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></div>
        <div><label htmlFor="password" className="mb-1 block text-sm">รหัสผ่าน</label>
          <input id="password" type="password" className={input} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === "register" ? 8 : undefined}
            autoComplete={mode === "login" ? "current-password" : "new-password"} />
          {mode === "register" && <p className="mt-1 text-xs text-muted">อย่างน้อย 8 ตัวอักษร</p>}</div>
        {err && <p className="rounded-md bg-bad-soft/50 px-3 py-2 text-sm text-bad" role="alert">{err}</p>}
        <Button type="submit" variant="primary" className="w-full" loading={busy}>{mode === "login" ? "เข้าสู่ระบบ" : "สมัครสมาชิก"}</Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        {mode === "login" ? <>ยังไม่มีบัญชี? <Link className="text-brand underline" href={`/register?next=${encodeURIComponent(next)}`}>สมัครสมาชิก</Link></>
          : <>มีบัญชีแล้ว? <Link className="text-brand underline" href={`/login?next=${encodeURIComponent(next)}`}>เข้าสู่ระบบ</Link></>}
      </p>
    </main>
  );
}
