import { mkdirSync } from "node:fs";
import { expect, test } from "./helpers/test";
import type { Page } from "@playwright/test";
import { PASSWORD } from "./helpers/totp";
const api = "http://127.0.0.1:18017/__e2e/manual";
const evidence = "../specs/features/2026-11-02-tp-sl/evidence/manual-acceptance-fix/ui";
async function setLanguage(page: Page, locale: "th" | "en") {
  await page.evaluate(async language => {
    const path = "/src/manualOrderMessages.ts";
    const messages = await import(/* @vite-ignore */ path) as { manualOrderI18n: { changeLanguage: (value: string) => Promise<unknown> } };
    await messages.manualOrderI18n.changeLanguage(language);
  }, locale);
}
async function capture(page: Page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0));
  mkdirSync(evidence, { recursive: true });
  await page.screenshot({ path: `${evidence}/${name}`, fullPage: true });
}
async function reloadPaperPair(page: Page) {
  // Arm before reload: the chart can select BTC before the selector is ready.
  const snapshot = page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.pathname === "/api/paper/trade" && url.searchParams.get("base") === "BTC" &&
      response.request().method() === "GET";
  });
  await page.reload();
  await expect(page.getByLabel("คู่เทรด")).toBeEnabled();
  await page.getByLabel("คู่เทรด").selectOption("BTC");
  const response = await snapshot;
  expect(response.status()).toBe(200);
  const data: unknown = await response.json();
  expect(data).toMatchObject({ mode: "PAPER", base: "BTC", wallet: {
    wallet_id: expect.any(String), episode_id: expect.any(String),
  } });
  // The wallet scope must render before filling: its first arrival remounts the form.
  await expect(page.locator('[aria-labelledby="manual-form-heading"] dl > div').first()
    .locator("dd .market-value")).toBeVisible();

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
  await reloadPaperPair(page);
  return identity.user_id;
}
async function fresh(page: Page) {
  expect((await page.request.post(`${api}/source`)).status()).toBe(204);
  await reloadPaperPair(page);
}
async function submitPaperOrder(page: Page) {
  const submit = page.getByRole("button", { name: "ส่งออเดอร์ Paper", exact: true });
  await expect(submit).toBeEnabled();
  await submit.click();
}
async function send(page: Page, amount: string, refresh = true) {
  if (refresh) await fresh(page);
  await page.getByLabel(/งบซื้อ|จำนวนเหรียญ Base/).fill(amount);
  const response = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
  await submitPaperOrder(page);
  const result = await response; expect(result.status()).toBe(202);
  return await result.json() as { request_id: string; order_id: string; idempotency_key: string };
}
async function drive(page: Page, owner: string, request: string, fill = false) {
  const response = await page.request.post(`${api}/drive`, { data: { user_id: owner, request_id: request, fill } });
  expect(response.ok()).toBe(true);
  return await response.json() as { commands: number; order_state: string | null; command_state: string; failure: string | null };
}
async function protectionDraft(page: Page, quantity: string, tp: string, sl: string) {
  await page.locator('[aria-labelledby="trading-activity-heading"]').getByRole("button", { name: "ตั้ง TP/SL ให้เหรียญที่ถือ", exact: true }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("จำนวนเหรียญ (BTC)", { exact: true }).fill(quantity);
  await modal.getByLabel("ราคา Take Profit", { exact: true }).fill(tp);
  await modal.getByLabel("ราคา Stop Loss", { exact: true }).fill(sl);
  return modal;
}
async function waitResolved(page: Page) {
  await expect.poll(() => page.evaluate(() => Object.keys(window.sessionStorage).filter(k => k.startsWith("tiewtrade.manual-order.v1:")).length)).toBe(0);
}
test("bracket fill, reload, replace and cancel use durable production requests", async ({ page }) => {
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/enable")).status()).toBe(204);
  const owner = await register(page);
  await page.getByLabel("ราคา Take Profit", { exact: true }).fill("110");
  await page.getByLabel("ราคา Stop Loss", { exact: true }).fill("90");
  const entry = await send(page, "100", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "FILLED" });
  const tick = async () => {
    const response = await page.request.post("http://127.0.0.1:18017/__e2e/protections/drive", { data: { user_id: owner } });
    expect(response.ok(), await response.text()).toBe(true);
  };
  await tick(); await page.reload();
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  await expect(panel.getByText("กำลังเฝ้าราคา", { exact: true })).toBeVisible();
  await expect(panel.getByText("0.999 BTC", { exact: true })).toHaveCount(2);
  await capture(page, "paper-th-desktop-armed.png");
  await panel.getByRole("button", { name: "แก้ไข", exact: true }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("ราคา Take Profit", { exact: true }).fill("120");
  const receipt = page.waitForResponse(r => r.url().includes("/replace") && r.request().method() === "POST");
  await modal.getByRole("button", { name: "บันทึก", exact: true }).click();
  expect((await receipt).status()).toBe(202);
  await tick();
  await expect(panel.getByText("120 USDT", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 844 });
  await capture(page, "paper-th-mobile-armed.png");
  const cancel = page.waitForResponse(r => r.url().includes("/protections/") && r.url().endsWith("/cancel"));
  await panel.getByRole("button", { name: "ยกเลิกการป้องกัน", exact: true }).click();
  expect((await cancel).status()).toBe(202); await tick();
  await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
  await expect(panel.getByText("ยกเลิกการป้องกันแล้ว", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
  await expect(panel.getByText("ยกเลิกการป้องกันแล้ว", { exact: true })).toBeVisible();
});

test("lost protection receipt and reload recover the same server request", async ({ page }) => {
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/enable")).status()).toBe(204);
  const owner = await register(page);
  const entry = await send(page, "100", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "FILLED" });
  await waitResolved(page); await fresh(page);
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  const modal = await protectionDraft(page, "0.2", "", "90");
  let committed: { request_id: string; idempotency_key: string } | undefined;
  let posts = 0;
  await page.route("**/api/paper/protections", async route => {
    if (route.request().method() !== "POST") return route.continue();
    posts += 1;
    const response = await route.fetch();
    expect(response.status()).toBe(202);
    committed = await response.json() as typeof committed;
    await route.abort("connectionreset");
  });
  await modal.getByRole("button", { name: "บันทึก", exact: true }).click();
  await expect.poll(() => committed?.request_id).toBeTruthy();
  await page.unroute("**/api/paper/protections");
  await page.reload();
  await expect(panel.getByText("มีคำขอที่กำลังดำเนินการ", { exact: true })).toBeVisible();
  expect(posts).toBe(1);
  const lookup = await page.request.get(`/api/paper/protection-requests/by-key/${committed!.idempotency_key}?action=CREATE`);
  expect(await lookup.json()).toMatchObject({ request_id: committed!.request_id, state: "PENDING" });
  const tick = await page.request.post("http://127.0.0.1:18017/__e2e/protections/drive", { data: { user_id: owner } });
  expect(tick.ok(), await tick.text()).toBe(true);
  await expect(panel.getByText("กำลังเฝ้าราคา", { exact: true })).toBeVisible();
  await expect(panel.getByText("0.2 BTC", { exact: true })).toHaveCount(2);
  expect(posts).toBe(1);
});

test("protection controls support Thai and English keyboard focus; Live sends no mutation", async ({ page }) => {
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/enable")).status()).toBe(204);
  const owner = await register(page);
  await page.getByLabel("ราคา Take Profit", { exact: true }).fill("110");
  await page.getByLabel("ราคา Stop Loss", { exact: true }).fill("90");
  const entry = await send(page, "100", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "FILLED" });
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/drive", { data: { user_id: owner } })).ok()).toBe(true);
  await page.reload();
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  await expect(panel.getByText("กำลังเฝ้าราคา", { exact: true })).toBeVisible();
  const mutations: string[] = [];
  page.on("request", request => {
    if (request.method() === "POST" && /\/api\/(paper|live)\/(protections|orders)/.test(request.url())) mutations.push(request.url());
  });
  for (const locale of ["th", "en"] as const) {
    await setLanguage(page, locale);
    const english = locale === "en";
    const edit = panel.getByRole("button", { name: english ? "Edit" : "แก้ไข", exact: true });
    await expect(edit).toBeEnabled();
    await edit.focus(); await page.keyboard.press("Enter");
    const modal = page.getByRole("dialog", { name: english ? "Edit" : "แก้ไข", exact: true });
    await expect(modal).toHaveAttribute("aria-modal", "true");
    const quantity = modal.getByLabel(english ? "Quantity (BTC)" : "จำนวนเหรียญ (BTC)", { exact: true });
    await expect(quantity).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(modal.getByRole("button", { name: english ? "Save" : "บันทึก", exact: true })).toBeFocused();
    await page.keyboard.press("Tab"); await expect(quantity).toBeFocused();
    for (const label of english ? ["Take profit price", "Stop loss price"] : ["ราคา Take Profit", "ราคา Stop Loss"]) {
      await page.keyboard.press("Tab"); await expect(modal.getByLabel(label, { exact: true })).toBeFocused();
    }
    await capture(page, `paper-${locale}-keyboard-dialog.png`);
    await page.keyboard.press("Escape");
    await expect(modal).toHaveCount(0); await expect(edit).toBeFocused();
  }
  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    for (const dark of [false, true]) {
      await page.evaluate(value => document.documentElement.classList.toggle("dark", value), dark);
      await capture(page, `paper-en-${dark ? "dark" : "light"}-${width}.png`);
    }
  }
  await page.goto("/live/trade");
  await setLanguage(page, "en");
  await expect(page.getByText("Live trading is unavailable. No order will be sent. Manage any existing Live orders directly at your exchange.", { exact: true })).toBeVisible();
  await expect(page.locator('[aria-labelledby="trading-activity-heading"]')).toHaveCount(0);
  expect(mutations).toEqual([]);
  await capture(page, "live-unavailable-mobile.png");
});

