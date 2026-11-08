import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PaperTradingActivity } from "../src/PaperTradingActivity";
import { protectionText as pt } from "../src/protectionMessages";
import { manualOrderText as t } from "../src/manualOrderMessages";
import type { PaperOrder } from "../src/manualOrders";

const stamp = "2026-10-30T00:00:00Z";
const order = (status: string, id: string): PaperOrder => ({
  accepted_at: stamp, base: "BTC", episode_id: "episode", failure_code: null,
  filled_quantity: status === "FILLED" ? "1" : "0", kind: "LIMIT", limit_price: "100",
  mode: "PAPER", order_id: id, quantity: "1", quote: "USDT", quote_budget: null,
  remaining_budget: null, remaining_quantity: status === "FILLED" ? "0" : "1",
  reserved_base: "0", reserved_quote: status === "FILLED" ? "0" : "100", sequence: 1,
  side: "BUY", snapshot_at: stamp, spent: status === "FILLED" ? "100" : "0",
  status, time_in_force: "GTC", wallet_id: "wallet",
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("separates open orders from history and does not claim an incomplete tab is empty", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("/paper/orders?") ? {
    orders: url.includes("cursor=") ? [order("FILLED", "closed")] : [order("ACCEPTED", "open")],
    snapshot_at: stamp,
    next_cursor: url.includes("cursor=") ? null : "next",
  } : { requests: [], next_cursor: null })))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const tree = (view: "OPEN" | "HISTORY") => <QueryClientProvider client={client}><PaperTradingActivity owner="owner" base="BTC" scope={{ expected_wallet_id: "wallet", expected_episode_id: "episode" }}
    visible view={view} onViewChange={() => {}} disabled={false} ready error={false} enabled available="0" rows={[]} ordersDisabled={false} onCancelOrder={() => {}}/></QueryClientProvider>;
  const ui = render(tree("OPEN"));
  expect(await screen.findByText("BTC/USDT")).toBeTruthy();
  expect(screen.getByRole("columnheader", { name: pt("snapshot") })).toBeTruthy();
  expect(screen.queryByRole("button", { name: t("refresh") })).toBeNull();
  expect(screen.queryByRole("button", { name: t("details") })).toBeNull();
  expect(screen.getAllByRole("columnheader")).toHaveLength(8);
  ui.rerender(tree("HISTORY"));
  expect(screen.getByText(t("incompleteResults"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("more") }));
  expect(await screen.findByText(t("FILLED"))).toBeTruthy();
  ui.rerender(tree("OPEN"));
  expect(screen.getByText(t("ACCEPTED"))).toBeTruthy();
  client.clear();
});

it("renders orders and monitored conditions together without routing their cancellation to the wrong target", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes("/paper/orders?") ? {
    orders: [order("ACCEPTED", "shared-id")], snapshot_at: stamp, next_cursor: null,
  } : { requests: [], next_cursor: null })))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onCancelOrder = vi.fn();
  render(<QueryClientProvider client={client}><PaperTradingActivity owner="owner" base="BTC" scope={{ expected_wallet_id: "wallet", expected_episode_id: "episode" }}
    visible view="OPEN" onViewChange={() => {}} disabled={false} ready error={false} enabled available="0" ordersDisabled={false} onCancelOrder={onCancelOrder}
    rows={[{ protection_id: "shared-id", wallet_id: "wallet", episode_id: "episode", mode: "PAPER", base: "ETH", quote: "USDT", quantity: "1.2345", protected_quantity: "1.23", executable_quantity: "1.23", step_residual_quantity: "0.0045", state: "ARMED", revision: 4, take_profit_price: "5000", stop_loss_price: "2500", conflicted: false, failure_code: null, market_ready: true, entry_order_id: null, snapshot_at: stamp }]}/></QueryClientProvider>);
  expect(await screen.findByText("BTC/USDT")).toBeTruthy();
  expect(screen.getByText("ETH/USDT")).toBeTruthy();
  expect(screen.getAllByRole("table")).toHaveLength(1);
  expect(screen.getAllByRole("row")).toHaveLength(3);
  expect(screen.getAllByRole("tablist")).toHaveLength(1);
  expect(screen.getByText("LIMIT · BUY")).toBeTruthy();
  expect(screen.getByText(pt("conditionRecord"))).toBeTruthy();
  expect(screen.getByText("1.23 ETH")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("cancel") }));
  expect(onCancelOrder).toHaveBeenCalledTimes(1);
  expect(onCancelOrder).toHaveBeenCalledWith(order("ACCEPTED", "shared-id"));
  client.clear();
});
