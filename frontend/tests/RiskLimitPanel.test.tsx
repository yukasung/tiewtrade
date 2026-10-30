import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { RiskLimitPanel } from "../src/RiskLimitPanel";
import { riskJournal, riskScope, type RiskAttempt } from "../src/riskLimitJournal";
import { riskText as t, riskLimitI18n } from "../src/riskLimitMessages";
import type { RiskReceipt, RiskSnapshot } from "../src/riskLimits";
const key = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const stamp = "2026-10-26T00:00:00Z";
const base: RiskSnapshot = { mode: "PAPER", amount: "100.000000000000000001", currency: "USDT", revision: 1, wallet_id: "w", episode_id: "e", latched: false, stop_alert_due: false, pause_alert_due: false, loss: "15", reason: "READY", source_revision: 2, evaluated_at: stamp, snapshot_at: stamp };
const attempt: RiskAttempt = { version: 1, owner: "owner", mode: "PAPER", key, action: "INCREASE", payload: { expected_revision: 1, expected_wallet_id: "w", expected_episode_id: "e", amount: "200.000000000000000001" } };
const receipt: RiskReceipt = { receipt_id: "r", mode: "PAPER", action: "INCREASE", idempotency_key: key, amount: "200.000000000000000001", expected_revision: 1, expected_wallet_id: "w", expected_episode_id: "e", state: "REQUEST_PENDING", applied_revision: null, failure_code: null, recorded_at: stamp };
const answer = (value: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(value), { status }));
let client: QueryClient;
function mount(custom?: (url: string, init?: RequestInit) => Promise<Response> | undefined, mode: "PAPER" | "LIVE" = "PAPER") {
  const fetcher = vi.fn((url: string, init?: RequestInit) => custom?.(url, init) ??
    (url.includes("requests") ? answer({ detail: "RISK_REQUEST_NOT_FOUND" }, 404) : answer(mode === "PAPER" ? base : { ...base, mode, wallet_id: null, episode_id: null, loss: null, reason: "RISK_SOURCE_UNAVAILABLE" })));
  vi.stubGlobal("fetch", fetcher);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  return { ...render(<StrictMode><QueryClientProvider client={client}><RiskLimitPanel owner="owner" mode={mode}/></QueryClientProvider></StrictMode>), fetcher };
}
afterEach(() => { cleanup(); client?.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.sessionStorage.clear(); void riskLimitI18n.changeLanguage("th"); });
it("journals exact intent before POST, sends the code only as a header, and never changes displayed money optimistically", async () => {
  vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(key);
  const { fetcher } = mount((url, init) => {
    if (init?.method !== "POST") return;
    expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(attempt);
    expect(window.sessionStorage.getItem("tiewtrade.risk-limit.v1:owner:PAPER")).not.toContain("654321");
    return answer(receipt, 202);
  });
  fireEvent.click(await screen.findByRole("button", { name: t("INCREASE") }));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByLabelText<HTMLInputElement>(t("amount")).value).toBe("");
  fireEvent.change(within(dialog).getByLabelText(t("amount")), { target: { value: "200.000000000000000001" } });
  fireEvent.change(within(dialog).getByLabelText(t("totp")), { target: { value: "654321" } });
  fireEvent.click(within(dialog).getByRole("button", { name: t("confirm") }));
  await screen.findByText(t("REQUEST_PENDING"));
  expect(document.activeElement).toBe(screen.getByRole("region", { name: t("recovery") }));
  const posts = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(posts).toHaveLength(1);
  expect((posts[0]![1]!.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBe("654321");
  expect(posts[0]![1]!.body).not.toContain("654321");
  expect(screen.getByText("100.000000000000000001 USDT")).toBeTruthy();
});
it("recovers AUTHORIZATION_ONLY after reload and retries the original identity without a new code", async () => {
  riskJournal.write(attempt);
  const { fetcher } = mount((url, init) => url.includes("requests/by-key") ? answer({ ...receipt, state: "AUTHORIZATION_ONLY" }) : init?.method === "POST" ? answer(receipt, 202) : undefined);
  await screen.findByText(t("AUTHORIZATION_ONLY"));
  expect(fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: t("retry") }));
  await waitFor(() => expect(fetcher.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1));
  const init = fetcher.mock.calls.find(([, init]) => init?.method === "POST")![1]!;
  expect((init.headers as Record<string, string>)["Idempotency-Key"]).toBe(key);
  expect((init.headers as Record<string, string>)["X-TiewTrade-TOTP"]).toBeUndefined();
  expect(JSON.parse(init.body as string)).toEqual(attempt.payload);
});
it("keeps UNKNOWN on lookup404 and storage failure cannot send", async () => {
  riskJournal.write(attempt);
  const first = mount();
  await screen.findByText(t("unknown"));
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(attempt);
  expect(first.fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  first.unmount(); client.clear(); riskJournal.clear(riskScope("owner", "PAPER"));
  const second = mount();
  fireEvent.click(await screen.findByRole("button", { name: t("DECREASE") }));
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage denied"); });
  fireEvent.change(screen.getByLabelText(t("amount")), { target: { value: "50" } });
  fireEvent.click(screen.getByRole("button", { name: t("confirm") }));
  await screen.findByText(t("storage"));
  expect(second.fetcher.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
});
it("reset warns about still-open losses, requires no TOTP and returns keyboard focus", async () => {
  mount(); const trigger = await screen.findByRole("button", { name: t("RESET") }); trigger.focus(); fireEvent.click(trigger);
  expect(screen.getByText(t("resetWarning"))).toBeTruthy();
  expect(screen.queryByLabelText(t("totp"))).toBeNull();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull(); expect(document.activeElement).toBe(trigger);
});
it("keeps Live requests, scope and unavailable PnL separate from Paper recovery", async () => {
  riskJournal.write(attempt);
  const { fetcher } = mount(undefined, "LIVE");
  await screen.findByText(t("RISK_SOURCE_UNAVAILABLE"));
  expect(fetcher.mock.calls.every(([url]) => url.includes("/live/risk-limit"))).toBe(true);
  expect(screen.queryByText(t("unknown"))).toBeNull();
  expect(riskJournal.read(riskScope("owner", "PAPER"))).toEqual(attempt);
});
it("does not mix a newer effects page with older counts or claim complete from an empty page", async () => {
  mount(url => url.includes("/stops/") ? answer({ stop_id: "s", mode: "PAPER", effects_revision: 11, snapshot_at: stamp, next_cursor: null, items: [{ target_kind: "ORDER", target_id: "new-target", order_id: "new-order", state: "CANCELED", attempt: 1, details: {}, recorded_at: stamp }] }) : answer({ ...base, latched: true, reason: "RISK_LOSS_LIMIT_REACHED", stop_id: "s", effects_revision: 10, target_count: 0, pending_count: 0, failed_count: 0, target_set_complete: false, stop_progress: "STOPPING" }));
  await screen.findByText(t("incomplete"));
  await screen.findByText(t("loadError"));
  expect(screen.queryByText("new-order")).toBeNull();
  expect(screen.queryByText(t("STOPPED"))).toBeNull();
});
