import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiRequestError, send } from "../src/auth";
import { candles, history, live, verify, type Series, type Window } from "../src/chart/api";
import { useChartData } from "../src/chart/useChartData";
import { candleHistory, chartLive, chartPage, chartSeries } from "./chartFixture";

vi.mock("../src/chart/api", async (original) => ({
  ...await original<typeof import("../src/chart/api")>(),
  candles: vi.fn(), history: vi.fn(), live: vi.fn(), verify: vi.fn(),
}));
vi.mock("../src/auth", async (original) => ({
  ...await original<typeof import("../src/auth")>(), send: vi.fn(),
}));

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date", "performance"] });
  vi.mocked(history).mockImplementation(parameters => Promise.resolve({ ...chartPage(),
    ...("base" in parameters ? { base: parameters.base, quote: parameters.quote, timeframe: parameters.timeframe } : {}) }));
  vi.mocked(live).mockResolvedValue(chartLive());
  vi.mocked(candles).mockResolvedValue(candleHistory());
  vi.mocked(verify).mockResolvedValue({ status: "MATCHED", checked_at: chartPage().as_of });
});
afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.resetAllMocks(); vi.restoreAllMocks();
});

async function tick(milliseconds = 0) {
  await act(async () => { await vi.advanceTimersByTimeAsync(milliseconds); });
}

function mount(strict = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const wrapper = ({ children }: { children: ReactNode }) => {
    const content = <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    return strict ? <StrictMode>{content}</StrictMode> : content;
  };
  const initialProps: { series: Series; window?: Window } = { series: chartSeries };
  return { client, ...renderHook(({ series, window }: typeof initialProps) => useChartData("user", series, window), { wrapper, initialProps }) };
}

it("StrictMode starts one read and never polls live sooner than two seconds", async () => {
  mount(true);
  await tick(2010);
  expect(history).toHaveBeenCalledTimes(1);
  expect(live).toHaveBeenCalledTimes(1);
  await tick(1000);
  expect(live).toHaveBeenCalledTimes(1);
  await tick(1000);
  expect(live).toHaveBeenCalledTimes(2);
});

it("starts provisional and coherent history immediately without duplicate StrictMode calls", async () => {
  const hook = mount(true);
  await tick(10);
  expect(candles).toHaveBeenCalledTimes(1);
  expect(history).toHaveBeenCalledTimes(1);
  expect(hook.result.current.provisional.data?.coverage).toBe("INCOMPLETE");
  await tick(2010);
  expect(history).toHaveBeenCalledTimes(1);
});

it("allows coherent history to finish after candle-only failure", async () => {
  vi.mocked(candles).mockRejectedValue(new Error("candle-only unavailable"));
  const hook = mount();
  await tick(2010);
  expect(hook.result.current.provisional.error).toBeTruthy();
  expect(hook.result.current.query.data?.pages[0]?.dataset_revision).toBe("a");
  expect(hook.result.current.stopped).toBe(false);
});

it("cancels candle-only reads on series change and ignores their late result", async () => {
  let finish!: (value: ReturnType<typeof candleHistory>) => void;
  vi.mocked(candles).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }))
    .mockResolvedValueOnce({ ...candleHistory(), base: "ETH" });
  const hook = mount();
  await tick(10);
  const oldSignal = vi.mocked(candles).mock.calls[0]![2];
  hook.rerender({ series: { ...chartSeries, base: "ETH" } });
  await tick(10);
  expect(oldSignal.aborted).toBe(true);
  await act(async () => { finish(candleHistory()); await Promise.resolve(); });
  expect(hook.result.current.provisional.data?.base).toBe("ETH");
  hook.unmount();
  await tick(10);
  expect(hook.client.getQueryCache().getAll()).toHaveLength(0);
});

