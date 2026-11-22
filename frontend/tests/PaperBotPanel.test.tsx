import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BotRunStatus } from "../src/BotRunStatus";
import { PaperBotPanel } from "../src/PaperBotPanel";
import { paperBotText as bt } from "../src/paperBotMessages";
import { manualOrderText as t } from "../src/manualOrderMessages";
import { strategyJournal } from "../src/strategyJournal";
import { manualKey } from "../src/manualOrders";
function setupQueries() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  vi.stubGlobal("fetch", vi.fn(() =>
    Promise.resolve(new Response(JSON.stringify({ status: null, run_id: null }), { status: 200 }))
  ));
  return {
    wrapper: ({ children }: PropsWithChildren) =>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  };
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("refreshes only this owner's wallet cache when verified bot holdings change", async () => {
  const owner = "f21-wallet-refresh";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const held = { mode: "PAPER", status: "RUNNING", run_id: "run", exposure_available: true,
    positions: [{ base: "BTC", quote: "USDT", quantity: "14.985" }], protections: [] };
  const walletKey = [...manualKey(owner), "trade", "BTC"];
  const otherKey = [...manualKey("other-owner"), "trade", "BTC"];
  client.setQueryData(walletKey, { balance: "4391" });
  client.setQueryData(otherKey, { balance: "20000" });
  vi.stubGlobal("fetch", vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(
    path.endsWith("/bots/status") ? held : { stop_id: null, pending_count: 0 },
  )))));
  render(<PaperBotPanel owner={owner} available="4391" loading={false}/>, {
    wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  await screen.findByText(bt("RUNNING"));
  expect(client.getQueryState(walletKey)?.isInvalidated).toBe(false);
  act(() => { client.setQueryData(["bot-status", owner, "PAPER"], { ...held, positions: [] }); });
  await vi.waitFor(() => expect(client.getQueryState(walletKey)?.isInvalidated).toBe(true));
  expect(client.getQueryState(otherKey)?.isInvalidated).toBe(false);
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
  client.clear();
});
it("keeps the budget as a local string, never submits and keeps start disabled", () => {
  const queries = setupQueries();
  const view = render(<PaperBotPanel owner="owner-a" available="10000.000000000000000001" loading={false}/>, queries);
  expect(screen.getByLabelText<HTMLSelectElement>(bt("strategy")).value).toBe("rsi-step-grid-ema-single-tp");
  expect(screen.getByLabelText<HTMLSelectElement>(bt("maxEntries")).options).toHaveLength(10);
  const input = screen.getByLabelText(bt("budget"));
  fireEvent.change(input, { target: { value: "123.450000000000000001" } });
  fireEvent.keyDown(input, { key: "Enter" }); fireEvent.click(screen.getByRole("button", { name: bt("start") }));
  fireEvent(window, new Event("resize"));
  view.rerender(<PaperBotPanel owner="owner-a" available={null} loading/>);
  expect((input as HTMLInputElement).value).toBe("123.450000000000000001");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  expect(view.container.querySelector("form")).toBeNull(); expect(vi.mocked(fetch).mock.calls.every(([path, init]) =>
    (path === "/api/paper/bots/status" || path === "/api/paper/bots/strategy" || path === "/api/paper/kill-switch") && init?.method === "GET"
  )).toBe(true);
  expect(screen.queryByText(/10,000/)).toBeNull(); expect(screen.getByText(bt("loading"))).toBeTruthy();
  view.rerender(<PaperBotPanel owner="owner-a" available={null} loading={false}/>);
  expect(screen.getByText(t("unavailable"))).toBeTruthy();
});
it("clears only on scope remount and preserves exact balance display", () => {
  const view = render(<PaperBotPanel owner="owner-a" key="w:e:BTC" available="0.000000000000000001" loading={false}/>, setupQueries());
  expect(screen.getByText("0.000000000000000001 USDT")).toBeTruthy();
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "20" } });
  view.rerender(<PaperBotPanel owner="owner-a" key="w:e:ETH" available={null} loading={false}/>);
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("");
});


