import type { Page } from "@playwright/test";
import { expect, test } from "./helpers/test";
import { navigationLink } from "./helpers/ui";

const control = "http://127.0.0.1:18020/__e2e/bots";
const panelSelector = '[aria-labelledby="paper-bot-title"]';
async function register(page: Page) {
  await page.goto("/account");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`f20-${globalThis.crypto.randomUUID()}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("bot-feature-fixture-password-long");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("log-out")).toBeVisible();
  const who = await (await page.request.get("/api/auth/me")).json() as { user_id: string };
  expect((await page.request.post(`${control}/prepare`, { data: who })).status()).toBe(204);
  await expect.poll(async () => (await (await page.request.get("/api/paper/risk-limit")).json() as { reason: string }).reason).toBe("READY");
  await page.goto("/paper/trade");
  await expect(page.getByRole("heading", { name: "Paper Spot", exact: true })).toBeVisible();
  return who.user_id;
}
async function phase(page: Page, owner: string, value: string) {
  const result = await page.request.post(`${control}/phase`, { data: { user_id: owner, phase: value } });
  expect(result.status()).toBe(200);
  return await result.json() as { run_id?: string; order_id?: string };
}
async function status(page: Page) {
  return await (await page.request.get("/api/paper/bots/status")).json() as {
    status: string | null; pending_request_id: string | null; run_id: string | null;
    positions: { quantity: string }[]; protections: { state: string; quantity: string }[];
  };
}
async function language(page: Page, locale: string) {
  await page.evaluate(async selected => {
    const manualPath = "/src/manualOrderMessages.ts", stopPath = "/src/killSwitchMessages.ts";
    const manual = await import(/* @vite-ignore */ manualPath) as { manualOrderI18n: { changeLanguage: (locale: string) => Promise<unknown> } };
    const stops = await import(/* @vite-ignore */ stopPath) as { killSwitchI18n: { changeLanguage: (locale: string) => Promise<unknown> } };
    await manual.manualOrderI18n.changeLanguage(selected);
    await stops.killSwitchI18n.changeLanguage(selected);
  }, locale);
  await page.locator(`${panelSelector} input`).fill(locale === "en" ? "100" : "101");
}

test("real API lifecycle, exposure and stop recovery across responsive locales/themes", async ({ page }, info) => {
  test.setTimeout(120_000);
  const owner = await register(page), panel = page.locator(panelSelector);
  await phase(page, owner, "pending");
  await expect(panel.getByText("รับคำขอเริ่มแล้ว · กำลังตรวจความพร้อม")).toBeVisible();
  expect((await status(page)).status).toBeNull();
  await expect(panel.getByRole("button", { name: "เริ่มบอท", exact: true })).toBeDisabled();
  await panel.screenshot({ path: info.outputPath("f20-pending.png") });
  await phase(page, owner, "start");
  await expect(panel.getByText("กำลังเริ่ม", { exact: true })).toBeVisible();
  expect((await status(page)).pending_request_id).toBeNull();
  await phase(page, owner, "evaluate");
  await expect(panel.getByText("กำลังทำงาน", { exact: true })).toBeVisible();
  const entry = await phase(page, owner, "exposure");
  await expect.poll(async () => (await (await page.request.get(`/api/paper/orders/${entry.order_id}`)).json() as { status: string }).status).toBe("FILLED");
  await expect.poll(async () => (await status(page)).protections[0]?.state).toBe("ARMED");
  expect((await status(page)).positions[0]?.quantity).toBe("0.999");
  await expect(panel.getByText("0.999 BTC", { exact: true })).toHaveCount(2);
  await expect(panel.locator("time")).toBeVisible();
  await expect(panel.locator("dd")).toHaveText("9,900 USDT");
  for (const width of [375, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const locale of ["th", "en"]) {
      await language(page, locale);
      for (const theme of ["light", "dark"]) {
        await page.evaluate(value => document.documentElement.classList.toggle("dark", value === "dark"), theme);
        await expect(panel.getByRole("button", { name: locale === "th" ? "เริ่มบอท" : "Start bot", exact: true })).toBeDisabled();
        await expect(panel.getByText(locale === "th" ? "กำลังทำงาน" : "Running", { exact: true })).toBeVisible();
        await panel.locator("input").focus();
        await page.keyboard.press("Shift+Tab");
        await expect(panel.getByRole("combobox")).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(panel.locator("input")).toBeFocused();
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
        // Capture the real page from its top: a locator screenshot scrolls the
        // mobile panel beneath the existing sticky market toolbar and clips it.
        await page.evaluate(() => {
          window.scrollTo(0, 0);
          document.querySelector(".trade-workspace-form")?.scrollTo(0, 0);
        });
        await page.screenshot({ fullPage: true, path: info.outputPath(`f20-running-${width}-${locale}-${theme}.png`) });
      }
    }
  }
  await language(page, "th");
  await page.evaluate(() => document.documentElement.classList.remove("dark"));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await phase(page, owner, "pause");
  await expect(panel.getByText("พักชั่วคราว", { exact: true })).toBeVisible();
  await panel.screenshot({ path: info.outputPath("f20-paused.png") });
  await phase(page, owner, "evaluate");
  await expect(panel.getByText("กำลังทำงาน", { exact: true })).toBeVisible();

  await page.route("**/api/paper/kill-switch/stop", async route => {
    const committed = await route.fetch();
    expect(committed.status()).toBe(202);
    await route.abort("failed");
  }, { times: 1 });
  await panel.getByRole("button", { name: "หยุดบอท Paper", exact: true }).click();
  await expect.poll(async () => (await status(page)).status).toBe("STOPPED");
  expect(await page.evaluate(id => window.localStorage.getItem(`tiewtrade.kill-switch.stop.v1:${id}:PAPER`), owner)).toBeTruthy();
  const recovery = page.waitForRequest(request => request.url().includes("/kill-switch/requests/by-key/"));
  await page.reload();
  await recovery;
  await expect(panel.getByText("หยุดแล้ว", { exact: true }).first()).toBeVisible();
  await expect.poll(() => page.evaluate(id => window.localStorage.getItem(`tiewtrade.kill-switch.stop.v1:${id}:PAPER`), owner)).toBeNull();
  const metrics = await (await page.request.post(`${control}/metrics`, { data: { user_id: owner } })).json() as { stop_requests: number; orders: number; position_events: number };
  expect(metrics).toEqual({ stop_requests: 1, orders: 1, position_events: 1 });
  expect((await status(page)).positions[0]?.quantity).toBe("0.999");
  expect((await status(page)).protections[0]?.quantity).toBe("0.999");
  await panel.getByRole("button", { name: "ดูรายละเอียด", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "เปิดบอทกลับ", exact: true })).toBeEnabled();
  await dialog.screenshot({ path: info.outputPath("f20-resume-summary.png") });
  await page.keyboard.press("Escape");
  await expect(panel.getByRole("button", { name: "หยุดบอท Paper", exact: true })).toBeFocused();
  await panel.getByRole("button", { name: "ดูรายละเอียด", exact: true }).click();
  await dialog.getByRole("button", { name: "เปิดบอทกลับ", exact: true }).click();
  await expect.poll(async () => (await status(page)).status).toBe("RECOVERING");
  await page.keyboard.press("Escape");
  await phase(page, owner, "evaluate");
  await expect(panel.getByText("กำลังทำงาน", { exact: true })).toBeVisible();
  expect((await status(page)).positions[0]?.quantity).toBe("0.999");
});

test("late Paper responses and another owner's session cannot cross mode or owner scope", async ({ page }, info) => {
  const owner = await register(page), panel = page.locator(panelSelector);
  await phase(page, owner, "pending"); await phase(page, owner, "start"); await phase(page, owner, "evaluate");
  await expect(panel.getByText("กำลังทำงาน", { exact: true })).toBeVisible();
  let release!: () => void, observed!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const captured = new Promise<void>(resolve => { observed = resolve; });
  await page.route("**/api/paper/bots/status", async route => {
    const response = await route.fetch();
    observed(); await held;
    try { await route.fulfill({ response }); } catch { /* Navigation may cancel the old request. */ }
  }, { times: 1 });
  await captured;
  await (await navigationLink(page, "/live/trade")).click();
  release();
  await expect(page.getByText("Live ยังไม่พร้อมใช้งาน จึงไม่มีการส่งออเดอร์ หากมีออเดอร์ Live อยู่ ให้จัดการโดยตรงที่ตลาด")).toBeVisible();
  expect((await (await page.request.get("/api/live/bots/status")).json() as { run_id: string | null }).run_id).toBeNull();
  await expect(page.getByText("กำลังทำงาน", { exact: true })).toHaveCount(0);
  await page.screenshot({ fullPage: true, path: info.outputPath("f20-live-unavailable.png") });
  await page.goto("/account");
  await page.getByTestId("log-out").click();
  const other = await register(page);
  expect(other).not.toBe(owner);
  expect((await status(page)).run_id).toBeNull();
  expect((await status(page)).pending_request_id).toBeNull();
  expect((await (await page.request.post(`${control}/metrics`, { data: { user_id: other } })).json() as { orders: number }).orders).toBe(0);
});
