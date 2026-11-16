"use client";

import Editor, { loader, type Monaco, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef } from "react";
import type * as MonacoNS from "monaco-editor";
import { api } from "@/lib/api";
import type { SyntaxIssue, TableInfo } from "@/lib/types";
import { useTheme } from "./providers";
import { Spinner } from "./ui";

// Monaco is served from our own origin (copied to /public by scripts/copy-monaco.mjs).
loader.config({ paths: { vs: "/monaco/vs" } });

const KEYWORDS = [
  "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE", "ILIKE", "BETWEEN", "EXISTS", "AS", "DISTINCT",
  "ORDER BY", "GROUP BY", "HAVING", "LIMIT", "OFFSET", "ASC", "DESC", "NULLS FIRST", "NULLS LAST", "JOIN", "INNER JOIN",
  "LEFT JOIN", "RIGHT JOIN", "FULL OUTER JOIN", "CROSS JOIN", "LATERAL", "ON", "USING", "UNION", "UNION ALL", "INTERSECT",
  "EXCEPT", "CASE", "WHEN", "THEN", "ELSE", "END", "WITH", "RECURSIVE", "OVER", "PARTITION BY", "ROWS BETWEEN",
  "PRECEDING", "FOLLOWING", "CURRENT ROW", "UNBOUNDED", "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM",
  "RETURNING", "ON CONFLICT", "DO NOTHING", "DO UPDATE", "CREATE TABLE", "ALTER TABLE", "ADD COLUMN", "DROP COLUMN",
  "DROP TABLE", "TRUNCATE", "PRIMARY KEY", "FOREIGN KEY", "REFERENCES", "UNIQUE", "CHECK", "DEFAULT", "CONSTRAINT",
  "CREATE INDEX", "BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "EXPLAIN", "EXPLAIN ANALYZE", "FILTER", "GENERATED ALWAYS AS IDENTITY",
];
const FUNCTIONS = [
  "COUNT", "SUM", "AVG", "MIN", "MAX", "ROUND", "COALESCE", "NULLIF", "CAST", "UPPER", "LOWER", "INITCAP", "TRIM", "LENGTH",
  "SUBSTRING", "REPLACE", "CONCAT", "CONCAT_WS", "SPLIT_PART", "LEFT", "RIGHT", "LPAD", "POSITION", "STRING_AGG", "ARRAY_AGG",
  "NOW", "CURRENT_DATE", "DATE_TRUNC", "EXTRACT", "AGE", "TO_CHAR", "GENERATE_SERIES", "ROW_NUMBER", "RANK", "DENSE_RANK",
  "NTILE", "LAG", "LEAD", "FIRST_VALUE", "LAST_VALUE", "PERCENTILE_CONT", "GREATEST", "LEAST", "ABS", "CEIL", "FLOOR",
];

// Shared across editor instances; the completion provider is registered once per page load.
const schemaRef: { current: TableInfo[] } = { current: [] };
let completionRegistered = false;

