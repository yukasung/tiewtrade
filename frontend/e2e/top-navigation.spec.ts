import { test, expect } from "./helpers/test";
import { execFileSync } from "node:child_process";
import { backendPython, e2eEnvironment } from "./helpers/environment";
import { navigationLink } from "./helpers/ui";
import type { Page } from "@playwright/test";

async function register(page: Page) {
  await page.goto("/account");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`navigation-${Date.now()}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("navigation-fixture-password-long");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("log-out")).toBeVisible();
}
function stopStatus(mode: string, stopped = false) {
  return { mode, active_causes: stopped ? ["USER"] : [], stop_id: stopped ? "fixture-stop" : null,
    cause: stopped ? "USER" : null, generation: stopped ? 1 : null, revision: stopped ? 1 : 0,
    summary_revision: 0, progress: stopped ? "STOPPED" : null, target_set_complete: stopped,
    target_count: 0, pending_count: 0, failed_count: 0, platform_stop_id: null, platform_reason: null,
    resume_ready: false, reconciliation_revision: stopped ? 0 : null,
    capability: mode === "PAPER" ? "AVAILABLE" : "LIVE_EXECUTION_UNAVAILABLE" };
}
async function fixtureStops(page: Page, stopped = false) {
  await page.route(/\/api\/(paper|live)\/kill-switch$/, route => route.fulfill({ json: stopStatus(route.request().url().includes("/paper/") ? "PAPER" : "LIVE", stopped) }));
  await page.route("**/api/paper/risk-limit", route => route.fulfill({ json: { latched: false } }));
}
async function language(page: Page, locale: string) {
  await page.evaluate(async value => {
    for (const [path, key] of [["/src/accountMessages.ts", "accountI18n"], ["/src/chartMessages.ts", "chartI18n"], ["/src/killSwitchMessages.ts", "killSwitchI18n"]]) {
      const module = await import(/* @vite-ignore */ path!) as Record<string, { changeLanguage: (value: string) => Promise<unknown> }>;
      await module[key!]?.changeLanguage(value);
    }
    // Translation instances are read at render time, as in the existing UI tests.
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, locale);
  const trigger = page.locator('button[aria-controls="compact-navigation"]:visible,button[aria-controls="account-dropdown"]:visible');
  await trigger.click(); await page.keyboard.press("Escape");
}
for (const width of [375, 768, 1024, 1279, 1280, 1440, 2553]) {
  test(`navigation geometry, focus and theme at ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 900 });
    await fixtureStops(page, true);
    let posts = 0;
    page.on("request", request => { if (request.method() === "POST" && /kill-switch/.test(request.url())) posts++; });
    await register(page);
    await page.locator("#account-details").evaluate(element => element.setAttribute("data-navigation-stable", "yes"));
    for (const locale of ["th", "en"]) {
      await language(page, locale);
      for (const theme of ["light", "dark"]) {
        const compact = width < 1280;
        const trigger = page.locator('button[aria-controls="compact-navigation"]');
        if (compact) {
          await trigger.click();
          await expect(trigger).toBeFocused();
          await expect(page.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
          expect(await page.evaluate(() => document.body.style.overflow)).toBe("hidden");
          expect(await page.locator("#account-details").evaluate(element => !!element.closest("[inert]"))).toBe(true);
          const last = page.locator("#compact-navigation .account-theme-toggle");
          await last.focus(); await page.keyboard.press("Tab");
          await expect(page.locator(".account-compact-actions a")).toBeFocused();
          await page.keyboard.press("Shift+Tab"); await expect(last).toBeFocused();
        }
        await expect(page.locator(".account-header")).toHaveCSS("height", compact ? "56px" : "64px");
        await expect(page.locator(".account-brand")).toHaveText("TiewTrade");
        const toggle = page.locator(".account-theme-toggle:visible");
        if (await page.locator("html").getAttribute("data-color-scheme") !== theme) await toggle.click();
        await expect(page.locator("html")).toHaveAttribute("data-color-scheme", theme);
        const paper = page.getByRole("button", { name: "Paper", exact: true });
        const live = page.getByRole("button", { name: "Live", exact: true });
        const ink = await page.locator(".account-header").evaluate(element => globalThis.getComputedStyle(element).color);
        await expect(paper).toHaveCSS("color", ink);
        await paper.click(); await live.click();
        await expect(live).toHaveAttribute("aria-expanded", "true");
        await expect(paper).toHaveAttribute("aria-expanded", "false");
        await live.click();
        for (const [market, path] of [[paper, "/paper/trade"], [live, "/live/trade"]] as const) {
          await market.click();
          const spot = page.getByRole("link", { name: "Spot", exact: true });
          await expect(spot).toHaveAttribute("href", path);
          const futures = page.getByRole("button", { name: "Futures", exact: true });
          await expect(futures).toBeDisabled();
          expect(await futures.getAttribute("href")).toBeNull();
          await page.screenshot({ path: info.outputPath(`market-${path.includes("paper") ? "paper" : "live"}-${width}-${locale}-${theme}.png`) });
          await market.focus(); await page.keyboard.press("Tab");
          await expect(spot).toBeFocused();
          await page.keyboard.press("Escape");
          await expect(market).toBeFocused();
          await expect(market).toHaveAttribute("aria-expanded", "false");
          if (compact) await expect(trigger).toHaveAttribute("aria-expanded", "true");
          await market.click(); await spot.focus(); await page.keyboard.press("Tab");
          await expect(market === paper ? live : compact
            ? page.locator('#compact-navigation .account-nav-account a[href="/account"]')
            : toggle).toBeFocused();
          await expect(market).toHaveAttribute("aria-expanded", "false");
        }
        await page.mouse.move(width - 1, 899);
        await expect(toggle).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
        await expect(page.locator(".kill-switch-readouts")).toHaveCount(0);
        await expect(page.locator(".kill-switch-control:visible")).toHaveCount(0);
        const settings = page.locator(".kill-switch-settings > button");
        await expect(settings).toBeVisible();
        await expect(settings).toHaveCSS("border-width", "0px");
        await expect(settings).toHaveCSS("box-shadow", "none");
        await expect(settings.locator(".navigation-icon")).toHaveCSS("width", "24px");
        await expect(settings.locator(".navigation-icon")).toHaveCSS("height", "24px");
        for (const glyph of await page.locator(".account-header .account-icon-button:visible .navigation-icon,.account-header .navigation-toggle-icon:visible,.account-header .account-theme-toggle:visible svg").all()) {
          await expect(glyph).toHaveCSS("width", "24px");
          await expect(glyph).toHaveCSS("height", "24px");
        }
        const settingsBounds = await settings.boundingBox();
        expect(settingsBounds && settingsBounds.width >= 44 && settingsBounds.height >= 44).toBeTruthy();
        expect(settingsBounds && Math.abs(settingsBounds.x + settingsBounds.width - (width - 16)) < 1).toBeTruthy();
        if (!compact) {
          const icons = await page.locator(".account-desktop-actions > .account-theme-toggle,.account-desktop-actions .account-disclosure > button").all();
          const bounds = await Promise.all([...icons, settings].map(control => control.boundingBox()));
          for (let index = 1; index < bounds.length; index++) {
            const previous = bounds[index - 1]!;
            const current = bounds[index]!;
            expect(Math.abs(current.x - (previous.x + previous.width))).toBeLessThanOrEqual(1);
            expect(Math.abs(current.x + current.width / 2 - previous.x - previous.width / 2 - 44)).toBeLessThanOrEqual(1);
          }
        }
        for (const control of await page.locator(".account-desktop-actions:visible > .account-theme-toggle,.account-desktop-actions:visible .account-disclosure > button,.account-compact-actions:visible > a,.account-compact-actions:visible > button").all()) {
          const bounds = await control.boundingBox();
          expect(bounds && settingsBounds && bounds.x + bounds.width <= settingsBounds.x).toBeTruthy();
        }
        await expect(page.locator(".kill-switch-settings-panel").getByRole("button")).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
        await page.screenshot({ path: info.outputPath(`navigation-${width}-${locale}-${theme}.png`), fullPage: true });
        if (compact) {
          const geometry = await page.locator("#compact-navigation").evaluate(element => ({ top: element.getBoundingClientRect().top, bottom: element.getBoundingClientRect().bottom, header: element.closest("header")!.getBoundingClientRect().bottom }));
          expect(Math.abs(geometry.top - geometry.header)).toBeLessThan(1);
          expect(Math.abs(geometry.bottom - 900)).toBeLessThan(1);
          await page.keyboard.press("Escape");
          await expect(trigger).toBeFocused();
          expect(await page.evaluate(() => document.body.style.overflow)).toBe("");
        } else {
          const account = page.locator('button[aria-controls="account-dropdown"]');
          await account.click();
          await page.keyboard.press("Tab");
          await expect(page.locator('#account-dropdown a[href="/account"]')).toBeFocused();
          await page.keyboard.press("Escape"); await expect(account).toBeFocused();
          await account.click(); await page.locator("#account-details h1").click();
          await expect(account).toHaveAttribute("aria-expanded", "false");
        }
        await settings.click();
        await expect(settings).toHaveAttribute("aria-expanded", "true");
        const settingsPanel = page.locator(".kill-switch-settings-panel");
        const popupBounds = await settingsPanel.boundingBox();
        const headerBounds = await page.locator(".account-header").boundingBox();
        expect(popupBounds && popupBounds.x >= 0 && popupBounds.x + popupBounds.width <= width).toBeTruthy();
        expect(popupBounds && headerBounds && Math.abs(popupBounds.y - headerBounds.y - headerBounds.height) < 1).toBeTruthy();
        await expect(settingsPanel.getByRole("status")).toHaveCount(2);
        const actions = settingsPanel.getByRole("button");
        await expect(actions).toHaveCount(4);
        await settings.focus();
        for (const action of await actions.all()) { await page.keyboard.press("Tab"); await expect(action).toBeFocused(); }
        for (const button of await actions.all()) {
          expect(await button.evaluate(element => {
            const r = element.getBoundingClientRect();
            return element.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
          })).toBe(true);
        }
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
        await page.screenshot({ path: info.outputPath(`settings-${width}-${locale}-${theme}.png`), fullPage: true });
        await page.keyboard.press("Escape"); await expect(settings).toBeFocused();
        await expect(actions.first()).toBeHidden();
      }
    }
    if (width === 1280) {
      const settings = page.locator(".kill-switch-settings > button");
      await settings.click();
      await page.locator(".kill-switch-settings-panel").getByRole("button").first().focus();
      await page.setViewportSize({ width: 1279, height: 900 });
      await expect(settings).toHaveAttribute("aria-expanded", "false");
      await expect(settings).toBeFocused();
      await page.setViewportSize({ width, height: 900 });
      await (await navigationLink(page, "/api-keys")).focus();
      await page.setViewportSize({ width: 1279, height: 900 });
      await expect(page.locator('button[aria-controls="compact-navigation"]')).toBeFocused();
      await page.setViewportSize({ width, height: 900 });
    }
    if (width === 375) {
      await page.setViewportSize({ width, height: 320 });
      await page.locator('button[aria-controls="compact-navigation"]').click();
      const panel = page.locator("#compact-navigation");
      await panel.evaluate(element => { element.scrollTop = 100; });
      expect(await panel.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
      expect(await page.evaluate(() => window.scrollY)).toBe(0);
      await page.keyboard.press("Escape");
    }
    await expect(page.locator("[data-navigation-stable='yes']")).toHaveCount(1);
    await expect(page.locator(".account-sidebar")).toHaveCount(0);
    expect(posts).toBe(0);
  });
}

