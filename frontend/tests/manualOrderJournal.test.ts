import { afterEach, expect, it, vi } from "vitest";
import { clearAttempt, readAttempt, writeAttempt, type ManualAttempt } from "../src/manualOrderJournal";
const value: ManualAttempt = { version: 1, owner: "owner", mode: "PAPER", action: "NEW", key: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", payload: { expected_wallet_id: "wallet", expected_episode_id: "episode", base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget: "1.000000000000000001" } };
afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
it("round trips the exact owner, key, episode and decimal payload", () => {
  writeAttempt(value); expect(readAttempt("owner")).toEqual(value); expect(readAttempt("other")).toBeNull();
  clearAttempt("owner", "different-key"); expect(readAttempt("owner")).toEqual(value);
  clearAttempt("owner", value.key); expect(readAttempt("owner")).toBeNull();
});
it("fails closed on denied writes, missing readback and corrupted journal", () => {
  const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {});
  expect(() => writeAttempt(value)).toThrow(); set.mockRestore();
  window.sessionStorage.setItem("tiewtrade.manual-order.v1:owner", '{"mode":"LIVE"}');
  expect(() => readAttempt("owner")).toThrow();
});
