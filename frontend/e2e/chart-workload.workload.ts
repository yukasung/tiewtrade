import { readFileSync, writeFileSync } from "node:fs";
import { expect, test, type BrowserContext, type Page, type Request } from "@playwright/test";

type Account = { session: string; csrf: string };
type Sample = { client: number; status: number; seconds: number; rows?: number | undefined; outcome?: string | undefined };

const duration = Number(process.env.CHART_WORKLOAD_SECONDS ?? "600");
const warmup = Number(process.env.CHART_WORKLOAD_WARMUP_SECONDS ?? "60");
const lifecycleCycles = Number(process.env.CHART_WORKLOAD_LIFECYCLE_CYCLES ?? "100");
const historySwitchSpacingMs = 30_000 / 5;
const output = process.env.CHART_WORKLOAD_BROWSER_OUTPUT;
const accountFile = process.env.CHART_WORKLOAD_ACCOUNTS;
if (!output || !accountFile) throw new Error("CHART_WORKLOAD_CONFIGURATION_REQUIRED");
const accounts = JSON.parse(readFileSync(accountFile, "utf8")) as Account[];
if (accounts.length !== 20) throw new Error("CHART_WORKLOAD_REQUIRES_20_ACCOUNTS");

test("F-12 V-17 controlled authenticated browser workload", async ({ browser }) => {
  const contexts: BrowserContext[] = [];
  const pages: Page[] = [];
  const live: Sample[] = [], history: Sample[] = [], proofs: Sample[] = [];
  const browserTextSeconds: number[] = [];
  const forbiddenRequests: string[] = [];
  const pendingSamples = new Set<Promise<void>>();
  const requestStartedAt = new WeakMap<Request, number>();
  let maximumPageRows = 0;
  let measuring = false;
  const track = (sample: Promise<void>) => {
    pendingSamples.add(sample);
    void sample.finally(() => pendingSamples.delete(sample));
  };
  try {
    for (const [index, account] of accounts.entries()) {
      const context = await browser.newContext();
      await context.addCookies([
        { name: "tiewtrade_session", value: account.session, url: "http://127.0.0.1:5173", httpOnly: true, sameSite: "Strict" },
        { name: "tiewtrade_csrf", value: account.csrf, url: "http://127.0.0.1:5173", sameSite: "Strict" },
      ]);
      const page = await context.newPage();
      page.on("request", request => {
        const url = request.url();
        const path = new URL(url).pathname;
        if (/\/market-data\/(?:chart\/(?:live|history|verify)|candles\/pages)$/.test(path)) {
          requestStartedAt.set(request, Date.now());
        }
        if (/binance/i.test(url) || /\/(?:orders?|trading-mode)(?:\/|$)/i.test(path) ||
            /\/market-data\/(?:chart\/(?:history|verify)|indicators)$/.test(path)) {
          forbiddenRequests.push(`${request.method()} ${path}`);
        }
      });
      page.on("response", response => {
        const path = new URL(response.url()).pathname;
        if (path.endsWith("/market-data/candles/pages")) {
          const started = requestStartedAt.get(response.request()) ?? Date.now();
          const sampled = measuring;
          track(response.json().then((body: { rows?: unknown[]; detail?: string }) => {
            maximumPageRows = Math.max(maximumPageRows, body.rows?.length ?? 0);
            if (!sampled) return;
            const timeframe = new URL(response.url()).searchParams.get("timeframe") ?? "unknown";
            history.push({ client: index, status: response.status(), seconds: (Date.now() - started) / 1000,
              rows: body.rows?.length, outcome: `${timeframe}:${body.detail ?? "OK"}` });
          }).catch(() => undefined));
          return;
        }
        if (path.endsWith("/market-data/chart/history")) {
          const started = requestStartedAt.get(response.request()) ?? Date.now();
          const sampled = measuring;
          track(response.json().then((body: { rows?: unknown[]; display_proof?: string; detail?: string }) => {
            if (!sampled) return;
            const timeframe = new URL(response.url()).searchParams.get("timeframe") ?? "unknown";
            history.push({ client: index, status: response.status(), seconds: (Date.now() - started) / 1000,
              rows: body.rows?.length, outcome: `${timeframe}:${body.detail ?? "OK"}` });
          }).catch(() => undefined));
          return;
        }
        if (path.endsWith("/market-data/chart/verify")) {
          const started = requestStartedAt.get(response.request()) ?? Date.now();
          const sampled = measuring;
          track(response.json().then((body: { status?: string; detail?: string }) => {
            if (!sampled) return;
            proofs.push({ client: index, status: response.status(), seconds: (Date.now() - started) / 1000,
              outcome: body.status ?? body.detail });
          }).catch(() => undefined));
          return;
        }
        if (!path.endsWith("/market-data/chart/live")) return;
        const started = requestStartedAt.get(response.request()) ?? Date.now();
        const sampled = measuring;
        track(response.json().then(async (body: { event_at?: string; rows?: Array<{ close: string }> }) => {
          const latest = body.rows?.at(-1);
          if (!sampled) return;
          live.push({ client: index, status: response.status(), seconds: (Date.now() - started) / 1000, rows: body.rows?.length });
          if (!latest || !body.event_at || response.status() !== 200) return;
          const visible = page.getByText(`${latest.close} USDT`, { exact: true });
          try {
            await visible.waitFor({ state: "visible", timeout: 5000 });
            browserTextSeconds.push((Date.now() - Date.parse(body.event_at)) / 1000);
          } catch { /* A newer coalesced update may replace this value. */ }
        }).catch(() => undefined));
      });
      contexts.push(context); pages.push(page);
    }
    // Exercise cleanup before starting the concurrent workload. Repeatedly
    // remounting one client as fast as navigation permits is a lifecycle check,
    // not an extra source of unbounded traffic during the 20-client measurement.
    await pages[0]!.goto("/chart");
    await expect(pages[0]!.getByTestId("candlestick-chart")).toBeVisible({ timeout: 30_000 });
    for (let cycle = 0; cycle < lifecycleCycles; cycle += 1) {
      await pages[0]!.goto("/account");
      await pages[0]!.goto("/chart");
      await expect(pages[0]!.getByTestId("candlestick-chart")).toBeVisible();
    }

    // Mount the remaining clients one at a time so their independent 2-second
    // poll phases stay distributed instead of forming a synchronized startup herd.
    for (const page of pages.slice(1)) {
      await page.goto("/chart");
      await expect(page.getByTestId("candlestick-chart")).toBeVisible({ timeout: 30_000 });
      await page.waitForTimeout(100);
    }
    await pages[0]!.waitForTimeout(warmup * 1000);

    measuring = true;
    const measurementStartedAt = new Date().toISOString();
    const started = Date.now();
    let historyRound = 0;
    while ((Date.now() - started) / 1000 < duration) {
      const elapsed = (Date.now() - started) / 1000;
      if (Math.floor(elapsed / 30) > historyRound) {
        historyRound = Math.floor(elapsed / 30);
        await Promise.all(pages.slice(0, 5).map(async (page, index) => {
          // Keep five switches in every 30-second round, evenly distributed so
          // independent clients do not become an artificial synchronized herd.
          await page.waitForTimeout(index * historySwitchSpacingMs);
          const timeframe = (["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"] as const)[historyRound % 8]!;
          await page.getByRole("combobox", { name: "Timeframe", exact: true }).selectOption(timeframe);
        }));
      }
      await pages[0]!.waitForTimeout(250);
    }
    const measurementEndedAt = new Date().toISOString();
    measuring = false;
    const errors = await Promise.all(pages.map(page => page.locator('[role="alert"]').allTextContents()));
    await Promise.race([
      Promise.all([...pendingSamples]),
      new Promise<void>(resolve => globalThis.setTimeout(resolve, 5000)),
    ]);
    const sampleDrainForced = pendingSamples.size > 0;
    await Promise.all(contexts.map(context => context.close()));
    contexts.length = 0;
    await Promise.all([...pendingSamples]);
    writeFileSync(output, JSON.stringify({ duration, warmup, clients: pages.length,
      browser_version: browser.version(),
      mount_unmount_cycles: lifecycleCycles, history_switch_spacing_ms: historySwitchSpacingMs,
      maximum_page_rows: maximumPageRows,
      maximum_retained_slots: maximumPageRows * 5 + 120,
      measurement_started_at: measurementStartedAt, measurement_ended_at: measurementEndedAt,
      live, history, proofs, browser_text_seconds: browserTextSeconds, errors,
      forbidden_requests: forbiddenRequests, sample_drain_forced: sampleDrainForced }, null, 2) + "\n");
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});