it("reloads status on a mode change and drops the old mode's status", async () => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(
    path === "/api/paper/bots/status"
      ? { status: "RUNNING", run_id: "paper-run" }
      : { status: "PAUSED", run_id: "live-run" },
  ), { status: 200 }))));
  const view = render(<BotRunStatus owner="owner-a" mode="PAPER"/>, queries);
  await screen.findByText(bt("RUNNING"));
  view.rerender(<BotRunStatus owner="owner-a" mode="LIVE"/>);
  expect(screen.queryByText(bt("RUNNING"))).toBeNull();
  await screen.findByText(bt("PAUSED"));
});

it("reports a status outage without displaying the raw server error", async () => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(
    JSON.stringify({ detail: "sensitive internal failure" }), { status: 503 },
  ))));
  render(<BotRunStatus owner="owner-a" mode="PAPER"/>, queries);
  expect(await screen.findByText(bt("statusUnavailable"))).toBeTruthy();
  expect(screen.queryByText("sensitive internal failure")).toBeNull();
  expect(screen.getByRole("button", { name: bt("retry") })).toBeTruthy();
});

it("shows a pending start request without presenting a running bot", async () => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
    mode: "PAPER", status: null, run_id: null, pending_request_id: "pending-request",
    exposure_available: true, positions: [], protections: [],
  }), { status: 200 }))));
  render(<BotRunStatus owner="owner-a" mode="PAPER"/>, queries);
  expect(await screen.findByText(bt("requestPending"))).toBeTruthy();
  expect(screen.queryByText(bt("RUNNING"))).toBeNull();
  expect(screen.queryByText(bt("STARTING"))).toBeNull();
});

it("shows server holdings and protection state without claiming full coverage", async () => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(
    path.endsWith("/bots/status") ? {
      mode: "PAPER", status: "STOPPED", run_id: "run", stop_reason: "SYSTEM",
      exposure_available: true, protections_more: true,
      positions: [{ base: "BTC", quote: "USDT", quantity: "0.000000000000000001" }],
      protections: [{ protection_id: "p", base: "BTC", quantity: "0.000000000000000001", state: "ARMING", conflicted: false }],
    } : { mode: "PAPER", stop_id: null, pending_count: 0 },
  )))));
  render(<BotRunStatus owner="owner-a" mode="PAPER"/>, queries);
  expect(await screen.findByText(bt("STOPPED"))).toBeTruthy();
  expect(screen.getAllByText("0.000000000000000001 BTC")).toHaveLength(2);
  expect(screen.getByText(bt("exposureNotice"))).toBeTruthy();
  expect(screen.getByText(bt("moreProtections"))).toBeTruthy();
  expect(screen.getByRole("button", { name: /Paper/ })).toBeTruthy();
});

it("recovers an uncertain start after remount with the same keys and original pair", async () => {
  const owner = "f21-recover";
  window.sessionStorage.clear();
  const posts: { path: string; key: string | undefined; body: string }[] = [];
  let uncertain = true;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    await Promise.resolve();
    if (init?.method === "POST") {
      posts.push({ path, key: (init.headers as Record<string, string>)["Idempotency-Key"], body: typeof init.body === "string" ? init.body : "" });
      if (path.endsWith("/configurations")) return new Response(JSON.stringify({ reference: "f21:11111111-1111-4111-8111-111111111111" }));
      if (uncertain) { uncertain = false; throw new TypeError("private transport failure"); }
      return new Response(JSON.stringify({ pending: true, failure_code: null }));
    }
    if (path.includes("/requests/by-key/")) return new Response(JSON.stringify({ detail: "missing" }), { status: 404 });
    return new Response(JSON.stringify(path.endsWith("/strategy")
      ? { timeframes: ["1m", "5m", "1M"] }
      : { status: null, run_id: null, can_start: true, unavailable_reason: null }));
  }));
  const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const view = render(<PaperBotPanel owner={owner} base="BTC" available="1000" loading={false}/>, { wrapper });
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "100.000000000000000001" } });
  await vi.waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: bt("start") }));
  await screen.findByRole("alert");
  expect(screen.queryByText("private transport failure")).toBeNull();
  expect(posts).toHaveLength(2);
  view.unmount();
  render(<PaperBotPanel owner={owner} base="ETH" available="1000" loading={false}/>, { wrapper });
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("100.000000000000000001");
  expect(screen.getByText(`${bt("pair")}: BTC/USDT`)).toBeTruthy();
  expect(posts).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: bt("recoverStart") }));
  await vi.waitFor(() => expect(posts).toHaveLength(3));
  expect(posts[2]).toEqual(posts[1]);
  expect(posts.filter(p => p.path.endsWith("/configurations"))).toHaveLength(1);
  window.sessionStorage.clear();
});

