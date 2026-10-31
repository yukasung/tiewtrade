import { mkdirSync } from "node:fs";
import { expect, test } from "./helpers/test";
import { PASSWORD } from "./helpers/totp";
import type { Page } from "@playwright/test";
const control = "http://127.0.0.1:18018/__e2e/risk";
const evidence = "../specs/features/2026-10-25-wallet-risk-limits/evidence/ui";
async function capture(page: Page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0));
  mkdirSync(evidence, { recursive: true });
  await page.screenshot({ path: `${evidence}/${name}.png`, fullPage: true });
}
async function snapshot(page: Page) {
  return await (await page.request.get("/api/paper/risk-limit")).json() as { amount: string | null; loss: string | null; revision: number; latched: boolean; reason: string; stop_id: string | null; target_set_complete: boolean; pending_count: number; current_allowance: string | null };
}
async function register(page: Page) {
  await page.goto("/paper/trade");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`risk-${Date.now()}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
  const identity = await (await page.request.get("/api/auth/me")).json() as { user_id: string };
  expect((await page.request.post(`${control}/prepare`, { data: identity })).status()).toBe(204);
  await page.reload();
  await expect(page.getByRole("link", { name: "ตั้งค่าในหน้าบัญชีเทรด", exact: true })).toBeVisible();
  expect((await snapshot(page)).amount).toBeNull();
  return identity.user_id;
}
async function openTradingAccount(page: Page) {
  await page.getByRole("link", { name: "บัญชีเทรด", exact: true }).click();
  await expect(page).toHaveURL(/\/trading-account$/);
  await expect(page.getByLabel("เพดานขาดทุน (USDT)")).toBeVisible();
}
async function openPaperTrade(page: Page) {
  await page.getByRole("link", { name: "เทรด Paper", exact: true }).click();
  await expect(page).toHaveURL(/\/paper\/trade$/);
  await expect(page.getByLabel("คู่เทรด")).toBeEnabled();
}
async function setLimit(page: Page, amount = "10") {
  await openTradingAccount(page);
  await page.getByLabel("เพดานขาดทุน (USDT)").fill(amount);
  await page.getByRole("button", { name: "บันทึก", exact: true }).click();
  await expect.poll(async () => (await snapshot(page)).amount).toBe(amount);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("READY");
  await openPaperTrade(page);
}
async function submitManual(page: Page) {
  let button = page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true });
  let identity: string | null = null;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await expect(button).toBeEnabled();
    const response = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
    await button.click();
    const result = await response;
    if (result.status() === 202 || result.status() === 200) return await result.json() as { order_id: string; request_id: string };
    expect(await result.json()).toEqual({ detail: "RISK_SOURCE_UNAVAILABLE" });
    const stored = await page.evaluate(() => Object.keys(window.sessionStorage).filter(k => k.startsWith("tiewtrade.manual-order.v1:")).map(k => window.sessionStorage.getItem(k))[0] ?? null);
    if (identity === null) identity = stored;
    expect(stored).toBe(identity);
    await expect.poll(async () => (await (await page.request.get("/api/paper/trade?base=BTC")).json() as { admission_ready: boolean }).admission_ready).toBe(true);
    button = page.getByRole("region", { name: "คำขอและผลการตรวจ", exact: true }).getByRole("button", { name: "ส่งคำขอเดิมอีกครั้ง", exact: true });
  }
  throw new Error("Risk evidence did not remain ready for intake with the same key");
}
async function send(page: Page, amount: string) {
  await page.getByLabel("งบซื้อ (USDT)").fill(amount);
  return submitManual(page);
}
async function order(page: Page, id: string) {
  return await (await page.request.get(`/api/paper/orders/${id}`)).json() as { status: string; filled_quantity: string; reserved_quote: string; spent_quote: string };
}
test("production risk composition: unset→set→BUY→breach→cancel→bounded SELL→reset→eligible BUY", async ({ page }) => {
  const owner = await register(page); await capture(page, "unset-th-light-desktop");
  await setLimit(page);
  await page.getByLabel("คู่เทรด").selectOption("BTC");
  const buy = await send(page, "110");
  await expect.poll(async () => (await order(page, buy.order_id)).status).toBe("FILLED");
  await expect.poll(async () => page.evaluate(id => window.sessionStorage.getItem("tiewtrade.manual-order.v1:" + id), owner)).toBeNull();
  await page.getByRole("tab", { name: "LIMIT", exact: true }).click();
  await page.getByLabel("จำนวนเหรียญ Base (BTC)").fill("1");
  await page.getByLabel("ราคา Limit (USDT)").fill("90");
  const limit = await submitManual(page);
  await expect.poll(async () => (await order(page, limit.order_id)).status).toBe("ACCEPTED");
  await expect.poll(async () => page.evaluate(id => window.sessionStorage.getItem("tiewtrade.manual-order.v1:" + id), owner)).toBeNull();
  expect((await page.request.post(`${control}/hold-transfer`, { data: { user_id: owner } })).status()).toBe(204);
  await page.getByRole("tab", { name: "MARKET", exact: true }).click();
  const queued = await send(page, "11");
  await expect.poll(async () => (await (await page.request.get(`${control}/transfer-held`)).json() as { held: boolean }).held).toBe(true);
  expect((await page.request.post(`${control}/price`, { data: { amount: "80" } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).latched).toBe(true);
  await expect.poll(async () => {
    const receipt = await (await page.request.get(`/api/paper/order-requests/${queued.request_id}`)).json() as { intake_state: string; intake_failure_code: string | null; command_id: string | null };
    return { state: receipt.intake_state, failure: receipt.intake_failure_code, command: receipt.command_id };
  }).toEqual({ state: "REJECTED", failure: "ORDER_SAFETY_UNAVAILABLE", command: null });
  expect((await page.request.get(`/api/paper/orders/${queued.order_id}`)).status()).toBe(404);
  expect((await page.request.post(`${control}/release-transfer`)).status()).toBe(204);
  await expect.poll(async () => (await order(page, limit.order_id)).status, { timeout: 60_000 }).toBe("CANCELED");
  expect((await order(page, limit.order_id)).reserved_quote).toBe("0");
  await expect.poll(async () => { const risk = await snapshot(page); return risk.target_set_complete && risk.pending_count === 0; }).toBe(true);
  await expect(page.getByRole("alert").filter({ hasText: "สถานะหยุดความเสี่ยง" })).toBeVisible();
  await capture(page, "breached-th-light-desktop");
  await page.getByRole("tab", { name: "MARKET", exact: true }).click();
  await page.getByRole("tab", { name: "SELL", exact: true }).click();
  await page.getByLabel("จำนวนเหรียญ Base (BTC)").fill("0.1");
  await expect(page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true })).toBeEnabled();
  const selling = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true }).click();
  const sell = await (await selling).json() as { order_id: string };
  await expect.poll(async () => (await order(page, sell.order_id)).status).toBe("FILLED");
  await openTradingAccount(page);
  await expect(page.getByRole("button", { name: "รีเซ็ตการนับขาดทุน", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "รีเซ็ตการนับขาดทุน", exact: true }).click();
  await expect(page.getByRole("dialog").getByText(/สถานะที่ถือยังเปิดอยู่/)).toBeVisible();
  await expect(page.getByRole("dialog").getByLabel("รหัสปัจจุบันจากแอปยืนยันตัวตน")).toHaveCount(0);
  await page.getByRole("dialog").getByRole("button", { name: "ยืนยัน", exact: true }).click();
  await expect.poll(async () => (await snapshot(page)).latched).toBe(false);
  expect((await snapshot(page)).loss).toBe("0");
  expect((await snapshot(page)).current_allowance).not.toBe("0");
  await openPaperTrade(page);
  await page.getByLabel("คู่เทรด").selectOption("BTC");
  await page.getByRole("tab", { name: "BUY", exact: true }).click();
  const resumed = await send(page, "11");
  await expect.poll(async () => (await order(page, resumed.order_id)).status).toBe("FILLED");
  const trade = await (await page.request.get("/api/paper/trade?base=BTC")).json() as { wallet: { balance: string; base_balances: { asset: string; held: string }[] } };
  // Independent cash/quantity oracle: 10000−110+(0.1×99×0.999)−11;
  // received base: 1.1×0.999−0.1+0.11×0.999.
  expect(trade.wallet.balance).toBe("9888.8901");
  expect(trade.wallet.base_balances.find(row => row.asset === "BTC")?.held).toBe("1.10879");
  expect((await snapshot(page)).loss).toBe("2.2088");
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await capture(page, "reset-th-dark-desktop");
  await page.setViewportSize({ width: 375, height: 844 }); await capture(page, "reset-th-dark-mobile");
  await page.setViewportSize({ width: 768, height: 1024 }); await capture(page, "reset-th-dark-tablet");
  await page.evaluate(async () => {
    const source = "/src/riskLimitMessages.ts";
    const messages = await import(/* @vite-ignore */ source) as { riskLimitI18n: { changeLanguage: (language: string) => Promise<unknown> } };
    await messages.riskLimitI18n.changeLanguage("en");
  });
  await page.getByRole("link", { name: "บัญชีเทรด", exact: true }).click();
  await expect(page.getByLabel("Loss limit (USDT)")).toBeVisible();
  await capture(page, "reset-en-dark-tablet");
  await page.evaluate(() => document.documentElement.classList.remove("dark"));
  await page.setViewportSize({ width: 1440, height: 1000 }); await capture(page, "reset-en-light-desktop");
  await page.getByRole("link", { name: "เทรด Live", exact: true }).click();
  await expect(page.getByText(/Live ยังไม่พร้อมใช้งาน/)).toBeVisible();
  await expect(page.getByRole("button", { name: "ไม่พร้อมใช้งาน", exact: true })).toBeDisabled();
});
test("UNKNOWN reload keeps the same risk key and no optimistic setting is shown", async ({ page }) => {
  await register(page);
  let committed: { idempotency_key: string } | undefined;
  let posts = 0;
  await page.route("**/api/paper/risk-limit", async route => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1;
    const result = await route.fetch(); committed = await result.json() as typeof committed;
    await route.abort("connectionreset");
  });
  await setLimit(page, "100");
  await expect.poll(() => committed?.idempotency_key).toBeTruthy();
  await page.unroute("**/api/paper/risk-limit");
  await page.reload();
  await openTradingAccount(page);
  await expect.poll(() => page.evaluate(() => Object.keys(window.sessionStorage).filter(k => k.startsWith("tiewtrade.risk-limit.v1:")).length)).toBe(0);
  expect(posts).toBe(1);
  expect((await snapshot(page)).revision).toBe(1);
  expect((await page.request.get(`/api/paper/risk-limit/requests/by-key/${committed!.idempotency_key}`)).status()).toBe(200);
});

test("Paper increase survives API disconnect and replays the same request without TOTP", async ({ page }) => {
  const owner = await register(page);
  await setLimit(page, "100");
  await openTradingAccount(page);
  expect((await page.request.post(`${control}/disconnect-intake`, { data: { user_id: owner } })).status()).toBe(204);
  await page.getByLabel("เพดานขาดทุน (USDT)").fill("200");
  const disconnected = page.waitForResponse(response =>
    response.url().endsWith("/api/paper/risk-limit/increase") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "บันทึก", exact: true }).click();
  expect((await disconnected).status()).toBe(503);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect((await snapshot(page)).amount).toBe("100");
  await page.reload();
  await expect(page.getByLabel("เพดานขาดทุน (USDT)")).toHaveValue("200");
  const retry = page.waitForRequest(r => r.url().endsWith("/api/paper/risk-limit/increase") && r.method() === "POST");
  const save = page.getByRole("button", { name: "บันทึก", exact: true });
  await expect(save).toBeEnabled();
  await save.click();
  expect((await retry).headers()["x-tiewtrade-totp"]).toBeUndefined();
  await expect.poll(async () => (await snapshot(page)).amount).toBe("200");
  expect((await snapshot(page)).revision).toBe(2);
});

test("price outage blocks opening; risk-only cache failure preserves bounded reduction and correction replay", async ({ page }) => {
  const owner = await register(page);
  expect((await page.request.post(`${control}/price`, { data: { amount: "110", connected: true } })).status()).toBe(204);
  await setLimit(page, "1000");
  await page.getByLabel("คู่เทรด").selectOption("BTC");
  const buy = await send(page, "110");
  await expect.poll(async () => (await order(page, buy.order_id)).status).toBe("FILLED");
  await expect.poll(async () => page.evaluate(id => window.sessionStorage.getItem("tiewtrade.manual-order.v1:" + id), owner)).toBeNull();
  expect((await page.request.post(`${control}/price`, { data: { amount: "110", connected: false } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("RISK_PRICE_UNAVAILABLE");
  await expect(page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true })).toBeDisabled();
  expect((await snapshot(page)).loss).toBeNull();
  await capture(page, "price-pause-th-light-desktop");
  expect((await page.request.post(`${control}/price`, { data: { amount: "110", connected: true } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("READY");
  expect((await page.request.post(`${control}/cache-gap`, { data: { user_id: owner } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("RISK_SOURCE_UNAVAILABLE");
  await expect(page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true })).toBeDisabled();
  await page.getByRole("tab", { name: "SELL", exact: true }).click();
  await page.getByLabel("จำนวนเหรียญ Base (BTC)").fill("0.1");
  const sell = await submitManual(page);
  await expect.poll(async () => (await order(page, sell.order_id)).status).toBe("FILLED");
  expect((await snapshot(page)).loss).toBeNull();
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const corrected = await page.request.post(`${control}/replay-correction`, { data: { user_id: owner } });
    expect(corrected.ok()).toBe(true);
    expect(await corrected.json()).toEqual({ unchanged_cash: true, records: 2, replacements: 1, fill_events: 2 });
  }
  expect((await page.request.post(`${control}/repair-cache`, { data: { user_id: owner } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("READY");
  await page.reload();
  const trade = await (await page.request.get("/api/paper/trade?base=BTC")).json() as { wallet: { balance: string; base_balances: { asset: string; held: string }[] } };
  expect(trade.wallet.balance).toBe("9899.8901");
  expect(trade.wallet.base_balances.find(row => row.asset === "BTC")?.held).toBe("0.9989");
  // F14 allocates released cost AWAY_FROM_ZERO: 11/1.0989 → 10.010010010010010011.
  expect((await snapshot(page)).loss).toBe("0.119910010010010011");
  expect((await order(page, buy.order_id)).filled_quantity).toBe("1.1");
});
