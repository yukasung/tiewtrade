import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "../src/auth";
import { addApiKey, deleteApiKey, fetchApiKeys } from "../src/apiKeys";
import { fetchTradingAccount, selectTradingUse } from "../src/tradingAccount";
import { createPaperWallet, fetchPaperWallet } from "../src/paperWallet";
import { fetchTrade, postNewOrder, type NewManualOrder } from "../src/manualOrders";
import { fetchProtections, postProtection, type ProtectionCreate } from "../src/protections";
import { fetchRisk, postRisk } from "../src/riskLimits";
import { fetchStopStatus, postStop } from "../src/killSwitch";

// Independent expectations captured before extracting the seven request wrappers.
// Exercise the public functions and real sender; only the network boundary is stubbed.
type ApiCase = {
  name: string;
  read: (signal: AbortSignal) => Promise<unknown>;
  path: string;
  fallback: string;
  allowed: string[];
  abort: boolean;
  retry: boolean;
};
const cases: ApiCase[] = [
  { name: "apiKeys", read: fetchApiKeys, path: "/api/api-keys", fallback: "API_KEY_REQUEST_FAILED",
    allowed: [], abort: false, retry: true },
  { name: "tradingAccount", read: fetchTradingAccount, path: "/api/trading-account",
    fallback: "TRADING_ACCOUNT_REQUEST_FAILED", abort: false, retry: true,
    allowed: ["TRADING_ACCOUNT_ACTIVITY_UNKNOWN", "TRADING_ACCOUNT_INPUT_REJECTED"] },
  { name: "paperWallet", read: fetchPaperWallet, path: "/api/paper-wallet",
    fallback: "PAPER_WALLET_REQUEST_FAILED", abort: false, retry: true,
    allowed: ["ACTIVITY_UNKNOWN", "EPISODE_CONFLICT", "IDEMPOTENCY_CONFLICT", "INITIAL_CAPITAL_INVALID",
      "INITIAL_CAPITAL_TOO_SMALL", "PAPER_WALLET_INPUT_REJECTED", "PAPER_WALLET_DEPENDENCY_UNAVAILABLE",
      "RESET_UNSAFE", "WALLET_EXISTS"] },
  { name: "manualOrders", read: signal => fetchTrade("BTC", signal), path: "/api/paper/trade?base=BTC",
    fallback: "MANUAL_ORDER_REQUEST_FAILED", abort: true, retry: true,
    allowed: ["RISK_LIMIT_UNSET", "RISK_LOSS_LIMIT_REACHED", "RISK_SOURCE_UNAVAILABLE", "RISK_PRICE_UNAVAILABLE",
      "MANUAL_ORDER_EPISODE_CLOSED", "MANUAL_ORDER_INPUT_REJECTED", "MANUAL_ORDER_RATE_LIMITED",
      "ORDER_SAFETY_UNAVAILABLE", "MANUAL_USE_REQUIRED", "EPISODE_CONFLICT", "ORDER_CONFLICT", "ORDER_UNSUPPORTED"] },
  { name: "protections", read: signal => fetchProtections("episode", null, signal),
    path: "/api/paper/protections?episode_id=episode", fallback: "PROTECTION_UNAVAILABLE", abort: true, retry: true,
    allowed: ["ORDER_CONFLICT", "ORDER_INPUT_INVALID", "PROTECTION_INPUT_REJECTED", "PROTECTION_NOT_FOUND",
      "PROTECTION_EPISODE_CLOSED", "ORDER_SAFETY_UNAVAILABLE"] },
  { name: "riskLimits", read: signal => fetchRisk("PAPER", signal), path: "/api/paper/risk-limit",
    fallback: "RISK_REQUEST_FAILED", abort: true, retry: true,
    allowed: ["RISK_INPUT_INVALID", "RISK_SOURCE_UNAVAILABLE", "RISK_REVISION_CONFLICT", "RISK_SCOPE_CONFLICT",
      "RISK_REQUEST_CONFLICT", "RISK_REQUEST_NOT_FOUND", "RISK_EFFECT_CURSOR_INVALID"] },
  { name: "killSwitch", read: signal => fetchStopStatus("PAPER", signal), path: "/api/paper/kill-switch",
    fallback: "TRADING_STOP_REQUEST_FAILED", abort: true, retry: false,
    allowed: ["TRADING_STOP_UNAVAILABLE", "TRADING_STOP_NOT_FOUND", "TRADING_STOP_REQUEST_NOT_FOUND",
      "TRADING_STOP_IDEMPOTENCY_CONFLICT", "PLATFORM_NOT_AUTHORIZED", "PLATFORM_OWNER_REQUIRED"] },
];
const sentinel = "synthetic-sensitive-proxy-text";
const now = "2026-11-06T00:00:00.000Z";
const deadline = "2026-11-06T00:00:30.000Z";
const fetcher = vi.fn<typeof fetch>();
let signal: AbortSignal;

