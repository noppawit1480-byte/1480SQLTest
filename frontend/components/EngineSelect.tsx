"use client";

import type { SelectHTMLAttributes } from "react";
import { useApi } from "@/lib/hooks";
import type { Engine } from "@/lib/types";

export interface EngineInfo { key: Engine; name: string; available: boolean; reason?: string | null }

/** Engines this server can really execute — MySQL is shown disabled (with the reason) when it is not configured. */
export function useEngines() {
  return useApi<{ engines: EngineInfo[] }>("/engines").data?.engines ?? [
    { key: "postgresql", name: "PostgreSQL 16", available: true }, { key: "sqlite", name: "SQLite 3", available: true }];
}

export function EngineSelect({ value, onChange, ...rest }: { value: Engine; onChange: (e: Engine) => void } &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange">) {
  const engines = useEngines();
  const unavailable = engines.filter((e) => !e.available);
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as Engine)}
      title={unavailable.map((e) => `${e.name}: ${e.reason ?? "ไม่พร้อมใช้งาน"}`).join("\n") || undefined} {...rest}>
      {engines.map((e) => (
        <option key={e.key} value={e.key} disabled={!e.available}>{e.name}{e.available ? "" : " (ไม่พร้อมใช้งาน)"}</option>
      ))}
    </select>
  );
}

export const ENGINE_LABEL: Record<Engine, string> = { postgresql: "PostgreSQL", sqlite: "SQLite", mysql: "MySQL" };
