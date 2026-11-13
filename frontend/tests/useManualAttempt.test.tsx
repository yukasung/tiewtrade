import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { useManualAttempt } from "../src/useManualAttempt";
import { readAttempt, type ManualAttempt } from "../src/manualOrderJournal";
const attempt: ManualAttempt = { version: 1, owner: "owner", mode: "PAPER", action: "NEW", key: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee", payload: { expected_wallet_id: "w", expected_episode_id: "e", base: "BTC", quote: "USDT", side: "SELL", kind: "MARKET", base_quantity: "0.01" } };
const clients: QueryClient[] = [];
function mount(owner = "owner") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); clients.push(client);
  return renderHook(() => useManualAttempt(owner, true), { wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
}
afterEach(() => { cleanup(); clients.splice(0).forEach(c => c.clear()); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.sessionStorage.clear(); });
it("writes before POST, gates duplicate sends and retries the original scope after remount", async () => {
  const posts: RequestInit[] = [];
  vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => {
    if (init?.method === "POST") { expect(readAttempt("owner")).toEqual(attempt); posts.push(init); return Promise.reject(new Error("offline")); }
    return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }));
  }));
  const first = mount();
  act(() => { first.result.current.send(attempt); first.result.current.send(attempt); });
  await waitFor(() => expect(first.result.current.busy).toBe(false));
  expect(posts).toHaveLength(1); first.unmount();
  const second = mount(); await waitFor(() => expect(second.result.current.lookup.isError).toBe(true));
  expect(posts).toHaveLength(1);
  act(() => second.result.current.send(second.result.current.attempt!, true));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]?.body).toBe(posts[0]?.body);
  expect((posts[1]?.headers as Record<string, string>)["Idempotency-Key"]).toBe(attempt.key);
});
it("does not POST when journal persistence fails", async () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  const view = mount(); vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
  act(() => view.result.current.send(attempt));
  await waitFor(() => expect(view.result.current.storageError).toBe(true)); expect(fetcher).not.toHaveBeenCalled();
});
it("rejects a send for a different owner", () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  const view = mount("other"); act(() => view.result.current.send(attempt));
  expect(fetcher).not.toHaveBeenCalled(); expect(readAttempt("owner")).toBeNull();
});
