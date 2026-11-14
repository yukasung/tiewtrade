import { navigationLink } from "./helpers/ui";
import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomUUID } from "node:crypto";
import { setTimeout, clearTimeout } from "node:timers";
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { backendPython, e2eEnvironment } from "./helpers/environment";
import { PASSWORD } from "./helpers/totp";
import type { CandlePage, ChartLive } from "../src/chart/api";

function fixture(action: string): void {
  execFileSync(backendPython,
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

async function expectLiveStatus(page: Page, expected: string[]) {
  await expect.poll(async () => {
    const response = await page.request.get(
      "/api/market-data/chart/live?base=BTC&quote=USDT&timeframe=1h",
    );
    const body = await response.json() as { status?: string; detail?: string; reason?: string };
    if (process.env.CHART_E2E_DIAGNOSTICS === "1") {
      process.stdout.write(JSON.stringify({ probe: "live-status", http: response.status(),
        status: body.status, detail: body.detail, reason: body.reason }) + "\n");
    }
    if (response.status() !== 200) return false;
    return body.status !== undefined && expected.includes(body.status);
  }).toBe(true);
}

function producer(script: string) {
  const directory = mkdtempSync(join(tmpdir(), "tiewtrade-chart-"));
  const control = join(directory, "control");
  const mode = (value: string) => writeFileSync(control, value);
  mode("healthy");
  const worker = spawn(backendPython,
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
  const pair = chart.getByRole("combobox", { name: "คู่เทรด", exact: true });
  const pairStyle = await pair.evaluate(element => {
    const style = globalThis.getComputedStyle(element);
    return {
      appearance: style.appearance,
      borderColor: style.borderColor,
      borderRadius: style.borderRadius,
      height: style.height,
    };
  });
  expect(pairStyle).toEqual({
    appearance: "none",
    borderColor: "rgb(208, 213, 221)",
    borderRadius: "8px",
    height: "44px",
  });
  await pair.focus();
  await expect(pair).toHaveCSS("border-color", "rgb(156, 185, 255)");
  const disabled = chart.getByRole("button", { name: "ยังไม่เปิดใช้งาน", exact: true });
  await expect(disabled).toBeDisabled();
  await expect(disabled).toHaveCSS("cursor", "not-allowed");
  await expect(disabled).toHaveCSS("opacity", "0.5");
  await expect(disabled).toHaveCSS("border-radius", "8px");
  await expect(chart.getByRole("link", { name: "Charting by TradingView", exact: true })).toBeVisible();
  await page.screenshot({ path: "../specs/features/2026-10-12-candlestick-chart/evidence/chart-browser.png", fullPage: true });
  expect(errors).toEqual([]);
  expect(requests.some(url => /binance|\/(?:orders|trading-account\/use|indicators)(?:[/?#]|$)/i.test(url))).toBe(false);
});

test("module pages preserve navigation history, deep links and cancel inactive chart work", async ({ page }) => {
  await registerAccount(page);
  await expect(page).toHaveURL(/\/chart$/);
  await expect(page.getByTestId("candlestick-chart").getByText("100.000000000000000001 USDT", { exact: true })).toBeVisible({ timeout: 60_000 });
  let chartCalls = 0;
  page.on("request", request => { if (request.url().includes("/market-data/chart/")) chartCalls += 1; });
  for (const [name, testId] of [["API key", "api-key-panel"], ["บัญชีเทรด", "trading-account-panel"], ["TOTP / 2FA", "totp-panel"]] as const) {
    const path = testId === "api-key-panel" ? "/api-keys" : testId === "trading-account-panel" ? "/trading-account" : "/security";
    await (await navigationLink(page, path)).click();
    await expect(page.getByTestId(testId)).toBeVisible();
    await expect(page.getByTestId("candlestick-chart")).toHaveCount(0);
    await expect(await navigationLink(page, path)).toHaveText(name);
    await expect(await navigationLink(page, path)).toHaveAttribute("aria-current", "page");
    await page.keyboard.press("Escape");
  }
  const stopped = chartCalls;
  await page.waitForTimeout(4000);
  expect(chartCalls).toBe(stopped);
  await page.goBack();
  await expect(page.getByTestId("trading-account-panel")).toBeVisible();
  await page.goForward();
  await expect(page.getByTestId("totp-panel")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("totp-panel")).toBeVisible();
  await page.goto("/api-keys");
  await expect(page.getByTestId("api-key-panel")).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  const desktopToggle = page.locator('button[aria-controls="account-dropdown"]');
  await desktopToggle.click();
  const active = page.locator('#account-dropdown [aria-current="page"]');
  await expect(active).toHaveCSS("background-color", "rgb(236, 243, 255)");
  await expect(active).toHaveCSS("color", "rgb(70, 95, 255)");
  await page.keyboard.press("Escape");
  await expect(desktopToggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".account-sidebar")).toHaveCount(0);
  await expect(page.getByTestId("api-key-panel")).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const trigger = page.getByRole("button", { name: "เปิดเมนูบัญชี" });
  await trigger.click();
  await page.getByRole("link", { name: "กราฟแท่งเทียน", exact: true }).click();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("candlestick-chart")).toBeVisible();
});

test("removed prices bookmarks return to the chart without starting a price subscription", async ({ page }, testInfo) => {
  const priceRequests: string[] = [];
  page.on("request", request => { if (request.url().includes("/market-data/prices")) priceRequests.push(request.url()); });
  page.on("websocket", socket => { if (socket.url().includes("/market-data/prices")) priceRequests.push(socket.url()); });
  const email = await registerAccount(page);
  await page.goto("/prices?from=bookmark");
  await expect(page).toHaveURL(/\/chart\?from=bookmark$/);
  await expect(page.getByTestId("candlestick-chart")).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/\/chart\?from=bookmark$/);
  await expect(page.getByTestId("candlestick-chart")).toBeVisible();

  for (const language of ["th", "en"]) {
    await page.evaluate(async value => {
      const accountPath = "/src/accountMessages.ts";
      const chartPath = "/src/chartMessages.ts";
      const account = await import(/* @vite-ignore */ accountPath) as { accountI18n: { changeLanguage: (language: string) => Promise<unknown> } };
      const chart = await import(/* @vite-ignore */ chartPath) as { chartI18n: { changeLanguage: (language: string) => Promise<unknown> } };
      await account.accountI18n.changeLanguage(value);
      await chart.chartI18n.changeLanguage(value);
    }, language);
    // Re-render through navigation, as the existing translation instances are read at render time.
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 1000 });
      const trigger = page.locator('button[aria-controls="compact-navigation"]');
      if (width === 375) await trigger.click();
      await expect(page.locator('.account-header a[href="/prices"]')).toHaveCount(0);
      await expect(page.getByRole("link", { name: /ราคาสด|Live prices/ })).toHaveCount(0);
      await (await navigationLink(page, "/account")).click();
      await expect(page.getByTestId("log-out")).toBeVisible();
      if (width === 375) await trigger.click();
      const chartLink = await navigationLink(page, "/chart");
      await chartLink.focus();
      await expect(chartLink).toBeFocused();
      await page.keyboard.press("Enter");
      if (width === 375) await expect(trigger).toHaveAttribute("aria-expanded", "false");
      const chart = page.getByTestId("candlestick-chart");
      await expect(chart).toBeVisible();
      // F-12 explicitly keeps the chart locale Thai; account navigation supports both languages.
      await expect(chart).toHaveAttribute("aria-label", "กราฟแท่งเทียน");
      await expect(chart).not.toContainText(/เมนูราคาสด|live prices page/);
      await page.screenshot({ path: testInfo.outputPath(`removed-prices-${language}-${String(width)}.png`), fullPage: true });
    }
  }

  await page.setViewportSize({ width: 1440, height: 1000 });
  await (await navigationLink(page, "/account")).click();
  await page.getByTestId("log-out").click();
  await expect(page.getByTestId("signed-out")).toBeVisible();
  await page.goto("/prices");
  await expect(page.getByTestId("signed-out")).toBeVisible();
  await expect(page).toHaveURL(/\/prices$/);
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByTestId("submit").click();
  await expect(page).toHaveURL(/\/chart$/);
  await expect(page.getByTestId("candlestick-chart")).toBeVisible();
  expect(priceRequests).toEqual([]);
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
  fixture("preview");
  await expectLiveStatus(page, ["READY"]);
  fixture("disconnect");
  await expectLiveStatus(page, ["RECOVERING", "STALE"]);
  fixture("preview");
  await expectLiveStatus(page, ["READY"]);
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
  await (await navigationLink(page, "/account")).click();
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
    await expect.poll(async () => {
      const response = await page.request.get("/api/market-data/prices");
      expect(response.status()).toBe(200);
      const view = await response.json() as { rows: { base: string; amount: string | null; readiness: string }[] };
      const btc = view.rows.find(row => row.base === "BTC");
      return { amount: btc?.amount, readiness: btc?.readiness };
    }, { timeout: 15_000 }).toEqual({ amount: "83348.47", readiness: "READY" });
    await (await navigationLink(page, "/account")).click();
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
    await expectLiveStatus(page, ["READY"]);
    await context.setOffline(true);
    await expect.poll(() => page.evaluate(() => globalThis.navigator.onLine)).toBe(false);
    await context.setOffline(false);
    await expectLiveStatus(page, ["READY"]);
    await worker.stop();
    await expectLiveStatus(page, ["RECOVERING", "STALE"]);
    worker = producer("tests/e2e_candle_runner.py");
    await expectLiveStatus(page, ["READY"]);
    await expect(chart.locator(".chart-status")).toHaveCount(0);
  } finally { await worker.stop(); }
});

