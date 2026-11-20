import { execSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";
import { registerNewUser, setEditor } from "./helpers";

const sqlCmd = process.env.E2E_SQL_CMD ?? `psql "${process.env.E2E_MAIN_DB ?? "postgresql://app:app@127.0.0.1:5433/sqlplatform"}" -c`;

test("playground runs the same query on SQLite and shows an execution plan", async ({ page }) => {
  await page.goto("/playground?db=ecommerce");
  await setEditor(page, "SELECT COUNT(*) AS n FROM customers");
  await page.getByTestId("engine-select").selectOption("sqlite");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("exec-status")).toContainText("สำเร็จ");
  const sqliteCount = await page.getByTestId("result-table").locator("tbody td").first().innerText();
  await page.getByTestId("engine-select").selectOption("postgresql");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("result-table").locator("tbody td").first()).toHaveText(sqliteCount);
  await page.getByTestId("explain-btn").click();
  await expect(page.getByTestId("plan-tree")).toBeVisible();
  await expect(page.getByTestId("plan-node").first()).toBeVisible();
});

test("dialect comparison reports differences between engines", async ({ page }) => {
  await page.goto("/dialects");
  await expect(page.getByTestId("dialect-table")).toContainText("ILIKE");
  await setEditor(page, "SELECT first_name FROM customers WHERE first_name ILIKE 'a%' ORDER BY 1 LIMIT 3");
  await page.getByTestId("compare-btn").click();
  await expect(page.getByTestId("compare-verdict")).toBeVisible();
});

test("ER designer validates, generates DDL and creates the tables in the learner's sandbox", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/designer");
  await expect(page.getByTestId("design-table")).toHaveCount(2);
  await expect(page.getByText("CREATE TABLE customers")).toBeVisible();
  await page.getByTestId("save-design").click();
  page.once("dialog", (d) => d.accept());
  await page.getByTestId("apply-design").click();
  await expect(page.getByTestId("apply-result")).toBeVisible();
  await page.getByTestId("apply-result").getByRole("link").click();
  await setEditor(page, "SELECT COUNT(*) FROM orders");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("exec-status")).toContainText("สำเร็จ");
});

test("CSV import previews types and loads rows", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/designer");
  await page.getByRole("tab", { name: /นำเข้า CSV/ }).click();
  await page.getByTestId("csv-file").setInputFiles({ name: "Sales Data.csv", mimeType: "text/csv",
    buffer: Buffer.from("id,amount,sold_on,note\n1,10.5,2024-01-02,a\n2,20,2024-02-03,\n3,7.25,2024-03-04,c\n") });
  const cols = page.getByTestId("csv-columns");
  await expect(cols).toContainText("numeric");
  await expect(cols).toContainText("date");
  await expect(page.getByTestId("csv-table")).toHaveValue("sales_data");
  await page.getByTestId("csv-import").click();
  await expect(page.getByTestId("csv-done")).toContainText("3");
});

test("random challenge: server timer, wrong answer, finish and report", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/challenges");
  await page.getByTestId("mode-random").click();
  await page.getByTestId("start-challenge").click();
  await page.waitForURL(/\/challenges\/\d+/);
  await expect(page.getByTestId("timer")).toContainText(/1[45]:\d\d/);
  await setEditor(page, "SELECT 1");
  await page.getByTestId("challenge-submit").click();
  await expect(page.getByTestId("challenge-verdict")).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page.getByTestId("finish-challenge").click();
  await expect(page.getByTestId("challenge-report")).toContainText("0/1");
  await page.goto("/challenges");
  await expect(page.getByTestId("challenge-history")).toContainText("จบแล้ว");
});

test("mock interview shows the approach box and a rubric", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/challenges");
  await page.getByTestId("mode-interview").click();
  await page.getByTestId("start-challenge").click();
  await page.waitForURL(/\/challenges\/\d+/);
  await page.getByTestId("approach").fill("ผมจะเริ่มจาก JOIN ตารางที่เกี่ยวข้องก่อน แล้วค่อย GROUP BY และกรองด้วย HAVING");
  page.once("dialog", (d) => d.accept());
  await page.getByTestId("finish-challenge").click();
  await expect(page.getByTestId("rubric-overall")).toBeVisible();
});

async function post(page: Page, text: string) {
  await page.getByTestId("post-body").first().fill(text);
  await page.getByTestId("post-submit").first().click();
}

test("discussion hides SQL spoilers from learners who have not solved the exercise; leaderboard opt-out", async ({ page, browser }) => {
  await registerNewUser(page);
  await page.goto("/practice/EX-E001");
  await page.getByRole("tab", { name: "สนทนา" }).click();
  await post(page, "ลองแบบนี้\n```sql\nSELECT * FROM customers;\n```");
  await expect(page.getByTestId("post").first()).toContainText("spoiler");

  const ctx = await browser.newContext();
  const other = await ctx.newPage();
  await registerNewUser(other);
  await other.goto("/practice/EX-E001");
  await other.getByRole("tab", { name: "สนทนา" }).click();
  await expect(other.getByTestId("spoiler-locked").first()).toBeVisible();
  await other.getByTestId("reveal-spoilers").click();
  await expect(other.getByTestId("discussion")).toContainText("SELECT * FROM customers");

  await other.goto("/leaderboard");
  await other.getByTestId("lb-optin").uncheck();
  await expect(other.getByText("คุณซ่อนชื่อจาก Leaderboard อยู่")).toBeVisible();
  await ctx.close();
});

test("admin can hide a reported post", async ({ page, browser }) => {
  const email = await registerNewUser(page);
  await page.goto("/practice/EX-E002");
  await page.getByRole("tab", { name: "สนทนา" }).click();
  const msg = `ข้อความที่จะถูกรายงาน ${Date.now()}`;
  await post(page, msg);
  const ctx = await browser.newContext();
  const reporter = await ctx.newPage();
  await registerNewUser(reporter);
  await reporter.goto("/practice/EX-E002");
  await reporter.getByRole("tab", { name: "สนทนา" }).click();
  reporter.once("dialog", (d) => d.accept("สแปม"));
  await reporter.getByTestId("post").filter({ hasText: msg }).getByRole("button", { name: "รายงาน" }).click();
  await expect(reporter.getByText("ส่งรายงานแล้ว")).toBeVisible();
  await ctx.close();

  execSync(`${sqlCmd} "UPDATE users SET role='admin' WHERE email='${email}'"`, { cwd: ".." });
  await page.goto("/admin");
  await page.getByRole("tab", { name: "รายงานโพสต์" }).click();
  await expect(page.getByTestId("admin-reports")).toContainText("สแปม");
  await page.getByTestId("admin-reports").locator("li", { hasText: msg }).getByRole("button", { name: "ซ่อนโพสต์" }).click();
  await expect(page.getByText("ซ่อนโพสต์แล้ว")).toBeVisible();
});
