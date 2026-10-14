import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { setTimeout, clearTimeout } from "node:timers";
import { expect, test, type Page } from "@playwright/test";
import { e2eEnvironment } from "./helpers/environment";
import { PASSWORD } from "./helpers/totp";

function fixture(action: string): void {
  execFileSync(process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
    ["-X", "utf8", "../specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py", action],
    { cwd: "../backend", env: e2eEnvironment(), stdio: "pipe" });
}

async function registerAccount(page: Page): Promise<string> {
  const email = `chart-${randomUUID()}@example.com`;
  await page.goto("/");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("candlestick-chart")).toBeVisible();
  return email;
}

function waitForLiveStatus(page: Page, expected: string[]) {
  return page.waitForResponse(async response => {
    if (!response.url().includes("/market-data/chart/live") || response.status() !== 200) return false;
    try {
      const body = await response.json() as { status?: string };
      return body.status !== undefined && expected.includes(body.status);
    } catch {
      // Navigation and offline transitions may discard a completed response body.
      return false;
    }
  });
}

function producer(script: string) {
  const directory = mkdtempSync(join(tmpdir(), "tiewtrade-chart-"));
  const control = join(directory, "control");
  const mode = (value: string) => writeFileSync(control, value);
  mode("healthy");
  const worker = spawn(process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
    ["-B", script, "--control-file", control], { cwd: "../backend", env: e2eEnvironment(), stdio: "ignore" });
  const exited = new Promise<void>((resolve, reject) => {
    worker.once("exit", () => resolve());
    worker.once("error", () => reject(new Error("F12_BROWSER_PRODUCER_FAILED")));
  });
  let stopped = false;
  const stop = async () => {
    if (stopped) return;
    stopped = true;
    mode("stop");
    const timer = setTimeout(() => { worker.kill(); }, 3000);
    await exited;
    clearTimeout(timer);
    rmSync(directory, { recursive: true });
  };
  return { mode, stop };
}

test.beforeEach(({ page }) => {
  fixture("seed");
  if (process.env.CHART_E2E_DIAGNOSTICS === "1") {
    page.on("pageerror", error => process.stdout.write(`browser_error: ${error.name}: ${error.message}\n`));
    page.on("response", response => {
      const path = new URL(response.url()).pathname;
      if (!path.includes("/market-data/chart/") && !path.includes("/market-data/candles")) return;
      void response.json().then((body: { detail?: string; status?: string; accepted?: boolean;
        refresh?: { required: boolean }; rows?: unknown[] }) => {
        process.stdout.write(JSON.stringify({ path, http: response.status(), detail: body.detail,
          status: body.status, accepted: body.accepted, refresh: body.refresh?.required,
          rows: body.rows?.length }) + "\n");
      }).catch(() => undefined);
    });
  }
});

test("actual chart panes, exact values and keyboard selection", async ({ page }) => {
  const errors: string[] = [];
  const requests: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => requests.push(request.url()));
  page.on("response", response => {
    if (response.url().includes("/market-data/chart/history") && response.status() !== 200) {
      void response.json().then((body: { detail?: string }) => {
        process.stdout.write(`chart history refusal: ${response.status()} ${body.detail ?? "UNKNOWN"}\n`);
      }).catch(() => undefined);
    }
  });
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart).toBeVisible();
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(chart.locator("canvas").first()).toBeVisible();
  await expect(chart.getByRole("button", { name: "รีเซ็ตกราฟ" })).toBeEnabled();
  await expect(chart.getByLabel("MACD_LINE", { exact: true })).toHaveCount(0);
  for (const name of ["EMA20", "EMA50", "EMA200", "RSI14", "ATR14"]) {
    await expect(chart.getByText(name, { exact: true })).toHaveCount(0);
  }
  await expect(chart.getByRole("combobox", { name: "ภาษา", exact: true })).toHaveCount(0);
  await expect(chart.getByRole("heading", { name: "กราฟแท่งเทียน" })).toHaveCount(0);
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(chart.locator("canvas").first()).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= globalThis.innerWidth)).toBe(true);
  }
  await expect(chart.getByRole("link", { name: "Charting by TradingView", exact: true })).toBeVisible();
  await page.screenshot({ path: "../specs/features/2026-10-12-candlestick-chart/evidence/chart-browser.png", fullPage: true });
  expect(errors).toEqual([]);
  expect(requests.some(url => /binance|\/orders|\/trading-account\/use/i.test(url))).toBe(false);
});

