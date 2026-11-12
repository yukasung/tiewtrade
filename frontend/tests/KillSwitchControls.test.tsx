import { openStopSettings } from "./stopSettings";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { KillSwitchBanner, KillSwitchControls } from "../src/KillSwitchControls";
import { killSwitchText as t } from "../src/killSwitchMessages";
import { riskText } from "../src/riskLimitMessages";
import { postResume, type StopReceipt, type StopStatus } from "../src/killSwitch";

const status = (mode: "PAPER" | "LIVE", stop: string | null = null): StopStatus => ({
  active_causes: stop ? ["USER"] : [],
  mode, stop_id: stop, cause: stop ? "USER" : null, generation: stop ? 1 : null, revision: stop ? 1 : 0, summary_revision: 0,
  progress: stop ? "STOPPED" : null, target_set_complete: mode === "PAPER" && stop !== null,
  target_count: 0, pending_count: 0, failed_count: 0, platform_stop_id: null,
  platform_reason: null, resume_ready: mode === "PAPER" && stop !== null,
  reconciliation_revision: stop ? 0 : null,
  capability: mode === "PAPER" ? "AVAILABLE" : "LIVE_EXECUTION_UNAVAILABLE",
});

const appliedUserStop: StopReceipt = { request_id: "r1", stop_id: "s1", mode: "PAPER", action: "STOP", cause: "USER", generation: 1, revision: 1, state: "APPLIED", failure_code: null, recorded_at: "2026-11-08T00:00:00Z" };

function makeControlClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
}

function renderControls(client: QueryClient, owner = "owner") {
  return render(<QueryClientProvider client={client}><KillSwitchControls owner={owner}/></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); window.localStorage.clear(); });

it("keeps durable loss and system banners visible after the risk latch resets", async () => {
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    const body = url.includes("/risk-limit") ? { latched: false } : {
      ...status("PAPER", "latest-user-stop"),
      active_causes: ["USER", "LOSS_LIMIT", "SYSTEM"],
    };
    return Promise.resolve(new Response(JSON.stringify(body)));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><KillSwitchBanner owner="owner"/></QueryClientProvider>);
  expect(await screen.findByText(t("lossTitle"))).toBeTruthy();
  expect(screen.getByText(t("systemTitle"))).toBeTruthy();
});

it("shows separate Paper and Live stop controls and preserves the unknown request key", async () => {
  let fail = true;
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      if (fail) { fail = false; return Promise.resolve(new Response(JSON.stringify({ detail: "TRADING_STOP_UNAVAILABLE" }), { status: 503 })); }
      return Promise.resolve(new Response(JSON.stringify({ request_id: "r", stop_id: "s", mode: "PAPER", action: "STOP", cause: "USER", generation: 1, revision: 1, state: "REQUEST_PENDING", failure_code: null, recorded_at: "2026-10-31T00:00:00Z" })));
    }
    return Promise.resolve(new Response(JSON.stringify(url.includes("/live/") ? status("LIVE") : status("PAPER"))));
  });
  vi.stubGlobal("fetch", fetcher);
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "11111111-1111-4111-8111-111111111111") });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  renderControls(client);
  openStopSettings();
  expect(await screen.findByRole("button", { name: t("paperStop") })).toBeTruthy();
  openStopSettings();
  expect(screen.getByRole("button", { name: t("liveStop") })).toBeTruthy();
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  openStopSettings();
  expect((await screen.findByRole("alert")).textContent).toContain(t("requestFailed"));
  const saved = window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:owner:PAPER");
  expect(saved).toBe("11111111-1111-4111-8111-111111111111");
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: `${t("paperStop")} — ${t("retry")}` }));
  await waitFor(() => expect(window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:owner:PAPER")).toBeNull());
  const posts = fetcher.mock.calls.filter(([, init]) => init?.method === "POST");
  expect(posts).toHaveLength(2);
  expect((posts[0]?.[1]?.headers as Record<string, string>)["Idempotency-Key"]).toBe(saved);
  expect((posts[1]?.[1]?.headers as Record<string, string>)["Idempotency-Key"]).toBe(saved);
});

