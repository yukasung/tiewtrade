import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { PaperTradePage } from "../src/PaperTradePage";
import { paperBotText as bt } from "../src/paperBotMessages";
import { writeAttempt } from "../src/manualOrderJournal";
import { manualOrderText as t } from "../src/manualOrderMessages";
import { protectionText as pt } from "../src/protectionMessages";
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
    if (url.includes("/paper/protections?") || url.includes("/paper/protection-requests?")) return Promise.resolve(answer({ protections: [], requests: [], next_cursor: null }));
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
  fireEvent.click(screen.getByRole("button", { name: bt("reduce") }));
  fireEvent.change(screen.getByLabelText(`${t("quantity")} (BTC)`), { target: { value: "100" } });
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("sell") }).disabled).toBe(false));
}
it("keeps conflicted protections editable after reloading an unavailable balance", async () => {
  const protection = { protection_id: "g", wallet_id: "w", episode_id: "e", mode: "PAPER", base: "BTC", quote: "USDT", quantity: "0.999", protected_quantity: "0", executable_quantity: "0", step_residual_quantity: null, state: "ARMED", revision: 4, take_profit_price: "110", stop_loss_price: "90", conflicted: true, failure_code: "ORDER_CONFLICT", market_ready: true, entry_order_id: "entry", snapshot_at: stamp };
  const { fetcher } = mount((url, init) => {
    if (url.includes("/paper/trade")) return Promise.resolve(answer({ mode: "PAPER", protection_enabled: true,
      wallet: { ...wallet, source_availability: "UNKNOWN", base_balances: [{ asset: "BTC", held: "0.5", reserved: "0", protection_allocated: "0.999", available: null }] },
      account_use: "MANUAL", base: url.includes("base=BTC") ? "BTC" : null, quote: "USDT", snapshot_at: stamp,
      admission_ready: false, admission_reasons: ["ORDER_CONFLICT"] }));
    if (url.includes("/paper/protections/g/replace") && init?.method === "POST") return Promise.resolve(answer({ request_id: "repair" }, 202));
    if (url.includes("/paper/protections?")) return Promise.resolve(answer({ protections: [protection], next_cursor: null }));
    if (url.includes("/paper/protection-requests?")) return Promise.resolve(answer({ requests: [], next_cursor: null }));
    if (url.includes("/paper/protection-requests/repair")) return Promise.resolve(answer({ state: "PENDING" }));
  });
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  const edit = await screen.findByRole<HTMLButtonElement>("button", { name: pt("edit") });
  await waitFor(() => expect(edit.disabled).toBe(false));
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  expect(screen.getAllByText(pt("conflict")).length).toBeGreaterThan(0);
  fireEvent.click(edit);
  fireEvent.change(screen.getByLabelText(`${pt("quantity")} (BTC)`), { target: { value: "0.5" } });
  fireEvent.click(screen.getByRole("button", { name: pt("save") }));
  await waitFor(() => {
    const repair = fetcher.mock.calls.find(([url, init]) => url.includes("/protections/g/replace") && init?.method === "POST");
    expect(repair).toBeTruthy();
    expect(JSON.parse(repair![1]!.body as string)).toHaveProperty("quantity", "0.5");
  });
});
it("journals before POST, blocks duplicate clicks, and recovers reload with same-key retry after lookup404", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  const first = mount((url, init) => {
    if (url.endsWith("/paper/orders") && init?.method === "POST") {
      expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toContain(key);
      return Promise.reject(new Error("RAW SECRET"));
    }
  });
  await draft();
  const submit = screen.getByRole("button", { name: bt("sell") });
  fireEvent.click(submit); fireEvent.click(submit);
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
  expect(JSON.parse(sent.body as string)).toMatchObject({ expected_episode_id: "e", base_quantity: "100", side: "SELL" });
});
it("does not POST when storage write fails and blocks new requests when discovery fails", async () => {
  const { fetcher } = mount(); await draft();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
  fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
  await screen.findByText(t("storage"));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});
