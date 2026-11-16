import { defineConfig } from "@playwright/test";

// Runs against an already-running stack (docker compose up, or backend + `npm run start`).
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  workers: 2,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000", viewport: { width: 1400, height: 900 } },
});