it.each([new ApiRequestError("INDICATOR_NUMERIC_ERROR", 422),
  new ApiRequestError("INDICATOR_DEADLINE_EXCEEDED", 504)])(
  "terminal history errors retain the initial live snapshot and stop automatic work", async error => {
    vi.mocked(history).mockRejectedValue(error);
    const hook = mount();
    await tick(2010);
    const calls = vi.mocked(live).mock.calls.length;
    await tick(60_000);
    expect(live).toHaveBeenCalledTimes(calls);
    expect(history).toHaveBeenCalledTimes(1);
    expect(verify).not.toHaveBeenCalled();
    expect(hook.result.current.preview.data?.status).toBe("NO_DATA");
    expect(hook.result.current.valid).toBe(false);
  });

it("enables manual retry after Retry-After despite a backward wall-clock change", async () => {
  vi.mocked(history)
    .mockImplementationOnce(() => {
      throw new ApiRequestError("INDICATOR_RATE_LIMITED", 429, "1");
    })
    .mockResolvedValue(chartPage("retried"));
  const hook = mount();
  await tick(10);
  expect(history).toHaveBeenCalledTimes(1);
  expect(hook.result.current.stopped).toBe(true);
  expect(hook.result.current.cooldownActive).toBe(true);

  act(() => hook.result.current.retry());
  expect(history).toHaveBeenCalledTimes(1);
  vi.setSystemTime(new Date(Date.now() - 60_000));
  await tick(1001);
  expect(history).toHaveBeenCalledTimes(1);
  expect(hook.result.current.cooldownActive).toBe(false);

  act(() => hook.result.current.retry());
  await tick(2010);
  expect(history).toHaveBeenCalledTimes(2);
  expect(hook.result.current.query.data?.pages[0]?.dataset_revision).toBe("retried");
});

it("recovers busy history while keeping the same active read", async () => {
  vi.mocked(history).mockImplementationOnce(() => Promise.reject(new ApiRequestError("INDICATOR_BUSY", 503, "3")))
    .mockResolvedValueOnce(chartPage("recovered"));
  const hook = mount();
  await tick(10);
  expect(hook.result.current.stopped).toBe(false);
  expect(hook.result.current.query.isFetching).toBe(true);
  await tick(2900);
  expect(history).toHaveBeenCalledTimes(1);
  await tick(200);
  expect(history).toHaveBeenCalledTimes(2);
  expect(hook.result.current.query.data?.pages[0]?.dataset_revision).toBe("recovered");
});

it("failed admission cancels a readiness wait and stops proof polling", async () => {
  vi.mocked(history).mockRejectedValue(new ApiRequestError("INDICATOR_DATA_NOT_READY", 503));
  vi.mocked(live).mockRejectedValue(new ApiRequestError("CHART_ADMISSION_UNAVAILABLE", 503));
  mount();
  await tick(2010);
  await tick(60_000);
  expect(history).toHaveBeenCalledTimes(1);
  expect(live).toHaveBeenCalledTimes(1);
  expect(verify).not.toHaveBeenCalled();
});

it("switching series aborts the old read and rejects a late response", async () => {
  let resolve!: (value: ReturnType<typeof chartPage>) => void;
  vi.mocked(history).mockImplementationOnce(() => new Promise(done => { resolve = done; }));
  const hook = mount();
  await tick(2010);
  const signal = vi.mocked(history).mock.calls[0]![1];
  hook.rerender({ series: { ...chartSeries, base: "ETH" } });
  await tick(1000);
  expect(history).toHaveBeenCalledTimes(1);
  hook.rerender({ series: { ...chartSeries, base: "SOL" } });
  await tick(990);
  expect(history).toHaveBeenCalledTimes(1);
  await tick(2010);
  expect(signal.aborted).toBe(true);
  await act(async () => { resolve(chartPage("old")); await Promise.resolve(); });
  await tick(2010);
  expect(hook.result.current.query.data?.pages[0]?.dataset_revision).toBe("a");
  hook.unmount();
  await tick(2010);
  expect(hook.client.getQueryCache().getAll()).toHaveLength(0);
});

it("switches immediately when the previous history and proof are idle", async () => {
  const hook = mount();
  await tick(10);
  expect(history).toHaveBeenCalledTimes(1);
  hook.rerender({ series: { ...chartSeries, base: "ETH" } });
  await tick(10);
  expect(history).toHaveBeenCalledTimes(2);
});

