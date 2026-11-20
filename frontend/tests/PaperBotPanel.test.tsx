import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BotRunStatus } from "../src/BotRunStatus";
import { PaperBotPanel } from "../src/PaperBotPanel";
import { paperBotText as bt } from "../src/paperBotMessages";
import { manualOrderText as t } from "../src/manualOrderMessages";
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
it("keeps the budget as a local string, never submits and keeps start disabled", () => {
  const queries = setupQueries();
  const view = render(<PaperBotPanel owner="owner-a" available="10000.000000000000000001" loading={false}/>, queries);
  expect(screen.getByRole<HTMLOptionElement>("option").selected).toBe(true);
  const input = screen.getByLabelText(bt("budget"));
  fireEvent.change(input, { target: { value: "123.450000000000000001" } });
  fireEvent.keyDown(input, { key: "Enter" }); fireEvent.click(screen.getByRole("button", { name: bt("start") }));
  fireEvent(window, new Event("resize"));
  view.rerender(<PaperBotPanel owner="owner-a" available={null} loading/>);
  expect((input as HTMLInputElement).value).toBe("123.450000000000000001");
  expect(screen.getByRole<HTMLButtonElement>("button", { name: bt("start") }).disabled).toBe(true);
  expect(view.container.querySelector("form")).toBeNull(); expect(vi.mocked(fetch).mock.calls.every(([path, init]) =>
    path === "/api/paper/bots/status" && init?.method === "GET"
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
