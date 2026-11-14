import { expect, type Page } from "@playwright/test";
import type { NewManualOrder } from "../../src/manualOrders";
type WithoutScope<T> = T extends unknown ? Omit<T, "expected_wallet_id" | "expected_episode_id"> : never;
export type FixtureOrder = WithoutScope<NewManualOrder>;
export async function orderPayload(page: Page, order: FixtureOrder) {
  const response = await page.request.get(`/api/paper/trade?base=${order.base}`);
  expect(response.status()).toBe(200);
  const { wallet } = await response.json() as { wallet: { wallet_id: string; episode_id: string } };
  return { ...order, expected_wallet_id: wallet.wallet_id, expected_episode_id: wallet.episode_id } as NewManualOrder;
}
/** Test setup for removed BUY UI. Uses the authenticated production API, never a test-only order engine. */
export async function requestFixtureOrder(page: Page, order: FixtureOrder) {
  const payload = await orderPayload(page, order);
  const csrf = (await page.context().cookies()).find(c => c.name === "tiewtrade_csrf")!.value;
  const response = await page.request.post("/api/paper/orders", { data: payload,
    headers: { "X-CSRF-Token": csrf, "Idempotency-Key": globalThis.crypto.randomUUID() } });
  return response;
}
export async function postFixtureOrder(page: Page, order: FixtureOrder) {
  const response = await requestFixtureOrder(page, order);
  expect(response.status()).toBe(202);
  const receipt = await response.json() as { request_id: string; order_id: string; idempotency_key: string };
  await page.reload();
  return receipt;
}
/** Shared BUY setup for manual-order and protection scenarios. */
export function postFixtureBuy(page: Page, amount: string, options: { limit?: string; tp?: string; sl?: string } = {}) {
  return postFixtureOrder(page, {
    base: "BTC", quote: "USDT", side: "BUY",
    ...(options.limit
      ? { kind: "LIMIT", base_quantity: amount, limit_price: options.limit, time_in_force: "GTC" }
      : { kind: "MARKET", quote_budget: amount }),
    ...(options.tp || options.sl
      ? { protection: { take_profit_price: options.tp ?? null, stop_loss_price: options.sl ?? null } }
      : {}),
  });
}

/** A legacy BUY may already exist in a browser journal. Seed only that precondition, then exercise real recovery UI. */
export async function seedLegacyBuy(page: Page, quote_budget: string) {
  const payload = await orderPayload(page, { base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget });
  const { user_id } = await (await page.request.get("/api/auth/me")).json() as { user_id: string };
  await page.evaluate(({ payload, owner, key }) => {
    window.sessionStorage.setItem(`tiewtrade.manual-order.v1:${owner}`, JSON.stringify({ version: 1, owner, mode: "PAPER", action: "NEW", key, payload }));
  }, { payload, owner: user_id, key: globalThis.crypto.randomUUID() });
  await page.reload();
  await expect(page.getByRole("button", { name: "ส่งคำขอเดิมอีกครั้ง", exact: true })).toBeEnabled();
}
export async function openSell(page: Page) {
  await page.getByRole("button", { name: "ลด/ปิดสถานะ", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
}
export async function submitSell(page: Page) {
  const button = page.getByRole("button", { name: "ส่งคำขอขาย Paper", exact: true });
  await expect(button).toBeEnabled();
  const pending = page.waitForResponse(r => r.url().endsWith("/api/paper/orders") && r.request().method() === "POST");
  await button.click();
  return pending;
}
