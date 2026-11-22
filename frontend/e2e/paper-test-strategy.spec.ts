import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { PASSWORD } from "./helpers/totp";

for (const leg of ["TP", "SL"] as const) {
  test(`CLOSED green signal buys once and exits via actual ${leg}`, async ({ page }, info) => {
    await page.goto("/account");
    await page.getByTestId("switch-mode").click();
    await page.getByLabel("อีเมล").fill(`paper-test-${randomUUID()}@example.com`);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
    await page.getByTestId("submit").click();
    await expect(page.getByTestId("signed-in")).toBeVisible();
    const owner = await (await page.request.get("/api/auth/me")).json() as { user_id: string };
    expect((await page.request.post("http://127.0.0.1:18022/__e2e/strategy/prepare", { data: owner, timeout: 70_000 })).status()).toBe(204);
    await page.goto("/paper/trade");
    const panel = page.locator('[aria-labelledby="paper-bot-title"]');
    await expect(panel.locator("dd")).toHaveText("10,000 USDT");
    await panel.getByLabel("เลือกบอท").selectOption("paper-green-atr-test");
    await expect(panel.getByLabel("จำนวนไม้ที่เปิดได้สูงสุด")).toHaveCount(0);
    await panel.getByLabel("เงินต่อไม้ (USDT)").fill("355");
    await panel.getByLabel("Timeframe ของบอท").selectOption("1m");
    await panel.getByRole("button", { name: "เริ่มบอท", exact: true }).click();
    const status = async () => (await (await page.request.get("/api/paper/bots/status")).json()) as {
      status: string; open_entries: number; positions: { quantity: string }[];
      pinned_configuration: { strategy_name: string; timeframe: string };
    };
    const metrics = async () => (await (await page.request.post("http://127.0.0.1:18022/__e2e/strategy/metrics", { data: owner })).json()) as {
      orders: number; executions: number; active_reservations: number;
      order_sides: { BUY: number; SELL: number }; position_state: { quantity: string; realized_pnl: string }[];
    };
    await expect.poll(async () => (await status()).status).toBe("RUNNING");
    expect((await status()).pinned_configuration).toMatchObject({ strategy_name: "paper-green-atr-test", timeframe: "1m" });
    expect((await metrics()).orders).toBe(0);
    expect((await page.request.post("http://127.0.0.1:18022/__e2e/strategy/step", { data: owner, timeout: 70_000 })).status()).toBe(200);
    await expect.poll(async () => (await status()).open_entries).toBe(1);
    expect((await metrics()).order_sides.BUY).toBe(1);
    await page.reload();
    await expect(panel.getByLabel("เลือกบอท")).toHaveValue("paper-green-atr-test");
    await expect(panel.getByLabel("จำนวนไม้ที่เปิดได้สูงสุด")).toHaveCount(0);
    await page.screenshot({ path: info.outputPath(`paper-test-${leg}-entry.png`), fullPage: true });
    expect((await page.request.post("http://127.0.0.1:18022/__e2e/paper-test/cross-target", { data: { ...owner, leg } })).status()).toBe(204);
    await expect.poll(async () => (await status()).positions).toEqual([]);
    await expect.poll(async () => (await metrics()).active_reservations).toBe(0);
    const final = await metrics();
    expect(final.order_sides).toEqual({ BUY: 1, SELL: 1 });
    expect(final.orders).toBe(2);
    expect(final.executions).toBe(2);
    expect(final.position_state[0]?.quantity).toBe("0");
    expect(final.position_state[0]?.realized_pnl.startsWith("-")).toBe(leg === "SL");
    await panel.getByRole("button", { name: "หยุดบอท", exact: true }).click();
    await expect.poll(async () => (await status()).status).toBe("STOPPED");
    await page.screenshot({ path: info.outputPath(`paper-test-${leg}-closed.png`), fullPage: true });
  });
}