it("renders the complete PROBLEMS snapshot and keeps resume unavailable", async () => {
  const stopId = "11111111-1111-4111-8111-111111111111";
  const problemStatus: StopStatus = {
    ...status("PAPER", stopId), progress: "PROBLEMS", summary_revision: 2,
    target_count: 3, pending_count: 1, failed_count: 1, resume_ready: false,
    reconciliation_revision: 4,
  };
  vi.stubGlobal("fetch", vi.fn((url: string) => {
    if (url.includes("resume-summary")) return Promise.resolve(new Response(JSON.stringify({
      status: problemStatus,
      positions: [{ base: "BTC", quote: "USDT", quantity: "0.11" }],
      snapshot_revision: 2,
      reconciled_at: "2026-10-31T00:01:00Z",
    })));
    if (url.includes("/effects?")) return Promise.resolve(new Response(JSON.stringify({
      effects_revision: 2, mode: "PAPER", stop_id: stopId, next_cursor: null,
      snapshot_at: "2026-10-31T00:01:00Z",
      items: [
        { target_kind: "ORDER", target_id: "failed-target", order_id: "failed-order", state: "FAILED", attempt: 2, details: {}, recorded_at: "2026-10-31T00:00:58Z" },
        { target_kind: "ORDER", target_id: "canceled-target", order_id: "canceled-order", state: "CANCELED", attempt: 1, details: {}, recorded_at: "2026-10-31T00:00:59Z" },
        { target_kind: "REQUEST", target_id: "pending-target", order_id: "pending-order", state: "PENDING", attempt: 1, details: {}, recorded_at: "2026-10-31T00:01:00Z" },
      ],
    })));
    return Promise.resolve(new Response(JSON.stringify(url.includes("/live/") ? status("LIVE") : problemStatus)));
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  renderControls(client);

  openStopSettings();
  fireEvent.click(await screen.findByRole("button", { name: t("details") }));
  expect(await screen.findByText("BTC/USDT: 0.11")).toBeTruthy();
  expect(await screen.findByText("failed-target")).toBeTruthy();
  expect(screen.getByText("canceled-target")).toBeTruthy();
  expect(screen.getByText("pending-target")).toBeTruthy();
  expect(screen.getByText(`${t("reconciledAt")}: 2026-10-31T00:01:00Z`)).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("resume") }).disabled).toBe(true);
  expect(screen.getByText(t("resumeUnavailable"))).toBeTruthy();
});

