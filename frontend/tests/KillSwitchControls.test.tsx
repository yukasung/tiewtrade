import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { KillSwitchBanner, KillSwitchControls } from "../src/KillSwitchControls";
import { killSwitchText as t } from "../src/killSwitchMessages";
import { riskText } from "../src/riskLimitMessages";
import type { StopStatus } from "../src/killSwitch";

const status = (mode: "PAPER" | "LIVE", stop: string | null = null): StopStatus => ({
  active_causes: stop ? ["USER"] : [],
  mode, stop_id: stop, cause: stop ? "USER" : null, generation: stop ? 1 : null, revision: stop ? 1 : 0, summary_revision: 0,
  progress: stop ? "STOPPED" : null, target_set_complete: mode === "PAPER" && stop !== null,
  target_count: 0, pending_count: 0, failed_count: 0, platform_stop_id: null,
  platform_reason: null, resume_ready: mode === "PAPER" && stop !== null,
  reconciliation_revision: stop ? 0 : null,
  capability: mode === "PAPER" ? "AVAILABLE" : "LIVE_EXECUTION_UNAVAILABLE",
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear(); });

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
  render(<QueryClientProvider client={client}><KillSwitchControls owner="owner"/></QueryClientProvider>);
  expect(await screen.findByRole("button", { name: t("paperStop") })).toBeTruthy();
  expect(screen.getByRole("button", { name: t("liveStop") })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("paperStop") }));
  expect((await screen.findByRole("alert")).textContent).toContain(t("requestFailed"));
  const saved = window.localStorage.getItem("tiewtrade.kill-switch.stop.v1:owner:PAPER");
  expect(saved).toBe("11111111-1111-4111-8111-111111111111");
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
  render(<QueryClientProvider client={client}><KillSwitchControls owner="owner"/></QueryClientProvider>);

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
  render(<QueryClientProvider client={client}><KillSwitchControls owner="owner"/></QueryClientProvider>);

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