it("blocks SELL transmission after discovery fails", async () => {
  let fail = false;
  const { fetcher } = mount(url => fail && url.includes("order-requests?") ? Promise.resolve(answer({ detail: "private" }, 503)) : undefined);
  await draft();
  fail = true;
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "all-episodes", "unresolved"] }); });
  await screen.findByText(t("recoveryError"));
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("sell") }).disabled).toBe(true);
  fireEvent.submit(screen.getByLabelText(`${t("quantity")} (BTC)`).closest("form")!);
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull();
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
  expect(screen.queryByText(t("unknown"))).toBeNull();
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
it("omits loss-limit summary and recovery heading from the bot panel", async () => {
  mount(url => url.includes("/risk-limit") ? Promise.resolve(answer({ amount: null, latched: false, stop_id: null, reason: "RISK_LIMIT_UNSET" })) : undefined);
  await screen.findByRole("heading", { name: bt("title") });
  expect(screen.queryByRole("link", { name: t("manageRisk") })).toBeNull();
  expect(screen.queryByText(t("riskSummary"))).toBeNull();
  expect(screen.queryByRole("heading", { name: t("recovery") })).toBeNull();
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
  await draft(); fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
  await screen.findByText(t("safeFailure"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});
it("retains recovery identity for an unrecognized 422 response", async () => {
  mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "untrusted-proxy-rejection" }, 422)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
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
  expect((await screen.findByText(t("TRANSFERRED"))).closest("[hidden]")).toBeTruthy();
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
  await draft(); fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
  await waitFor(() => expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: bt("reduce") }));
  expect(screen.getByLabelText<HTMLInputElement>(`${t("quantity")} (BTC)`).value).toBe("");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("sell") }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
});