it("refetches a stale resume snapshot and disables another submit", async () => {
  const stopId = "22222222-2222-4222-8222-222222222222";
  const ready: StopStatus = {
    ...status("PAPER", stopId), summary_revision: 1, reconciliation_revision: 1,
  };
  const stale: StopStatus = {
    ...ready, revision: 2, summary_revision: 2, resume_ready: false,
    reconciliation_revision: 2,
  };
  let rejected = false;
  let summaryReads = 0;
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" && url.endsWith("/paper/kill-switch/resume")) {
      return Promise.resolve(new Response(JSON.stringify({
        request_id: "resume-request", stop_id: stopId, mode: "PAPER", action: "RESUME",
        cause: "USER", generation: 1, revision: 1, state: "REQUEST_PENDING",
        failure_code: null, recorded_at: "2026-10-31T00:00:00Z",
      }), { status: 202 }));
    }
    if (url.endsWith("/paper/kill-switch/requests/resume-request")) {
      rejected = true;
      return Promise.resolve(new Response(JSON.stringify({
        request_id: "resume-request", stop_id: stopId, mode: "PAPER", action: "RESUME",
        cause: "USER", generation: 1, revision: 1, state: "REJECTED",
        failure_code: "TRADING_STOP_NOT_READY", recorded_at: "2026-10-31T00:00:01Z",
      })));
    }
    if (url.includes("resume-summary")) {
      summaryReads += 1;
      const current = rejected ? stale : ready;
      return Promise.resolve(new Response(JSON.stringify({
        status: current, positions: [], snapshot_revision: current.summary_revision,
        reconciled_at: "2026-10-31T00:00:00Z",
      })));
    }
    if (url.includes("/effects?")) return Promise.resolve(new Response(JSON.stringify({
      effects_revision: rejected ? 2 : 1, mode: "PAPER", stop_id: stopId,
      next_cursor: null, snapshot_at: "2026-10-31T00:00:00Z", items: [],
    })));
    return Promise.resolve(new Response(JSON.stringify(url.includes("/live/") ? status("LIVE") : rejected ? stale : ready)));
  });
  vi.stubGlobal("fetch", fetcher);
  vi.stubGlobal("crypto", { randomUUID: vi.fn(() => "33333333-3333-4333-8333-333333333333") });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  renderControls(client);

  openStopSettings();
  fireEvent.click(await screen.findByRole("button", { name: t("details") }));
  const resume = await screen.findByRole("button", { name: t("resume") });
  await screen.findByText(riskText("empty"));
  expect((resume as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(resume);

  expect(await screen.findByText("TRADING_STOP_NOT_READY")).toBeTruthy();
  await waitFor(() => expect(summaryReads).toBeGreaterThanOrEqual(2));
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("resume") }).disabled).toBe(true));
  expect(screen.getByText(t("resumeUnavailable"))).toBeTruthy();
  const resumePost = fetcher.mock.calls.find(([url, init]) =>
    String(url).endsWith("/paper/kill-switch/resume") && init?.method === "POST");
  const resumeBody = resumePost?.[1]?.body;
  expect(typeof resumeBody).toBe("string");
  expect(JSON.parse(resumeBody as string) as Record<string, unknown>).toMatchObject({
    expected_stop_id: stopId,
    expected_revision: 1,
    expected_summary_revision: 1,
    expected_reconciliation_revision: 1,
  });
});


it.each(["getItem", "setItem", "removeItem", "property"] as const)("keeps STOP usable when storage %s fails", async method => {
  const blocked = () => { throw new DOMException("blocked", "SecurityError"); };
  if (method === "property") vi.spyOn(window, "localStorage", "get").mockImplementation(blocked);
  else vi.spyOn(Storage.prototype, method).mockImplementation(blocked);
  const keys: string[] = [];
  let failures = 1;
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      keys.push(new Headers(init.headers).get("Idempotency-Key")!);
      if (failures-- > 0) return Promise.resolve(new Response(JSON.stringify({ detail: "TRADING_STOP_UNAVAILABLE" }), { status: 503 }));
      return Promise.resolve(new Response(JSON.stringify({ request_id: "r", stop_id: "s", mode: "PAPER", action: "STOP", cause: "USER", generation: 1, revision: 1, state: "REQUEST_PENDING", failure_code: null, recorded_at: "2026-11-08T00:00:00Z" })));
    }
    return Promise.resolve(new Response(JSON.stringify(status(url.includes("/live/") ? "LIVE" : "PAPER"))));
  }));
  const client = makeControlClient();
  renderControls(client);
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  await screen.findByText(t("requestFailed"));
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: `${t("paperStop")} — ${t("retry")}` }));
  await waitFor(() => expect(keys).toHaveLength(2));
  expect(keys[1]).toBe(keys[0]);
  await waitFor(() => expect(screen.queryByText(t("requestFailed"))).toBeNull());
  openStopSettings();
  expect(within(screen.getByRole("group", { name: t("modeStatus", { mode: "PAPER" }) })).getByText(t("storageUnavailable"))).toBeTruthy();
  client.clear();
});