type ChartObservation = {
  path: string;
  requestedBase: string;
  base: string;
  timeframe: string;
  status: string | undefined;
  rows: Pick<CandlePage["rows"][number], "open" | "high" | "low" | "close" | "open_at" | "end_at">[];
};
type ChartObserverWindow = typeof window & {
  chart3mObserver: {
    completed: ChartObservation[]; aborted: number; failure: string | null;
    requests: ChartRequestObservation[]; truncated: boolean;
  };
};
type ChartRequestObservation = {
  path: string; base: string; startedMs: number; headersMs: number | null;
  finishedMs: number | null; http: number | null; status: string | null;
  rowCount: number | null; outcome: "pending" | "complete" | "aborted" | "failed";
};
const native3mTitle = "native 3m history and live feed work for BTC and ETH without order requests";

async function attachNative3mFailure({ page }: { page: Page }, info: TestInfo) {
  if (info.title !== native3mTitle || info.status === "passed" || info.status === "skipped") return;
  let evidence: unknown = { unavailable: true };
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    evidence = await Promise.race([
      page.evaluate(() => {
        const state = (window as Partial<ChartObserverWindow>).chart3mObserver;
        if (!state) return { unavailable: true };
        const paths = ["/api/market-data/candles/pages", "/api/market-data/chart/live"];
        const statuses = ["READY", "RECOVERING", "STALE", "NO_DATA", "UNAVAILABLE"];
        const failures = ["abort-overflow", "fetch-or-body-error", "http-error", "invalid-shape", "response-overflow"];
        const number = (value: number | null | undefined) =>
          typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
        const base = (value: string) => ["BTC", "ETH"].includes(value) ? value : "unknown";
        const path = (value: string) => paths.includes(value) ? value : "unknown";
        const status = (value: string | null | undefined) => value && statuses.includes(value) ? value : null;
        const selection = (label: string) => document.querySelector<HTMLSelectElement>(
          `[data-testid="candlestick-chart"] select[aria-label="${label}"]`,
        )?.value ?? "unknown";
        const timeframe = selection("Timeframe");
        return {
          selectedBase: base(selection("คู่เทรด")),
          selectedTimeframe: ["1m", "3m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"].includes(timeframe) ? timeframe : "unknown",
          aborted: number(state.aborted), truncated: state.truncated === true,
          failure: state.failure === null ? null : failures.includes(state.failure) ? state.failure : "unknown",
          completed: state.completed.slice(0, 16).map(row => ({
            path: path(row.path), base: base(row.base), timeframe: row.timeframe === "3m" ? "3m" : "unknown",
            status: status(row.status), rowCount: number(row.rows.length),
          })),
          requests: state.requests.slice(0, 32).map(row => ({
            path: path(row.path), base: base(row.base), timeframe: "3m",
            startedMs: number(row.startedMs), headersMs: number(row.headersMs), finishedMs: number(row.finishedMs),
            http: number(row.http), status: status(row.status), rowCount: number(row.rowCount),
            outcome: ["pending", "complete", "aborted", "failed"].includes(row.outcome) ? row.outcome : "unknown",
          })),
        };
      }),
      new Promise(resolve => { timer = setTimeout(() => resolve({ unavailable: true }), 2000); }),
    ]);
  } catch { /* Failure evidence must never replace the original test failure. */ }
  finally { if (timer) clearTimeout(timer); }
  try {
    // The existing CI uploads test-results even without an HTML/JSON reporter.
    const output = info.outputPath("native-3m-failure-observer.json");
    writeFileSync(output, JSON.stringify(evidence));
    await info.attach("native-3m-failure-observer", { path: output, contentType: "application/json" });
  } catch { console.warn("Native3m failure evidence unavailable"); }
}