it("blocks a new start when request identity storage cannot be read", () => {
  const storage = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
  try {
    render(<PaperBotPanel owner="blocked" available="1000" loading={false}/>, setupQueries());
    expect(screen.getByText(bt("storageError"))).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
    expect(vi.mocked(fetch).mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
  } finally { storage.mockRestore(); }
});

it("starts directly with the current flat replacement proof and journals it with the new config", async () => {
  window.sessionStorage.clear();
  const owner = "replacement-owner";
  const replacement = { run_id: "11111111-1111-4111-8111-111111111111", run_revision: 5,
    stop_id: null, stop_revision: null, summary_revision: 0, reconciliation_revision: 2 };
  const status = { status: "STOPPED", run_id: replacement.run_id, can_start: true, replacement,
    exposure_available: true, positions: [], protections: [],
    pinned_configuration: { base: "BTC", timeframe: "5m", max_entries: 10, capital_per_entry: "100" } };
  let currentStatus = status;
  const posts: { path: string; body: unknown }[] = [];
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  vi.stubGlobal("fetch", vi.fn((path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ path, body: JSON.parse(typeof init.body === "string" ? init.body : "{}") as unknown });
      return Promise.resolve(new Response(JSON.stringify(path.endsWith("/configurations")
        ? { reference: "f21:22222222-2222-4222-8222-222222222222" } : { pending: true, failure_code: null })));
    }
    return Promise.resolve(new Response(JSON.stringify(path.endsWith("/strategy")
      ? { timeframes: ["5m", "1M"] } : path.endsWith("/bots/status") ? currentStatus : { stop_id: null, pending_count: 0 })));
  }));
  render(<PaperBotPanel owner={owner} available="1000" loading={false}/>, { wrapper: ({ children }: PropsWithChildren) =>
    <QueryClientProvider client={client}>{children}</QueryClientProvider> });
  await screen.findByRole("button", { name: bt("start") });
  expect(screen.queryByRole("checkbox")).toBeNull();
  const input = screen.getByLabelText<HTMLInputElement>(bt("budget"));
  expect(input.value).toBe("");
  fireEvent.change(input, { target: { value: "17.000000000000000001" } });
  fireEvent.change(screen.getByLabelText(bt("maxEntries")), { target: { value: "3" } });
  const start = screen.getByRole<HTMLButtonElement>("button", { name: bt("start") });
  await vi.waitFor(() => expect(start.disabled).toBe(false));
  const changed = { ...status, replacement: { ...replacement, run_revision: 6 } };
  currentStatus = changed;
  await act(async () => {
    await client.refetchQueries({ queryKey: ["bot-status", owner, "PAPER"] });
    // React Query schedules observer notifications after the refetch resolves.
    await new Promise<void>(resolve => window.setTimeout(resolve, 0));
  });
  await vi.waitFor(() => expect(start.disabled).toBe(false));
  fireEvent.click(start);
  await vi.waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[0]?.body).toEqual({ base: "BTC", timeframe: "5m", capital_per_entry: "17.000000000000000001", max_entries: 3 });
  expect(posts[1]?.body).toEqual({ strategy_config_ref: "f21:22222222-2222-4222-8222-222222222222", replacement: changed.replacement });
  window.sessionStorage.clear();
});