test("partial bracket entry triggers one exit, cancels entry remainder and closes with exact cash", async ({ page }) => {
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/enable")).status()).toBe(204);
  const owner = await register(page);
  // Reuse F-16's recorded liquidity-debt precondition for the partial LIMIT fixture.
  const prior = await send(page, "1000", false);
  expect(await drive(page, owner, prior.request_id, true)).toMatchObject({ order_state: "FILLED" });
  await waitResolved(page); await fresh(page);
  await page.getByRole("tab", { name: "LIMIT", exact: true }).click();
  await page.getByLabel("ราคา Limit (USDT)", { exact: true }).fill("100");
  await page.getByLabel("ราคา Take Profit", { exact: true }).fill("110");
  await page.getByLabel("ราคา Stop Loss", { exact: true }).fill("90");
  const entry = await send(page, "11", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "PARTIALLY_FILLED" });
  const endpoint = "http://127.0.0.1:18017/__e2e/protections";
  const tick = await page.request.post(`${endpoint}/drive`, { data: { user_id: owner } });
  expect(tick.ok(), await tick.text()).toBe(true);
  await page.reload();
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  await expect(panel.getByText("กำลังเฝ้าราคา", { exact: true })).toBeVisible();
  await expect(panel.getByText("9.99 BTC", { exact: true })).toHaveCount(2);
  await capture(page, "paper-partial-entry-protected.png");
  expect((await page.request.post(`${endpoint}/price`, { data: { user_id: owner, price: "110" } })).status()).toBe(204);
  expect((await page.request.post(`${endpoint}/drive`, { data: { user_id: owner } })).ok()).toBe(true);
  await expect(panel.getByText("กำลังดำเนินคำสั่งปิด", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: "แก้ไข", exact: true })).toBeDisabled();
  await expect(panel.getByRole("button", { name: "ยกเลิกการป้องกัน", exact: true })).toBeDisabled();
  const settle = await page.request.post(`${endpoint}/settle`, { data: { user_id: owner } });
  expect(settle.ok(), await settle.text()).toBe(true);
  const financial = await settle.json() as { balance: string; held: string; reserved: string; exits: number; fills: number; triggers: number; audits: number };
  // Prior BUY1000 leaves9.99 unprotected; bracket BUY10 @100 adds9.99 after fee.
  // Recorded bids are2 @99 then7.99 @1: proceeds205.99 less0.20599 quote fee.
  // MARKET uses both levels; the trigger price is not a guaranteed execution price.
  expect(financial).toMatchObject({ balance: "8205.78401", held: "9.99", reserved: "0", exits: 1, fills: 4, triggers: 1 });
  expect(financial.audits).toBeGreaterThan(0);
  await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
  await expect(panel.getByText("ปิดครบแล้ว", { exact: true })).toBeVisible();
  await panel.getByRole("button", { name: "รายละเอียด", exact: true }).click();
  await expect(page.getByRole("dialog").getByText("0 BTC", { exact: true })).toHaveCount(3);
  await page.keyboard.press("Escape");
  const entryStatus = await page.request.get(`/api/paper/order-requests/${entry.request_id}`);
  expect(await entryStatus.json()).toMatchObject({ order_state: "CANCELED" });
  await page.reload();
  await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
  await expect(panel.getByText("ปิดครบแล้ว", { exact: true })).toBeVisible();
  await capture(page, "paper-partial-entry-closed.png");
  const replay = await page.request.post(`${endpoint}/settle`, { data: { user_id: owner } });
  expect(replay.ok(), await replay.text()).toBe(true);
  expect(await replay.json()).toEqual(financial);
});