it("hidden pages cancel work and retain no valid freshness claim", async () => {
  const hook = mount();
  await tick(2010);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  act(() => { document.dispatchEvent(new Event("visibilitychange")); });
  await tick(2010);
  const calls = vi.mocked(live).mock.calls.length;
  await tick(60_000);
  expect(live).toHaveBeenCalledTimes(calls);
  expect(hook.result.current.valid).toBe(false);
});

it("refresh polls use a bodyless GET and stop after failure", async () => {
  const page = chartPage();
  page.refresh = { ...page.refresh, required: true,
    target: { ...chartSeries, start: page.result_start, end: page.result_end } };
  vi.mocked(history).mockResolvedValue(page);
  vi.mocked(send).mockResolvedValueOnce({ accepted: true }).mockResolvedValueOnce({ status: "FAILED" });
  const hook = mount();
  await tick(2010);
  let work!: Promise<void>;
  act(() => { work = hook.result.current.refresh(); });
  const rejected = expect(work).rejects.toMatchObject({ message: "CHART_DELIVERY_FAILED" });
  await tick(10_000);
  await rejected;
  await tick(2010);
  expect(vi.mocked(send).mock.calls[1]?.[1]).toBeUndefined();
  expect(vi.mocked(send).mock.calls[1]?.[3]).toBe("GET");
  const calls = vi.mocked(live).mock.calls.length;
  await tick(60_000);
  expect(live).toHaveBeenCalledTimes(calls);
  expect(hook.result.current.valid).toBe(false);
});

it.each([false, true])("successful refresh %s reads a new bundle once", async accepted => {
  const page = chartPage();
  page.refresh = { ...page.refresh, required: true,
    target: { ...chartSeries, start: page.result_start, end: page.result_end } };
  vi.mocked(history).mockResolvedValueOnce(page).mockResolvedValue(chartPage("updated"));
  vi.mocked(send).mockResolvedValueOnce({ accepted }).mockResolvedValue({ status: "COMPLETE" });
  const hook = mount();
  await tick(2010);
  let work!: Promise<void>;
  act(() => { work = hook.result.current.refresh(); });
  await tick(accepted ? 10_010 : 10);
  await work;
  await tick(2010);
  expect(history).toHaveBeenCalledTimes(2);
  expect(hook.result.current.query.data?.pages[0]?.dataset_revision).toBe("updated");
});

it("hiding an older window cancels that window's active request", async () => {
  const hook = mount();
  await tick(2010);
  vi.mocked(history).mockImplementationOnce(() => new Promise(() => undefined));
  hook.rerender({ series: chartSeries, window: { start: "2026-09-01T00:00:00Z", end: "2026-09-02T00:00:00Z" } });
  await tick(2010);
  const signal = vi.mocked(history).mock.calls.at(-1)![1];
  expect(signal.aborted).toBe(false);
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  act(() => { document.dispatchEvent(new Event("visibilitychange")); });
  await tick(10);
  expect(signal.aborted).toBe(true);
});

it("a cancelled proof from an old series cannot renew the current proof TTL", async () => {
  let reply!: (value: Awaited<ReturnType<typeof verify>>) => void;
  vi.mocked(verify).mockImplementationOnce(() => new Promise(resolve => { reply = resolve; }));
  const hook = mount();
  await tick(2010);
  await tick(15_000);
  expect(verify).toHaveBeenCalledOnce();
  hook.rerender({ series: { ...chartSeries, base: "ETH" } });
  await tick(2010);
  expect(vi.mocked(verify).mock.calls[0]![1].aborted).toBe(true);
  await tick(10);
  await act(async () => { reply({ status: "MATCHED", checked_at: chartPage().as_of }); await Promise.resolve(); });
  vi.spyOn(globalThis.performance, "now").mockReturnValue(globalThis.performance.now() + 44_995);
  hook.rerender({ series: { ...chartSeries, base: "ETH" } });
  expect(hook.result.current.valid).toBe(false);
});
