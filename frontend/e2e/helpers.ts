import { expect, type Page } from "@playwright/test";

export async function registerNewUser(page: Page) {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/register");
  await page.fill("#name", "E2E Learner");
  await page.fill("#email", email);
  await page.fill("#password", "password123");
  await page.click("button[type=submit]");
  await page.waitForURL("**/dashboard");
  return email;
}

/** Monaco suggestions intercept typed keys, so tests set the model value directly. */
export async function setEditor(page: Page, sql: string) {
  await page.waitForSelector(".monaco-editor");
  await page.waitForFunction(() => (window as any).monaco?.editor.getModels().length > 0);
  await page.evaluate((v) => (window as any).monaco.editor.getModels()[0].setValue(v), sql);
}

export async function expectNoConsoleErrors(errors: string[]) {
  expect(errors.filter((e) => !e.includes("favicon"))).toEqual([]);
}
