import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PlatformKillSwitchPanel } from "../src/PlatformKillSwitchPanel";
import { killSwitchText as t } from "../src/killSwitchMessages";
import type { PlatformStopStatus } from "../src/killSwitch";

const status: PlatformStopStatus = {
  stop_id: "stop", revision: 1, summary_revision: 1, reconciliation_revision: 1,
  reason: "maintenance", progress: "PROBLEMS", discovery_complete: false,
  owner_count: 3, pending_count: 2, failed_count: 1, can_resume: false,
};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear(); });

it.each([false, true])("does not invent zero counts before the status read (failure=%s)", async failure => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(done => { resolve = done; })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<QueryClientProvider client={client}><PlatformKillSwitchPanel owner="owner" role="PLATFORM_OWNER"/></QueryClientProvider>);
  expect(screen.getByRole("status").textContent).toBe(t("loading"));
  expect(screen.queryByText(new RegExp(`${t("pending")}:`))).toBeNull();
  expect(screen.getByRole<HTMLButtonElement>("button", { name: t("platformResume") }).disabled).toBe(true);
  await waitFor(() => expect(resolve).toBeTypeOf("function"));
  await act(async () => { resolve(new Response(JSON.stringify(failure ? { detail: "TRADING_STOP_UNAVAILABLE" } : status), { status: failure ? 503 : 200 })); await Promise.resolve(); });
  if (failure) {
    expect((await screen.findByRole("alert")).textContent).toBe(t("loadError"));
    expect(screen.queryByText(new RegExp(`${t("pending")}:`))).toBeNull();
  } else {
    expect(await screen.findByText(`PROBLEMS · ${t("pending")}: 2 · ${t("failed")}: 1`)).toBeTruthy();
  }
  expect(screen.queryByText(t("loading"))).toBeNull();
  client.clear();
});