test("selected sale reduces two protections once and canceled sale stays unprotected", async ({ page }) => {
  const endpoint = "http://127.0.0.1:18017/__e2e/protections";
  expect((await page.request.post(`${endpoint}/enable`)).status()).toBe(204);
  const owner = await register(page);
  const entry = await send(page, "100", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "FILLED" });
  await waitResolved(page); await fresh(page);
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  for (const [quantity, tp, sl] of [["0.4", "110", "90"], ["0.3", "120", "80"]] as const) {
    await fresh(page);
    const modal = await protectionDraft(page, quantity, tp, sl);
    const receipt = page.waitForResponse(r => r.url().endsWith("/api/paper/protections") && r.request().method() === "POST");
    await modal.getByRole("button", { name: "บันทึก", exact: true }).click();
    expect((await receipt).status()).toBe(202);
    expect((await page.request.post(`${endpoint}/drive`, { data: { user_id: owner } })).ok()).toBe(true);
    await expect(panel.getByText(`${quantity} BTC`, { exact: true })).toHaveCount(2);
    await expect(panel.getByRole("button", { name: "ตั้ง TP/SL ให้เหรียญที่ถือ", exact: true })).toBeEnabled();
  }
  const snapshot = await (await page.request.get("/api/paper/trade?base=BTC")).json() as { wallet: { episode_id: string } };
  const before = await (await page.request.get(`/api/paper/protections?episode_id=${snapshot.wallet.episode_id}`)).json() as { protections: Array<{ protection_id: string; quantity: string }> };
  expect(before.protections).toHaveLength(2);
  await fresh(page);
  await page.getByRole("tab", { name: "SELL", exact: true }).click();
  await page.getByRole("tab", { name: "LIMIT", exact: true }).click();
  await page.getByLabel("ราคา Limit (USDT)", { exact: true }).fill("110");
  for (const group of before.protections) {
    await page.locator(`[id="release-${group.protection_id}"]`).fill(group.quantity === "0.4" ? "0.1" : "0.101");
  }
  await expect(page.getByText("เหรียญส่วนที่เลือกขายจะออกจาก TP/SL เดิม เมื่อยกเลิกขาย ส่วนที่ขายไม่ออกจะไม่มี TP/SL ต้องตั้งใหม่เอง", { exact: true })).toBeVisible();
  const sale = await send(page, "0.5", false);
  expect(await drive(page, owner, sale.request_id)).toMatchObject({ order_state: "ACCEPTED" });
  await waitResolved(page);
  const orderRow = page.getByRole("row").filter({ hasText: "รับออเดอร์แล้ว" });
  await expect(orderRow).toHaveCount(1);
  const cancel = page.waitForResponse(r => r.url().endsWith(`/orders/${sale.order_id}/cancel`) && r.request().method() === "POST");
  await orderRow.getByRole("button", { name: "ขอยกเลิก", exact: true }).click();
  const cancellation = await (await cancel).json() as { request_id: string };
  expect(await drive(page, owner, cancellation.request_id)).toMatchObject({ order_state: "CANCELED" });
  await waitResolved(page); await fresh(page);
  const final = await (await page.request.get("/api/paper/trade?base=BTC")).json() as { wallet: { balance: string; base_balances: Array<{ asset: string; held: string; reserved: string; protection_allocated: string; available: string }> } };
  expect(final.wallet.balance).toBe("9900");
  expect(final.wallet.base_balances.find(row => row.asset === "BTC")).toMatchObject({ held: "0.999", reserved: "0", protection_allocated: "0.499", available: "0.5" });
  await expect(panel.getByText("0.3 BTC", { exact: true })).toHaveCount(2);
  await expect(panel.getByText("0.199 BTC", { exact: true })).toHaveCount(2);
  await capture(page, "paper-two-protections-after-sale-cancel.png");
});