test.afterEach(attachNative3mFailure);

test(native3mTitle, async ({ page }) => {
  fixture("seed-3m");
  // Observe native browser fetches rather than retrieving bodies from CDP after
  // the app has consumed/aborted them. Never issue a probe or replace a response.
  await page.addInitScript(() => {
    const state: ChartObserverWindow["chart3mObserver"] = {
      completed: [], aborted: 0, failure: null, requests: [], truncated: false,
    };
    (window as ChartObserverWindow).chart3mObserver = state;
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : String(input), window.location.href);
      const base = url.searchParams.get("base");
      const observed = url.origin === window.location.origin && url.searchParams.get("timeframe") === "3m"
        && (base === "BTC" || base === "ETH")
        && ["/api/market-data/candles/pages", "/api/market-data/chart/live"].includes(url.pathname);
      if (!observed) return nativeFetch(input, init);
      // Separate bounded diagnostics; never alter existing observer verdicts.
      const observation: ChartRequestObservation | undefined = state.requests.length < 32 ? {
        path: url.pathname, base, startedMs: window.performance.now(), headersMs: null,
        finishedMs: null, http: null, status: null, rowCount: null, outcome: "pending",
      } : undefined;
      if (observation) state.requests.push(observation);
      else state.truncated = true;
      const failed = (error: unknown) => {
        const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined);
        const aborted = signal?.aborted || (error instanceof DOMException && error.name === "AbortError");
        if (observation) {
          observation.finishedMs = window.performance.now();
          observation.outcome = aborted ? "aborted" : "failed";
        }
        if (aborted) {
          state.aborted += 1;
          if (state.aborted > 16) state.failure = "abort-overflow";
        } else state.failure = "fetch-or-body-error";
      };
      let response: Response;
      try { response = await nativeFetch(input, init); }
      catch (error) { failed(error); throw error; }
      if (observation) { observation.headersMs = window.performance.now(); observation.http = response.status; }
      if (!response.ok) state.failure = "http-error";
      try {
        void response.clone().json().then((body: CandlePage | ChartLive) => {
          if (observation) {
            observation.finishedMs = window.performance.now();
            observation.outcome = "complete";
          }
          if (body.base !== base || body.timeframe !== "3m" || !Array.isArray(body.rows)
            || body.rows.length > 1000 || body.rows.some(row => !row ||
              ![row.open, row.high, row.low, row.close, row.open_at, row.end_at]
                .every(value => typeof value === "string"))) {
            state.failure = "invalid-shape";
            return;
          }
          if (observation) {
            observation.status = "status" in body && typeof body.status === "string" ? body.status : null;
            observation.rowCount = body.rows.length;
          }
          if (state.completed.length >= 16) { state.failure = "response-overflow"; return; }
          // Allowlist public fixture fields only; never retain request headers,
          // cookies, tokens, login data or a complete API response.
          state.completed.push({ path: url.pathname, requestedBase: base,
            base: body.base, timeframe: body.timeframe,
            status: "status" in body && typeof body.status === "string" ? body.status : undefined,
            rows: body.rows.map(({ open, high, low, close, open_at, end_at }) =>
              ({ open, high, low, close, open_at, end_at })) });
        }).catch(failed);
      } catch (error) { failed(error); }
      return response;
    };
  });
  const mutations: string[] = [];
  page.on("request", request => {
    if (request.method() !== "GET" && /\/api\/(paper\/orders|live\/orders|trading-account)/.test(request.url())) mutations.push(request.url());
  });
  const worker = producer("tests/e2e_candle_runner.py");
  try {
    await registerAccount(page);
    const chart = page.getByTestId("candlestick-chart");
    for (const base of ["BTC", "ETH"]) {
      const open = base === "BTC" ? "200.000000000000000001" : "300.000000000000000001";
      if (base === "BTC") await chart.getByRole("combobox", { name: "Timeframe" }).selectOption("3m");
      else await chart.getByRole("combobox", { name: "คู่เทรด" }).selectOption(base);
      // The existing test timeout bounds normal UI polling. A failed observer
      // fails the test; an aborted stale request cannot count as READY evidence.
      const captured = await page.waitForFunction(selectedBase => {
        const state = (window as ChartObserverWindow).chart3mObserver;
        if (state.failure) throw new Error(`CHART_OBSERVER_${state.failure}`);
        const history = state.completed.find(row => row.requestedBase === selectedBase
          && row.path === "/api/market-data/candles/pages");
        const live = state.completed.find(row => row.requestedBase === selectedBase
          && row.path === "/api/market-data/chart/live" && row.status === "READY");
        return history && live ? [history, live] : false;
      }, base);
      const bodies = await captured.jsonValue() as ChartObservation[];
      await captured.dispose();
      for (const body of bodies) {
        expect(body.base).toBe(base);
        expect(body.timeframe).toBe("3m");
        expect(body.rows.length).toBeGreaterThan(0);
        expect(body.rows.every(row => row.open === open
          && Date.parse(row.end_at) - Date.parse(row.open_at) === 180_000)).toBe(true);
      }
      await expect(chart.getByText(`${open} USDT`, { exact: true })).toBeVisible();
      await expect(chart.getByText("100.000000000000000001 USDT", { exact: true })).toHaveCount(0);
      if (base === "ETH") await expect(chart.getByText("200.000000000000000001 USDT", { exact: true })).toHaveCount(0);
    }
    const observationSummary = await page.evaluate(() => {
      const state = (window as ChartObserverWindow).chart3mObserver;
      return { aborted: state.aborted, failure: state.failure,
        completed: state.completed.map(({ path, base, timeframe, status, rows }) =>
          ({ path, base, timeframe, status, rowCount: rows.length })) };
    });
    expect(observationSummary.failure).toBeNull();
    await test.info().attach("native-3m-browser-fetch", {
      body: JSON.stringify(observationSummary), contentType: "application/json",
    });
    await page.reload();
    await expect(chart).toBeVisible();
    expect(mutations).toEqual([]);
  } finally { await worker.stop(); }
});