function registerCompletion(monaco: Monaco) {
  if (completionRegistered) return;
  completionRegistered = true;
  monaco.languages.registerCompletionItemProvider("sql", {
    triggerCharacters: ["."],
    provideCompletionItems(model: MonacoNS.editor.ITextModel, position: MonacoNS.Position) {
      const word = model.getWordUntilPosition(position);
      const range = { startLineNumber: position.lineNumber, endLineNumber: position.lineNumber,
        startColumn: word.startColumn, endColumn: word.endColumn };
      const K = monaco.languages.CompletionItemKind;
      const tables = schemaRef.current;
      const before = model.getLineContent(position.lineNumber).slice(0, word.startColumn - 1);
      const dot = /([A-Za-z_][\w]*)\.$/.exec(before);
      if (dot) {
        // resolve "alias." → table via "FROM/JOIN table [AS] alias" in the whole text
        const text = model.getValue();
        const qual = dot[1].toLowerCase();
        let tableName = tables.find((t) => t.name === qual)?.name;
        if (!tableName) {
          const re = /\b(?:from|join)\s+([a-z_][\w]*)\s+(?:as\s+)?([a-z_][\w]*)/gi;
          for (const m of text.matchAll(re)) if (m[2].toLowerCase() === qual) tableName = m[1].toLowerCase();
        }
        const t = tables.find((x) => x.name === tableName);
        return {
          suggestions: (t?.columns ?? []).map((c) => ({
            label: c.name, kind: K.Field, insertText: c.name, range, detail: `${c.type}${c.is_pk ? " · PK" : ""}${c.fk ? ` · FK→${c.fk}` : ""}`,
            documentation: c.comment ?? undefined,
          })),
        };
      }
      const suggestions = [
        ...KEYWORDS.map((k) => ({ label: k, kind: K.Keyword, insertText: k, range, sortText: "3" + k })),
        ...FUNCTIONS.map((f) => ({ label: f, kind: K.Function, insertText: `${f}($0)`, range, sortText: "4" + f,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet })),
        ...tables.map((t) => ({ label: t.name, kind: K.Struct, insertText: t.name, range, sortText: "1" + t.name,
          detail: `table · ${t.row_estimate} rows`, documentation: t.comment ?? undefined })),
        ...tables.flatMap((t) => t.columns.map((c) => ({ label: c.name, kind: K.Field, insertText: c.name, range,
          sortText: "2" + c.name, detail: `${t.name}.${c.name} · ${c.type}` }))),
      ];
      // de-duplicate column names that exist in several tables
      const seen = new Set<string>();
      return { suggestions: suggestions.filter((s) => (seen.has(s.label + s.kind) ? false : (seen.add(s.label + s.kind), true))) };
    },
  });
}

export interface ErrorMarker { line: number; column: number; message: string }

export function SqlEditor({ value, onChange, onRun, schema, height = "100%", errorMarker, validate = true, readOnly, ariaLabel = "SQL editor" }: {
  value: string;
  onChange: (v: string) => void;
  onRun?: () => void;
  schema?: TableInfo[];
  height?: string | number;
  errorMarker?: ErrorMarker | null;
  validate?: boolean;
  readOnly?: boolean;
  ariaLabel?: string;
}) {
  const { theme } = useTheme();
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const runRef = useRef(onRun);
  runRef.current = onRun;

  useEffect(() => {
    if (schema) schemaRef.current = schema;
  }, [schema]);

  // Debounced syntax validation using the real PostgreSQL parser on the server.
  useEffect(() => {
    if (!validate) return;
    const id = window.setTimeout(async () => {
      const m = monacoRef.current;
      const model = editorRef.current?.getModel();
      if (!m || !model) return;
      try {
        const r = await api.post<{ issues: SyntaxIssue[] }>("/playground/validate", { sql: value });
        m.editor.setModelMarkers(model, "syntax", r.issues.map((i) => ({
          startLineNumber: i.line, endLineNumber: i.line, startColumn: i.column, endColumn: i.end_column,
          message: i.message, severity: m.MarkerSeverity.Error,
        })));
      } catch { /* validation is best-effort */ }
    }, 500);
    return () => window.clearTimeout(id);
  }, [value, validate]);

  // Execution error marker (from the database).
  useEffect(() => {
    const m = monacoRef.current;
    const model = editorRef.current?.getModel();
    if (!m || !model) return;
    m.editor.setModelMarkers(model, "exec", errorMarker ? [{
      startLineNumber: errorMarker.line, endLineNumber: errorMarker.line, startColumn: errorMarker.column,
      endColumn: model.getLineMaxColumn(errorMarker.line), message: errorMarker.message, severity: m.MarkerSeverity.Error,
    }] : []);
  }, [errorMarker]);

  const onMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;
    registerCompletion(monaco);
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => runRef.current?.());
    editor.focus();
  };

  return (
    <div className="h-full min-h-0" aria-label={ariaLabel} data-testid="sql-editor">
      <Editor
        height={height}
        language="sql"
        value={value}
        onChange={(v) => onChange(v ?? "")}
        onMount={onMount}
        theme={theme === "dark" ? "vs-dark" : "vs"}
        loading={<Spinner label="กำลังโหลด editor..." />}
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Fira Code', ui-monospace, Menlo, Consolas, monospace",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 2,
          wordWrap: "on",
          autoIndent: "full",
          formatOnPaste: false,
          readOnly,
          padding: { top: 10 },
          renderLineHighlight: "line",
          suggest: { showWords: false },
          acceptSuggestionOnEnter: "smart",
          fixedOverflowWidgets: true,
        }}
      />
    </div>
  );
}
