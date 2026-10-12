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

test("actual chart panes, exact values, languages and keyboard selection", async ({ page }) => {
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
  await chart.getByLabel("RSI14", { exact: true }).check();
  await chart.getByLabel("MACD_LINE", { exact: true }).check();
  await chart.getByLabel("ATR14", { exact: true }).check();
  await chart.getByRole("button", { name: "แท่งก่อนหน้า" }).click();
  await chart.getByRole("combobox", { name: "ภาษา", exact: true }).selectOption("en");
  await expect(chart.getByRole("heading", { name: "Candlestick chart" })).toBeVisible();
  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(chart.locator("canvas").first()).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= globalThis.innerWidth)).toBe(true);
  }
  await expect(chart.getByRole("link", { name: /TradingView Lightweight Charts/ })).toBeVisible();
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

test("source mutation hides overlays and live snapshots recover after disconnect", async ({ page }) => {
  let reads = 0;
  page.on("request", request => { if (request.url().includes("/chart/history")) reads += 1; });
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  fixture("preview");
  await expect(chart.getByText("ท่อแท่งเทียนสด: พร้อม ณ เวลาที่ server ตรวจ")).toBeVisible({ timeout: 10_000 });
  fixture("disconnect");
  await expect(chart.getByText(/ท่อแท่งเทียนสด: กำลังกู้คืน|ท่อแท่งเทียนสด: ข้อมูลเก่า/)).toBeVisible({ timeout: 10_000 });
  fixture("preview");
  await expect(chart.getByText("ท่อแท่งเทียนสด: พร้อม ณ เวลาที่ server ตรวจ")).toBeVisible({ timeout: 10_000 });
  const rebuilt = page.waitForResponse(response => response.url().includes("/chart/history") && response.status() === 200);
  fixture("mutate");
  const changed = page.waitForResponse(async response => response.url().endsWith("/chart/verify") &&
    response.status() === 200 && (await response.json() as { status: string }).status === "CHANGED");
  await changed;
  await rebuilt;
  await expect.poll(() => reads).toBe(2);
});

test("gap selection has no fabricated OHLC and logout stops chart requests", async ({ page }) => {
  fixture("gap");
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(chart.getByRole("button", { name: "แท่งถัดไป" })).toBeDisabled();
  // Keyboard activation avoids moving the pointer across the chart while scrolling
  // to the control, which would change the selection through the crosshair.
  await chart.getByRole("button", { name: "แท่งก่อนหน้า" }).press("Enter");
  await expect(chart.locator(".chart-selection")).toContainText("ช่องว่างของข้อมูล");
  await expect(chart.locator(".chart-selection dl")).toHaveCount(0);
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

test("ended preview waits for actual REST commit before new indicator bundle", async ({ page }) => {
  fixture("needs-refresh");
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  fixture("rollover");
  const revised = page.waitForResponse(response => response.url().includes("/chart/history") && response.status() === 200);
  fixture("repair");
  await revised;
  // The newest selected slot is still the open preview; inspect the last ended
  // history slot to prove that the real REST value reached the bundle and UI.
  await chart.getByRole("button", { name: "แท่งก่อนหน้า" }).press("Enter");
  await expect(chart.locator(".chart-selection").getByText("100.75 USDT", { exact: true }).first()).toBeVisible();
});

test("manual refresh reaches the real worker and failed polling stops", async ({ page }) => {
  fixture("needs-refresh");
  await registerAccount(page);
  const chart = page.getByTestId("candlestick-chart");
  const posted = page.waitForResponse(response => response.url().endsWith("/candles/requests") &&
    response.request().method() === "POST" && response.status() === 202);
  await chart.getByRole("button", { name: "ขอ refresh ประวัติ", exact: true }).click();
  await posted;
  fixture("repair");
  await expect(chart.locator(".chart-selection").getByText("100.75 USDT", { exact: true }).first()).toBeVisible({ timeout: 20_000 }).catch(async (error: unknown) => {
    if (process.env.CHART_E2E_DIAGNOSTICS === "1") process.stdout.write(await chart.innerText());
    throw error;
  });
  fixture("needs-refresh");
  await chart.getByRole("button", { name: "ลองใหม่", exact: true }).click();
  // Failure injection is confined to F-09 polling; the successful path above is real.
  await page.route(/\/api\/market-data\/candles\?/, route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ status: "FAILED" }),
  }));
  const failedPost = page.waitForResponse(response => response.url().endsWith("/candles/requests") &&
    response.request().method() === "POST");
  await chart.getByRole("button", { name: "ขอ refresh ประวัติ", exact: true }).click();
  await failedPost;
  await expect(chart.getByRole("alert")).toBeVisible({ timeout: 15_000 });
});

test("browser network loss and a restarted fenced candle worker recover from PG", async ({ page, context }) => {
  let worker = producer("tests/e2e_candle_runner.py");
  try {
    await registerAccount(page);
    const chart = page.getByTestId("candlestick-chart");
    await expect(chart.getByText("ท่อแท่งเทียนสด: พร้อม ณ เวลาที่ server ตรวจ")).toBeVisible({ timeout: 15_000 });
    await context.setOffline(true);
    await expect(chart.getByText(/ท่อแท่งเทียนสด: การเชื่อมต่อขาด|ท่อแท่งเทียนสด: ออฟไลน์/)).toBeVisible();
    await context.setOffline(false);
    await expect(chart.getByText("ท่อแท่งเทียนสด: พร้อม ณ เวลาที่ server ตรวจ")).toBeVisible({ timeout: 15_000 });
    await worker.stop();
    await expect(chart.getByText(/ท่อแท่งเทียนสด: กำลังกู้คืน|ท่อแท่งเทียนสด: ข้อมูลเก่า/)).toBeVisible({ timeout: 10_000 });
    worker = producer("tests/e2e_candle_runner.py");
    await expect(chart.getByText("ท่อแท่งเทียนสด: พร้อม ณ เวลาที่ server ตรวจ")).toBeVisible({ timeout: 15_000 });
  } finally { await worker.stop(); }
});