it.each(["pending", "RUNNING", "PAUSED"])("keeps %s on the main screen with the stop-bot action", async (state) => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(
    path.endsWith("/bots/status") ? {
      mode: "PAPER", status: state === "pending" ? null : state,
      run_id: state === "pending" ? null : "run",
      pinned_configuration: { base: "BTC", timeframe: "5m", max_entries: 10, capital_per_entry: "100" },
      pending_request_id: state === "pending" ? "request" : null,
      exposure_available: true, positions: [], protections: [],
    } : { mode: "PAPER", stop_id: null, pending_count: 0 },
  )))));
  render(<PaperBotPanel owner={`compact-${state}`} available="10000" loading={false}/>, queries);
  expect(await screen.findByRole("button", { name: bt("stopBot") })).toBeTruthy();
  if (state === "PAUSED") expect(screen.queryByText(bt("PAUSED"))).toBeNull();
  else expect(screen.getByText(bt(state === "pending" ? "requestPending" : "RUNNING"))).toBeTruthy();
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).disabled).toBe(true);
  expect(screen.getByLabelText<HTMLSelectElement>(bt("maxEntries")).disabled).toBe(true);
  expect(screen.queryByText(bt("holdings"))).toBeNull();
  expect(screen.queryByRole("button", { name: bt("recoverStart") })).toBeNull();
});

it("replaces Start with Stop inside the same main-panel action group", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  let pending = false;
  vi.stubGlobal("fetch", vi.fn(async (path: string, init?: RequestInit) => {
    await Promise.resolve();
    if (init?.method === "POST" && path.endsWith("/configurations")) {
      return new Response(JSON.stringify({ reference: "f21:11111111-1111-4111-8111-111111111111" }));
    }
    if (init?.method === "POST" && path.endsWith("/bots/requests")) {
      pending = true;
      return new Response(JSON.stringify({ pending: true, failure_code: null }));
    }
    return new Response(JSON.stringify(path.endsWith("/bots/status")
      ? { mode: "PAPER", can_start: !pending, status: null, run_id: null,
        pending_request_id: pending ? "request" : null }
      : path.endsWith("/strategy") ? { timeframes: ["5m"] }
      : { mode: "PAPER", stop_id: null, pending_count: 0 }));
  }));
  render(<QueryClientProvider client={client}><PaperBotPanel owner="same-panel" available="10000" loading={false}/></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "100" } });
  const start = screen.getByRole<HTMLButtonElement>("button", { name: bt("start") });
  await vi.waitFor(() => expect(start.disabled).toBe(false));
  const actionGroup = start.closest('[role="group"]');
  const url = window.location.href;
  fireEvent.click(start);
  const stop = await screen.findByRole("button", { name: bt("stopBot") });
  expect(actionGroup?.contains(stop)).toBe(true);
  expect(window.location.href).toBe(url);
  expect(screen.queryByRole("button", { name: bt("start") })).toBeNull();
  window.sessionStorage.clear();
});


it.each([
  { exposure: true, positions: [], message: null },
  { exposure: true, positions: [{ base: "BTC", quote: "USDT", quantity: "1" }], message: "stoppedWithHoldings" as const },
  { exposure: false, positions: [], message: "stoppedCheckHoldings" as const },
])("keeps Start after STOPPED without the stopped notice ($message)", async ({ exposure, positions, message }) => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(
    path.endsWith("/bots/status") ? {
      mode: "PAPER", status: "STOPPED", run_id: "stopped-run", can_start: false,
      pinned_configuration: { base: "BTC", timeframe: "5m", max_entries: 10, capital_per_entry: "100" },
      exposure_available: exposure, positions, protections: [],
    } : { mode: "PAPER", stop_id: null, pending_count: 0 },
  )))));
  render(<PaperBotPanel owner="stopped-action" available="10000" loading={false}/>, queries);
  await vi.waitFor(() => expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("100"));
  expect(screen.queryByText(/บอทหยุดแล้ว|Bot stopped/)).toBeNull();
  if (message) expect(await screen.findByText(bt(message))).toBeTruthy();
  const start = screen.getByRole<HTMLButtonElement>("button", { name: bt("start") });
  expect(start.disabled).toBe(true);
  expect(screen.queryByText(bt("snapshotAt"))).toBeNull();
  expect(screen.queryByText(bt("holdings"))).toBeNull();
  expect(screen.queryByRole("button", { name: bt("stopBot") })).toBeNull();
});


