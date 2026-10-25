import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { PASSWORD, codeFor, secretOf, stepAt } from "./helpers/totp";

const screenshots = "../specs/reviews/2026-10-24-f37-supported-symbol-management";

async function register(page: import("@playwright/test").Page, email: string) {
  await page.goto("/account");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
}

async function enableTotp(page: import("@playwright/test").Page) {
  await page.goto("/security");
  await page.getByLabel("รหัสผ่านปัจจุบัน").fill(PASSWORD);
  await page.getByTestId("start-totp").click();
  const uri = await page.getByTestId("otpauth-uri").textContent();
  const secret = secretOf(uri ?? "");
  await page.getByLabel("รหัสจากแอป").fill(codeFor(secret, stepAt(Date.now()) - 1));
  await page.getByTestId("confirm-totp").click();
  await expect(page.getByTestId("totp-state")).toHaveText("เปิดอยู่");
  return secret;
}

test("owner manages the catalog through the real browser, API, and database", async ({ page }) => {
  test.setTimeout(120_000);
  mkdirSync(screenshots, { recursive: true });
  await register(page, `e2e-catalog-owner-${String(Date.now())}@example.com`);
  const secret = await enableTotp(page);
  const identity = await (await page.request.get("/api/auth/me")).json() as { user_id: string };
  const prepared = await page.request.post(
    `${process.env.TIEWTRADE_E2E_BACKEND_URL ?? "http://127.0.0.1:18037"}/__e2e/catalog/prepare`,
    { data: { user_id: identity.user_id } },
  );
  expect(prepared.status()).toBe(204);

  await page.goto("/supported-symbols");
  await expect(page.getByRole("heading", { name: "คู่เทรดที่รองรับ" })).toBeVisible();
  await expect(page.getByRole("link", { name: "คู่เทรดที่รองรับ" })).toBeVisible();

  const add = page.getByRole("button", { name: "เพิ่มคู่เทรด" });
  await add.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(add).toBeFocused();
  await add.click();
  await page.getByLabel("Base asset").fill("sol");
  const addStep = stepAt(Date.now());
  await page.getByLabel("รหัส TOTP ใหม่").fill(codeFor(secret, addStep));
  await page.getByRole("button", { name: "ยืนยันเพิ่ม" }).click();
  await expect(page.getByRole("row", { name: /SOL\/USDT REQUESTED/ })).toBeVisible();

  while (stepAt(Date.now()) === addStep) {
    await page.waitForTimeout(250);
  }
  const eth = page.getByRole("row", { name: /ETH\/USDT ACTIVE/ });
  await eth.getByRole("button", { name: "ถอนคู่" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("หลังยืนยัน ระบบจะห้ามเปิดความเสี่ยงใหม่ทันที");
  await expect(dialog.getByText("0", { exact: true })).toHaveCount(5);
  await dialog.getByLabel("รหัส TOTP ใหม่").fill(codeFor(secret, stepAt(Date.now())));
  await dialog.getByRole("button", { name: "ยืนยันถอนคู่" }).click();
  await expect(page.getByRole("row", { name: /ETH\/USDT REMOVED/ })).toBeVisible();
  const reconciled = await page.request.post(
    `${process.env.TIEWTRADE_E2E_BACKEND_URL ?? "http://127.0.0.1:18037"}/__e2e/catalog/reconcile`,
  );
  expect(reconciled.status()).toBe(204);
  await page.reload();
  await expect(page.getByRole("row", { name: /ETH\/USDT REMOVED.*PARTIAL/ })).toBeVisible();

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 950 });
    const layout = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      overflow: Array.from(document.querySelectorAll<HTMLElement>("body *"))
        .map(element => ({
          tag: element.tagName,
          className: element.className,
          right: Math.round(element.getBoundingClientRect().right),
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
        }))
        .filter(element => element.right > window.innerWidth || element.scrollWidth > element.clientWidth)
        .slice(0, 12),
    }));
    expect(layout, JSON.stringify(layout.overflow)).toMatchObject({ scrollWidth: expect.any(Number) });
    expect(layout.scrollWidth, JSON.stringify(layout.overflow)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: `${screenshots}/catalog-th-light-${String(width)}.png`, fullPage: true });
  }
  await page.getByRole("button", { name: "เปลี่ยนเป็นโหมดมืด" }).click();
  await page.screenshot({ path: `${screenshots}/catalog-th-dark-1440.png`, fullPage: true });

  await page.evaluate(async () => {
    type Messages = { changeLanguage: (language: string) => Promise<unknown> };
    const accountPath = "/src/accountMessages.ts";
    const catalogPath = "/src/supportedSymbolMessages.ts";
    const account = await import(/* @vite-ignore */ accountPath) as { accountI18n: Messages };
    const catalog = await import(/* @vite-ignore */ catalogPath) as { supportedSymbolI18n: Messages };
    await account.accountI18n.changeLanguage("en");
    await catalog.supportedSymbolI18n.changeLanguage("en");
  });
  await page.getByRole("button", { name: "เพิ่มคู่เทรด" }).click();
  await expect(page.getByRole("heading", { name: "Add trading pair" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Supported symbols" })).toBeVisible();
  await page.screenshot({ path: `${screenshots}/catalog-en-dark-1440.png`, fullPage: true });
});

test("trader cannot see or force-open the administration page", async ({ page }) => {
  await register(page, `e2e-catalog-trader-${String(Date.now())}@example.com`);
  await expect(page.getByRole("link", { name: "คู่เทรดที่รองรับ" })).toHaveCount(0);
  await page.goto("/supported-symbols");
  await expect(page).toHaveURL(/\/chart$/);
  const response = await page.request.get("/api/admin/supported-symbols");
  expect(response.status()).toBe(403);
});
