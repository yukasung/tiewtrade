import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { backendPython, e2eEnvironment } from "./helpers/environment";
import { expect, test } from "./helpers/test";
import { PASSWORD } from "./helpers/totp";
import { supportedBases } from "../src/marketCatalog";

test("actual quote producer → PostgreSQL → Redis → API → browser recovery", async ({ page, context }) => {
  test.setTimeout(90000);
  const directory = mkdtempSync(join(tmpdir(), "tiewtrade-prices-"));
  const control = join(directory, "control");
  const mode = (value: string) => writeFileSync(control, value);
  mode("healthy");
  const producer = spawn(backendPython, ["-B", "tests/e2e_realtime_runner.py", "--control-file", control], {
    cwd: "../backend", env: e2eEnvironment(), stdio: "ignore",
  });
  try {
    await page.goto("/prices");
    await page.getByTestId("switch-mode").click();
    await page.getByLabel("อีเมล").fill(`e2e-prices-${String(Date.now())}@example.com`);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
    await page.getByTestId("submit").click();
    await expect(page.getByTestId("signed-in")).toBeVisible();
    const panel = page.getByTestId("realtime-prices");
    const btc = page.getByTestId("price-BTC");
    await expect(btc).toContainText("83348.47 USDT", { timeout: 15000 });
    await expect(btc).toContainText("พร้อม ณ เวลาที่ตรวจ");
    await expect(panel.getByRole("status")).toHaveText("เชื่อมต่อการส่งข้อมูลแล้ว");
    await expect(panel.getByRole("listitem")).toHaveCount(supportedBases.length);
    await expect(panel).toContainText("เวลาที่ตรวจโดย server");
    await expect(btc).toContainText("เวลาซื้อขาย");

    // Real authenticated browser → Vite WS proxy → bounded Uvicorn decoder.
    const oversizedClose = await page.evaluate(() => new Promise<number>((resolve, reject) => {
      const url = new URL("/api/market-data/prices/stream", window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      const socket = new WebSocket(url);
      const timeout = window.setTimeout(() => {
        socket.close();
        reject(new Error("oversized message did not close"));
      }, 3000);
      socket.onopen = () => socket.send("x".repeat(257));
      socket.onclose = event => { window.clearTimeout(timeout); resolve(event.code); };
    }));
    expect(oversizedClose).toBe(1008);

    mode("silent");
    await expect(btc).toContainText("ราคาเก่า ณ เวลาที่ตรวจ", { timeout: 15000 });
    await expect(btc).toContainText("83348.47 USDT");
    mode("outage-alert");
    await expect(btc).toContainText("กำลังกู้คืน ณ เวลาที่ตรวจ");
    // The test producer seeds a DB-clock outage onset 61s ago; no browser clock countdown.
    await expect(btc).toContainText("ราคาตลาดไม่พร้อมต่อเนื่องครบ 60 วินาที ณ เวลาที่ตรวจ");
    await page.setViewportSize({ width: 360, height: 1000 });
    await panel.screenshot({ path: "../specs/reviews/2026-10-07-f10-realtime-prices/market-warning-th-360.png" });
    mode("healthy");
    await expect(btc).toContainText("พร้อม ณ เวลาที่ตรวจ", { timeout: 15000 });
    await expect(btc).not.toContainText("ราคาตลาดไม่พร้อมต่อเนื่องครบ 60 วินาที ณ เวลาที่ตรวจ");

    await context.setOffline(true);
    await expect(panel.getByRole("status")).toHaveText("การเชื่อมต่อขาด ข้อมูลอาจไม่เป็นปัจจุบัน");
    await expect(btc).toContainText("83348.47 USDT");
    // APIRequestContext remains online: only browser delivery was interrupted.
    await panel.screenshot({ path: "../specs/reviews/2026-10-07-f10-realtime-prices/delivery-warning-th-360.png" });
    const serverSnapshot = await page.request.get("/api/market-data/prices");
    expect(serverSnapshot.status()).toBe(200);
    const serverView = await serverSnapshot.json() as { rows: { readiness: string; alert_due: boolean }[] };
    expect(serverView.rows.every(row => row.readiness === "READY" && !row.alert_due)).toBe(true);
    await context.setOffline(false);
    await expect(panel.getByRole("status")).toHaveText("เชื่อมต่อการส่งข้อมูลแล้ว", { timeout: 15000 });
    await expect(btc).toContainText("พร้อม ณ เวลาที่ตรวจ");

    for (const width of [360, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await panel.screenshot({ path: `../specs/reviews/2026-10-07-f10-realtime-prices/ready-th-${String(width)}.png` });
    }
    await page.evaluate(async () => {
      const modulePath = "/src/realtimePriceMessages.ts";
      const messages = await import(/* @vite-ignore */ modulePath) as { realtimePriceI18n: { changeLanguage: (value: string) => Promise<unknown> } };
      await messages.realtimePriceI18n.changeLanguage("en");
    });
    await expect(btc).toContainText("Ready at last check");
    for (const width of [360, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await panel.screenshot({ path: `../specs/reviews/2026-10-07-f10-realtime-prices/ready-en-${String(width)}.png` });
    }
    // Revoke through an independent HTTP request while the page/socket remains mounted.
    const csrf = (await context.cookies()).find(cookie => cookie.name === "tiewtrade_csrf");
    expect(csrf).toBeDefined();
    const revoked = await page.request.post("/api/auth/logout-all", { headers: { "X-CSRF-Token": csrf?.value ?? "" } });
    expect(revoked.status()).toBe(200);
    await expect(panel).not.toBeVisible({ timeout: 10000 });
  } finally {
    producer.kill("SIGTERM");
    if (producer.exitCode === null && producer.signalCode === null) {
      await new Promise<void>((resolve) => producer.once("exit", () => resolve()));
    }
    rmSync(directory, { recursive: true, force: true });
  }
});
