import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { candlePage, type CandlePage } from "../src/chart/api";
import { useChartPages } from "../src/chart/useChartPages";
import { candleHistory, chartSeries } from "./chartFixture";
import { ApiRequestError } from "../src/auth";

vi.mock("../src/chart/api", () => ({ candlePage: vi.fn() }));
const page = (index = 0): CandlePage => ({ ...candleHistory(), display_start: "2026-07-14T00:00:00Z",
  display_end: "2026-10-14T00:00:00Z", earliest_known: true,
  older_before: `2026-10-${String(12-index).padStart(2,"0")}T00:00:00Z`, newer_after: null });
beforeEach(() => { vi.useFakeTimers(); vi.mocked(candlePage).mockResolvedValue(page()); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks(); });
const tick = async () => { await act(async () => { await vi.advanceTimersByTimeAsync(10); }); };

it("cancels a previous user's page and rejects its late result", async () => {
  let complete!: (value: CandlePage) => void;
  vi.mocked(candlePage).mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  const hook = renderHook(({ user }) => useChartPages(user, chartSeries), { initialProps: { user: "one" } });
  await tick(); const signal = vi.mocked(candlePage).mock.calls[0]![2];
  hook.rerender({ user: "two" }); await tick();
  expect(signal.aborted).toBe(true);
  await act(async () => { complete({ ...page(), earliest_known: false }); await Promise.resolve(); });
  expect(hook.result.current.latest?.earliest_known).toBe(true);
});

it("deduplicates pending page requests and reuses a bounded page cache", async () => {
  const hook = renderHook(() => useChartPages("one", chartSeries)); await tick();
  let complete!: (value: CandlePage) => void;
  vi.mocked(candlePage).mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
  act(() => { hook.result.current.navigate("older"); hook.result.current.navigate("older"); });
  expect(candlePage).toHaveBeenCalledTimes(2);
  await act(async () => { complete(page()); await Promise.resolve(); });
  act(() => hook.result.current.reset());
  act(() => hook.result.current.navigate("older"));
  expect(candlePage).toHaveBeenCalledTimes(2);
});

it("stops on 429 and enforces cooldown for manual retry", async () => {
  vi.mocked(candlePage).mockRejectedValueOnce(new ApiRequestError("CHART_RATE_LIMITED", 429, "60"));
  const hook = renderHook(() => useChartPages("one", chartSeries)); await tick();
  act(() => hook.result.current.retry()); await tick();
  expect(candlePage).toHaveBeenCalledTimes(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  act(() => hook.result.current.retry()); await tick();
  expect(candlePage).toHaveBeenCalledTimes(2);
});
it("refetches evicted history after navigating beyond five cached pages", async () => {
  vi.mocked(candlePage).mockImplementation(() => Promise.resolve(page(vi.mocked(candlePage).mock.calls.length)));
  const hook = renderHook(() => useChartPages("one", chartSeries)); await tick();
  for (let index = 0; index < 6; index += 1) {
    act(() => hook.result.current.navigate("older")); await tick();
  }
  expect(candlePage).toHaveBeenCalledTimes(7);
  act(() => hook.result.current.reset());
  act(() => hook.result.current.navigate("older")); await tick();
  expect(candlePage).toHaveBeenCalledTimes(8);
});
