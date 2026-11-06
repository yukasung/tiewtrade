import { afterEach, expect, it } from "vitest";
import { protectionJournal, type ProtectionAttempt } from "../src/protectionJournal";
import { readAttempt, writeAttempt, type ManualAttempt } from "../src/manualOrderJournal";
const key = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
afterEach(() => window.sessionStorage.clear());
it("keeps recovery identities and exact prices scoped to the owner", () => {
  const value: ProtectionAttempt = { version: 1, owner: "owner", mode: "PAPER", key, action: "CREATE", payload: { expected_wallet_id: "w", expected_episode_id: "e", base: "BTC", quantity: "0.123456789012345678", stop_loss_price: "90" } };
  protectionJournal.write(value); expect(protectionJournal.read("owner")).toEqual(value);
  expect(protectionJournal.read("other")).toBeNull();
  protectionJournal.clear("owner", "other"); expect(protectionJournal.read("owner")).toEqual(value);
  protectionJournal.clear("owner", key); expect(protectionJournal.read("owner")).toBeNull();
});
it("preserves bracket and explicit sale allocations in the shared manual journal", () => {
  const scope = { expected_wallet_id: "w", expected_episode_id: "e", base: "BTC", quote: "USDT" as const };
  const buy: ManualAttempt = { version: 1, owner: "owner", mode: "PAPER", key, action: "NEW", payload: { ...scope, kind: "MARKET", side: "BUY", quote_budget: "100", protection: { take_profit_price: "110", stop_loss_price: "90" } } };
  writeAttempt(buy); expect(readAttempt("owner")).toEqual(buy); window.sessionStorage.clear();
  const sell: ManualAttempt = { version: 1, owner: "owner", mode: "PAPER", key, action: "NEW", payload: { ...scope, kind: "MARKET", side: "SELL", base_quantity: "0.4", protection_allocations: [{ protection_id: "group", expected_revision: 3, quantity: "0.4" }] } };
  writeAttempt(sell); expect(readAttempt("owner")).toEqual(sell);
});
it("rejects corrupted Live, cross-owner, and undeclared payload fields", () => {
  window.sessionStorage.setItem("tiewtrade.protection.v1:owner", JSON.stringify({ version: 1, owner: "other", mode: "LIVE", key, action: "CREATE", payload: {} }));
  expect(() => protectionJournal.read("owner")).toThrow();
  const value: unknown = { version: 1, owner: "owner", mode: "PAPER", key, action: "CREATE", payload: { expected_wallet_id: "w", expected_episode_id: "e", base: "BTC", quantity: "1", stop_loss_price: "90", api_secret: "unexpected" } };
  window.sessionStorage.setItem("tiewtrade.protection.v1:owner", JSON.stringify(value));
  expect(() => protectionJournal.read("owner")).toThrow();
});
