import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiRequestError } from "../src/auth";
import { candlePage, history, live, verify, type CandlePage, type ChartLive, type Series } from "../src/chart/api";
import { useChartData } from "../src/chart/useChartData";
import { candleHistory, chartLive, chartSeries } from "./chartFixture";
vi.mock("../src/chart/api", async original => ({ ...await original<typeof import("../src/chart/api")>(),
  candlePage: vi.fn(), history: vi.fn(), live: vi.fn(), verify: vi.fn() }));
const page = (): CandlePage => ({ ...candleHistory(), display_start: "2026-07-12T00:00:00Z",
  display_end: "2026-10-12T00:00:00Z", earliest_known: true, older_before: null, newer_after: null });
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date", "performance"] });
  vi.mocked(candlePage).mockImplementation(series => Promise.resolve({ ...page(), ...series }));
  vi.mocked(live).mockImplementation(series => Promise.resolve({ ...chartLive(), ...series }));
  vi.mocked(history).mockRejectedValue(new ApiRequestError("INDICATOR_RATE_LIMITED", 429, "60"));
  vi.mocked(verify).mockRejectedValue(new ApiRequestError("INDICATOR_RATE_LIMITED", 429, "60"));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks(); });
const tick = async (ms = 10) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const wrapper = ({ children }: { children: ReactNode }) => <StrictMode><QueryClientProvider client={client}>{children}</QueryClientProvider></StrictMode>;
  const initialProps: { series: Series } = { series: chartSeries };
  return renderHook(({ series }: { series: Series }) => useChartData("one", series), { wrapper, initialProps });
}
it("reads candle-only APIs under StrictMode, TF changes, retry and resume", async () => {
  const hook = mount(); await tick();
  expect(candlePage).toHaveBeenCalledTimes(1); expect(live).toHaveBeenCalledTimes(1);
  hook.rerender({ series: { ...chartSeries, timeframe: "4h" } }); await tick();
  act(() => hook.result.current.retry()); await tick();
  act(() => { globalThis.dispatchEvent(new Event("online")); }); await tick();
  expect(history).not.toHaveBeenCalled(); expect(verify).not.toHaveBeenCalled();
  expect(hook.result.current.browsing.latest?.timeframe).toBe("4h");
});
it("polls live at two seconds and refreshes latest once per new boundary", async () => {
  const hook = mount(); await tick(); await tick(1000);
  expect(live).toHaveBeenCalledTimes(1);
  vi.mocked(live).mockResolvedValue({ ...chartLive(), history_end: null, rows: [liveCandle(0)] });
  await tick(1100); await tick(10);
  expect(candlePage).toHaveBeenCalledTimes(2);
  await tick(6000); expect(candlePage).toHaveBeenCalledTimes(2);
  expect(hook.result.current.browsing.latest).toBeDefined();
});
it("stops on candle 429 and manual retry honors cooldown", async () => {
  vi.mocked(candlePage).mockRejectedValueOnce(new ApiRequestError("CHART_RATE_LIMITED", 429, "60"));
  const hook = mount(); await tick(); const reads = vi.mocked(live).mock.calls.length;
  act(() => hook.result.current.retry()); await tick(10_000);
  expect(candlePage).toHaveBeenCalledTimes(1); expect(live).toHaveBeenCalledTimes(reads);
  await tick(60_000); act(() => hook.result.current.retry()); await tick();
  expect(candlePage).toHaveBeenCalledTimes(2); expect(hook.result.current.error).toBeFalsy();
});
it("cancels old series responses and prevents them replacing new candles", async () => {
  let complete!: (value: ChartLive) => void;
  vi.mocked(live).mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  const hook = mount(); await tick(); const signal = vi.mocked(live).mock.calls[0]![1];
  hook.rerender({ series: { ...chartSeries, timeframe: "1M" } }); await tick();
  expect(signal.aborted).toBe(true);
  await act(async () => { complete(chartLive()); await Promise.resolve(); });
  expect(hook.result.current.preview.data?.timeframe).toBe("1M");
});
it("401 cancels an in-flight page and stops polling", async () => {
  vi.mocked(candlePage).mockImplementationOnce(() => new Promise(() => undefined));
  vi.mocked(live).mockRejectedValueOnce(new ApiRequestError("AUTH_REQUIRED", 401));
  mount(); await tick(); await tick(5000);
  expect(vi.mocked(candlePage).mock.calls[0]![2].aborted).toBe(true);
  expect(live).toHaveBeenCalledTimes(1);
});

