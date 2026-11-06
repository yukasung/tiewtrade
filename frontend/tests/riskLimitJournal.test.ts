import { afterEach, expect, it, vi } from "vitest";
import { JournalUnavailable } from "../src/attemptJournal";
import { riskJournal, riskScope, type RiskAttempt } from "../src/riskLimitJournal";

const attempt: RiskAttempt = {
  version: 1, owner: "owner", mode: "PAPER", key: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", action: "SET",
  payload: { expected_revision: 0, expected_wallet_id: "wallet", expected_episode_id: "episode", amount: "200.000000000000000001" },
};
const scope = riskScope(attempt.owner, attempt.mode);
const storageKey = "tiewtrade.risk-limit.v1:" + scope;
afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

it.each(["SET", "DECREASE", "INCREASE", "RESET"] as const)("round trips %s with exact money, scope and identity", action => {
  for (const mode of ["PAPER", "LIVE"] as const) {
    const expected = { expected_revision: 1, expected_wallet_id: mode === "PAPER" ? "wallet" : null, expected_episode_id: mode === "PAPER" ? "episode" : null };
    const value: RiskAttempt = { ...attempt, action, mode, payload: action === "RESET" ? expected : { ...expected, amount: "200.000000000000000001" } };
    riskJournal.write(value);
    expect(riskJournal.read(riskScope("owner", mode))).toEqual(value);
    expect(riskJournal.read(riskScope("other", mode))).toBeNull();
    expect(riskJournal.read(riskScope("owner", mode === "PAPER" ? "LIVE" : "PAPER"))).toBeNull();
    riskJournal.clear(riskScope("owner", mode), "another-request");
    expect(riskJournal.read(riskScope("owner", mode))).toEqual(value);
    riskJournal.clear(riskScope("owner", mode), value.key);
    expect(riskJournal.read(riskScope("owner", mode))).toBeNull();
  }
});

it("recovers the persisted key across module reload without generating an identity", async () => {
  riskJournal.write(attempt);
  const before = window.sessionStorage.getItem(storageKey);
  const random = vi.spyOn(globalThis.crypto, "randomUUID");
  vi.resetModules();
  const reloaded = await import("../src/riskLimitJournal");
  expect(reloaded.riskJournal.read(scope)).toEqual(attempt);
  expect(window.sessionStorage.getItem(storageKey)).toBe(before);
  expect(random).not.toHaveBeenCalled();
});

const corrupt: Array<[string, unknown]> = [
  ["null root", null], ["array root", []], ["primitive root", 1],
  ["null payload", { ...attempt, payload: null }],
  ["array payload", { ...attempt, payload: [] }],
  ["primitive payload", { ...attempt, payload: "invalid" }],
  ["other owner", { ...attempt, owner: "other" }],
  ["other mode", { ...attempt, mode: "LIVE" }],
  ["version", { ...attempt, version: 2 }],
  ["key", { ...attempt, key: "-".repeat(36) }],
  ["unknown action", { ...attempt, action: "DELETE" }],
  ["negative revision", { ...attempt, payload: { ...attempt.payload, expected_revision: -1 } }],
  ["fractional revision", { ...attempt, payload: { ...attempt.payload, expected_revision: 1.5 } }],
  ["missing wallet", { ...attempt, payload: { expected_revision: 0, expected_episode_id: "episode", amount: "1" } }],
  ["extra root key", { ...attempt, extra: true }],
  ["extra payload key", { ...attempt, payload: { ...attempt.payload, extra: true } }],
  ["reset carrying amount", { ...attempt, action: "RESET" }],
];
it.each(corrupt)("fails closed on %s without deleting the pending record", (_name, value) => {
  const raw = JSON.stringify(value);
  window.sessionStorage.setItem(storageKey, raw);
  expect(() => riskJournal.read(scope)).toThrow(JournalUnavailable);
  expect(window.sessionStorage.getItem(storageKey)).toBe(raw);
});

it("distinguishes a missing entry from malformed JSON", () => {
  expect(riskJournal.read(scope)).toBeNull();
  window.sessionStorage.setItem(storageKey, "{");
  expect(() => riskJournal.read(scope)).toThrow(JournalUnavailable);
});

it("rejects Paper identities in a Live payload", () => {
  const value: RiskAttempt = { ...attempt, mode: "LIVE" };
  expect(() => riskJournal.write(value)).toThrow(JournalUnavailable);
  expect(riskJournal.read(riskScope("owner", "LIVE"))).toBeNull();
});

it.each(["getItem", "setItem", "removeItem"] as const)("fails closed when %s is denied", method => {
  riskJournal.write(attempt);
  vi.spyOn(Storage.prototype, method).mockImplementation(() => { throw new Error("denied"); });
  const operation = method === "getItem" ? () => riskJournal.read(scope)
    : method === "setItem" ? () => riskJournal.write(attempt) : () => riskJournal.clear(scope);
  expect(operation).toThrow(JournalUnavailable);
});

it("detects silent write and remove failures", () => {
  const write = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {});
  expect(() => riskJournal.write(attempt)).toThrow(JournalUnavailable);
  write.mockRestore();
  riskJournal.write(attempt);
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {});
  expect(() => riskJournal.clear(scope, attempt.key)).toThrow(JournalUnavailable);
  expect(riskJournal.read(scope)).toEqual(attempt);
});

it("rejects incorrect write readback and corrupted conditional-clear reads", () => {
  const read = vi.spyOn(Storage.prototype, "getItem").mockReturnValue("{");
  expect(() => riskJournal.write(attempt)).toThrow(JournalUnavailable);
  expect(() => riskJournal.clear(scope, attempt.key)).toThrow(JournalUnavailable);
  read.mockRestore();
  expect(riskJournal.read(scope)).toEqual(attempt);
});
