import { execSync } from "node:child_process";
import { expect, test } from "@playwright/test";
import { registerNewUser, setEditor } from "./helpers";

test("projects: brief, tasks, and a task page linked back to its project", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/projects");
  await expect(page.getByTestId("project-list").getByRole("link")).toHaveCount(6);
  await page.getByRole("link", { name: /SaaS Metrics/ }).click();
  await expect(page.getByTestId("project-tasks").getByRole("link")).toHaveCount(5);
  await page.getByTestId("project-tasks").getByRole("link").first().click();
  await expect(page.getByText(/Project: SaaS Metrics/)).toBeVisible();
  await setEditor(page, "SELECT p.name AS plan, COUNT(*) AS companies, SUM(s.mrr) AS mrr FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE s.ended_at IS NULL AND s.status = 'active' GROUP BY p.name ORDER BY mrr DESC");
  await page.getByTestId("submit-btn").click();
  await expect(page.getByTestId("verdict")).toHaveText("Correct");
});

test("assistant (rules) explains, reviews and optimizes without any AI key", async ({ page }) => {
  await page.goto("/playground?db=ecommerce&sql=" + encodeURIComponent("SELECT * FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.status = 'paid' LIMIT 5"));
  await page.waitForSelector(".monaco-editor");
  await page.getByRole("tab", { name: "Assistant" }).click();
  await page.getByTestId("assist-review").click();
  await expect(page.getByTestId("assistant-findings")).toContainText("LEFT JOIN");
  await page.getByTestId("assist-explain").click();
  await expect(page.getByTestId("assistant-answer")).toContainText("WHERE");
  await page.getByTestId("assist-optimize").click();
  await expect(page.getByTestId("assistant-answer")).toContainText("Execution plan");
});

test("assistant explains the last SQL error", async ({ page }) => {
  await page.goto("/playground");
  await setEditor(page, "SELECT frist_name FROM customers");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("sql-error")).toBeVisible();
  await page.getByRole("tab", { name: "Assistant" }).click();
  await page.getByTestId("assist-explain_error").click();
  await expect(page.getByTestId("assistant-answer")).toContainText("first_name");
});

test("admin panel is restricted and lets an admin create a validated exercise", async ({ page }) => {
  const email = await registerNewUser(page);
  await page.goto("/admin");
  await expect(page.getByText("ไม่มีสิทธิ์เข้าถึง")).toBeVisible();
  // How to reach the main DB depends on the deployment; override with E2E_SQL_CMD
  // (e.g. "docker compose exec -T main-db psql -U sqlab -d sqlab -c") for the Docker stack.
  const sqlCmd = process.env.E2E_SQL_CMD ?? `psql "${process.env.E2E_MAIN_DB ?? "postgresql://app:app@127.0.0.1:5433/sqlplatform"}" -c`;
  execSync(`${sqlCmd} "UPDATE users SET role='admin' WHERE email='${email}'"`, { cwd: ".." });
  await page.goto("/admin");
  await expect(page.getByTestId("admin-overview")).toBeVisible();
  const code = `EX-E2E${Date.now() % 100000}`;
  await page.goto("/admin/exercises/new");
  await page.getByLabel("รหัส (เช่น EX-C001)").fill(code);
  await page.getByLabel("ชื่อโจทย์").fill("E2E: จำนวนแผนก");
  await page.getByLabel("รายละเอียดโจทย์ (markdown)").fill("นับจำนวนแผนกในคอลัมน์ **n**");
  await page.getByLabel("ฐานข้อมูล").selectOption("hr");
  await page.getByTestId("solution-sql").fill("SELECT COUNT(*) AS n FROM departments");
  for (const i of [1, 2, 3]) await page.getByLabel(`Hint ${i}`).fill(`hint ${i}`);
  await page.getByLabel("คำอธิบายเฉลย (markdown)").fill("COUNT(*) นับทุกแถว");
  await page.getByTestId("save-exercise").click();
  await page.waitForURL(/\/admin\/exercises\/\d+$/);
  const id = page.url().split("/").pop();
  await expect(page.getByText("จากการรันเฉลยจริง")).toBeVisible();
  await page.goto(`/practice/${code}`);
  await expect(page.getByTestId("exercise-title")).toHaveText("E2E: จำนวนแผนก");
  // clean up so the shared catalogue isn't polluted by test data
  expect((await page.request.delete(`/api/admin/exercises/${id}`)).status()).toBe(204);
});
