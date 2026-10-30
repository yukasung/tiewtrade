import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { PaperTradePage } from "../src/PaperTradePage";
import { writeAttempt } from "../src/manualOrderJournal";
import { manualOrderText as t } from "../src/manualOrderMessages";
vi.mock("../src/CandlestickChartPanel", () => ({ CandlestickChartPanel: ({ base, onMarketSnapshot }: {
  base: string; onMarketSnapshot: (value: { base: string; price: string; observedAt: string }) => void;
}) => <button type="button" data-testid="embedded-chart" onClick={() => onMarketSnapshot({ base, price: "100", observedAt: stamp })}>chart</button> }));
const stamp = "2026-10-25T00:00:00Z";
const key = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const wallet = { wallet_id: "w", episode_id: "e", balance: "10000.000000000000000001", reserved_quote: "0", available_quote: "10000.000000000000000001", base_balances: [], source_availability: "READY", revision: 1 };
const receipt = { mode: "PAPER", request_id: "r", wallet_id: "w", episode_id: "e", order_id: "o", action: "NEW", idempotency_key: key, request_summary: { base: "BTC", quote: "USDT", kind: "MARKET", side: "BUY", quote_budget: "100", base_quantity: null, limit_price: null, time_in_force: null }, recorded_at: stamp, snapshot_at: stamp, intake_state: "TRANSFERRED", intake_failure_code: null, command_id: "c", command_state: "PENDING", command_failure_code: null, command_snapshot: null, order_state: null, status_url: "/paper/order-requests/r" };
const answer = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
let queryClient: QueryClient;
function mount(custom?: (url: string, init?: RequestInit) => Promise<Response> | undefined) {
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    const override = custom?.(url, init); if (override) return override;
    if (url.includes("/risk-limit")) return Promise.resolve(answer({ detail: "unavailable" }, 503));
    if (url.includes("/market-catalog")) return Promise.resolve(answer({ active_pairs: [["BTC", "USDT"]] }));
    if (url.includes("/paper/trade")) return Promise.resolve(answer({ mode: "PAPER", wallet, account_use: "MANUAL", base: url.includes("base=BTC") ? "BTC" : null, quote: "USDT", catalog_revision: 1, snapshot_at: stamp, admission_ready: url.includes("base=BTC"), admission_reasons: url.includes("base=BTC") ? [] : ["ORDER_PAIR_REQUIRED"] }));
    if (url.includes("/paper/order-requests?")) return Promise.resolve(answer({ requests: [], next_cursor: null }));
    if (url.includes("/paper/orders?")) return Promise.resolve(answer({ orders: [], snapshot_at: stamp, next_cursor: null }));
    if (url.includes("order-requests")) return Promise.resolve(answer({ detail: "not found" }, 404));
    throw new Error("unexpected request");
  });
  vi.stubGlobal("fetch", fetcher);
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  const view = render(<StrictMode><QueryClientProvider client={queryClient}><PaperTradePage owner="owner"/></QueryClientProvider></StrictMode>);
  return { fetcher, ...view };
}
afterEach(() => { cleanup(); queryClient?.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.sessionStorage.clear(); });
async function draft() {
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  fireEvent.change(screen.getByLabelText(t("budget")), { target: { value: "100" } });
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("submit") }).disabled).toBe(false));
}
it("journals before POST, blocks duplicate clicks, and recovers reload with same-key retry after lookup404", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  const first = mount((url, init) => {
    if (url.endsWith("/paper/orders") && init?.method === "POST") {
      expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toContain(key);
      return Promise.reject(new Error("RAW SECRET"));
    }
  });
  await draft();
  fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("unknown"));
  expect(first.fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  expect(document.body.textContent).not.toContain("RAW SECRET");
  first.unmount(); queryClient.clear();
  const second = mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer(receipt, 202)) : undefined);
  await screen.findByText(t("unknown"));
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("retry") }).disabled).toBe(false));
  expect(second.fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: t("retry") }));
  await waitFor(() => expect(second.fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const sent = second.fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect((sent.headers as Record<string,string>)["Idempotency-Key"]).toBe(key);
  expect(JSON.parse(sent.body as string)).toMatchObject({ expected_episode_id: "e", quote_budget: "100" });
});
it("does not POST when storage write fails and blocks new requests when discovery fails", async () => {
  const { fetcher } = mount(); await draft();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
  fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("storage"));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});
