import { expect, test } from "@playwright/test";
import { registerNewUser, setEditor } from "./helpers";

// Runs only when the server has the MySQL engine configured (MYSQL_HOST); otherwise the UI must show it as unavailable.
test.beforeEach(async ({ request }) => {
  const r = await request.get("/api/engines");
  const mysql = (await r.json()).engines.find((e: { key: string }) => e.key === "mysql");
  test.skip(!mysql?.available, "MySQL engine not configured on this server");
});

test("playground runs on MySQL, shows a plan, and writes go to the learner's own MySQL database", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/playground?db=ecommerce");
  await page.getByTestId("engine-select").selectOption("mysql");
  await setEditor(page, "SELECT 7/2 AS d");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("result-table")).toContainText("3.5000");
  await setEditor(page, "SELECT * FROM orders WHERE customer_id = 5");
  await page.getByTestId("explain-btn").click();
  await expect(page.getByTestId("plan-tree")).toContainText("idx_orders_customer");
  await setEditor(page, "DELETE FROM payments");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("sql-error")).toContainText("Read-only");
});

test("dialect comparison runs on three engines and explains MySQL's case-insensitive grouping", async ({ page }) => {
  await page.goto("/dialects");
  await setEditor(page, "SELECT city, COUNT(*) AS n FROM customers GROUP BY city ORDER BY n DESC, city");
  await page.getByTestId("compare-btn").click();
  await expect(page.getByTestId("verdict-sqlite")).toContainText("ตรงกับ PostgreSQL");
  await expect(page.getByTestId("verdict-mysql")).toContainText("ต่างจาก PostgreSQL");
  await expect(page.getByTestId("compare-verdict")).toContainText("collation");
});

test("ER designer creates the tables in MySQL", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/designer");
  await page.getByTestId("save-design").click();
  await page.getByTestId("apply-engine").selectOption("mysql");
  page.once("dialog", (d) => d.accept());
  await page.getByTestId("apply-design").click();
  await expect(page.getByTestId("apply-result")).toBeVisible();
  await page.getByTestId("apply-result").getByRole("link").click();
  await setEditor(page, "SHOW CREATE TABLE orders");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("result-table")).toContainText("FOREIGN KEY");
});