test("failed standalone request warns without selling assets and survives reload", async ({ page }) => {
  const endpoint = "http://127.0.0.1:18017/__e2e/protections";
  expect((await page.request.post(`${endpoint}/enable`)).status()).toBe(204);
  const owner = await register(page);
  const entry = await send(page, "100", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "FILLED" });
  await waitResolved(page); await fresh(page);
  const modal = await protectionDraft(page, "2", "110", "90");
  const receipt = page.waitForResponse(r => r.url().endsWith("/api/paper/protections") && r.request().method() === "POST");
  await modal.getByRole("button", { name: "บันทึก", exact: true }).click();
  const response = await receipt; expect(response.status()).toBe(202);
  const request = await response.json() as { request_id: string };
  expect((await page.request.post(`${endpoint}/drive`, { data: { user_id: owner } })).ok()).toBe(true);
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  await expect(panel.getByRole("alert")).toHaveText("ดำเนินการไม่ได้ ตรวจข้อมูลล่าสุดแล้วลองใหม่");
  const status = await (await page.request.get(`/api/paper/protection-requests/${request.request_id}`)).json() as { state: string };
  expect(status.state).toBe("REJECTED");
  await page.reload();
  await expect(panel.getByText("ไม่มีออเดอร์เปิดอยู่หรือ TP/SL ที่กำลังทำงานหรือมีปัญหา", { exact: true })).toBeVisible();
  const trade = await (await page.request.get("/api/paper/trade?base=BTC")).json() as { wallet: { episode_id: string; balance: string; base_balances: Array<{ asset: string; held: string; reserved: string; protection_allocated: string; available: string }> } };
  expect(trade.wallet.balance).toBe("9900");
  expect(trade.wallet.base_balances.find(row => row.asset === "BTC")).toMatchObject({ held: "0.999", reserved: "0", protection_allocated: "0", available: "0.999" });
  const orders = await (await page.request.get(`/api/paper/orders?episode_id=${trade.wallet.episode_id}`)).json() as { orders: Array<{ side: string }> };
  expect(orders.orders.every(order => order.side === "BUY")).toBe(true);
  await capture(page, "paper-failed-protection-reload.png");
});