it("shows discovery failure instead of an empty successful recovery", async () => {
  mount(url => url.includes("order-requests?") ? Promise.resolve(answer({ detail: "private" }, 503)) : undefined);
  await screen.findByText(t("recoveryError"));
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("submit") }).disabled).toBe(true);
});
it("polls a transferred command until rejection even without an order and keeps its reason visible", async () => {
  writeAttempt({ version: 1, owner: "owner", mode: "PAPER", key, action: "NEW", payload: { expected_wallet_id: "w", expected_episode_id: "e", base: "BTC", quote: "USDT", side: "BUY", kind: "MARKET", quote_budget: "100" } });
  mount(url => url.includes("order-requests/") ? Promise.resolve(answer({ ...receipt, command_state: "REJECTED", command_failure_code: "ORDER_INSUFFICIENT_FUNDS" })) : undefined);
  await screen.findByText(`${t("failure")}: ${t("ORDER_INSUFFICIENT_FUNDS")}`);
  await waitFor(() => expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull());
  expect(screen.queryByText(t("FILLED"))).toBeNull();
});
it("does not duplicate a completed cancel recovery result outside the order table", async () => {
  const cancel = { ...receipt, action: "CANCEL", request_summary: null, command_state: "SUCCEEDED", order_state: "FILLED" };
  const { fetcher } = mount(url => url.includes("order-requests?") ? Promise.resolve(answer({ requests: [cancel], next_cursor: null })) : url.includes("order-requests/r") ? Promise.resolve(answer(cancel)) : undefined);
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("order-requests?"))).toBe(true));
  expect(screen.queryByText(t("FILLED"))).toBeNull(); expect(screen.queryByText(t("CANCELED"))).toBeNull();
});
it("does not read a different owner's journal", async () => {
  window.sessionStorage.setItem("tiewtrade.manual-order.v1:other", "malformed");
  const { fetcher } = mount(); await draft();
  await act(async () => { await Promise.resolve(); });
  expect(fetcher.mock.calls.some(([url]) => url.includes("by-key"))).toBe(false);
});
it("continues polling after transfer until the linked command becomes terminal", async () => {
  let reads = 0;
  mount(url => url.includes("order-requests?") ? Promise.resolve(answer({ requests: [receipt], next_cursor: null })) : url.includes("order-requests/r") ? Promise.resolve(answer(++reads < 2 ? receipt : { ...receipt, command_state: "REJECTED", command_failure_code: "ORDER_INSUFFICIENT_FUNDS" })) : undefined);
  await screen.findByText(`${t("failure")}: ${t("ORDER_INSUFFICIENT_FUNDS")}`, {}, { timeout: 3500 });
  expect(reads).toBeGreaterThanOrEqual(2);
  expect(screen.queryByText(t("TRANSFERRED"))).toBeNull();
  await waitFor(() => expect(screen.queryByRole("heading", { name: t("recovery") })).toBeNull());
});
it("clears a previous pair's displayed market price before the next pair snapshot", async () => {
  mount(url => {
    if (url.includes("/market-catalog")) return Promise.resolve(answer({ active_pairs: [["BTC", "USDT"], ["ETH", "USDT"]] }));
    if (url.includes("/paper/trade")) {
      const selected = url.includes("base=BTC") ? "BTC" : url.includes("base=ETH") ? "ETH" : null;
      return Promise.resolve(answer({ mode: "PAPER", wallet, account_use: "MANUAL", base: selected, quote: "USDT", catalog_revision: 1,
        snapshot_at: stamp, admission_ready: selected !== null, admission_reasons: selected ? [] : ["ORDER_PAIR_REQUIRED"] }));
    }
  });
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  fireEvent.click(screen.getByTestId("embedded-chart"));
  const latest = screen.getByText(t("latestPrice")).parentElement!;
  expect(latest.textContent).toContain("100.00");
  expect(latest.textContent).not.toContain("USDT");
  expect(screen.queryByText(t("marketStatus"))).toBeNull();
  expect(screen.queryByText(t("marketObserved"))).toBeNull();
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "ETH" } });
  expect(latest.textContent).toContain(t("unavailable"));
  expect(latest.textContent).not.toContain("100 USDT");
});
it("shows a latched risk stop beside the form without a risk-settings control", async () => {
  mount(url => url.includes("/risk-limit") ? Promise.resolve(answer({
    amount: "1000", latched: true, stop_id: "stop", stop_progress: "STOPPING", reason: "RISK_LOSS_LIMIT_REACHED",
  })) : undefined);
  expect(await screen.findByText(t("riskStopStatus"))).toBeTruthy();
  expect(screen.getByText("กำลังหยุดออเดอร์เพิ่มความเสี่ยง")).toBeTruthy();
  expect(screen.queryByText("รายละเอียด / ตั้งค่าความเสี่ยง")).toBeNull();
});
it("links an unset loss limit to Trading account without embedding risk controls", async () => {
  mount(url => url.includes("/risk-limit") ? Promise.resolve(answer({ amount: null, latched: false, stop_id: null, reason: "RISK_LIMIT_UNSET" })) : undefined);
  const link = await screen.findByRole<HTMLAnchorElement>("link", { name: t("manageRisk") });
  expect(new URL(link.href).pathname).toBe("/trading-account");
  expect(screen.queryByRole("button", { name: "ตั้งเพดาน" })).toBeNull();
});
it("keeps the chart, order history and form in one desktop workspace", async () => {
  const { container } = mount();
  await screen.findByRole("tab", { name: t("openOrders") });
  const workspace = container.querySelector(".trade-workspace-with-orders")!;
  expect(workspace.querySelector(":scope > .trade-workspace-chart")).toBeTruthy();
  expect(workspace.querySelector(":scope > .trade-workspace-orders")).toBeTruthy();
  expect(workspace.querySelector(":scope > .trade-workspace-form .trade-workspace-details")).toBeNull();
});
it("requires every recovery page before permitting new requests", async () => {
  const { fetcher } = mount(url => url.includes("order-requests?") ? Promise.resolve(answer({ requests: [], next_cursor: url.includes("cursor=") ? null : "next" })) : undefined);
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("cursor=next"))).toBe(true));
  expect(screen.queryByRole("button", { name: t("more") })).toBeNull();
  await draft();
});
it("a definitive input refusal permits correcting the draft while unknown outcomes retain their journal", async () => {
  const { fetcher } = mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "MANUAL_ORDER_INPUT_REJECTED" }, 422)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("safeFailure"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});
