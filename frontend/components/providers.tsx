"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { CheckCircle2, Trophy, XCircle } from "lucide-react";
import { api, ACHIEVEMENT_TITLES } from "@/lib/api";
import { useHeartbeat } from "@/lib/hooks";
import type { User } from "@/lib/types";

// ---------------------------------------------------------------- auth
interface AuthCtx {
  user: User | null;
  ready: boolean;
  refresh: () => Promise<void>;
  setUser: (u: User | null) => void;
}
const AuthContext = createContext<AuthCtx>({ user: null, ready: false, refresh: async () => {}, setUser: () => {} });
export const useAuth = () => useContext(AuthContext);

// ---------------------------------------------------------------- theme
type Theme = "light" | "dark";
const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({ theme: "light", toggle: () => {} });
export const useTheme = () => useContext(ThemeContext);

// ---------------------------------------------------------------- toasts
interface Toast { id: number; kind: "ok" | "err" | "award"; text: string }
const ToastContext = createContext<{ push: (kind: Toast["kind"], text: string) => void; awards: (keys?: string[]) => void }>({
  push: () => {}, awards: () => {},
});
export const useToast = () => useContext(ToastContext);

export function Providers({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [theme, setTheme] = useState<Theme>("light");
  const [toasts, setToasts] = useState<Toast[]>([]);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get<{ user: User | null }>("/auth/me");
      setUser(r.user);
    } catch {
      setUser(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    setTheme(document.documentElement.classList.contains("dark") ? "dark" : "light");
  }, [refresh]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try { localStorage.setItem("theme", next); } catch { /* private mode */ }
      return next;
    });
  }, []);

  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "award" ? 6000 : 3500);
  }, []);
  const awards = useCallback((keys?: string[]) => {
    (keys ?? []).forEach((k) => push("award", `ได้รับ Achievement: ${ACHIEVEMENT_TITLES[k] ?? k}`));
  }, [push]);

  useHeartbeat(!!user);

  return (
    <AuthContext.Provider value={{ user, ready, refresh, setUser }}>
      <ThemeContext.Provider value={{ theme, toggle }}>
        <ToastContext.Provider value={{ push, awards }}>
          {children}
          <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2" aria-live="polite">
            {toasts.map((t) => (
              <div key={t.id} className="pointer-events-auto flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm shadow-lg">
                {t.kind === "ok" && <CheckCircle2 className="size-4 text-ok" />}
                {t.kind === "err" && <XCircle className="size-4 text-bad" />}
                {t.kind === "award" && <Trophy className="size-4 text-warn" />}
                {t.text}
              </div>
            ))}
          </div>
        </ToastContext.Provider>
      </ThemeContext.Provider>
    </AuthContext.Provider>
  );
}
