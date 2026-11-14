import { postFixtureOrder, requestFixtureOrder, openSell } from "./helpers/paperOrders";
import { navigationLink } from "./helpers/ui";
import { mkdirSync } from "node:fs";
import { expect, test } from "./helpers/test";
import { PASSWORD } from "./helpers/totp";
import type { Page } from "@playwright/test";
const control = "http://127.0.0.1:18018/__e2e/risk";
const evidence = "test-results/paper-bot-panel/risk";
const killSwitchEvidence = "test-results/paper-bot-panel/kill-switch";
const accountRoutes = ["chart", "paper/trade", "live/trade", "account", "security", "api-keys", "trading-account", "supported-symbols", "system-safety"] as const;
async function capture(page: Page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0));
  mkdirSync(evidence, { recursive: true });
  await page.screenshot({ path: `${evidence}/${name}.png`, fullPage: true });
}
async function captureKillSwitch(page: Page, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0));
  mkdirSync(killSwitchEvidence, { recursive: true });
  await page.screenshot({ path: `${killSwitchEvidence}/${name}.png`, fullPage: true });
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
  await expect(page.getByRole("heading", { name: "Paper Spot", exact: true })).toBeVisible();
  expect((await snapshot(page)).amount).toBeNull();
  return identity.user_id;
}
async function openTradingAccount(page: Page) {
  await page.goto("/trading-account");
  await expect(page).toHaveURL(/\/trading-account$/);
  await expect(page.getByLabel("เพดานขาดทุน (USDT)")).toBeVisible();
}
async function openPaperTrade(page: Page) {
  await (await navigationLink(page, "/paper/trade")).click();
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
  let button = page.getByRole("button", { name: "ส่งคำขอขาย Paper", exact: true });
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
  await expect.poll(async () => (
    await (await page.request.get("/api/paper/trade?base=BTC")).json() as {
      admission_ready: boolean;
    }
  ).admission_ready).toBe(true);
  return postFixtureOrder(page, { base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget: amount });
}
async function order(page: Page, id: string) {
  return await (await page.request.get(`/api/paper/orders/${id}`)).json() as { status: string; filled_quantity: string; reserved_quote: string; spent_quote: string };
}
test("production risk composition: unset→set→BUY→breach→cancel→bounded SELL→reset keeps opening blocked", async ({ page }) => {
  test.setTimeout(120_000);
  const owner = await register(page); await capture(page, "unset-th-light-desktop");
  await setLimit(page);
  await page.getByLabel("คู่เทรด").selectOption("BTC");
  const buy = await send(page, "110");
  await expect.poll(async () => (await order(page, buy.order_id)).status).toBe("FILLED");
  await expect.poll(async () => page.evaluate(id => window.sessionStorage.getItem("tiewtrade.manual-order.v1:" + id), owner)).toBeNull();
  const limit = await postFixtureOrder(page, { base: "BTC", quote: "USDT", side: "BUY", kind: "LIMIT", base_quantity: "1", limit_price: "90", time_in_force: "GTC" });
  await expect.poll(async () => (await order(page, limit.order_id)).status).toBe("ACCEPTED");
  await expect.poll(async () => page.evaluate(id => window.sessionStorage.getItem("tiewtrade.manual-order.v1:" + id), owner)).toBeNull();
  expect((await page.request.post(`${control}/hold-transfer`, { data: { user_id: owner } })).status()).toBe(204);
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
  await openSell(page);
  await page.getByLabel("จำนวนเหรียญ Base (BTC)").fill("0.1");
  await expect(page.getByRole("button", { name: "ส่งคำขอขาย Paper", exact: true })).toBeEnabled();
  const selling = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
  await page.getByRole("button", { name: "ส่งคำขอขาย Paper", exact: true }).click();
  const sell = await (await selling).json() as { order_id: string };
  await expect.poll(async () => (await order(page, sell.order_id)).status).toBe("FILLED");
  await openTradingAccount(page);
  await expect(page.getByRole("button", { name: "รีเซ็ตการนับขาดทุน", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "รีเซ็ตการนับขาดทุน", exact: true }).click();
  await expect(page.getByRole("dialog").getByText(/สถานะที่ถือยังเปิดอยู่/)).toBeVisible();
  await expect(page.getByRole("dialog").getByLabel("รหัสปัจจุบันจากแอปยืนยันตัวตน")).toHaveCount(0);
  await page.getByRole("dialog").getByRole("button", { name: "ยืนยัน", exact: true }).click();
  await expect.poll(async () => (await snapshot(page)).latched).toBe(false);
  await expect.poll(async () => (
    await (await page.request.get("/api/paper/kill-switch")).json() as {
      cause: string | null;
      resume_ready: boolean;
    }
  )).toMatchObject({ cause: "LOSS_LIMIT", resume_ready: false });
  expect((await snapshot(page)).loss).toBe("0");
  expect((await snapshot(page)).current_allowance).not.toBe("0");
  await openPaperTrade(page);
  await page.getByLabel("คู่เทรด").selectOption("BTC");

  const trade = await (await page.request.get("/api/paper/trade?base=BTC")).json() as {
    wallet: { balance: string; base_balances: { asset: string; held: string }[] };
  };
  const rejected = await requestFixtureOrder(page, { base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget: "11" });
  expect(rejected.status()).toBe(503);
  expect(await rejected.json()).toEqual({ detail: "ORDER_SAFETY_UNAVAILABLE" });
  // RESET clears the loss baseline only; it must not create a trade or bypass the shared stop.
  expect(trade.wallet.balance).toBe("9899.8901");
  expect(trade.wallet.base_balances.find(row => row.asset === "BTC")?.held).toBe("0.9989");
  expect((await snapshot(page)).loss).toBe("0");
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await capture(page, "reset-th-dark-desktop");
  await page.setViewportSize({ width: 375, height: 844 }); await capture(page, "reset-th-dark-mobile");
  await page.setViewportSize({ width: 768, height: 1024 }); await capture(page, "reset-th-dark-tablet");
  await page.goto("/trading-account");
  await page.evaluate(async () => {
    const source = "/src/riskLimitMessages.ts";
    const messages = await import(/* @vite-ignore */ source) as { riskLimitI18n: { changeLanguage: (language: string) => Promise<unknown> } };
    await messages.riskLimitI18n.changeLanguage("en");
  });
  await expect(page.getByLabel("Loss limit (USDT)")).toBeVisible();
  await capture(page, "reset-en-dark-tablet");
  await page.evaluate(() => document.documentElement.classList.remove("dark"));
  await page.setViewportSize({ width: 1440, height: 1000 }); await capture(page, "reset-en-light-desktop");
  await (await navigationLink(page, "/live/trade")).click();
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

test("F-19 Paper and Live stops stay separate and UNKNOWN retries the same request", async ({ page }) => {
  const browserErrors: string[] = [];
  const requestFailures: string[] = [];
  const unexpectedHttpErrors: string[] = [];
  page.on("console", message => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", error => browserErrors.push(error.message));
  page.on("requestfailed", request => {
    if (request.url().endsWith("/api/paper/kill-switch/stop")) {
      requestFailures.push(request.failure()?.errorText ?? "UNKNOWN_REQUEST_FAILURE");
    }
  });
  page.on("response", response => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    const expectedNotFound = response.status() === 404 && (
      url.pathname === "/api/market-data/chart/live"
      || url.pathname.startsWith("/api/paper/order-requests/by-key/")
    );
    if (!expectedNotFound) unexpectedHttpErrors.push(`${response.status()} ${url.pathname}`);
  });
  const owner = await register(page);
  browserErrors.length = 0;
  unexpectedHttpErrors.length = 0;
  const paperButton = page.getByRole("button", { name: "หยุดบอท Paper", exact: true });
  const liveButton = page.getByRole("button", { name: "หยุดบอท Live", exact: true });
  await expect(paperButton).toBeHidden();
  await expect(page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true })).toBeVisible();
  await expect(liveButton).toBeHidden();

  let committedKey: string | undefined;
  let committedReceipt: { request_id: string; generation: number } | undefined;
  await page.route("**/api/paper/kill-switch/stop", async route => {
    if (route.request().method() !== "POST") return route.continue();
    committedKey = route.request().headers()["idempotency-key"];
    const response = await route.fetch();
    expect(response.status()).toBe(202);
    committedReceipt = await response.json() as { request_id: string; generation: number };
    await route.abort("connectionreset");
  }, { times: 1 });
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await expect(liveButton).toBeVisible();
  await paperButton.click();
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ยังไม่ทราบผลการหยุด" })).toBeVisible();
  expect(requestFailures.some(error => error.includes("ERR_CONNECTION_RESET"))).toBe(true);
  browserErrors.length = 0;
  expect(committedKey).toBeTruthy();
  expect(await page.evaluate(
    key => window.localStorage.getItem(key),
    `tiewtrade.kill-switch.stop.v1:${owner}:PAPER`,
  )).toBe(committedKey);

  // Before reload, the lost response is still UNKNOWN: retry must keep its key.
  const retry = page.waitForRequest(request =>
    request.url().endsWith("/api/paper/kill-switch/stop") && request.method() === "POST",
  );
  const replay = page.waitForResponse(response =>
    response.url().endsWith("/api/paper/kill-switch/stop") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "หยุดบอท Paper — ส่งคำขอหยุดเดิมซ้ำ", exact: true }).click();
  expect((await retry).headers()["idempotency-key"]).toBe(committedKey);
  const replayed = await replay;
  expect(replayed.status()).toBe(200);
  const firstStop = await replayed.json() as { request_id: string; generation: number };
  expect(firstStop).toMatchObject({ request_id: committedReceipt!.request_id, generation: committedReceipt!.generation });
  await expect.poll(() => page.evaluate(
    key => window.localStorage.getItem(key),
    `tiewtrade.kill-switch.stop.v1:${owner}:PAPER`,
  )).toBeNull();

  // A persisted lost ACK has a different recovery path: GET resolves it without POST.
  let lostKey: string | undefined;
  let lostReceipt: { request_id: string; generation: number } | undefined;
  let paperPosts = 0;
  page.on("request", request => {
    if (request.url().endsWith("/api/paper/kill-switch/stop") && request.method() === "POST") paperPosts++;
  });
  await page.route("**/api/paper/kill-switch/stop", async route => {
    if (route.request().method() !== "POST") return route.continue();
    lostKey = route.request().headers()["idempotency-key"];
    const response = await route.fetch();
    expect(response.status()).toBe(202);
    lostReceipt = await response.json() as { request_id: string; generation: number };
    await route.abort("connectionreset");
  }, { times: 1 });
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await paperButton.click();
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "ยังไม่ทราบผลการหยุด" })).toBeVisible();
  expect(lostKey).toBeTruthy();
  expect(lostKey).not.toBe(committedKey);
  expect(lostReceipt!.request_id).not.toBe(firstStop.request_id);
  expect(lostReceipt!.generation).toBe(firstStop.generation + 1);
  browserErrors.length = 0;
  const recoveredResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === `/api/paper/kill-switch/requests/by-key/${lostKey}`
      && response.request().method() === "GET",
  );
  await page.reload();
  const recovered = await recoveredResponse;
  expect(recovered.status()).toBe(200);
  expect(await recovered.json()).toMatchObject({ request_id: lostReceipt!.request_id, generation: lostReceipt!.generation, mode: "PAPER", action: "STOP" });
  await expect.poll(() => page.evaluate(
    key => window.localStorage.getItem(key),
    `tiewtrade.kill-switch.stop.v1:${owner}:PAPER`,
  )).toBeNull();
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await expect(page.locator('.kill-switch-settings-group[aria-label="PAPER"] > button[aria-label]').first()).toBeEnabled();
  expect(paperPosts).toBe(1);
  await page.keyboard.press("Escape");

  await page.getByLabel("คู่เทรด").selectOption("BTC");
  await expect.poll(async () => {
    const trade = await (await page.request.get("/api/paper/trade?base=BTC")).json() as {
      admission_ready: boolean;
    };
    return trade.admission_ready;
  }, { timeout: 15_000 }).toBe(true);
  const afterCutoff = await send(page, "11");
  await expect.poll(async () => (await order(page, afterCutoff.order_id)).status).toBe("FILLED");
  const repeatedStop = page.waitForResponse(response =>
    response.url().endsWith("/api/paper/kill-switch/stop")
      && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await page.getByRole("button", { name: "หยุดบอท Paper", exact: true }).click();
  const repeated = await repeatedStop;
  expect(repeated.status()).toBe(202);
  const secondStop = await repeated.json() as { request_id: string; generation: number };
  expect(repeated.request().headers()["idempotency-key"]).not.toBe(lostKey);
  expect(secondStop.request_id).not.toBe(lostReceipt!.request_id);
  expect(secondStop.generation).toBe(lostReceipt!.generation + 1);
  await expect.poll(async () => {
    const status = await (await page.request.get("/api/paper/kill-switch")).json() as {
      stop_id: string | null;
      progress: string | null;
    };
    return status.stop_id !== null && status.progress === "STOPPED";
  }).toBe(true);

  const liveBefore = await (await page.request.get("/api/live/kill-switch")).json() as {
    stop_id: string | null;
  };
  expect(liveBefore.stop_id).toBeNull();
  const paperControl = page.getByRole("group", { name: "สถานะหยุด PAPER", exact: true });
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await expect(paperControl.getByText("หยุดแล้ว", { exact: true })).toBeVisible();
  await page.getByRole("region", { name: "PAPER", exact: true }).getByRole("button", { name: "ดูรายละเอียด", exact: true }).click();
  await expect(page.getByRole("dialog").getByText("สรุปการหยุด", { exact: false })).toBeVisible();
  await expect(page.getByRole("dialog").getByText(/BTC\/USDT:/)).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "ปิด", exact: true }).click();

  const liveStop = page.waitForResponse(response =>
    response.url().endsWith("/api/live/kill-switch/stop") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await page.getByRole("button", { name: "หยุดบอท Live", exact: true }).click();
  expect((await liveStop).status()).toBe(202);
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  const liveDetails = page.getByRole("region", { name: "LIVE", exact: true }).getByRole("button", { name: "ดูรายละเอียด", exact: true });
  await liveDetails.click();
  await expect(page.getByRole("dialog").getByText(/Live execution ยังไม่พร้อม/)).toBeVisible();
  const liveAfter = await (await page.request.get("/api/live/kill-switch")).json() as {
    stop_id: string | null;
    target_set_complete: boolean;
    resume_ready: boolean;
  };
  expect(liveAfter.stop_id).not.toBeNull();
  expect(liveAfter.target_set_complete).toBe(false);
  expect(liveAfter.resume_ready).toBe(false);
  await captureKillSwitch(page, "paper-live-separated-th-light-desktop");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true })).toBeFocused();

  await page.evaluate(async () => {
    const source = "/src/killSwitchMessages.ts";
    const messages = await import(/* @vite-ignore */ source) as {
      killSwitchI18n: { changeLanguage: (language: string) => Promise<unknown> };
    };
    await messages.killSwitchI18n.changeLanguage("en");
    document.documentElement.classList.add("dark");
  });
  await page.setViewportSize({ width: 375, height: 844 });
  await page.getByRole("button", { name: "Stop settings", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop Paper bot", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop Live bot", exact: true })).toBeVisible();
  await captureKillSwitch(page, "paper-live-separated-en-dark-mobile");
  expect(browserErrors).toEqual([]);
  expect(unexpectedHttpErrors).toEqual([]);
});