it("resolves only an explicit closed-episode refusal and requires a new draft", async () => {
  mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "MANUAL_ORDER_EPISODE_CLOSED" }, 409)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
  await screen.findByText(t("episodeClosed"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: bt("reduce") }));
  expect(screen.getByLabelText<HTMLInputElement>(`${t("quantity")} (BTC)`).value).toBe("");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("sell") }).disabled).toBe(true);
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
});
it("retains UNKNOWN and the original journal for a generic conflict", async () => {
  mount((url, init) => url.endsWith("/paper/orders") && init?.method === "POST" ? Promise.resolve(answer({ detail: "ORDER_CONFLICT" }, 409)) : undefined);
  await draft(); fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
  await screen.findByText(t("unknown"));
  expect(window.sessionStorage.getItem("tiewtrade.manual-order.v1:owner")).not.toBeNull();
  expect(screen.queryByRole("button", { name: bt("sell") })).toBeNull();
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
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  fireEvent.click(screen.getByRole("button", { name: bt("reduce") }));
  expect(screen.getByLabelText<HTMLInputElement>(`${t("quantity")} (BTC)`).value).toBe("");
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.change(screen.getByLabelText(`${t("quantity")} (BTC)`), { target: { value: "100" } });
  fireEvent.click(screen.getByRole("button", { name: bt("sell") }));
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


it.each([
  { state: "WAITING_ENTRY", quantity: "0", market_ready: true, editable: true },
  { state: "ARMING", quantity: "0.3996", market_ready: true, editable: true },
  { state: "ARMED", quantity: "0.999", market_ready: false, editable: true },
  { state: "EXITING", quantity: "0.499", market_ready: true, editable: false },
  { state: "FAILED", quantity: "0.499", market_ready: true, editable: true },
])("never claims a $state allocation is fully protected or closed", async ({ state, quantity, market_ready, editable }) => {
  const protection = { protection_id: "g", wallet_id: "w", episode_id: "e", mode: "PAPER", base: "BTC", quote: "USDT", quantity, protected_quantity: "0", executable_quantity: "0", step_residual_quantity: null, state, revision: 4, take_profit_price: "110", stop_loss_price: "90", conflicted: false, failure_code: state === "FAILED" ? "ORDER_INSUFFICIENT_LIQUIDITY" : null, market_ready, entry_order_id: "entry", snapshot_at: stamp,
    exit_order_id: ["EXITING", "FAILED"].includes(state) ? "exit-order" : null,
    exit_order_state: state === "FAILED" ? "EXPIRED" : null,
    exit_command_state: state === "EXITING" ? "PENDING" : null,
    exit_quantity: "0.999", exit_filled_quantity: "0.5" };
  mount(url => {
    if (url.includes("/paper/trade")) return Promise.resolve(answer({ mode: "PAPER", protection_enabled: true, wallet, account_use: "MANUAL", base: url.includes("base=BTC") ? "BTC" : null, quote: "USDT", snapshot_at: stamp, admission_ready: true, admission_reasons: [] }));
    if (url.includes("/paper/protections?")) return Promise.resolve(answer({ protections: [protection], next_cursor: null }));
    if (url.includes("/paper/protection-requests?")) return Promise.resolve(answer({ requests: [], next_cursor: null }));
  });
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  const panel = screen.getByRole("heading", { name: t("orders") }).closest("section")!;
  await within(panel).findByText(pt(state as "ARMED"));
  const covered = within(panel).getAllByRole("row")[1]!.querySelectorAll("td")[4]!;
  expect(within(covered).getByText("0 BTC").textContent).toBe("0 BTC");
  expect(within(panel).queryByText(pt("CLOSED"))).toBeNull();
  await waitFor(() => expect(within(panel).getByRole<HTMLButtonElement>("button", { name: pt("edit") }).disabled).toBe(!editable));
  expect(within(panel).getByRole<HTMLButtonElement>("button", { name: pt("cancel") }).disabled).toBe(!editable);
  if (!market_ready) expect(within(panel).getByRole("alert").textContent).toBe(pt("unavailable"));
  if (state === "FAILED") {
    expect(within(panel).getByRole("alert").textContent).toBe(pt("failed"));
    expect(within(panel).getByText("0.499 BTC")).toBeTruthy();
    expect(within(panel).getByText(t("EXPIRED"))).toBeTruthy();
  }
  if (state === "EXITING") expect(within(panel).getByText(t("PENDING"))).toBeTruthy();
});


it("displays the protected executable portion and uncovered step residual without money arithmetic", async () => {
  const protection = { protection_id: "g", wallet_id: "w", episode_id: "e", mode: "PAPER", base: "BTC", quote: "USDT", quantity: "0.00131868", protected_quantity: "0.00131", executable_quantity: "0.00131", step_residual_quantity: "0.00000868", state: "ARMED", revision: 4, take_profit_price: "76500", stop_loss_price: "75000", conflicted: false, failure_code: null, market_ready: true, entry_order_id: "entry", snapshot_at: stamp };
  mount(url => {
    if (url.includes("/paper/protections?")) return Promise.resolve(answer({ protections: [protection], next_cursor: null }));
  });
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  expect(await screen.findByText(pt("noAutoSale"))).toBeTruthy();
  expect(screen.getByText("0.00000868 BTC")).toBeTruthy();
  expect(screen.getAllByText("0.00131 BTC")).toHaveLength(1);
});

const activityProtection = { protection_id: "activity-group", wallet_id: "w", episode_id: "e", mode: "PAPER", base: "BTC", quote: "USDT", quantity: "0.00131868", protected_quantity: "0", executable_quantity: "0.00131", step_residual_quantity: "0.00000868", state: "FAILED", revision: 4, take_profit_price: "76500", stop_loss_price: "75000", conflicted: false, failure_code: "PROTECTION_SETUP_REJECTED", market_ready: true, entry_order_id: null, snapshot_at: stamp };
function activityData(url: string) {
  if (url.includes("/paper/protections?")) return Promise.resolve(answer({ protections: [activityProtection, { ...activityProtection, protection_id: "canceled", state: "CANCELED", quantity: "0", protected_quantity: "0", step_residual_quantity: "0", failure_code: null }], next_cursor: null }));
  if (url.includes("/paper/protection-requests?")) return Promise.resolve(answer({ requests: [], next_cursor: null }));
}
it("shows normal orders and conditions in one table with one toolbar and read-only history", async () => {
  const { fetcher } = mount(activityData);
  await draft();
  fireEvent.keyDown(document, { key: "Escape" });
  const activity = screen.getByRole("region", { name: t("orders") });
  expect(within(activity).getAllByRole("tablist")).toHaveLength(1);
  expect(within(activity).getAllByRole("table")).toHaveLength(1);
  expect(await screen.findByText(pt("attention"))).toBeTruthy();
  expect(screen.getByText(pt("FAILED"))).toBeTruthy();
  expect(screen.getByText(pt("conditionRecord"))).toBeTruthy();
  const open = screen.getByRole("tab", { name: t("openOrders") });
  const history = screen.getByRole("tab", { name: t("orderHistory") });
  open.focus(); fireEvent.keyDown(open, { key: "ArrowRight" });
  expect(document.activeElement).toBe(history);
  expect(history.getAttribute("aria-selected")).toBe("true");
  expect(screen.getByText(pt("attention"))).toBeTruthy();
  expect(screen.getByText(pt("CANCELED"))).toBeTruthy();
  expect(screen.queryByRole("button", { name: pt("edit") })).toBeNull();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: pt("create") }).disabled).toBe(true);
  fireEvent.keyDown(history, { key: "Home" });
  expect(document.activeElement).toBe(open);
  expect(screen.getByText(pt("FAILED"))).toBeTruthy();
  expect(screen.queryByText(pt("CANCELED"))).toBeNull();
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
});
it("does not lose an unknown protection attempt or generate a new key when switching activity tabs", async () => {
  const { protectionJournal } = await import("../src/protectionJournal");
  const attempt = { version: 1 as const, owner: "owner", mode: "PAPER" as const, key, action: "CANCEL" as const, target: "g", payload: { expected_wallet_id: "w", expected_episode_id: "e", expected_revision: 4 } };
  protectionJournal.write(attempt);
  const { fetcher } = mount((url, init) => {
    if (url.includes("/paper/protection-requests/by-key/")) return Promise.resolve(answer({ detail: "PROTECTION_NOT_FOUND" }, 404));
    if (url.includes("/paper/protections/g/cancel") && init?.method === "POST") return Promise.reject(new Error("lost receipt"));
    return activityData(url);
  });
  await draft();
  expect(await screen.findByText(pt("unknown"))).toBeTruthy();
  for (const name of [t("orderHistory"), t("openOrders"), t("orderHistory"), t("openOrders")]) {
    fireEvent.click(screen.getByRole("tab", { name }));
    expect(protectionJournal.read("owner")).toEqual(attempt);
  }
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: pt("retry") }).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: pt("retry") }));
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const posted = fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect(new Headers(posted.headers).get("Idempotency-Key")).toBe(key);
  expect(JSON.parse(posted.body as string)).toEqual(attempt.payload);
  expect(protectionJournal.read("owner")).toEqual(attempt);
});