it("recovers server stop status after remount without automatically resending when storage is blocked", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
  let posts = 0;
  const fetcher = vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts++; return Promise.resolve(new Response("{}", { status: 503 })); }
    return Promise.resolve(new Response(JSON.stringify(status(url.includes("/live/") ? "LIVE" : "PAPER", posts ? "durable-stop" : null))));
  });
  vi.stubGlobal("fetch", fetcher);
  const client = makeControlClient();
  const first = renderControls(client);
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  await screen.findByText(t("requestFailed"));
  first.unmount();
  client.clear();
  renderControls(client);
  openStopSettings();
  expect((await screen.findAllByText(t("STOPPED"))).length).toBeGreaterThan(0);
  expect(posts).toBe(1);
  client.clear();
});


it.each([false, true])("creates fresh STOP identities after resume despite failed cleanup (remount=%s)", async remount => {
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
  const receipts = new Map<string, StopReceipt>();
  const keys: string[] = [];
  let generation = 0;
  let stopped = false;
  const receipt = (action: "STOP" | "RESUME"): StopReceipt => ({ request_id: `request-${generation}`, stop_id: `stop-${generation}`, mode: "PAPER", action, cause: "USER", generation, revision: generation, state: "APPLIED", failure_code: null, recorded_at: "2026-11-08T00:00:00Z" });
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST" && url.endsWith("/stop")) {
      const key = new Headers(init.headers).get("Idempotency-Key")!;
      keys.push(key);
      if (!receipts.has(key)) { generation++; stopped = true; receipts.set(key, receipt("STOP")); }
      return Promise.resolve(new Response(JSON.stringify(receipts.get(key))));
    }
    if (init?.method === "POST" && url.endsWith("/resume")) {
      stopped = false;
      return Promise.resolve(new Response(JSON.stringify(receipt("RESUME"))));
    }
    if (url.includes("/requests/by-key/")) {
      const key = decodeURIComponent(new URL(url, "http://localhost").pathname.split("/").at(-1)!);
      return Promise.resolve(new Response(JSON.stringify(receipts.get(key))));
    }
    return Promise.resolve(new Response(JSON.stringify(url.includes("/live/") ? status("LIVE") : status("PAPER", stopped ? `stop-${generation}` : null))));
  }));
  const client = makeControlClient();
  const mount = () => renderControls(client);
  let view = mount();
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  await waitFor(() => expect(generation).toBe(1));
  await screen.findByText(t("storageUnavailable"));
  // Leave the first key in storage even when subsequent writes also fail.
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  for (const expected of [2, 3]) {
    await postResume("PAPER", { status: status("PAPER", `stop-${generation}`), positions: [], snapshot_revision: 0, reconciled_at: null }, window.crypto.randomUUID());
    expect(stopped).toBe(false);
    await client.invalidateQueries({ queryKey: ["kill-switch", "owner", "PAPER"] });
    if (remount) { view.unmount(); client.clear(); view = mount(); }
    openStopSettings();
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("paperStop") }).disabled).toBe(false));
    openStopSettings();
    fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
    await waitFor(() => expect(generation).toBe(expected));
    expect(stopped).toBe(true);
  }
  expect(new Set(keys).size).toBe(3);
  expect(screen.queryByText(t("requestFailed"))).toBeNull();
  client.clear();
});