test("module pages preserve navigation history, deep links and cancel inactive chart work", async ({ page }) => {
  await registerAccount(page);
  await expect(page).toHaveURL(/\/chart$/);
  await expect(page.getByTestId("candlestick-chart").getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  let chartCalls = 0;
  page.on("request", request => { if (request.url().includes("/market-data/chart/")) chartCalls += 1; });
  for (const [name, testId] of [["API key", "api-key-panel"], ["บัญชีเทรด", "trading-account-panel"], ["TOTP / 2FA", "totp-panel"], ["ราคาสด", "realtime-prices"]] as const) {
    await page.getByRole("link", { name, exact: true }).click();
    await expect(page.getByTestId(testId)).toBeVisible();
    await expect(page.getByTestId("candlestick-chart")).toHaveCount(0);
    await expect(page.locator('#account-navigation [aria-current="page"]')).toHaveText(name);
  }
  const stopped = chartCalls;
  await page.waitForTimeout(4000);
  expect(chartCalls).toBe(stopped);
  await page.goBack();
  await expect(page.getByTestId("totp-panel")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("realtime-prices")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("realtime-prices")).toBeVisible();
  await page.goto("/api-keys");
  await expect(page.getByTestId("api-key-panel")).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  const desktopToggle = page.getByRole("button", { name: "เปิดเมนูบัญชี" });
  const sidebar = page.locator("#account-navigation");
  await expect(sidebar.locator('[aria-current="page"]')).toHaveCSS("background-color", "rgb(236, 243, 255)");
  await expect(sidebar.locator('[aria-current="page"]')).toHaveCSS("color", "rgb(70, 95, 255)");
  await desktopToggle.click();
  await expect(desktopToggle).toHaveAttribute("aria-expanded", "false");
  await expect.poll(() => sidebar.evaluate(el => el.getBoundingClientRect().width)).toBe(90);
  await expect(page.getByTestId("api-key-panel")).toBeVisible();
  await desktopToggle.click();
  await expect.poll(() => sidebar.evaluate(el => el.getBoundingClientRect().width)).toBe(290);
  await page.setViewportSize({ width: 375, height: 812 });
  const trigger = page.getByRole("button", { name: "เปิดเมนูบัญชี" });
  await trigger.click();
  await page.getByRole("link", { name: "กราฟแท่งเทียน", exact: true }).click();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("candlestick-chart")).toBeVisible();
});

test("live snapshots recover after disconnect without indicator reads", async ({ page }) => {
  const legacyReads: string[] = [];
  page.on("request", request => {
    if (request.url().includes("/chart/history") || request.url().endsWith("/chart/verify")) {
      legacyReads.push(request.url());
    }
  });
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  let live = waitForLiveStatus(page, ["READY"]);
  fixture("preview");
  await live;
  live = waitForLiveStatus(page, ["RECOVERING", "STALE"]);
  fixture("disconnect");
  await live;
  live = waitForLiveStatus(page, ["READY"]);
  fixture("preview");
  await live;
  await expect(chart.locator(".chart-status")).toHaveCount(0);
  expect(legacyReads).toEqual([]);
});

test("removed manual controls stay absent and logout stops chart requests", async ({ page }) => {
  fixture("gap");
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  for (const name of ["กลับช่วงล่าสุด", "เพิ่มประวัติก่อนหน้า", "ลองใหม่", "ขอ refresh ประวัติ",
    "แท่งก่อนหน้า", "แท่งถัดไป"]) {
    await expect(chart.getByRole("button", { name })).toHaveCount(0);
  }
  let calls = 0;
  page.on("request", request => { if (request.url().includes("/market-data/chart/")) calls += 1; });
  await page.getByRole("link", { name: "บัญชี", exact: true }).click();
  await page.getByRole("button", { name: "ออกจากระบบ", exact: true }).click();
  await expect(page.getByTestId("signed-out")).toBeVisible();
  const stopped = calls;
  await page.waitForTimeout(4000);
  expect(calls).toBe(stopped);
});

test("password login, series switching and actual latest-price worker", async ({ page }) => {
  const quotes = producer("tests/e2e_realtime_runner.py");
  try {
    const email = await registerAccount(page);
    await page.getByRole("link", { name: "ราคาสด", exact: true }).click();
    await expect(page.getByTestId("price-BTC")).toContainText("83348.47 USDT", { timeout: 15_000 });
    await page.getByRole("link", { name: "บัญชี", exact: true }).click();
  await page.getByRole("button", { name: "ออกจากระบบ", exact: true }).click();
    await expect(page.getByTestId("signed-out")).toBeVisible();
    await page.goto("/chart");
    await page.getByLabel("อีเมล").fill(email);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
    await page.getByTestId("submit").click();
    const chart = page.getByTestId("candlestick-chart");
    await expect(chart).toBeVisible();
    await chart.getByRole("combobox", { name: "คู่เทรด", exact: true }).selectOption("ETH");
    await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
    await chart.getByRole("combobox", { name: "Timeframe", exact: true }).selectOption("5m");
    await chart.getByRole("combobox", { name: "Timeframe", exact: true }).selectOption("1h");
    await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  } finally { await quotes.stop(); }
});

test("ended preview waits for actual REST commit before the revised history response", async ({ page }) => {
  fixture("needs-refresh");
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  fixture("rollover");
  const revised = page.waitForResponse(response => response.url().includes("/candles/pages") && response.status() === 200);
  fixture("repair");
  const response = await revised;
  const body = await response.json() as { rows: Array<{ close: string }> };
  expect(body.rows.some(candle => candle.close === "100.75")).toBe(true);
});

test("browser network loss and a restarted fenced candle worker recover from PG", async ({ page, context }) => {
  let worker = producer("tests/e2e_candle_runner.py");
  try {
    await registerAccount(page);
    const chart = page.getByTestId("candlestick-chart");
    await waitForLiveStatus(page, ["READY"]);
    await context.setOffline(true);
    await expect.poll(() => page.evaluate(() => globalThis.navigator.onLine)).toBe(false);
    const online = waitForLiveStatus(page, ["READY"]);
    await context.setOffline(false);
    await online;
    const recovering = waitForLiveStatus(page, ["RECOVERING", "STALE"]);
    await worker.stop();
    await recovering;
    const ready = waitForLiveStatus(page, ["READY"]);
    worker = producer("tests/e2e_candle_runner.py");
    await ready;
    await expect(chart.locator(".chart-status")).toHaveCount(0);
  } finally { await worker.stop(); }
});