it.each([
  [429, "CHART_RATE_LIMITED"], [503, "CHART_ADMISSION_UNAVAILABLE"], [504, "CHART_DEADLINE_EXCEEDED"],
] as const)("stops automatic live work after terminal HTTP %s", async (status, code) => {
  vi.mocked(live).mockRejectedValueOnce(new ApiRequestError(code, status));
  const hook = mount(); await tick();
  await tick(30_000);
  globalThis.dispatchEvent(new Event("focus")); await tick();
  expect(live).toHaveBeenCalledTimes(1);
  expect(history).not.toHaveBeenCalled(); expect(verify).not.toHaveBeenCalled();
  act(() => hook.result.current.retry()); await tick();
  expect(live).toHaveBeenCalledTimes(2);
});

it.each(["hidden", "offline"])("cancels live reads while %s and resumes once", async transition => {
  let active = true;
  const property = transition === "hidden" ? vi.spyOn(document, "visibilityState", "get")
    .mockImplementation(() => active ? "visible" : "hidden")
    : vi.spyOn(globalThis.navigator, "onLine", "get").mockImplementation(() => active);
  try {
    vi.mocked(live).mockImplementationOnce(() => new Promise(() => undefined));
    mount(); await tick();
    const signal = vi.mocked(live).mock.calls[0]![1];
    act(() => { active = false;
      if (transition === "hidden") document.dispatchEvent(new Event("visibilitychange"));
      else globalThis.dispatchEvent(new Event("offline"));
    });
    await tick(10_000);
    expect(signal.aborted).toBe(true); expect(live).toHaveBeenCalledTimes(1);
    act(() => { active = true;
      if (transition === "hidden") document.dispatchEvent(new Event("visibilitychange"));
      else globalThis.dispatchEvent(new Event("online"));
    });
    await tick(); expect(live).toHaveBeenCalledTimes(2);
  } finally { property.mockRestore(); }
});

it("keeps Retry-After monotonic when the browser wall clock jumps", async () => {
  vi.mocked(candlePage).mockRejectedValueOnce(new ApiRequestError("CHART_RATE_LIMITED", 429, "60"));
  const hook = mount(); await tick();
  vi.setSystemTime(Date.now() + 3_600_000);
  act(() => hook.result.current.retry()); await tick(30_000);
  expect(candlePage).toHaveBeenCalledTimes(1);
  vi.setSystemTime(Date.now() - 7_200_000);
  await tick(30_001);
  act(() => hook.result.current.retry()); await tick();
  expect(candlePage).toHaveBeenCalledTimes(2);
});

it("keeps rate-limit recovery available after switching timeframe during cooldown", async () => {
  vi.mocked(candlePage).mockRejectedValueOnce(new ApiRequestError("CHART_RATE_LIMITED", 429, "60"));
  const hook = mount(); await tick();
  hook.rerender({ series: { ...chartSeries, timeframe: "1M" } }); await tick(61_000);
  expect(hook.result.current.error).toBeInstanceOf(ApiRequestError);
  expect(hook.result.current.cooldownActive).toBe(false);
  expect(candlePage).toHaveBeenCalledTimes(1);
  act(() => hook.result.current.retry()); await tick();
  expect(candlePage).toHaveBeenCalledTimes(2);
  expect(hook.result.current.browsing.latest?.timeframe).toBe("1M");
});

function liveCandle(minute: number) {
  const opened = new Date(Date.UTC(2026, 9, 12, 0, minute)).toISOString();
  const end = new Date(Date.UTC(2026, 9, 12, 0, minute + 1)).toISOString();
  return { open_at: opened, end_at: end, open: "100", high: "101", low: "99", close: "100",
    volume: "1", finality: "OPEN" as const, observed_at: opened, last_checked_at: opened };
}
it("retains observed candles across eight boundaries while REST recovery remains null", async () => {
  const hook = mount(); await tick();
  for (let minute = 0; minute < 8; minute += 1) {
    vi.mocked(live).mockResolvedValue({ ...chartLive(), history_end: null,
      server_time: liveCandle(minute).open_at, rows: [liveCandle(minute)] });
    await tick(2000); await tick();
  }
  expect(hook.result.current.preview.data?.retained).toHaveLength(8);
  expect(hook.result.current.preview.data?.retained?.[0]?.finality).toBe("UNCONFIRMED");
  expect(candlePage).toHaveBeenCalledTimes(9);
  expect(history).not.toHaveBeenCalled(); expect(verify).not.toHaveBeenCalled();
});

it("bounds retained observations and clears them when the timeframe changes", async () => {
  const hook = mount(); await tick();
  for (let minute = 0; minute < 122; minute += 1) {
    vi.mocked(live).mockResolvedValue({ ...chartLive(), history_end: null,
      server_time: liveCandle(minute).open_at, rows: [liveCandle(minute)] });
    await tick(2000);
  }
  expect(hook.result.current.preview.data?.retained).toHaveLength(120);
  vi.mocked(live).mockResolvedValue({ ...chartLive(), timeframe: "1M" });
  hook.rerender({ series: { ...chartSeries, timeframe: "1M" } }); await tick();
  expect(hook.result.current.preview.data?.retained).toEqual([]);
});