it.each(["REQUEST_PENDING", "APPLIED", "missing"] as const)("resolves persisted STOP outcome %s with read-only recovery and no automatic new intent", async outcome => {
  const keys: string[] = [];
  let lookups = 0;
  const receipt: StopReceipt = { request_id: "r", stop_id: "s", mode: "PAPER", action: "STOP", cause: "USER", generation: 1, revision: 1, state: outcome === "APPLIED" ? "APPLIED" : "REQUEST_PENDING", failure_code: null, recorded_at: "2026-11-08T00:00:00Z" };
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      keys.push(new Headers(init.headers).get("Idempotency-Key")!);
      return Promise.resolve(keys.length === 1 ? new Response("{}", { status: 503 }) : new Response(JSON.stringify(receipt)));
    }
    if (url.includes("/requests/by-key/")) {
      lookups++;
      return Promise.resolve(outcome === "missing" ? new Response(JSON.stringify({ detail: "TRADING_STOP_REQUEST_NOT_FOUND" }), { status: 404 }) : new Response(JSON.stringify(receipt)));
    }
    const current = status(url.includes("/live/") ? "LIVE" : "PAPER", keys.length && outcome !== "missing" ? "s" : null);
    return Promise.resolve(new Response(JSON.stringify(current)));
  }));
  const client = makeControlClient();
  const mount = () => renderControls(client);
  const first = mount();
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  await screen.findByText(t("requestFailed"));
  first.unmount(); client.clear(); mount();
  expect(keys).toHaveLength(1);
  await waitFor(() => expect(lookups).toBe(1));
  if (outcome === "missing") {
    openStopSettings();
    const retry = screen.getByRole<HTMLButtonElement>("button", { name: `${t("paperStop")} — ${t("retry")}` });
    await waitFor(() => expect(retry.disabled).toBe(false));
    fireEvent.click(retry);
    await waitFor(() => expect(keys).toHaveLength(2));
  } else {
    openStopSettings();
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("paperStop") }).disabled).toBe(false));
    expect(keys).toHaveLength(1);
  }
  expect(new Set(keys).size).toBe(1);
  await waitFor(() => expect(screen.queryByText(t("requestFailed"))).toBeNull());
  client.clear();
});

it("preserves the recovery key when receipt lookup fails instead of issuing a new STOP", async () => {
  const key = window.crypto.randomUUID();
  window.localStorage.setItem("tiewtrade.kill-switch.stop.v1:owner:PAPER", key);
  let lookupFails = true;
  const posted: string[] = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posted.push(new Headers(init.headers).get("Idempotency-Key")!);
      return Promise.resolve(new Response(JSON.stringify({ request_id: "r", stop_id: "s", state: "REQUEST_PENDING" })));
    }
    if (url.includes("/requests/by-key/")) return Promise.resolve(new Response(JSON.stringify({ detail: lookupFails ? "TRADING_STOP_UNAVAILABLE" : "TRADING_STOP_REQUEST_NOT_FOUND" }), { status: lookupFails ? 503 : 404 }));
    return Promise.resolve(new Response(JSON.stringify(status(url.includes("/live/") ? "LIVE" : "PAPER"))));
  }));
  const client = makeControlClient();
  renderControls(client);
  await screen.findByText(t("requestFailed"));
  expect(posted).toHaveLength(0);
  expect(window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:owner:PAPER")).toBe(key);
  openStopSettings();
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: `${t("paperStop")} — ${t("retry")}` }).disabled).toBe(false));
  lookupFails = false;
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: `${t("paperStop")} — ${t("retry")}` }));
  await waitFor(() => expect(posted).toEqual([key]));
  client.clear();
});


it("does not continue the previous owner's recovery into a STOP after owner switch", async () => {
  const key = window.crypto.randomUUID();
  window.localStorage.setItem("tiewtrade.kill-switch.stop.v1:owner:PAPER", key);
  let resolveLookup!: (response: Response) => void;
  let started = false;
  let posts = 0;
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts++; return Promise.resolve(new Response("{}")); }
    if (url.includes("/requests/by-key/")) { started = true; return new Promise<Response>(resolve => { resolveLookup = resolve; }); }
    return Promise.resolve(new Response(JSON.stringify(status(url.includes("/live/") ? "LIVE" : "PAPER"))));
  }));
  const client = makeControlClient();
  const view = renderControls(client);
  await waitFor(() => expect(started).toBe(true));
  view.rerender(<QueryClientProvider client={client}><KillSwitchControls owner="other"/></QueryClientProvider>);
  await act(async () => {
    resolveLookup(new Response(JSON.stringify({ request_id: "r", stop_id: "s", mode: "PAPER", action: "STOP", state: "APPLIED" })));
    await new Promise(resolve => window.setTimeout(resolve, 0));
  });
  expect(posts).toBe(0);
  expect(window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:owner:PAPER")).toBe(key);
  expect(window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:other:PAPER")).toBeNull();
  client.clear();
});

