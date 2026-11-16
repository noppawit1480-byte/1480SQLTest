"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Eye, KeyRound, Link2, Table2 } from "lucide-react";
import type { TableInfo } from "@/lib/types";
import { cx } from "./ui";

export function SchemaExplorer({ tables, onPreview, onInsert }: {
  tables: TableInfo[];
  onPreview?: (table: string) => void;
  onInsert?: (text: string) => void;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  return (
    <ul className="space-y-0.5 text-[13px]" data-testid="schema-explorer">
      {tables.map((t) => {
        const isOpen = open[t.name];
        return (
          <li key={t.name}>
            <div className="group flex items-center gap-1 rounded px-1 py-1 hover:bg-surface-2">
              <button className="flex min-w-0 flex-1 items-center gap-1 text-left" onClick={() => setOpen((o) => ({ ...o, [t.name]: !isOpen }))}
                aria-expanded={!!isOpen} title={t.comment ?? undefined}>
                {isOpen ? <ChevronDown className="size-3.5 shrink-0 text-muted" /> : <ChevronRight className="size-3.5 shrink-0 text-muted" />}
                <Table2 className="size-3.5 shrink-0 text-brand" />
                <span className="truncate font-medium">{t.name}</span>
                <span className="ml-auto pl-1 text-[10px] text-muted">{t.row_estimate.toLocaleString()}</span>
              </button>
              {onPreview && (
                <button onClick={() => onPreview(t.name)} className="rounded p-0.5 text-muted opacity-60 hover:bg-surface hover:text-brand group-hover:opacity-100"
                  title={`Preview ${t.name}`} aria-label={`Preview ข้อมูลตาราง ${t.name}`}>
                  <Eye className="size-3.5" />
                </button>
              )}
            </div>
            {isOpen && (
              <ul className="mb-1 ml-5 border-l border-line pl-2">
                {t.comment && <li className="py-0.5 text-[11px] text-muted">{t.comment}</li>}
                {t.columns.map((c) => (
                  <li key={c.name}>
                    <button className={cx("flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-surface-2", !onInsert && "cursor-default")}
                      onClick={() => onInsert?.(c.name)} title={[c.comment, c.fk && `FK → ${c.fk}`, c.default && `default ${c.default}`].filter(Boolean).join("\n") || undefined}>
                      {c.is_pk ? <KeyRound className="size-3 shrink-0 text-warn" aria-label="Primary key" />
                        : c.fk ? <Link2 className="size-3 shrink-0 text-brand" aria-label="Foreign key" />
                        : <span className="size-3 shrink-0" />}
                      <span className="truncate font-mono text-[12px]">{c.name}</span>
                      <span className="ml-auto truncate pl-2 font-mono text-[10px] text-muted">{c.type.replace("character varying", "varchar")}{c.nullable ? "" : " ·NN"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
}