test("unknown STOP keeps one request key through menu, pending state and breakpoint changes", async ({ page }) => {
  await fixtureStops(page);
  await page.setViewportSize({ width: 1279, height: 900 });
  let release = () => {};
  const gate = new Promise<void>(resolve => { release = resolve; });
  const keys: string[] = [];
  await page.route("**/api/paper/kill-switch/stop", async route => {
    keys.push(route.request().headers()["idempotency-key"] ?? "");
    if (keys.length === 1) await gate;
    await route.fulfill({ status: 503, json: { detail: "TRADING_STOP_UNAVAILABLE" } });
  });
  await register(page);
  const trigger = page.locator('button[aria-controls="compact-navigation"]');
  await trigger.click();
  const settings = page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true });
  await settings.click();
  const stop = page.locator('.kill-switch-settings-group[aria-label="PAPER"] > button[aria-label]').first();
  try {
    await stop.click();
    await expect(trigger).toHaveAttribute("aria-expanded", "false");
    await expect(stop).toBeDisabled();
    await expect.poll(() => keys.length).toBe(1);
    await trigger.click();
    await page.getByRole("button", { name: "Paper", exact: true }).click();
    await page.getByRole("button", { name: "Live", exact: true }).click();
    await page.getByRole("link", { name: "Spot", exact: true }).focus();
    await page.setViewportSize({ width: 1280, height: 900 });
    await expect(page.locator(".account-market-dropdown")).toHaveCount(0);
    await expect(stop).toBeDisabled();
    expect(keys).toHaveLength(1);
  } finally { release(); }
  await expect(stop).toBeDisabled();
  await expect(page.locator(".kill-switch-unknown")).toBeHidden();
  await settings.click();
  await expect(page.locator(".kill-switch-unknown")).toBeVisible();
  expect(keys).toHaveLength(1);
  await page.setViewportSize({ width: 375, height: 900 });
  await trigger.click();
  await expect(page.locator(".kill-switch-unknown")).toBeHidden();
  await page.keyboard.press("Escape");
  expect(keys).toHaveLength(1);
  await page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true }).click();
  await page.getByRole("button", { name: "หยุดบอท Paper — ส่งคำขอหยุดเดิมซ้ำ", exact: true }).click();
  await expect.poll(() => keys.length).toBe(2);
  expect(keys[0]).toBeTruthy(); expect(keys[1]).toBe(keys[0]);
});

