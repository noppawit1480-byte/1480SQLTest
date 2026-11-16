import { expect, test } from "@playwright/test";
import { expectNoConsoleErrors, registerNewUser, setEditor } from "./helpers";

test("new learner sees a zeroed dashboard (no fake numbers)", async ({ page }) => {
  await registerNewUser(page);
  const stats = page.getByTestId("stats");
  await expect(stats).toContainText("0/62");
  await expect(stats).toContainText(/โจทย์ที่ทำสำเร็จ\s*0\//);
  await expect(page.getByTestId("level-name")).toHaveText("Novice");
});

test("guest can run SQL in the playground (read-only) and writes are refused", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/playground");
  await setEditor(page, "SELECT id, first_name FROM customers ORDER BY id LIMIT 3;");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("row-count")).toContainText("3 แถว");
  await expect(page.getByTestId("result-table")).toContainText("first_name");

  await setEditor(page, "DELETE FROM customers;");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("sql-error")).toContainText("Read-only");
  await expectNoConsoleErrors(errors);
});

test("SQL error shows line and column", async ({ page }) => {
  await page.goto("/playground");
  await setEditor(page, "SELECT 1;\nSELECT nope FROM customers;");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("sql-error")).toContainText("บรรทัด 2");
});

test("lesson → Try it opens the playground with the example", async ({ page }) => {
  await page.goto("/learn/beginner/where");
  await expect(page.getByTestId("lesson-title")).toContainText("WHERE");
  await expect(page.getByTestId("lesson-example").first()).toContainText("ผลลัพธ์จริงจาก PostgreSQL");
  await page.getByRole("link", { name: "Try it" }).first().click();
  await page.waitForURL(/\/playground\?db=ecommerce/);
  await page.waitForFunction(() => (window as any).monaco?.editor.getModels()[0]?.getValue().includes("price <= 1000"));
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("exec-status")).toContainText("สำเร็จ");
});

test("practice: hints, incorrect then correct submission updates progress", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/practice/EX-M009");
  await expect(page.getByTestId("exercise-title")).toBeVisible();
  await page.getByTestId("hint-btn").click();
  await expect(page.getByTestId("hint-1")).toBeVisible();

  await setEditor(page, "SELECT c.name AS category, COUNT(*) AS products FROM categories c LEFT JOIN products p ON p.category_id = c.id GROUP BY c.name");
  await page.getByTestId("submit-btn").click();
  await expect(page.getByTestId("verdict")).toHaveText("Incorrect");
  await expect(page.getByTestId("feedback")).toContainText("Toys");

  await setEditor(page, "SELECT c.name AS category, COUNT(p.id) AS products FROM categories c LEFT JOIN products p ON p.category_id = c.id GROUP BY c.name");
  await page.getByTestId("submit-btn").click();
  await expect(page.getByTestId("verdict")).toHaveText("Correct");
  await expect(page.getByTestId("feedback")).toContainText("+20 pts");

  await page.goto("/dashboard");
  await expect(page.getByTestId("stats")).toContainText(/โจทย์ที่ทำสำเร็จ\s*1\//);
  await expect(page.getByTestId("stats")).toContainText("50%");
  await expect(page.getByTestId("achievements")).toContainText("First Blood");
});

test("writable sandbox: modify then reset", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/playground?db=hr");
  await page.getByTestId("mode-writable").click();
  await setEditor(page, "DELETE FROM salaries; SELECT COUNT(*) AS n FROM salaries;");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("result-table")).toContainText("0");
  page.once("dialog", (d) => d.accept());
  await page.getByTestId("reset-btn").click();
  await setEditor(page, "SELECT COUNT(*) AS n FROM salaries;");
  await page.getByTestId("run-btn").click();
  await expect(page.getByTestId("result-table")).not.toContainText(/^\s*0\s*$/);
  await expect(page.getByTestId("row-count")).toContainText("1 แถว");
});

test("lesson completion is reflected in the course table of contents", async ({ page }) => {
  await registerNewUser(page);
  await page.goto("/learn/beginner/select");
  await page.getByTestId("complete-btn").click();
  await expect(page.getByText("เรียนจบแล้ว")).toBeVisible();
  await page.goto("/learn/beginner");
  await expect(page.getByLabel("เรียนจบแล้ว")).toHaveCount(1);
});

test("database page renders the ER diagram", async ({ page }) => {
  await page.goto("/databases/hr");
  await expect(page.getByTestId("er-diagram")).toBeVisible({ timeout: 20_000 });
});

test("mobile layout uses a drawer menu", async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto("/learn");
  await page.getByLabel("เปิดเมนู").click();
  await expect(page.getByRole("navigation", { name: "เมนูหลัก" })).toBeVisible();
});
