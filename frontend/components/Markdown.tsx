"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Fragment, type ReactNode } from "react";

const KW = new Set(("SELECT FROM WHERE AND OR NOT IN IS NULL LIKE ILIKE BETWEEN EXISTS AS DISTINCT ORDER BY GROUP HAVING LIMIT OFFSET ASC DESC " +
  "NULLS FIRST LAST JOIN INNER LEFT RIGHT FULL OUTER CROSS LATERAL ON USING UNION ALL INTERSECT EXCEPT CASE WHEN THEN ELSE END WITH " +
  "RECURSIVE OVER PARTITION ROWS PRECEDING FOLLOWING CURRENT ROW INSERT INTO VALUES UPDATE SET DELETE RETURNING CONFLICT DO NOTHING " +
  "CREATE TABLE ALTER ADD COLUMN DROP TRUNCATE PRIMARY KEY FOREIGN REFERENCES UNIQUE CHECK DEFAULT CONSTRAINT INDEX BEGIN COMMIT " +
  "ROLLBACK SAVEPOINT EXPLAIN ANALYZE FILTER GENERATED ALWAYS IDENTITY TRUE FALSE INTERVAL CASCADE FETCH ONLY ROLLUP TO RELEASE").split(" "));
const FN = /^(count|sum|avg|min|max|round|coalesce|nullif|upper|lower|initcap|trim|length|substring|replace|concat|concat_ws|split_part|left|right|lpad|position|string_agg|array_agg|now|date_trunc|extract|age|to_char|generate_series|row_number|rank|dense_rank|ntile|lag|lead|percentile_cont|grouping)$/i;

/** Tiny SQL highlighter for static code blocks (Monaco is reserved for editable areas). */
export function highlightSql(code: string): ReactNode {
  const re = /(--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][\w]*)|([\s\S])/g;
  const out: ReactNode[] = [];
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(code))) {
    const [tok, cm, str, num, word] = m;
    if (cm) out.push(<span key={i++} className="sql-cm">{cm}</span>);
    else if (str) out.push(<span key={i++} className="sql-str">{str}</span>);
    else if (num) out.push(<span key={i++} className="sql-num">{num}</span>);
    else if (word && KW.has(word.toUpperCase())) out.push(<span key={i++} className="sql-kw">{word}</span>);
    else if (word && FN.test(word)) out.push(<span key={i++} className="sql-fn">{word}</span>);
    else out.push(<Fragment key={i++}>{tok}</Fragment>);
  }
  return out;
}

export function SqlBlock({ code, className }: { code: string; className?: string }) {
  return (
    <pre className={`overflow-x-auto rounded-md border border-line bg-code p-3 font-mono text-[13px] leading-relaxed ${className ?? ""}`}>
      <code>{highlightSql(code)}</code>
    </pre>
  );
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-lesson">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        code({ className, children: c, ...props }) {
          const text = String(c ?? "");
          if (/language-sql/.test(className ?? "")) return <code {...props}>{highlightSql(text.replace(/\n$/, ""))}</code>;
          return <code className={className} {...props}>{c}</code>;
        },
      }}>{children}</ReactMarkdown>
    </div>
  );
}
