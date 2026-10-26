import type { components } from "./api-types";
import { ApiRequestError, send } from "./auth";

export type NewManualOrder = components["schemas"]["MarketBuyInput"] | components["schemas"]["MarketSellInput"] | components["schemas"]["LimitOrderInput"];
export type ExpectedEpisode = components["schemas"]["ExpectedPaperEpisode"];
export type ManualRequest = components["schemas"]["ManualRequestView"];
export type TradeSnapshot = components["schemas"]["PaperTradeView"];
export type PaperOrder = components["schemas"]["PaperOrderView"];
type RequestPage = components["schemas"]["ManualRequestPage"];
type OrderPage = components["schemas"]["PaperOrderPage"];
export const manualKey = (owner: string) => ["manual-orders", owner, "PAPER"] as const;

async function safe<T>(request: Promise<T>): Promise<T> {
  try { return await request; } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    const error = cause instanceof ApiRequestError ? cause : null;
    // Never render arbitrary server/proxy/network text.
    const allowed = new Set(["MANUAL_ORDER_EPISODE_CLOSED", "MANUAL_ORDER_INPUT_REJECTED", "MANUAL_ORDER_RATE_LIMITED", "ORDER_SAFETY_UNAVAILABLE", "MANUAL_USE_REQUIRED", "EPISODE_CONFLICT", "ORDER_CONFLICT", "ORDER_UNSUPPORTED"]);
    throw new ApiRequestError(error && allowed.has(error.message) ? error.message : "MANUAL_ORDER_REQUEST_FAILED", error?.status ?? 0, error?.retryAt ?? null);
  }
}
export const fetchTrade = (base: string, signal?: AbortSignal) => safe(send<TradeSnapshot>(`/paper/trade${base ? `?base=${encodeURIComponent(base)}` : ""}`, undefined, undefined, "GET", signal));
export const fetchRequests = (cursor: string | null, signal?: AbortSignal) => safe(send<RequestPage>(`/paper/order-requests?state=unresolved${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, "GET", signal));
export const fetchRequestKey = (key: string, action: "NEW" | "CANCEL", signal?: AbortSignal) => safe(send<ManualRequest>(`/paper/order-requests/by-key/${encodeURIComponent(key)}?action=${action}`, undefined, undefined, "GET", signal));
export const fetchRequest = (id: string, signal?: AbortSignal) => safe(send<ManualRequest>(`/paper/order-requests/${encodeURIComponent(id)}`, undefined, undefined, "GET", signal));
export const fetchOrders = (episode: string, cursor: string | null, signal?: AbortSignal) => safe(send<OrderPage>(`/paper/orders?episode_id=${encodeURIComponent(episode)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, "GET", signal));
export const fetchOrder = (id: string, signal?: AbortSignal) => safe(send<PaperOrder>(`/paper/orders/${encodeURIComponent(id)}`, undefined, undefined, "GET", signal));
export const postNewOrder = (body: NewManualOrder, key: string) => safe(send<ManualRequest>("/paper/orders", body, undefined, "POST", undefined, { "Idempotency-Key": key }));
export const postCancelOrder = (order: string, body: ExpectedEpisode, key: string) => safe(send<ManualRequest>(`/paper/orders/${encodeURIComponent(order)}/cancel`, body, undefined, "POST", undefined, { "Idempotency-Key": key }));
export function requestTerminal(value: ManualRequest): boolean {
  return value.intake_state === "REJECTED" || value.command_state === "REJECTED" || value.command_state === "SUCCEEDED";
}
export function orderTerminal(status: string): boolean {
  return ["FILLED", "CANCELED", "EXPIRED", "REJECTED"].includes(status);
}