test("F-19 Platform Owner stop publishes the reason and only resumes after completion", async ({ page }) => {
  const owner = await register(page);
  expect((await page.request.post(`${control}/bootstrap-platform-owner`, {
    data: { user_id: owner },
  })).status()).toBe(204);
  await page.reload();
  await (await navigationLink(page, "/system-safety")).click();
  await expect(page).toHaveURL(/\/system-safety$/);

  const reason = "<b>planned incident</b>";
  await page.getByLabel("เหตุผลที่แสดงต่อผู้ใช้").fill(reason);
  const stopped = page.waitForResponse(response =>
    response.url().endsWith("/api/admin/kill-switch/stop")
      && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "หยุดทั้งแพลตฟอร์ม", exact: true }).click();
  expect((await stopped).status()).toBe(202);
  await expect.poll(async () => {
    return await (await page.request.get("/api/admin/kill-switch")).json() as {
      progress: string | null;
      can_resume: boolean;
    };
  }).toMatchObject({ progress: "STOPPED", can_resume: true });
  await expect(page.getByRole("alert").filter({ hasText: reason })).toBeVisible();
  await expect(page.locator("b", { hasText: "planned incident" })).toHaveCount(0);
  for (const route of accountRoutes) {
    await page.goto(`/${route}`);
    await expect(page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true })).toBeVisible();
    await expect(page.getByRole("group", { name: "สถานะหยุด PAPER", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "หยุดบอท Live", exact: true })).toBeHidden();
    await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
    await expect(page.getByRole("button", { name: "หยุดบอท Live", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("alert").filter({ hasText: reason })).toBeVisible();
  }
  await page.setViewportSize({ width: 375, height: 844 });
  for (const route of accountRoutes) {
    await page.goto(`/${route}`);
    await expect(page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true })).toBeVisible();
    await expect(page.getByRole("group", { name: "สถานะหยุด PAPER", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "หยุดบอท Live", exact: true })).toBeHidden();
    await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
    await expect(page.getByRole("button", { name: "หยุดบอท Live", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("alert").filter({ hasText: reason })).toBeVisible();
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/system-safety");

  const browser = page.context().browser();
  expect(browser).not.toBeNull();
  const adminContext = await browser!.newContext({
    baseURL: "http://127.0.0.1:15118",
    viewport: { width: 1440, height: 1000 },
  });
  const adminPage = await adminContext.newPage();
  const admin = await register(adminPage);
  expect((await adminPage.request.post(`${control}/grant-platform-admin`, {
    data: { user_id: admin },
  })).status()).toBe(204);
  await adminPage.reload();
  await (await navigationLink(adminPage, "/system-safety")).click();
  await expect(adminPage.getByRole("button", { name: "เปิดแพลตฟอร์มกลับ", exact: true })).toBeDisabled();
  await expect(adminPage.getByText("เฉพาะ Platform Owner เท่านั้นที่เปิดกลับได้", { exact: true })).toBeVisible();
  await expect(adminPage.getByRole("alert").filter({ hasText: reason })).toBeVisible();
  await adminContext.close();

  const resumed = page.waitForResponse(response =>
    response.url().endsWith("/api/admin/kill-switch/resume")
      && response.request().method() === "POST",
  );
  const resume = page.getByRole("button", { name: "เปิดแพลตฟอร์มกลับ", exact: true });
  await expect(resume).toBeEnabled();
  await resume.click();
  expect((await resumed).status()).toBe(202);
  await expect.poll(async () => {
    return await (await page.request.get("/api/admin/kill-switch")).json() as {
      stop_id: string | null;
    };
  }).toMatchObject({ stop_id: null });
  await expect(page.getByRole("alert").filter({ hasText: reason })).toHaveCount(0);
  await expect(page.getByText("ระบบกำลังตรวจคำขอเปิดกลับ", { exact: true })).toHaveCount(0);
  await expect(page.locator(".platform-kill-switch-panel")).toContainText("— · ค้าง: 0 · ล้มเหลว: 0");
  await captureKillSwitch(page, "platform-owner-resumed-th-light-desktop");
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
  const priceRejected = await requestFixtureOrder(page, { base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget: "11" });
  expect(priceRejected.status()).toBe(503);
  expect(await priceRejected.json()).toEqual({ detail: "RISK_PRICE_UNAVAILABLE" });
  expect((await snapshot(page)).loss).toBeNull();
  await capture(page, "price-pause-th-light-desktop");
  expect((await page.request.post(`${control}/price`, { data: { amount: "110", connected: true } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("READY");
  expect((await page.request.post(`${control}/cache-gap`, { data: { user_id: owner } })).status()).toBe(204);
  await expect.poll(async () => (await snapshot(page)).reason).toBe("RISK_SOURCE_UNAVAILABLE");
  const cacheRejected = await requestFixtureOrder(page, { base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget: "11" });
  expect(cacheRejected.status()).toBe(503);
  expect(await cacheRejected.json()).toEqual({ detail: "RISK_SOURCE_UNAVAILABLE" });
  await openSell(page);
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