it("retires a resolved rejected start without a run and restores Start", async () => {
  const owner = "rejected-start-no-run";
  strategyJournal.write({ version: 1, owner, key: "11111111-1111-4111-8111-111111111111",
    configKey: "22222222-2222-4222-8222-222222222222",
    payload: { base: "BTC", timeframe: "5m", capital_per_entry: "100", max_entries: 10 } });
  const queries = setupQueries();
  const fetcher = vi.fn((path: string) => Promise.resolve(new Response(JSON.stringify(
    path.includes("/requests/by-key/") ? { pending: false, failure_code: "BOT_NOT_READY" }
      : path.endsWith("/bots/status") ? { mode: "PAPER", status: null, run_id: null, can_start: true }
      : path.endsWith("/strategy") ? { timeframes: ["5m"] } : {},
  ))));
  vi.stubGlobal("fetch", fetcher);
  render(<PaperBotPanel owner={owner} available="10000" loading={false}/>, queries);
  expect(await screen.findByRole("button", { name: bt("start") })).toBeTruthy();
  expect(strategyJournal.read(owner)).toBeNull();
  expect(fetcher.mock.calls.some(([path]) => path.includes("/requests/by-key/"))).toBe(true);
});


it("explains an active USER stop and blocks a new start before submission", async () => {
  const queries = setupQueries();
  const fetcher = vi.fn((path: string, init?: RequestInit) => Promise.resolve(new Response(JSON.stringify(
    path.endsWith("/kill-switch") ? { mode: "PAPER", active_causes: ["USER"], stop_id: "stop", progress: "STOPPED" }
      : path.endsWith("/bots/status") ? { mode: "PAPER", status: null, run_id: null, can_start: true }
      : path.endsWith("/strategy") ? { timeframes: ["5m"] } : {},
  ), { headers: { "x-test-method": init?.method ?? "GET" } })));
  vi.stubGlobal("fetch", fetcher);
  render(<PaperBotPanel owner="stopped-account-start" available="10000" loading={false}/>, queries);
  await screen.findByText(bt("accountStopped"));
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "100" } });
  const start = screen.getByRole<HTMLButtonElement>("button", { name: bt("start") });
  expect(start.disabled).toBe(true);
  expect(screen.getByRole("button", { name: bt("reviewStop") })).toBeTruthy();
  fireEvent.click(start);
  expect(fetcher.mock.calls.every(([, init]) => init?.method === "GET")).toBe(true);
});


it.each(["RUNNING", "STOPPED"])("does not flash an idle notice while reloading a %s run", async (state) => {
  const queries = setupQueries();
  let resolveStatus: ((response: Response) => void) | undefined;
  let resolveStop: ((response: Response) => void) | undefined;
  vi.stubGlobal("fetch", vi.fn((path: string) => {
    if (path.endsWith("/bots/status")) return new Promise<Response>(resolve => { resolveStatus = resolve; });
    if (path.endsWith("/kill-switch")) return new Promise<Response>(resolve => { resolveStop = resolve; });
    return Promise.resolve(new Response(JSON.stringify({ timeframes: ["5m"] })));
  }));
  render(<PaperBotPanel owner={`reload-${state}`} available="10000" loading={false}/>, queries);
  expect(screen.queryByText(bt("notice"))).toBeNull();
  expect(screen.queryByText(bt("pinnedConfig"))).toBeNull();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  await act(async () => {
    await Promise.resolve();
    resolveStop!(new Response(JSON.stringify({ mode: "PAPER", active_causes: [], stop_id: null })));
  });
  expect(screen.queryByText(bt("notice"))).toBeNull();
  await act(async () => {
    await Promise.resolve();
    resolveStatus!(new Response(JSON.stringify({ mode: "PAPER", status: state, run_id: "run", can_start: false,
      pinned_configuration: { base: "BTC", timeframe: "5m", capital_per_entry: "100", max_entries: 10 },
      exposure_available: true, positions: [], protections: [] })));
  });
  await vi.waitFor(() => expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("100"));
  expect(screen.queryByText(bt("notice"))).toBeNull();
  expect(screen.queryByText(bt("pinnedConfig"))).toBeNull();
});

