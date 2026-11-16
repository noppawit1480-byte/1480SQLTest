"use client";

import { useEffect, useId, useState } from "react";
import { useTheme } from "./providers";
import { Spinner } from "./ui";

/** Renders a Mermaid diagram (used for ER diagrams generated from the live catalog). */
export function Mermaid({ chart }: { chart: string }) {
  const { theme } = useTheme();
  const id = useId().replace(/:/g, "");
  const [svg, setSvg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: theme === "dark" ? "dark" : "neutral", securityLevel: "strict",
          er: { useMaxWidth: true } });
        const { svg } = await mermaid.render(`er-${id}-${theme}`, chart);
        if (!cancelled) setSvg(svg);
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [chart, theme, id]);

  if (err) return <pre className="overflow-auto rounded border border-line p-3 text-xs">{chart}</pre>;
  if (!svg) return <Spinner label="กำลังวาด ER Diagram..." />;
  return <div className="overflow-x-auto [&_svg]:mx-auto [&_svg]:max-w-full" data-testid="er-diagram" dangerouslySetInnerHTML={{ __html: svg }} />;
}