test("STOP details closes navigation and owns focus across resize; routing keeps session", async ({ page }) => {
  await fixtureStops(page, true);
  await page.route("**/api/paper/kill-switch/fixture-stop/resume-summary", route => route.fulfill({ json: {
    status: stopStatus("PAPER", true), positions: [], snapshot_revision: 0, reconciled_at: null,
  } }));
  await page.route("**/api/paper/kill-switch/fixture-stop/effects?**", route => route.fulfill({ json: {
    mode: "PAPER", stop_id: "fixture-stop", effects_revision: 0, items: [], next_cursor: null, snapshot_at: "2026-11-12T00:00:00Z",
  } }));
  await page.setViewportSize({ width: 375, height: 900 });
  await register(page);
  const owner = await page.getByTestId("user-id").textContent();
  await page.locator('button[aria-controls="compact-navigation"]').click();
  const settings = page.getByRole("button", { name: "ตั้งค่าการหยุด", exact: true });
  await settings.click();
  await expect(page.locator('button[aria-controls="compact-navigation"]')).toHaveAttribute("aria-expanded", "false");
  await page.getByRole("region", { name: "PAPER", exact: true }).getByRole("button", { name: "ดูรายละเอียด", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("PAPER");
  await page.setViewportSize({ width: 1280, height: 900 });
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(settings).toBeFocused();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("");
  await (await navigationLink(page, "/security")).click();
  await expect(page.getByTestId("totp-panel")).toBeVisible();
  await page.goBack(); await expect(page.getByTestId("user-id")).toHaveText(owner ?? "");
  await page.goForward(); await expect(page.getByTestId("totp-panel")).toBeVisible();
  await page.reload(); await expect(page.getByTestId("totp-panel")).toBeVisible();
});

test("long storage warnings stay inside the scrollable Settings panel", async ({ page }, info) => {
  let posts = 0;
  page.on("request", request => { if (request.method() === "POST" && request.url().includes("kill-switch")) posts++; });
  await page.addInitScript(() => {
    const blocked = () => { throw new DOMException("fixture storage blocked", "SecurityError"); };
    Storage.prototype.getItem = blocked;
    Storage.prototype.setItem = blocked;
  });
  await fixtureStops(page);
  await page.setViewportSize({ width: 375, height: 320 });
  await register(page);
  await language(page, "en");
  const settings = page.locator(".kill-switch-settings > button");
  await expect(page.locator(".kill-switch-unknown:visible")).toHaveCount(0);
  await settings.click();
  const panel = page.locator(".kill-switch-settings-panel");
  await expect(panel.getByRole("alert")).toHaveCount(2);
  for (const alert of await panel.getByRole("alert").all()) {
    await expect(alert).toContainText("Browser storage is unavailable");
    await expect(alert.locator("p")).toHaveCSS("color", "rgb(217, 45, 32)");
  }
  const bounds = await panel.boundingBox();
  expect(bounds && bounds.y >= 0 && bounds.y + bounds.height <= 320).toBeTruthy();
  await panel.evaluate(element => { element.scrollTop = element.scrollHeight; });
  expect(await panel.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await page.screenshot({ path: info.outputPath("settings-storage-warning-scroll.png") });
  await page.keyboard.press("Escape");
  await expect(settings).toBeFocused();
  await expect(page.locator(".kill-switch-unknown:visible")).toHaveCount(0);
  expect(posts).toBe(0);
});

for (const [width, height] of [[375, 900], [1024, 900], [1440, 900], [1024, 480]] as const) {
  test(`header mode cues remain visible while scrolling at ${width}x${height}`, async ({ page }, info) => {
    await fixtureStops(page);
    await page.route("**/api/market-catalog", route => route.fulfill({ json: { active_pairs: [] } }));
    let posts = 0;
    page.on("request", request => { if (request.method() === "POST" && /\/api\/(?:paper|live)\/(?:orders|order-requests|protections|protection-requests|kill-switch|risk-limit)(?:[/?]|$)/.test(request.url())) posts++; });
    await page.setViewportSize({ width, height });
    await register(page);
    for (const [path, mode] of [["/paper/trade", "PAPER"], ["/live/trade", "LIVE"]]) {
      await page.evaluate(() => window.scrollTo(0, 0));
      await (await navigationLink(page, path!)).click();
      await expect(page).toHaveURL(new RegExp(`${path}$`));
      await expect(page.locator(".account-brand")).toHaveText("TiewTrade");
      const bar = page.locator(".trade-workspace-bar");
      const cue = width < 1280 ? page.locator(".account-current-mode") : page.locator('.account-primary .account-market-trigger[data-active="true"]');
      await expect(cue).toContainText(mode === "PAPER" ? "Paper" : "Live");
      await expect(bar.locator(".rounded-full")).toHaveCount(0);
      const input = page.locator(".trade-workspace-form input").first();
      await input.evaluate(element => element.setAttribute("data-stable-draft", "yes"));
      await page.evaluate(() => window.scrollTo(0, 400));
      const headerHeight = width < 1280 ? 56 : 64;
      if (width < 1024 || height < 768) {
        await expect(bar).toHaveCSS("position", "sticky");
        await expect.poll(async () => (await bar.boundingBox())?.y).toBe(headerHeight);
      }
      const bounds = await bar.boundingBox();
      expect(bounds && bounds.y >= headerHeight && bounds.y + bounds.height <= height).toBeTruthy();
      const settings = page.locator(".kill-switch-settings > button");
      await settings.click(); await page.keyboard.press("Escape");
      await expect(page.locator('[data-stable-draft="yes"]')).toHaveCount(1);
      await expect(cue).toContainText(mode === "PAPER" ? "Paper" : "Live");
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await page.screenshot({ path: info.outputPath(`trade-mode-${width}-${mode}.png`) });
    }
    expect(posts).toBe(0);
  });
}


test("dense workspace fills the real chart and preserves it across breakpoints", async ({ page }, info) => {
  execFileSync(backendPython,
    ["-X", "utf8", "../specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py", "seed-3m"],
    { cwd: "../backend", env: e2eEnvironment(), stdio: "pipe" });
  await fixtureStops(page);
  // Reuse the PaperTradePage snapshot pattern: table geometry needs an active wallet.
  // Only this read response is simulated; candles and the chart renderer remain real.
  await page.route(/\/api\/paper\/trade(?:\?|$)/, route => route.fulfill({ json: {
    mode: "PAPER", account_use: "MANUAL", base: new URL(route.request().url()).searchParams.get("base"),
    quote: "USDT", catalog_revision: 1, snapshot_at: new Date().toISOString(),
    admission_ready: false, admission_reasons: ["RISK_LIMIT_UNSET"], protection_enabled: false,
    wallet: { wallet_id: "dense-wallet", episode_id: "dense-episode", balance: "10000",
      reserved_quote: "0", available_quote: "10000", base_balances: [], source_availability: "READY", revision: 1 },
  } }));
  await page.route(/\/api\/paper\/orders\?/, route => route.fulfill({ json: {
    orders: [], snapshot_at: new Date().toISOString(), next_cursor: null,
  } }));
  let writes = 0;
  page.on("request", request => {
    if (request.method() === "POST" && /\/api\/(?:paper|live)\//.test(request.url())) writes++;
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await register(page);
  await page.locator(".account-desktop-actions .account-theme-toggle").click();
  await expect(page.locator("html")).toHaveAttribute("data-color-scheme", "dark");
  await (await navigationLink(page, "/paper/trade")).click();
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  const canvas = chart.getByTestId("chart-canvas");
  await expect(canvas.locator("canvas").first()).toBeVisible();
  await canvas.evaluate(element => element.setAttribute("data-dense-stable", "yes"));
  const amount = page.locator("#paper-bot-budget");
  await amount.evaluate(element => element.setAttribute("data-dense-draft", "yes"));
  await expect(amount).toBeEnabled();
  await amount.fill("123.45");
  const timeframe = page.getByLabel("Timeframe", { exact: true });
  await timeframe.selectOption("3m");
  await expect(chart.getByTestId("chart-summary")).toContainText("3m");
  await expect(chart.getByText("200.000000000000000001 USDT", { exact: true })).toBeVisible();
  const originalTimeframe = await timeframe.inputValue();
  const pair = page.locator("#paper-workspace-pair");
  const originalPair = await pair.inputValue();
  for (const width of [375, 768, 1024, 1279, 1280, 1440, 2553]) {
    await page.setViewportSize({ width, height: width === 2553 ? 1240 : 1000 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.locator('[data-dense-stable="yes"]')).toHaveCount(1);
    await expect(page.locator('[data-dense-draft="yes"]')).toHaveCount(1);
    await expect(amount).toHaveValue("123.45");
    await expect(pair).toHaveValue(originalPair);
    await expect(timeframe).toHaveValue(originalTimeframe);
    await expect.poll(async () => canvas.evaluate(element => {
      const frame = element.closest(".chart-frame")!.getBoundingClientRect();
      const area = element.closest(".trading-chart-area")!.getBoundingClientRect();
      const bounds = element.getBoundingClientRect();
      const table = element.querySelector(".tv-lightweight-charts")!.getBoundingClientRect();
      return Math.max(Math.abs(frame.width - area.width), Math.abs(frame.height - area.height),
        Math.abs(bounds.height - frame.height), Math.abs(table.width - bounds.width), Math.abs(table.height - bounds.height));
    })).toBeLessThanOrEqual(2);
    const column = await page.locator(".trade-workspace-chart").boundingBox();
    expect(column && column.height >= (width < 1024 ? 420 : 352)).toBeTruthy();
    await expect(page.locator(".account-content-trade")).toHaveCSS("padding", "4px");
    await expect(page.locator(".trade-workspace-bar")).toHaveCSS("padding", "8px");
    await expect(page.locator(".trade-workspace-form")).toHaveCSS("padding", "8px");
    if (width >= 1024) {
      await expect(page.locator(".trade-workspace")).toHaveCSS("gap", "4px");
      const orders = await page.locator(".trade-workspace-orders").boundingBox();
      expect(orders && column && orders.height >= 160 && column.height > orders.height).toBeTruthy();
      expect(Math.abs(column!.height / (column!.height + orders!.height) - 0.64)).toBeLessThan(0.01);
      const bar = (await page.locator(".trade-workspace-bar").boundingBox())!;
      const form = (await page.locator(".trade-workspace-form").boundingBox())!;
      const workspace = (await page.locator(".trade-workspace").boundingBox())!;
      expect(Math.abs(bar.y - form.y)).toBeLessThanOrEqual(1);
      expect(Math.abs(bar.x - column!.x)).toBeLessThanOrEqual(1);
      expect(Math.abs(bar.width - column!.width)).toBeLessThanOrEqual(1);
      expect(Math.abs(orders!.width - column!.width)).toBeLessThanOrEqual(1);
      expect(Math.abs(form.x - (bar.x + bar.width) - 4)).toBeLessThanOrEqual(1);
      expect(Math.abs(form.y + form.height - (workspace.y + workspace.height - 1))).toBeLessThanOrEqual(1);
      await page.getByRole("tab", { name: "ประวัติออเดอร์", exact: true }).click();
      const history = await page.locator(".trade-workspace-orders").boundingBox();
      expect(Math.abs(history!.height - orders!.height)).toBeLessThanOrEqual(1);
      await page.getByRole("tab", { name: "ออเดอร์ที่เปิดอยู่", exact: true }).click();
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    await expect(timeframe).toBeVisible();
    const reset = page.locator(".trade-workspace-bar").getByRole("button", { name: "รีเซ็ตกราฟ", exact: true });
    await expect(reset).toBeVisible();
    const pairBounds = await pair.boundingBox();
    const timeframeBounds = await timeframe.boundingBox();
    const resetBounds = await reset.boundingBox();
    expect(pairBounds && timeframeBounds && resetBounds).toBeTruthy();
    expect(Math.abs(pairBounds!.y - timeframeBounds!.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(pairBounds!.y - resetBounds!.y)).toBeLessThanOrEqual(1);
    expect(timeframeBounds!.x).toBeGreaterThanOrEqual(pairBounds!.x + pairBounds!.width);
    expect(resetBounds!.x).toBeGreaterThanOrEqual(timeframeBounds!.x + timeframeBounds!.width);
    await expect(chart.getByTestId("chart-summary")).toBeVisible();
    await expect(chart.locator('a[href*="tradingview"]')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: info.outputPath(`dense-chart-${width}.png`) });
  }
  await page.setViewportSize({ width: 1024, height: 480 });
  const paperForm = page.locator(".trade-workspace-form");
  const paperSubmit = paperForm.getByRole("button", { name: "เริ่มบอท", exact: true });
  await paperSubmit.scrollIntoViewIfNeeded();
  await expect(paperSubmit).toBeVisible();
  await paperForm.evaluate(element => element.scrollTo(0, element.scrollHeight));
  expect(await paperForm.evaluate(element => element.scrollTop)).toBeGreaterThan(0);
  await expect(amount).toHaveValue("123.45");
  await (await navigationLink(page, "/chart")).click();
  await expect(page.locator(".trading-workspace canvas").first()).toBeVisible();
  const standalone = page.locator(".trading-workspace .trading-chart-area");
  await expect(standalone).toHaveCSS("padding", "0px");
  await expect.poll(async () => standalone.evaluate(element => {
    const bounds = element.getBoundingClientRect();
    const frame = element.querySelector(".chart-frame")!.getBoundingClientRect();
    return Math.abs(bounds.height - frame.height);
  })).toBeLessThanOrEqual(2);
  // Shared flex sizing must leave typed errors and retry controls usable on small screens.
  await page.route(/\/api\/market-data\/chart\/(?:history|live)\?/, route => route.fulfill({
    status: 504, json: { detail: "CHART_DEADLINE_EXCEEDED" },
  }));
  await page.setViewportSize({ width: 375, height: 900 });
  await page.reload();
  const failedChart = page.getByTestId("candlestick-chart");
  await expect(failedChart.getByRole("alert").first()).toBeVisible();
  const retry = failedChart.getByRole("button", { name: "ลองใหม่", exact: true });
  await expect(retry).toBeVisible();
  await retry.scrollIntoViewIfNeeded();
  const retryBox = await retry.boundingBox();
  expect(retryBox && retryBox.height >= 44 && retryBox.width >= 44).toBeTruthy();
  await page.screenshot({ path: info.outputPath("dense-chart-error-375.png") });
  await (await navigationLink(page, "/paper/trade")).click();
  const embeddedError = page.getByTestId("candlestick-chart");
  await expect(embeddedError.getByRole("alert").first()).toBeVisible();
  await expect(embeddedError.getByRole("button", { name: "ลองใหม่", exact: true })).toBeVisible();
  const errorLayout = await embeddedError.evaluate(element => {
    const area = element.querySelector(".trading-chart-area")!.getBoundingClientRect();
    const frame = element.querySelector(".chart-frame")!.getBoundingClientRect();
    const retry = element.querySelector(".trading-chart-area button")!.getBoundingClientRect();
    return { areaBottom: area.bottom, frameBottom: frame.bottom, frameTop: frame.top,
      frameHeight: frame.height, retryBottom: retry.bottom };
  });
  expect(errorLayout.frameHeight).toBeGreaterThan(0);
  expect(errorLayout.frameTop).toBeGreaterThanOrEqual(errorLayout.retryBottom);
  expect(errorLayout.frameBottom).toBeLessThanOrEqual(errorLayout.areaBottom + 1);
  await (await navigationLink(page, "/live/trade")).click();
  await expect(page.locator('.trade-workspace-form button[type="submit"]')).toBeDisabled();
  for (const width of [1024, 1440, 2553]) {
    await page.setViewportSize({ width, height: width === 2553 ? 1240 : 900 });
    const bar = (await page.locator(".trade-workspace-bar").boundingBox())!;
    const form = (await page.locator(".trade-workspace-form").boundingBox())!;
    const workspace = (await page.locator(".trade-workspace").boundingBox())!;
    expect(Math.abs(bar.y - form.y)).toBeLessThanOrEqual(1);
    expect(Math.abs(form.x - (bar.x + bar.width) - 4)).toBeLessThanOrEqual(1);
    expect(Math.abs(form.y + form.height - (workspace.y + workspace.height - 1))).toBeLessThanOrEqual(1);
  }
  await page.setViewportSize({ width: 375, height: 900 });
  await expect(page.locator(".account-current-mode")).toHaveText("Live");
  expect(writes).toBe(0);
});