it("keeps the card stop action after a running status read fails", async () => {
  const owner = "outage-running";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  let unavailable = false;
  const fetcher = vi.fn((path: string, init?: RequestInit) => {
    if (init?.method === "POST") return Promise.resolve(new Response(JSON.stringify({ request_id: "stop", state: "APPLIED" })));
    if (path.endsWith("/bots/status")) return Promise.resolve(new Response(JSON.stringify(unavailable
      ? { detail: "private upstream failure" }
      : { status: "RUNNING", run_id: "run", pinned_configuration: { base: "BTC", capital_per_entry: "100", max_entries: 10, timeframe: "5m" } }), { status: unavailable ? 503 : 200 }));
    return Promise.resolve(new Response(JSON.stringify({ active_causes: [], stop_id: null })));
  });
  vi.stubGlobal("fetch", fetcher);
  render(<PaperBotPanel owner={owner} available="10000" loading={false}/>, {
    wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  await screen.findByRole("button", { name: bt("stopBot") });
  unavailable = true;
  await act(async () => { await client.invalidateQueries({ queryKey: ["bot-status", owner, "PAPER"] }); });
  expect(await screen.findByText(bt("statusUnavailable"))).toBeTruthy();
  expect(screen.queryByText("private upstream failure")).toBeNull();
  expect(screen.queryByText(bt("RUNNING"))).toBeNull();
  const stop = screen.getByRole<HTMLButtonElement>("button", { name: bt("stopBot") });
  expect(stop.disabled).toBe(false);
  fireEvent.click(stop);
  await waitFor(() => expect(fetcher.mock.calls.some(([path, init]) => path.endsWith("/kill-switch/stop") && init?.method === "POST")).toBe(true));
  client.clear();
});

it.each(["/bots/status", "/kill-switch", "/bots/strategy"])("reports %s failure and retries without starting", async failedPath => {
  const owner = `outage-${failedPath}`;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  let unavailable = true;
  const fetcher = vi.fn((path: string) => {
    if (path.endsWith(failedPath) && unavailable) return Promise.resolve(new Response(JSON.stringify({ detail: "private read failure" }), { status: 503 }));
    const data = path.endsWith("/bots/status") ? { status: null, run_id: null, can_start: true }
      : path.endsWith("/bots/strategy") ? { timeframes: ["1m", "5m"] }
      : { active_causes: [], stop_id: null };
    return Promise.resolve(new Response(JSON.stringify(data)));
  });
  vi.stubGlobal("fetch", fetcher);
  render(<PaperBotPanel owner={owner} available="10000" loading={false}/>, {
    wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "100" } });
  expect(await screen.findByText(bt("statusUnavailable"))).toBeTruthy();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  expect(screen.queryByText("private read failure")).toBeNull();
  unavailable = false;
  fireEvent.click(screen.getByRole("button", { name: bt("retry") }));
  await waitFor(() => expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(false));
  expect(screen.queryByText(bt("statusUnavailable"))).toBeNull();
  expect(fetcher.mock.calls.every(([path]) => !path.endsWith("/bots/requests") && !path.endsWith("/bots/configurations"))).toBe(true);
  client.clear();
});

it("publishes the test choice only from the server catalogue and sends no entry-count parameter", async () => {
  const owner = "paper-test-choice";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const posts: { path: string; body: Record<string, unknown> }[] = [];
  let published = false;
  vi.stubGlobal("fetch", vi.fn((path: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      posts.push({ path, body: JSON.parse(init.body as string) as Record<string, unknown> });
      return Promise.resolve(new Response(JSON.stringify(path.endsWith("/configurations")
        ? { reference: "paper-test:22222222-2222-4222-8222-222222222222" } : { pending: true })));
    }
    if (path.includes("/requests/by-key/")) return Promise.resolve(new Response(JSON.stringify({ pending: true })));
    return Promise.resolve(new Response(JSON.stringify(path.endsWith("/bots/strategy")
      ? { timeframes: ["1m", "5m"], strategies: ["rsi-step-grid-ema-single-tp", ...(published ? ["paper-green-atr-test"] : [])] }
      : path.endsWith("/bots/status") ? { can_start: true, run_id: null, status: null }
      : { stop_id: null, active_causes: [] })));
  }));
  const ui = render(<PaperBotPanel owner={owner} available="10000" loading={false}/>, {
    wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  await waitFor(() => expect(screen.getByLabelText<HTMLSelectElement>(bt("strategy")).disabled).toBe(false));
  expect(screen.queryByRole("option", { name: "Paper Test Entry · ATR TP/SL" })).toBeNull();
  published = true;
  await act(async () => { await client.invalidateQueries({ queryKey: ["bot-strategy-catalog", owner] }); });
  await screen.findByRole("option", { name: "Paper Test Entry · ATR TP/SL" });
  fireEvent.change(screen.getByLabelText(bt("strategy")), { target: { value: "paper-green-atr-test" } });
  expect(screen.queryByLabelText(bt("maxEntries"))).toBeNull();
  fireEvent.change(screen.getByLabelText(bt("budget")), { target: { value: "100.123456789012345678" } });
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText(bt("timeframe")), { target: { value: "1m" } });
  const start = screen.getByRole<HTMLButtonElement>("button", { name: bt("start") });
  expect(start.disabled).toBe(false);
  fireEvent.click(start);
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[0]?.body).toEqual({ strategy_name: "paper-green-atr-test", base: "BTC", timeframe: "1m", capital_per_entry: "100.123456789012345678" });
  expect(posts[1]?.body.strategy_config_ref).toBe("paper-test:22222222-2222-4222-8222-222222222222");
  ui.unmount();
  render(<PaperBotPanel owner={owner} available="10000" loading={false}/>, {
    wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  });
  expect(screen.getByLabelText<HTMLSelectElement>(bt("strategy")).value).toBe("paper-green-atr-test");
  expect(screen.getByLabelText<HTMLInputElement>(bt("budget")).value).toBe("100.123456789012345678");
  expect(screen.queryByLabelText(bt("maxEntries"))).toBeNull();
  strategyJournal.clear(owner);
  client.clear();
});