it("keeps the bot draft across refresh but clears it on wallet/episode change and sends no command", async () => {
  let episode = "e"; let fail = false;
  const { fetcher } = mount(url => url.includes("/paper/trade") ? Promise.resolve(answer(fail ? { detail: "unavailable" } : {
    mode: "PAPER", wallet: { ...wallet, episode_id: episode }, base: url.includes("base=BTC") ? "BTC" : null,
    admission_ready: true, admission_reasons: [], snapshot_at: stamp,
  }, fail ? 503 : 200)) : undefined);
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  await waitFor(() => expect(screen.getByText("10,000.000000000000000001 USDT")).toBeTruthy());
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "100.123" } });
  fail = true;
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade"] }); });
  await waitFor(() => expect(screen.queryByText("10,000.000000000000000001 USDT")).toBeNull());
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("100.123");
  fail = false;
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade"] }); });
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("100.123");
  episode = "new";
  await act(async () => { await queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade"] }); });
  await waitFor(() => expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe(""));
  fireEvent.keyDown(screen.getByLabelText(bt("budget")), { key: "Enter" });
  fireEvent.click(screen.getByRole("button", { name: bt("start") }));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});
it("clears bot draft and closes the SELL dialog on pair change without reopening on return", async () => {
  mount(url => url.includes("market-catalog") ? Promise.resolve(answer({ active_pairs: [["BTC", "USDT"], ["ETH", "USDT"]] })) : undefined);
  await draft();
  const pair = screen.getByLabelText(t("pair"));
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "123" } });
  fireEvent.change(pair, { target: { value: "ETH" } });
  expect(screen.queryByRole("dialog")).toBeNull(); expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("");
  fireEvent.change(pair, { target: { value: "BTC" } }); expect(screen.queryByRole("dialog")).toBeNull();
});
it("does not display a delayed prior owner's balance or retain their bot draft", async () => {
  let nextOwner = false;
  let resolveOld: ((value: Response) => void) | undefined;
  let delayOld = false;
  const view = mount(url => {
    if (!url.includes("/paper/trade")) return undefined;
    if (delayOld && !nextOwner) return new Promise<Response>(resolve => { resolveOld = resolve; });
    return Promise.resolve(answer({ mode: "PAPER", wallet: { ...wallet, wallet_id: nextOwner ? "other-wallet" : "w", available_quote: nextOwner ? "42" : "999" },
      base: url.includes("base=BTC") ? "BTC" : null, admission_ready: true, admission_reasons: [], snapshot_at: stamp }));
  });
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  await screen.findByText("999 USDT");
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "123" } });
  delayOld = true;
  act(() => { void queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade"] }); });
  await waitFor(() => expect(resolveOld).toBeTruthy());
  nextOwner = true;
  view.rerender(<QueryClientProvider client={queryClient}><PaperTradePage owner="other"/></QueryClientProvider>);
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  await screen.findByText("42 USDT");
  await act(async () => { resolveOld!(answer({ mode: "PAPER", wallet: { ...wallet, available_quote: "999" }, base: "BTC", admission_ready: true, admission_reasons: [] })); await Promise.resolve(); });
  expect(screen.queryByText("999 USDT")).toBeNull();
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("");
});