test("net-fee protection displays executable coverage and step residual from the real API", async ({ page }) => {
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/enable")).status()).toBe(204);
  const owner = await register(page);
  await page.getByLabel("ราคา Take Profit", { exact: true }).fill("110");
  await page.getByLabel("ราคา Stop Loss", { exact: true }).fill("90");
  const entry = await send(page, "100", false);
  expect(await drive(page, owner, entry.request_id, true)).toMatchObject({ order_state: "FILLED" });
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/coarse-step", { data: { user_id: owner } })).status()).toBe(204);
  expect((await page.request.post("http://127.0.0.1:18017/__e2e/protections/drive", { data: { user_id: owner } })).ok()).toBe(true);
  await reloadPaperPair(page);
  const panel = page.locator('[aria-labelledby="trading-activity-heading"]');
  await expect(panel.getByText("กำลังเฝ้าราคา", { exact: true })).toBeVisible();
  await expect(panel.getByText("0.999 BTC", { exact: true })).toHaveCount(1);
  await expect(panel.getByText("0.99 BTC", { exact: true })).toBeVisible();
  await expect(panel.getByText("0.009 BTC", { exact: true })).toBeVisible();
  await expect(panel.getByText("ไม่ขายเศษอัตโนมัติ", { exact: true })).toBeVisible();
  mkdirSync(evidence, { recursive: true });
  await panel.screenshot({ path: `${evidence}/paper-net-fee-residual.png` });
});