beforeEach(() => {
  fetcher.mockReset();
  vi.stubGlobal("fetch", fetcher);
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(now));
  signal = new AbortController().signal;
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  document.cookie = "tiewtrade_csrf=; Max-Age=0; path=/";
});

async function rejected(work: Promise<unknown>): Promise<unknown> {
  try { await work; } catch (error) { return error; }
  throw new Error("expected request rejection");
}

function sanitized(error: unknown, code: string, status: number, retryAt: string | null = null) {
  expect(error).toBeInstanceOf(ApiRequestError);
  expect(error).toMatchObject({ message: code, status, retryAt });
  expect(error).not.toHaveProperty("cause");
  expect(JSON.stringify(error)).not.toContain(sentinel);
  if (!(error instanceof Error)) throw new Error("expected Error");
  expect(error.message).not.toContain(sentinel);
  expect(Object.values(error)).not.toContain(sentinel);
  expect(fetcher).toHaveBeenCalledTimes(1);
}

describe.each(cases)("$name public request policy", entry => {
  it("returns the successful value and preserves GET arguments and signal", async () => {
    const value = { unchanged: ["0.123456789012345678", null] };
    fetcher.mockResolvedValue(new Response(JSON.stringify(value)));
    await expect(entry.read(signal)).resolves.toEqual(value);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(entry.path, {
      method: "GET", credentials: "same-origin", headers: {}, signal,
    });
  });

  // Every allowed code must win even over risk's special 403/429 fallbacks.
  for (const code of entry.allowed) {
    it.each([403, 422, 429])(`preserves ${code} at status %s`, async status => {
      fetcher.mockResolvedValue(new Response(JSON.stringify({ detail: code }), { status }));
      sanitized(await rejected(entry.read(signal)), code, status);
    });
  }

  it.each([403, 429, 503])("sanitizes unknown HTTP errors at status %s", async status => {
    fetcher.mockResolvedValue(new Response(JSON.stringify({ detail: sentinel }), { status }));
    const code = entry.name === "riskLimits" && status === 403 ? "RISK_AUTHORIZATION_REQUIRED"
      : entry.name === "riskLimits" && status === 429 ? "RISK_RATE_LIMITED" : entry.fallback;
    sanitized(await rejected(entry.read(signal)), code, status);
  });

  it("sanitizes non-JSON proxy responses", async () => {
    fetcher.mockResolvedValue(new Response(`<html>${sentinel}</html>`, { status: 502 }));
    sanitized(await rejected(entry.read(signal)), entry.fallback, 502);
  });

  it.each([new Error(sentinel), sentinel, null, { message: sentinel, status: 403, retryAt: deadline }])(
    "does not trust arbitrary network rejection fields (%#)", async cause => {
      fetcher.mockRejectedValue(cause);
      sanitized(await rejected(entry.read(signal)), entry.fallback, 0);
    },
  );

  it("preserves the existing AbortError policy and identity", async () => {
    const cause = new DOMException("Aborted", "AbortError");
    fetcher.mockRejectedValue(cause);
    const error = await rejected(entry.read(signal));
    if (entry.abort) expect(error).toBe(cause);
    else sanitized(error, entry.fallback, 0);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("does not mistake a named Error for a DOMException", async () => {
    const cause = new Error(sentinel);
    cause.name = "AbortError";
    fetcher.mockRejectedValue(cause);
    sanitized(await rejected(entry.read(signal)), entry.fallback, 0);
  });

  it.each([
    [null, null], ["invalid", null], ["30", deadline],
    ["Fri, 06 Nov 2026 00:00:30 GMT", deadline], [deadline, deadline],
  ])("keeps the existing Retry-After behavior for %s", async (header, expected) => {
    fetcher.mockResolvedValue(new Response(JSON.stringify({ detail: sentinel }), {
      status: 503, headers: header === null ? {} : { "Retry-After": header },
    }));
    sanitized(await rejected(entry.read(signal)), entry.fallback, 503, entry.retry ? expected : null);
  });

  it("does not restart an already parsed retry deadline", async () => {
    const cause = new ApiRequestError(sentinel, 503, "30");
    vi.setSystemTime(new Date("2026-11-06T00:00:10.000Z"));
    fetcher.mockRejectedValue(cause);
    const error = await rejected(entry.read(signal));
    sanitized(error, entry.fallback, 503, entry.retry ? deadline : null);
    expect(error).not.toBe(cause);
  });
});

const key = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const scope = { expected_wallet_id: "wallet", expected_episode_id: "episode" };
const apiKey = { label: "test", key: "synthetic-key", secret: "synthetic-secret" };
const tradeUse = { use: "MANUAL" as const };
const wallet = { initial_capital: "1000.000000000000000001" };
const order: NewManualOrder = { ...scope, base: "BTC", quote: "USDT", kind: "MARKET", side: "BUY", quote_budget: "1.000000000000000001" };
const protection: ProtectionCreate = { ...scope, base: "BTC", quantity: "0.1", stop_loss_price: "90" };
const risk = { expected_revision: 1, expected_wallet_id: null, expected_episode_id: null, amount: "200.000000000000000001" };
type MutationCase = { name: string; call: () => Promise<unknown>; path: string; body?: object; totp?: string; idempotent?: boolean; method?: string; fallback: string };
const mutations: MutationCase[] = [
  { name: "apiKeys", call: () => addApiKey(apiKey, "123456"), path: "/api/api-keys", body: apiKey, totp: "123456", fallback: "API_KEY_REQUEST_FAILED" },
  { name: "tradingAccount", call: () => selectTradingUse(tradeUse), path: "/api/trading-account/use", body: tradeUse, fallback: "TRADING_ACCOUNT_REQUEST_FAILED" },
  { name: "paperWallet", call: () => createPaperWallet(wallet, key), path: "/api/paper-wallet", body: wallet, idempotent: true, fallback: "PAPER_WALLET_REQUEST_FAILED" },
  { name: "manualOrders", call: () => postNewOrder(order, key), path: "/api/paper/orders", body: order, idempotent: true, fallback: "MANUAL_ORDER_REQUEST_FAILED" },
  { name: "protections", call: () => postProtection("CREATE", undefined, protection, key), path: "/api/paper/protections", body: protection, idempotent: true, fallback: "PROTECTION_UNAVAILABLE" },
  // Stubbed fetch only: this verifies the existing Live TOTP envelope, never sends a Live order.
  { name: "riskLimits", call: () => postRisk("LIVE", "INCREASE", risk, key, "123456"), path: "/api/live/risk-limit/increase", body: risk, totp: "123456", idempotent: true, fallback: "RISK_REQUEST_FAILED" },
  { name: "killSwitch", call: () => postStop("PAPER", key), path: "/api/paper/kill-switch/stop", idempotent: true, fallback: "TRADING_STOP_REQUEST_FAILED" },
  { name: "deleteApiKey", call: () => deleteApiKey("key-one"), path: "/api/api-keys/key-one", method: "DELETE", fallback: "API_KEY_REQUEST_FAILED" },
];

describe.each(mutations)("$name mutation envelope", entry => {
  it.each(["success", "http", "network"])("keeps one request and unchanged arguments on %s", async outcome => {
    document.cookie = "tiewtrade_csrf=csrf-test; path=/";
    if (outcome === "network") fetcher.mockRejectedValue(new Error(sentinel));
    else if (outcome === "http") fetcher.mockResolvedValue(new Response(JSON.stringify({ detail: sentinel }), { status: 503 }));
    else fetcher.mockResolvedValue(entry.method === "DELETE" ? new Response(null, { status: 204 }) : new Response('{"receipt_id":"receipt"}'));
    if (outcome === "success") await expect(entry.call()).resolves.toEqual(entry.method === "DELETE" ? undefined : { receipt_id: "receipt" });
    else sanitized(await rejected(entry.call()), entry.fallback, outcome === "http" ? 503 : 0);
    const headers: Record<string, string> = { "Content-Type": "application/json", "X-CSRF-Token": "csrf-test" };
    if (entry.totp) headers["X-TiewTrade-TOTP"] = entry.totp;
    if (entry.idempotent) headers["Idempotency-Key"] = key;
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(entry.path, {
      method: entry.method ?? "POST", credentials: "same-origin", headers,
      ...(entry.body === undefined ? {} : { body: JSON.stringify(entry.body) }),
    });
  });
});