it("shows admission warnings only inside the SELL dialog and retains its safety gate", async () => {
  const { fetcher } = mount(url => url.includes("/paper/trade") ? Promise.resolve(answer({
    mode: "PAPER", wallet, base: url.includes("base=BTC") ? "BTC" : null,
    admission_ready: false, admission_reasons: ["ORDER_SAFETY_UNAVAILABLE"], snapshot_at: stamp,
  })) : undefined);
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(t("pair")).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText(t("pair")), { target: { value: "BTC" } });
  expect(screen.queryByText(t("blocked"))).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: bt("reduce") }));
  expect(within(screen.getByRole("dialog")).getByText(t("blocked"))).toBeTruthy();
  fireEvent.change(screen.getByLabelText(`${t("quantity")} (BTC)`), { target: { value: "1" } });
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("sell") }).disabled).toBe(true);
  fireEvent.submit(screen.getByLabelText(`${t("quantity")} (BTC)`).closest("form")!);
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByText(t("blocked"))).toBeNull();
});

it("keeps the balance node during refresh without relaxing SELL admission", async () => {
  let delay = false;
  let resolveRefresh: ((response: Response) => void) | undefined;
  const { fetcher } = mount(url => delay && url.includes("/paper/trade?base=BTC")
    ? new Promise<Response>(resolve => { resolveRefresh = resolve; }) : undefined);
  await draft();
  fireEvent.keyDown(document, { key: "Escape" });
  const amount = screen.getByText("10,000.000000000000000001 USDT");
  delay = true;
  act(() => { void queryClient.invalidateQueries({ queryKey: ["manual-orders", "owner", "PAPER", "trade", "BTC"] }); });
  await screen.findByText(bt("updating"));
  expect(screen.getByText("10,000.000000000000000001 USDT")).toBe(amount);
  fireEvent.click(screen.getByRole("button", { name: bt("reduce") }));
  fireEvent.change(screen.getByLabelText(`${t("quantity")} (BTC)`), { target: { value: "1" } });
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("sell") }).disabled).toBe(true);
  fireEvent.submit(screen.getByLabelText(`${t("quantity")} (BTC)`).closest("form")!);
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  await act(async () => {
    resolveRefresh!(answer({ mode: "PAPER", wallet: { ...wallet, available_quote: "9000" }, base: "BTC", admission_ready: true, admission_reasons: [], snapshot_at: stamp }));
    await Promise.resolve();
  });
  await screen.findByText("9,000 USDT");
  expect(screen.queryByText(bt("updating"))).toBeNull();
});
