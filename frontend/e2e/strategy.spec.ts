import type { Page } from "@playwright/test";
import { expect, test } from "./helpers/test";

const control = "http://127.0.0.1:18021/__e2e/strategy";

async function registerOwner(page: Page) {
  await page.goto("/account");
  await page.getByTestId("switch-mode").click();
  await page.getByLabel("อีเมล").fill(`f21-${globalThis.crypto.randomUUID()}@example.com`);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill("strategy-feature-fixture-password-long");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("log-out")).toBeVisible();
  return await (await page.request.get("/api/auth/me")).json() as { user_id: string };
}

test("real API start, fresh RSI signals, unequal entries and shared actual TP exits", async ({ page }, info) => {
  const who = await registerOwner(page);
  expect((await page.request.post(`${control}/prepare`, { data: who, timeout: 70_000 })).status()).toBe(204);
  await expect.poll(async () => ((await (await page.request.get("/api/paper/risk-limit")).json()) as { reason: string }).reason).toBe("READY");
  await page.goto("/paper/trade");
  const panel = page.locator('[aria-labelledby="paper-bot-title"]');
  await expect(panel.locator("dd")).toHaveText("10,000 USDT");
  await panel.getByLabel("เงินต่อไม้ (USDT)").fill("2804.5");
  await panel.getByLabel("จำนวนไม้ที่เปิดได้สูงสุด").selectOption("3");
  await panel.getByLabel("Timeframe ของบอท").selectOption("1m");
  await expect(panel.getByRole("button", { name: "เริ่มบอท", exact: true })).toBeEnabled();
  await panel.getByRole("button", { name: "เริ่มบอท", exact: true }).click();
  const status = async () => (await (await page.request.get("/api/paper/bots/status")).json()) as {
    status: string; open_entries: number; basket_target: string | null;
    positions: { quantity: string }[]; protections: { state: string }[];
  };
  const metrics = async () => (await (await page.request.post(`${control}/metrics`, { data: who })).json()) as {
    balance: string; orders: number; executions: number;
    commands: { NEW?: number; CANCEL?: number }; order_sides: { BUY?: number; SELL?: number };
    cancel_keys_valid: boolean; unfinished_commands: number; active_reservations: number;
    winning_triggers: number; position_state: { quantity: string; cost: string; realized_pnl: string }[];
    baskets: { status: string; target: string }[]; state: { fields: [string, unknown][] };
  };
  await expect.poll(async () => (await status()).status).toBe("RUNNING");
  expect((await metrics()).orders).toBe(0);
  for (let step = 1; step <= 5; step++) {
    const result = await page.request.post(`${control}/step`, { data: who, timeout: 70_000 });
    expect(result.status()).toBe(200);
    expect(((await result.json()) as { step: number }).step).toBe(step);
    if (step === 1 || step === 4) {
      await expect.poll(async () => Object.fromEntries((await metrics()).state.fields).reset_close)
        .toEqual({ money: { amount: step === 1 ? "310" : "260", currency: "USDT" } });
    }
    if (step === 2 || step === 5) {
      await expect.poll(async () => (await status()).open_entries).toBe(step === 2 ? 1 : 2);
      await expect.poll(async () => (await status()).basket_target).toBe("434.98");
      await expect.poll(async () => (await status()).protections.every(p => p.state === "ARMED")).toBe(true);
    }
  }
  await expect.poll(async () => (await status()).positions[0]?.quantity).toBe("14.985");
  expect((await metrics()).balance).toBe("4391");
  await page.locator(".trade-workspace").screenshot({ path: info.outputPath("f21-two-entries-shared-tp.png") });
  expect((await page.request.post(`${control}/trigger`)).status()).toBe(204);
  await expect.poll(async () => (await metrics()).baskets[0]?.status, { timeout: 15_000 }).toBe("CLOSED");
  expect((await metrics()).balance).toBe("10895.4715175");
  expect((await metrics()).executions).toBe(4);
  expect((await metrics()).orders).toBe(4);
  expect((await metrics()).commands).toEqual({ NEW: 4, CANCEL: 2 });
  expect((await metrics()).order_sides).toEqual({ BUY: 2, SELL: 2 });
  expect((await metrics()).cancel_keys_valid).toBe(true);
  await expect.poll(async () => (await metrics()).unfinished_commands).toBe(0);
  expect((await metrics()).position_state).toEqual([
    { quantity: "0", cost: "0", realized_pnl: "895.4715175" },
  ]);
  expect((await metrics()).active_reservations).toBe(0);
  expect((await metrics()).winning_triggers).toBe(1);
  await expect.poll(async () => (await status()).positions).toEqual([]);
  await page.locator(".trade-workspace").screenshot({ path: info.outputPath("f21-shared-tp-closed.png") });
});

for (const committed of [false, true]) {
  test(`recover start on reload after timeout ${committed ? "after" : "before"} commit`, async ({ page }) => {
    const owner = await registerOwner(page);
    expect((await page.request.post(`${control}/prepare-owner`, { data: owner })).status()).toBe(204);
    await expect.poll(async () => (await page.request.get("/api/paper/risk-limit")).json() as Promise<unknown>).toMatchObject({ reason: "READY" });
    await page.goto("/paper/trade");
    const panel = page.locator('[aria-labelledby="paper-bot-title"]');
    await expect(panel.locator("dd")).toHaveText("10,000 USDT");
    await panel.getByLabel("เงินต่อไม้ (USDT)").fill("100");
    const keys: string[] = [];
    await page.route("**/api/paper/bots/requests", async route => {
      if (route.request().method() !== "POST") return route.continue();
      const key = route.request().headers()["idempotency-key"];
      if (!key) throw new Error("start request lacks an idempotency key");
      keys.push(key);
      if (keys.length > 1) return route.continue();
      if (committed) expect((await route.fetch()).status()).toBe(202);
      await route.abort("timedout");
    });
    await panel.getByRole("button", { name: "เริ่มบอท", exact: true }).click();
    if (!committed) await expect(panel.getByRole("alert")).toBeVisible();
    await expect.poll(() => keys).toHaveLength(1);
    const receiptPath = `/api/paper/bots/requests/by-key/${keys[0]}`;
    await expect.poll(async () => (await page.request.get(receiptPath)).status()).toBe(committed ? 200 : 404);
    await page.reload();
    if (committed) {
      await expect(panel.getByRole("button", { name: "หยุดบอท", exact: true })).toBeVisible();
      await expect(panel.getByLabel("เงินต่อไม้ (USDT)")).toBeDisabled();
    } else {
      const recover = panel.getByRole("button", { name: "ตรวจสอบ / ลองคำขอเริ่มเดิมอีกครั้ง" });
      await expect(recover).toBeEnabled();
      const lookup = page.waitForResponse(response => response.url().endsWith(receiptPath));
      await recover.click();
      expect((await lookup).status()).toBe(404);
    }
    await expect.poll(() => keys.length).toBe(committed ? 1 : 2);
    await expect.poll(async () => (await (await page.request.get(receiptPath)).json()) as unknown).toMatchObject({
      pending: false, failure_code: null, run_id: expect.any(String),
    });
    expect(keys).toEqual(committed ? [keys[0]] : [keys[0], keys[0]]);
    const metrics: unknown = await (await page.request.post(`${control}/metrics`, { data: owner })).json();
    expect(metrics).toMatchObject({ orders: 0, executions: 0, balance: "10000" });
  });
}