it("retains recovery identity for an unrecognized 422 response", async () => {
  mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "untrusted-proxy-rejection" }, 422)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("unknown"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).not.toBeNull();
  expect(document.body.textContent).not.toContain("untrusted-proxy-rejection");
});

it("leaves terminal discovery results to the order table instead of duplicating them", async () => {
  const expired = { ...receipt, command_state: "SUCCEEDED", order_state: "EXPIRED" };
  const { fetcher } = mount(url => url.includes("order-requests?") ? Promise.resolve(answer({ requests: [expired], next_cursor: null })) : url.includes("order-requests/r") ? Promise.resolve(answer(expired)) : undefined);
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("order-requests?"))).toBe(true));
  expect(screen.queryByText(t("EXPIRED"))).toBeNull(); expect(screen.queryByText(t("FILLED"))).toBeNull();
});
it("stops pending polling while hidden and after route unmount", async () => {
  const { fetcher, unmount } = mount(url => url.includes("order-requests?") ? Promise.resolve(answer({ requests: [receipt], next_cursor: null })) : url.includes("order-requests/r") ? Promise.resolve(answer(receipt)) : undefined);
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("order-requests/r"))).toBe(true));
  expect(screen.getByText(t("TRANSFERRED")).closest("[hidden]")).toBeTruthy();
  expect(screen.queryByText(t("episodeDraftNotice"))).toBeNull();
  vi.useFakeTimers();
  try {
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    await act(async () => { document.dispatchEvent(new Event("visibilitychange")); await Promise.resolve(); });
    const before = fetcher.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(fetcher.mock.calls).toHaveLength(before);
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(fetcher.mock.calls).toHaveLength(before);
  } finally { vi.useRealTimers(); }
});
it("aborts pending owner reads when leaving the trade route", async () => {
  let signal: AbortSignal | null | undefined;
  const view = mount((url, init) => {
    if (!url.includes("/paper/trade")) return undefined;
    signal = init?.signal;
    return new Promise<Response>((_, reject) => signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
  });
  await waitFor(() => expect(signal).toBeTruthy());
  view.unmount(); expect(signal?.aborted).toBe(true);
});

it("clears the completed draft so a second click cannot silently create a new-key duplicate", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  const { fetcher } = mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ ...receipt, command_state: "SUCCEEDED", order_state: "ACCEPTED" }, 202)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await waitFor(() => expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull());
  expect(screen.getByLabelText<HTMLInputElement>(t("budget")).value).toBe("");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("submit") }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});

it("resolves only an explicit closed-episode refusal and requires a new draft", async () => {
  mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "MANUAL_ORDER_EPISODE_CLOSED" }, 409)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("episodeClosed"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull();
  expect(screen.getByLabelText<HTMLInputElement>(t("budget")).value).toBe("");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("submit") }).disabled).toBe(true);
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
});
it("retains UNKNOWN and the original journal for a generic conflict", async () => {
  mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "ORDER_CONFLICT" }, 409)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("unknown"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).not.toBeNull();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("submit") }).disabled).toBe(true);
});
it("discards a draft on episode replacement while retaining UNKNOWN's original retry scope", async () => {
  let episode = "e";
  const { fetcher } = mount((url, init) => {
    if (url.includes("/paper/trade")) return Promise.resolve(answer({ mode: "PAPER", wallet: { ...wallet, episode_id: episode }, account_use: "MANUAL", base: url.includes("base=BTC") ? "BTC" : null, admission_ready: url.includes("base=BTC"), admission_reasons: [], snapshot_at: stamp }));
    if (url.endsWith("/paper/orders") && init?.method === "POST") return Promise.reject(new Error("lost response"));
  });
  await draft();
  episode = "new-episode";
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade"] }); });
  await waitFor(() => expect(screen.getByLabelText<HTMLInputElement>(t("budget")).value).toBe(""));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.change(screen.getByLabelText(t("budget")), { target: { value: "100" } });
  fireEvent.click(screen.getByRole("button", { name: t("submit") }));
  await screen.findByText(t("unknown"));
  episode = "third-episode";
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade"] }); });
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("retry") }).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: t("retry") }));
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2));
  const posts = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(posts[0]![1]!.body).toBe(posts[1]![1]!.body);
  expect((JSON.parse(posts[1]![1]!.body as string) as { expected_episode_id: string }).expected_episode_id).toBe("new-episode");
});
