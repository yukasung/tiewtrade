import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout, clearTimeout } from "node:timers";
import type { Page } from "@playwright/test";
import type { components } from "../src/api-types";
import { backendPython, e2eEnvironment } from "./helpers/environment";
import { expect, test } from "./helpers/test";
import { PASSWORD } from "./helpers/totp";

type PricesView = components["schemas"]["PricesView"];
type ProbeWindow = Window & {
  priceTestProbe?: { socket: WebSocket; latest?: PricesView; closeCode?: number };
};

// Test-only consumer: the retired page is no longer needed to exercise the API/WS contract.
async function openStream(page: Page): Promise<void> {
  await page.evaluate(() => new Promise<void>((resolve, reject) => {
    const host = window as ProbeWindow;
    host.priceTestProbe?.socket.close();
    const url = new URL("/api/market-data/prices/stream", window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    const probe: NonNullable<ProbeWindow["priceTestProbe"]> = { socket: new WebSocket(url) };
    host.priceTestProbe = probe;
    const timeout = window.setTimeout(() => {
      probe.socket.close();
      reject(new Error("PRICE_TEST_SNAPSHOT_TIMEOUT"));
    }, 5000);
    probe.socket.onmessage = event => {
      try {
        probe.latest = JSON.parse(String(event.data)) as PricesView;
        window.clearTimeout(timeout);
        resolve();
      } catch {
        window.clearTimeout(timeout);
        probe.socket.close();
        reject(new Error("PRICE_TEST_INVALID_SNAPSHOT"));
      }
    };
    probe.socket.onclose = event => {
      probe.closeCode = event.code;
      window.clearTimeout(timeout);
      reject(new Error("PRICE_TEST_STREAM_CLOSED"));
    };
  }));
}

async function latestStream(page: Page): Promise<PricesView | undefined> {
  return page.evaluate(() => (window as ProbeWindow).priceTestProbe?.latest);
}
async function snapshot(page: Page): Promise<PricesView> {
  const response = await page.request.get("/api/market-data/prices");
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"]).toBe("no-store");
  return await response.json() as PricesView;
}

const btc = (view: PricesView | undefined) => view?.rows.find(row => row.base === "BTC");

async function latestStreamStatus(page: Page) {
  const row = btc(await latestStream(page));
  return { readiness: row?.readiness, alert_due: row?.alert_due };
}

test("actual quote producer → PostgreSQL → Redis → authenticated API/WS recovery", async ({ page, context }) => {
  test.setTimeout(90000);
  const directory = mkdtempSync(join(tmpdir(), "tiewtrade-prices-"));
  const control = join(directory, "control");
  const mode = (value: string) => writeFileSync(control, value);
  mode("healthy");
  const producer = spawn(backendPython, ["-B", "tests/e2e_realtime_runner.py", "--control-file", control], {
    cwd: "../backend", env: e2eEnvironment(), stdio: "ignore",
  });
  const exited = new Promise<void>(resolve => {
    producer.once("exit", () => resolve());
    producer.once("error", () => resolve());
  });
  try {
    await page.goto("/prices");
    await expect(page.getByTestId("signed-out")).toBeVisible();
    const unauthenticated = await page.request.get("/api/market-data/prices");
    expect(unauthenticated.status()).toBe(401);
    await page.getByTestId("switch-mode").click();
    await page.getByLabel("อีเมล").fill(`e2e-prices-${String(Date.now())}@example.com`);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
    await page.getByTestId("submit").click();
    await expect(page.getByTestId("signed-in")).toBeVisible();
    await expect(page).toHaveURL(/\/chart$/);
    await expect(page.getByTestId("realtime-prices")).toHaveCount(0);
    await expect(page.locator('a[href="/prices"]')).toHaveCount(0);

    await expect.poll(async () => btc(await snapshot(page))?.readiness, { timeout: 15000 }).toBe("READY");
    const catalogResponse = await page.request.get("/api/market-catalog");
    expect(catalogResponse.status()).toBe(200);
    const catalog = await catalogResponse.json() as { active_pairs: [string, string][] };
    const view = await snapshot(page);
    expect(view.schema_version).toBe(1);
    expect(view.delivery_status).toBe("CONNECTED");
    expect(view.rows.map(row => [row.base, row.quote]).sort()).toEqual([...catalog.active_pairs].sort());
    expect(view.server_time).toMatch(/(?:Z|\+00:00)$/);
    expect(btc(view)).toMatchObject({ amount: "83348.47", quote: "USDT", readiness: "READY", alert_due: false });
    expect(btc(view)?.trade_at).toMatch(/(?:Z|\+00:00)$/);
    expect(btc(view)?.received_at).toMatch(/(?:Z|\+00:00)$/);

    await openStream(page);
    await expect.poll(async () => btc(await latestStream(page))?.readiness).toBe("READY");
    expect(btc(await latestStream(page))?.amount).toBe("83348.47");

    // Real browser → Vite WS proxy → bounded Uvicorn decoder.
    const oversizedClose = await page.evaluate(() => new Promise<number>((resolve, reject) => {
      const url = new URL("/api/market-data/prices/stream", window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(url);
      const timeout = window.setTimeout(() => {
        socket.close();
        reject(new Error("PRICE_TEST_FRAME_CLOSE_TIMEOUT"));
      }, 3000);
      socket.onopen = () => socket.send("x".repeat(257));
      socket.onclose = event => { window.clearTimeout(timeout); resolve(event.code); };
    }));
    expect(oversizedClose).toBe(1008);

    mode("silent");
    await expect.poll(async () => btc(await latestStream(page))?.readiness, { timeout: 15000 }).toBe("STALE");
    expect(btc(await latestStream(page))?.amount).toBe("83348.47");
    expect(btc(await snapshot(page))?.readiness).toBe("STALE");
    mode("outage-alert");
    // The fixture seeds a DB-clock outage onset 61s ago; no browser clock countdown.
    await expect.poll(() => latestStreamStatus(page)).toEqual({ readiness: "RECOVERING", alert_due: true });
    expect(btc(await snapshot(page))?.alert_due).toBe(true);
    mode("healthy");
    await expect.poll(() => latestStreamStatus(page), { timeout: 15000 }).toEqual({ readiness: "READY", alert_due: false });

    await context.setOffline(true);
    // APIRequestContext remains online while browser delivery is interrupted.
    const serverView = await snapshot(page);
    expect(serverView.rows.every(row => row.readiness === "READY" && !row.alert_due)).toBe(true);
    await context.setOffline(false);
    // Graceful close needs an online transport; observe teardown before replacing the probe.
    await page.evaluate(() => (window as ProbeWindow).priceTestProbe?.socket.close());
    await expect.poll(() => page.evaluate(() => (window as ProbeWindow).priceTestProbe?.closeCode)).toBeDefined();
    await openStream(page);
    await expect.poll(async () => btc(await latestStream(page))?.readiness, { timeout: 15000 }).toBe("READY");

    const csrf = (await context.cookies()).find(cookie => cookie.name === "tiewtrade_csrf");
    expect(csrf).toBeDefined();
    const revoked = await page.request.post("/api/auth/logout-all", { headers: { "X-CSRF-Token": csrf?.value ?? "" } });
    expect(revoked.status()).toBe(200);
    await expect.poll(() => page.evaluate(() => (window as ProbeWindow).priceTestProbe?.closeCode), { timeout: 10000 }).toBe(4401);
    expect((await page.request.get("/api/market-data/prices")).status()).toBe(401);
  } finally {
    await context.setOffline(false);
    await page.evaluate(() => (window as ProbeWindow).priceTestProbe?.socket.close()).catch(() => undefined);
    producer.kill("SIGTERM");
    const timer = setTimeout(() => producer.kill("SIGKILL"), 3000);
    await exited;
    clearTimeout(timer);
    rmSync(directory, { recursive: true, force: true });
  }
});