it.each([
  ["PAUSED", "INDICATOR_NOT_READY", null],
  ["PAUSED", "BOT_CANDLE_NOT_READY", "awaitingData"],
  ["RUNNING", "INDICATOR_NOT_READY", null],
  ["STARTING", null, null],
] as const)("shows verified compact readiness for %s/%s below Stop", async (status, reason, message) => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
    mode: "PAPER", run_id: "run", status, readiness_reason: reason,
    pending_request_id: null, positions: [], protections: [], exposure_available: true,
  })))));
  render(<BotRunStatus owner="compact-readiness" mode="PAPER" compact/>, queries);
  const stop = await screen.findByRole("button", { name: bt("stopBot") });
  if (message) {
    const notice = screen.getByText(bt(message));
    expect(stop.compareDocumentPosition(notice) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  } else {
    expect(screen.queryByText(/Waiting for verified indicator data and complete warm-up/)).toBeNull();
    expect(screen.queryByText(bt("awaitingData"))).toBeNull();
  }
});

it.each([
  [true, "BOT_CANDLE_UNCONFIRMED"], [false, "BOT_CANDLE_UNCONFIRMED"],
  [true, "INDICATOR_NOT_READY"], [false, "INDICATOR_NOT_READY"],
] as const)("hides paused/waiting copy with compact=%s and reason=%s", async (compact, reason) => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({
    mode: "PAPER", run_id: "run", status: "PAUSED", readiness_reason: reason,
    pending_request_id: null, positions: [], protections: [], exposure_available: true,
  })))));
  render(<BotRunStatus owner="unconfirmed-reason" mode="PAPER" compact={compact}/>, queries);
  if (compact) await screen.findByRole("button", { name: bt("stopBot") });
  else await screen.findByText(bt("holdings"));
  expect(screen.queryByText(bt("PAUSED"))).toBeNull();
  expect(screen.queryByText(/Waiting for a confirmed closed candle/)).toBeNull();
  expect(screen.queryByText(/Waiting for verified indicator data and complete warm-up/)).toBeNull();
  expect(screen.queryByText(bt("awaitingData"))).toBeNull();
});

it("does not flash unconfirmed readiness before status has loaded", () => {
  const queries = setupQueries();
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
  render(<BotRunStatus owner="loading-finality" mode="PAPER" compact/>, queries);
  expect(screen.queryByText(/Waiting for a confirmed closed candle/)).toBeNull();
});
