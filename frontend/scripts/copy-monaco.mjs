// Copy Monaco's prebuilt AMD bundle into public/ so the editor loads from our own origin
// (no CDN dependency, works offline / behind strict CSP).
import { cpSync, existsSync, rmSync } from "node:fs";
const src = "node_modules/monaco-editor/min/vs";
const dst = "public/monaco/vs";
if (!existsSync(src)) {
  console.error("monaco-editor not installed; skipping copy");
  process.exit(0);
}
rmSync(dst, { recursive: true, force: true });
cpSync(src, dst, { recursive: true });
console.log("copied monaco-editor to", dst);
