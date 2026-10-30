import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PaperOrderList } from "../src/PaperOrderList";
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
  vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(new Response(JSON.stringify({
    orders: url.includes("cursor=") ? [order("FILLED", "closed")] : [order("ACCEPTED", "open")],
    snapshot_at: stamp,
    next_cursor: url.includes("cursor=") ? null : "next",
  })))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><PaperOrderList owner="owner" episode="episode"
    visible disabled={false} onCancel={() => {}}/></QueryClientProvider>);
  expect(await screen.findByText("BTC/USDT")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: t("orderHistory") }));
  expect(screen.getByText(t("incompleteResults"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("more") }));
  expect(await screen.findByText(t("FILLED"))).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: t("openOrders") }));
  expect(screen.getByText(t("ACCEPTED"))).toBeTruthy();
  client.clear();
});