it.each([false, true])("a normal STOP click creates a fresh MANUAL cutoff after stale APPLIED recovery (storage blocked=%s)", async blockedStorage => {
  const oldKey = "11111111-1111-4111-8111-111111111111";
  window.localStorage.setItem("tiewtrade.kill-switch.stop.v1:owner:PAPER", oldKey);
  if (blockedStorage) {
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("full", "QuotaExceededError"); });
  }
  const old = appliedUserStop;
  let lookups = 0;
  // Simulates a MANUAL intent admitted after the old cutoff; only a new STOP covers it.
  let pendingAfterOldCutoff = true;
  const posted: string[] = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      const key = new Headers(init.headers).get("Idempotency-Key")!;
      posted.push(key);
      if (key !== oldKey) pendingAfterOldCutoff = false;
      return Promise.resolve(new Response(JSON.stringify({ ...old, request_id: "r2", stop_id: "s2", generation: 2, revision: 2 })));
    }
    if (url.includes("/requests/by-key/")) { lookups++; return Promise.resolve(new Response(JSON.stringify(old))); }
    return Promise.resolve(new Response(JSON.stringify(url.includes("/live/") ? status("LIVE") : { ...status("PAPER", "s1"), resume_ready: false })));
  }));
  const client = makeControlClient(); renderControls(client);
  openStopSettings();
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("paperStop") }).disabled).toBe(false));
  expect(lookups).toBe(1); expect(posted).toHaveLength(0); expect(pendingAfterOldCutoff).toBe(true);
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  await waitFor(() => expect(posted).toHaveLength(1));
  expect(posted[0]).not.toBe(oldKey); expect(pendingAfterOldCutoff).toBe(false);
  await waitFor(() => expect(screen.queryByText(t("requestFailed"))).toBeNull());
  client.clear();
});
it("a recovered old receipt cannot retire a newer unknown STOP identity", async () => {
  const oldKey = "11111111-1111-4111-8111-111111111111";
  window.localStorage.setItem("tiewtrade.kill-switch.stop.v1:owner:PAPER", oldKey);
  const old = appliedUserStop;
  const posted: string[] = [];
  vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posted.push(new Headers(init.headers).get("Idempotency-Key")!); return Promise.resolve(new Response("{}", { status: 503 })); }
    if (url.includes("/requests/by-key/")) return Promise.resolve(new Response(JSON.stringify(old)));
    return Promise.resolve(new Response(JSON.stringify(url.includes("/live/") ? status("LIVE") : { ...status("PAPER", "s1"), resume_ready: false })));
  }));
  const client = makeControlClient(); renderControls(client);
  openStopSettings();
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: t("paperStop") }).disabled).toBe(false));
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  await screen.findByText(t("requestFailed"));
  expect(posted).toHaveLength(1); expect(posted[0]).not.toBe(oldKey);
  await act(async () => { client.setQueryData(["kill-switch", "owner", "recovery", "PAPER", oldKey], { ...old, recorded_at: "2026-11-08T00:01:00Z" }); await Promise.resolve(); });
  expect(window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:owner:PAPER")).toBe(posted[0]);
  openStopSettings();
  fireEvent.click(screen.getByRole("button", { name: `${t("paperStop")} — ${t("retry")}` }));
  await waitFor(() => expect(posted).toHaveLength(2)); expect(posted[1]).toBe(posted[0]);
  client.clear();
});
