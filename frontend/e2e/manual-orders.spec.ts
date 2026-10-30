import { mkdirSync } from "node:fs";
import { expect, test } from "./helpers/test";
import type { Page } from "@playwright/test";
import { PASSWORD } from "./helpers/totp";
const api = "http://127.0.0.1:18016/__e2e/manual";
const evidence = "../specs/features/2026-10-25-manual-order-entry/evidence/ui";
async function capture(page: Page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0));
  mkdirSync(evidence, { recursive: true });
  await page.screenshot({ path: `${evidence}/${name}`, fullPage: true });
}
async function register(page: Page, email = `manual-${Date.now()}@example.com`) {
  await page.goto("/paper/trade");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
  const identity = await (await page.request.get("/api/auth/me")).json() as { user_id: string };
  expect((await page.request.post(`${api}/prepare`, { data: identity })).status()).toBe(204);
  await page.reload();
  await expect(page.getByLabel("คู่เทรด")).toBeEnabled();
  await page.getByLabel("คู่เทรด").selectOption("BTC");
  return identity.user_id;
}
async function fresh(page: Page) {
  expect((await page.request.post(`${api}/source`)).status()).toBe(204);
  await page.reload();
  await expect(page.getByLabel("คู่เทรด")).toBeEnabled();
  await page.getByLabel("คู่เทรด").selectOption("BTC");
}
async function send(page: Page, amount: string, refresh = true) {
  if (refresh) await fresh(page);
  await page.getByLabel(/งบซื้อ|จำนวนเหรียญ Base/).fill(amount);
  const response = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true }).click();
  const result = await response; expect(result.status()).toBe(202);
  return await result.json() as { request_id: string; order_id: string; idempotency_key: string };
}
async function drive(page: Page, owner: string, request: string, fill = false) {
  const response = await page.request.post(`${api}/drive`, { data: { user_id: owner, request_id: request, fill } });
  expect(response.ok()).toBe(true);
  return await response.json() as { commands: number; order_state: string | null; command_state: string; failure: string | null };
}
async function waitResolved(page: Page) {
  await expect.poll(() => page.evaluate(() => Object.keys(window.sessionStorage).filter(k => k.startsWith("tiewtrade.manual-order.v1:")).length)).toBe(0);
}
test("real Paper MARKET BUY/SELL and LIMIT partial→cancel reconcile exact server state", async ({ page }) => {
  const owner = await register(page);
  const buy = await send(page, "1100");
  expect(await drive(page, owner, buy.request_id, true)).toMatchObject({ commands: 1, order_state: "FILLED" });
  await waitResolved(page);
  await fresh(page);
  await expect(page.getByText("8,900 USDT", { exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "SELL", exact: true }).click();
  await expect(page.getByRole("tab", { name: "SELL", exact: true })).toHaveAttribute("aria-selected", "true");
  const sell = await send(page, "1", false);
  expect(await drive(page, owner, sell.request_id, true)).toMatchObject({ commands: 1, order_state: "FILLED" });
  await waitResolved(page);
  await fresh(page);
  await page.getByRole("tab", { name: "BUY", exact: true }).click();
  await page.getByRole("tab", { name: "LIMIT", exact: true }).click();
  await expect(page.getByRole("tab", { name: "LIMIT", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.getByLabel("ราคา Limit (USDT)").fill("100");
  const limit = await send(page, "11", false);
  expect(await drive(page, owner, limit.request_id, true)).toMatchObject({ commands: 1, order_state: "PARTIALLY_FILLED" });
  await waitResolved(page);
  await fresh(page);
  const orderResponse = await page.request.get(`/api/paper/orders/${limit.order_id}`);
  const order = await orderResponse.json() as { status: string; filled_quantity: string; remaining_quantity: string; reserved_quote: string };
  expect(order).toMatchObject({ status: "PARTIALLY_FILLED", filled_quantity: "10", remaining_quantity: "1", reserved_quote: "100" });
  const row = page.getByRole("row").filter({ hasText: "จับคู่บางส่วน" });
  await expect(row).toHaveCount(1);
  const response = page.waitForResponse(r => r.url().endsWith(`/orders/${limit.order_id}/cancel`) && r.request().method() === "POST");
  await row.getByRole("button", { name: "ขอยกเลิก", exact: true }).click();
  const cancel = await (await response).json() as { request_id: string };
  expect(await drive(page, owner, cancel.request_id)).toMatchObject({ commands: 1, order_state: "CANCELED" });
  await waitResolved(page);
  await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "ยกเลิกแล้ว" })).toHaveCount(1);
  const final = await (await page.request.get(`/api/paper/orders/${limit.order_id}`)).json() as { reserved_quote: string; filled_quantity: string };
  expect(final.reserved_quote).toBe("0"); expect(final.filled_quantity).toBe("10");
  mkdirSync(evidence, { recursive: true });
  await capture(page, "paper-th-light-desktop.png");
  await expect(page.getByRole("button", { name: "รายละเอียดออเดอร์" })).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 844 });
  const table = page.getByRole("table");
  await expect.poll(() => table.evaluate(node => node.scrollWidth > node.parentElement!.clientWidth)).toBe(true);
  await capture(page, "paper-th-light-mobile.png");
});
test("receipt loss→reload→discovery preserves identity and Live never mutates Paper", async ({ page }) => {
  const owner = await register(page);
  let committed: { request_id: string; order_id: string; idempotency_key: string } | undefined;
  let posts = 0;
  page.on("request", request => { if (request.url().endsWith("/api/paper/orders") && request.method() === "POST") posts += 1; });
  await page.route("**/api/paper/orders", async route => {
    if (route.request().method() !== "POST") return route.continue();
    const response = await route.fetch();
    committed = await response.json() as typeof committed;
    await route.abort("connectionreset");
  });
  await fresh(page); await page.getByLabel("งบซื้อ (USDT)").fill("100000");
  await page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true }).click();
  await expect.poll(() => committed?.request_id).toBeTruthy();
  expect(posts).toBe(1);
  await page.unroute("**/api/paper/orders");
  await page.route("**/api/paper/order-requests/by-key/**", route => route.fulfill({ status: 404, contentType: "application/json", body: '{"detail":"MANUAL_REQUEST_NOT_FOUND"}' }));
  await page.reload();
  await expect(page.getByText(committed!.order_id, { exact: false }).first()).toBeVisible();
  expect(posts).toBe(1);
  const retried = page.waitForResponse(response => response.url().endsWith("/api/paper/orders") && response.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งคำขอเดิมอีกครั้ง" }).click();
  const replay = await retried; expect(replay.status()).toBe(200);
  expect(await replay.json()).toMatchObject({ request_id: committed!.request_id, idempotency_key: committed!.idempotency_key });
  expect(posts).toBe(2);
  await page.unroute("**/api/paper/order-requests/by-key/**");
  expect(await drive(page, owner, committed!.request_id)).toMatchObject({ commands: 1, command_state: "REJECTED", order_state: null, failure: "ORDER_INSUFFICIENT_FUNDS" });
  await waitResolved(page);
  await expect(page.getByText("เหตุปฏิเสธ: ยอดใช้ได้ไม่เพียงพอ")).toBeVisible();
  const missing = await page.request.get(`/api/paper/orders/${committed!.order_id}`); expect(missing.status()).toBe(404);
  await page.getByRole("link", { name: "เทรด Live", exact: true }).click();
  await expect(page).toHaveURL(/\/live\/trade$/);
  await expect(page.getByText(/Live ยังไม่พร้อมใช้งาน/)).toBeVisible();
  await expect(page.getByRole("button", { name: "ไม่พร้อมใช้งาน", exact: true })).toBeDisabled();
  await page.reload(); await expect(page).toHaveURL(/\/live\/trade$/);
  expect(posts).toBe(2);
  await page.goBack(); await expect(page).toHaveURL(/\/paper\/trade$/);
  await page.goForward(); await expect(page).toHaveURL(/\/live\/trade$/);
  expect(posts).toBe(2);
  await page.goBack(); await expect(page).toHaveURL(/\/paper\/trade$/);
  mkdirSync(evidence, { recursive: true });
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await capture(page, "paper-th-dark-desktop.png");
});
test("logout clears the local journal; login rediscovers the owner's pending request", async ({ page }) => {
  const email = `manual-session-${Date.now()}@example.com`;
  const owner = await register(page, email);
  const recorded = await send(page, "100");
  await page.getByRole("link", { name: "บัญชี", exact: true }).click();
  await page.getByTestId("log-out").click();
  await expect(page.getByTestId("signed-out")).toBeVisible();
  await expect.poll(() => page.evaluate(() => Object.keys(window.sessionStorage).filter(k => k.startsWith("tiewtrade.manual-order.v1:")).length)).toBe(0);
  const other = await register(page);
  expect(other).not.toBe(owner);
  expect((await page.request.get(`/api/paper/order-requests/${recorded.request_id}`)).status()).toBe(404);
  await expect(page.getByText(recorded.order_id, { exact: false })).toBeHidden();
  await page.getByRole("link", { name: "บัญชี", exact: true }).click();
  await page.getByTestId("log-out").click();
  await expect(page.getByTestId("signed-out")).toBeVisible();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("signed-in")).toBeVisible();
  await page.getByRole("link", { name: "เทรด Paper", exact: true }).click();
  await expect(page.getByText(recorded.order_id, { exact: false })).toBeVisible();
  expect(await drive(page, owner, recorded.request_id)).toMatchObject({ commands: 1, order_state: "ACCEPTED" });
  await expect(page.getByRole("row").filter({ hasText: "รับออเดอร์แล้ว" })).toHaveCount(1);
  // English/dark is driven through the established message layer, with no new language UI.
  await page.evaluate(async () => {
    const path = "/src/manualOrderMessages.ts";
    const messages = await import(/* @vite-ignore */ path) as { manualOrderI18n: { changeLanguage: (value: string) => Promise<unknown> } };
    await messages.manualOrderI18n.changeLanguage("en");
    const accountPath = "/src/accountMessages.ts";
    const account = await import(/* @vite-ignore */ accountPath) as { accountI18n: { changeLanguage: (value: string) => Promise<unknown> } };
    await account.accountI18n.changeLanguage("en");
    document.documentElement.classList.add("dark");
  });
  await page.setViewportSize({ width: 375, height: 844 });
  await expect(page.getByLabel("Paper trading", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.getByRole("heading", { name: "Manual order", exact: true })).toBeVisible();
  mkdirSync(evidence, { recursive: true });
  await capture(page, "paper-en-dark-desktop.png");
  await page.evaluate(() => document.documentElement.classList.remove("dark"));
  await capture(page, "paper-en-light-desktop.png");
  await page.setViewportSize({ width: 375, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await capture(page, "paper-en-light-mobile.png");
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await capture(page, "paper-en-dark-mobile.png");
  await page.evaluate(async () => {
    const path = "/src/manualOrderMessages.ts";
    const messages = await import(/* @vite-ignore */ path) as { manualOrderI18n: { changeLanguage: (value: string) => Promise<unknown> } };
    await messages.manualOrderI18n.changeLanguage("th");
    const accountPath = "/src/accountMessages.ts";
    const account = await import(/* @vite-ignore */ accountPath) as { accountI18n: { changeLanguage: (value: string) => Promise<unknown> } };
    await account.accountI18n.changeLanguage("th");
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.getByLabel("เทรด Paper", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 844 });
  await capture(page, "paper-th-dark-mobile.png");
});
test("browser storage denial blocks the POST before transmission", async ({ page }) => {
  await register(page);
  let posts = 0;
  page.on("request", request => { if (request.url().endsWith("/api/paper/orders") && request.method() === "POST") posts += 1; });
  await page.evaluate(() => {
    const original = Object.getOwnPropertyDescriptor(Storage.prototype, "setItem")!.value as (this: Storage, key: string, value: string) => void;
    Storage.prototype.setItem = function(key: string, value: string) {
      if (key.startsWith("tiewtrade.manual-order.v1:")) throw new DOMException("denied", "SecurityError");
      original.call(this, key, value);
    };
  });
  await fresh(page); await page.getByLabel("งบซื้อ (USDT)").fill("100");
  await page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true }).click();
  await expect(page.getByText("ใช้พื้นที่กู้คืนคำขอไม่ได้ จึงยังส่งคำขอใหม่ไม่ได้")).toBeVisible();
  expect(posts).toBe(0);
});
test("a cancel racing a fill shows FILLED and reset cannot cross pending intake", async ({ page }) => {
  const owner = await register(page);
  const order = await send(page, "100");
  const envelope = await (await page.request.get("/api/paper-wallet")).json() as { wallet: { episode_id: string } };
  const csrf = (await page.context().cookies()).find(cookie => cookie.name === "tiewtrade_csrf")!.value;
  const reset = await page.request.post("/api/paper-wallet/reset", { data: { initial_capital: "5000", expected_episode_id: envelope.wallet.episode_id }, headers: { "X-CSRF-Token": csrf, "Idempotency-Key": globalThis.crypto.randomUUID() } });
  expect(reset.status()).toBe(202);
  const resetCommand = await reset.json() as { command_id: string };
  // The dedicated harness processes the real wallet worker; it must reject the reset.
  expect((await page.request.post(`${api}/wallet-round`)).status()).toBe(204);
  const resetResult = await (await page.request.get(`/api/paper-wallet/commands/${resetCommand.command_id}`)).json() as { state: string; failure_code: string };
  expect(resetResult).toMatchObject({ state: "REJECTED", failure_code: "RESET_UNSAFE" });
  expect(await drive(page, owner, order.request_id)).toMatchObject({ commands: 1, order_state: "ACCEPTED" });
  await waitResolved(page);
  const row = page.getByRole("row").filter({ hasText: "รับออเดอร์แล้ว" });
  await expect(row).toHaveCount(1);
  const response = page.waitForResponse(r => r.url().endsWith(`/orders/${order.order_id}/cancel`) && r.request().method() === "POST");
  await row.getByRole("button", { name: "ขอยกเลิก", exact: true }).click();
  const cancel = await (await response).json() as { request_id: string };
  expect(await drive(page, owner, order.request_id, true)).toMatchObject({ commands: 1, order_state: "FILLED" });
  expect(await drive(page, owner, cancel.request_id)).toMatchObject({ commands: 1, command_state: "SUCCEEDED", order_state: "FILLED" });
  await waitResolved(page);
  await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
  await expect(page.getByRole("row").filter({ hasText: "จับคู่ครบ" })).toHaveCount(1);
  await expect(page.getByRole("row").filter({ hasText: "ยกเลิกแล้ว" })).toHaveCount(0);
});
test("DB connection loss before intake commit rolls back and same-key recovery creates one command", async ({ page }) => {
  const owner = await register(page);
  expect((await page.request.post(`${api}/disconnect-before-commit`, { data: { user_id: owner } })).status()).toBe(204);
  await fresh(page); await page.getByLabel("งบซื้อ (USDT)").fill("100");
  const failed = page.waitForResponse(response => response.url().endsWith("/api/paper/orders") && response.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true }).click();
  expect((await failed).status()).toBe(503);
  expect(await (await page.request.get(`${api}/disconnect-result`)).json()).toEqual({ result: "CONNECTION_TERMINATED" });
  await expect(page.getByText("UNKNOWN — ยังยืนยันผลไม่ได้ ตรวจสถานะหรือส่งซ้ำด้วย key เดิม")).toBeVisible();
  const attempt = await page.evaluate(() => {
    const raw = Object.keys(window.sessionStorage).find(key => key.startsWith("tiewtrade.manual-order.v1:"))!;
    return JSON.parse(window.sessionStorage.getItem(raw)!) as { key: string; payload: { expected_episode_id: string } };
  });
  expect((await page.request.get(`/api/paper/order-requests/by-key/${attempt.key}?action=NEW`)).status()).toBe(404);
  const before = await (await page.request.get(`/api/paper/orders?episode_id=${attempt.payload.expected_episode_id}`)).json() as { orders: unknown[] };
  expect(before.orders).toHaveLength(0);
  const replayed = page.waitForResponse(response => response.url().endsWith("/api/paper/orders") && response.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งคำขอเดิมอีกครั้ง" }).click();
  const retry = await replayed; expect(retry.status()).toBe(202);
  const receipt = await retry.json() as { request_id: string; idempotency_key: string };
  expect(receipt.idempotency_key).toBe(attempt.key);
  expect(await drive(page, owner, receipt.request_id, true)).toMatchObject({ commands: 1, order_state: "FILLED" });
  await waitResolved(page);
});

test("reset replaces an unsent draft and a lost closed-episode refusal recovers with the same key", async ({ page }) => {
  await register(page);
  async function reset() {
    const wallet = (await (await page.request.get("/api/paper-wallet")).json() as { wallet: { episode_id: string } }).wallet;
    const csrf = (await page.context().cookies()).find(cookie => cookie.name === "tiewtrade_csrf")!.value;
    const response = await page.request.post("/api/paper-wallet/reset", { data: { initial_capital: "5000", expected_episode_id: wallet.episode_id }, headers: { "X-CSRF-Token": csrf, "Idempotency-Key": globalThis.crypto.randomUUID() } });
    expect(response.status()).toBe(202);
    const command = await response.json() as { command_id: string };
    expect((await page.request.post(`${api}/wallet-round`)).status()).toBe(204);
    expect(await (await page.request.get(`/api/paper-wallet/commands/${command.command_id}`)).json()).toMatchObject({ state: "SUCCEEDED" });
  }
  await fresh(page);
  await page.getByLabel("งบซื้อ (USDT)").fill("100");
  await reset();
  await fresh(page);
  await expect(page.getByLabel("งบซื้อ (USDT)")).toHaveValue("");
  let original: string | null = null;
  let originalKey: string | undefined;
  let refusalLost = false;
  await page.route("**/api/paper/orders", async route => {
    original = route.request().postData();
    originalKey = route.request().headers()["idempotency-key"];
    // Reset wins while the browser's exact request is already in flight.
    await reset();
    const response = await route.fetch();
    expect(response.status()).toBe(409);
    expect(await response.json()).toEqual({ detail: "MANUAL_ORDER_EPISODE_CLOSED" });
    await route.abort("connectionreset");
    refusalLost = true;
  });
  await page.getByLabel("งบซื้อ (USDT)").fill("100");
  await page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true }).click();
  await expect(page.getByText(/UNKNOWN —/)).toBeVisible();
  await expect.poll(() => refusalLost).toBe(true);
  await page.unroute("**/api/paper/orders");
  await page.reload();
  await expect(page.getByText(/UNKNOWN —/)).toBeVisible();
  const retried = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งคำขอเดิมอีกครั้ง" }).click();
  const response = await retried;
  expect(response.status()).toBe(409);
  expect(response.request().postData()).toBe(original);
  expect(response.request().headers()["idempotency-key"]).toBe(originalKey);
  await expect(page.getByText(/คำขอนี้ไม่ได้ถูกบันทึก เพราะ episode ปิดแล้ว/)).toBeVisible();
  await waitResolved(page);
  expect((await page.request.get(`/api/paper/order-requests/by-key/${originalKey}?action=NEW`)).status()).toBe(404);
  await expect(page.getByLabel("คู่เทรด")).toBeEnabled();
  await expect(page.getByLabel("งบซื้อ (USDT)")).toHaveValue("");
});
