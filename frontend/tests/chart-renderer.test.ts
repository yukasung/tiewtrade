import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mountChart } from "../src/chart/renderer";
import type { Candle, Point } from "../src/chart/api";
import { TickMarkType, type AutoscaleInfoProvider, type Time, type UTCTimestamp } from "lightweight-charts";

type Datum = { time: number; value?: number; open?: number; close?: number };
type Setter = (rows: Datum[]) => void;
type ChartConfig = { layout?: { attributionLogo?: boolean }; timeScale?: {
  tickMarkFormatter?: (time: Time, type: TickMarkType, locale: string) => string | null;
} };
const plots = vi.hoisted(() => {
  const series: { setData: ReturnType<typeof vi.fn<Setter>>; applyOptions: ReturnType<typeof vi.fn> }[] = [];
  const added: { kind: string; pane: number | undefined }[] = [];
  const seriesOptions: unknown[] = [];
  const chart = {
    addSeries: vi.fn((kind: string, options: unknown, pane?: number) => {
      const plot = { setData: vi.fn<Setter>(), applyOptions: vi.fn() };
      series.push(plot); added.push({ kind, pane }); seriesOptions.push(options); return plot;
    }),
    removeSeries: vi.fn(), subscribeCrosshairMove: vi.fn(), unsubscribeCrosshairMove: vi.fn(), remove: vi.fn(),
    applyOptions: vi.fn(),
  };
  const createChart = vi.fn((element: HTMLElement, options: ChartConfig) => {
    void element;
    void options;
    return chart;
  });
  return { series, added, seriesOptions, chart, createChart };
});
vi.mock("lightweight-charts", () => ({ createChart: plots.createChart,
  CandlestickSeries: "candle", LineSeries: "line",
  TickMarkType: { Year: 0, Month: 1, DayOfMonth: 2, Time: 3, TimeWithSeconds: 4 } }));
beforeEach(() => { plots.series.length = 0; plots.added.length = 0; plots.seriesOptions.length = 0; vi.clearAllMocks(); });
afterEach(() => { document.body.replaceChildren(); });

const candle = (volume = "0"): Candle => ({
  open_at: "2026-10-12T00:00:00Z", end_at: "2026-10-12T01:00:00Z",
  open: "100.000000000000000001", high: "101.000000000000000001",
  low: "99.000000000000000001", close: "100.500000000000000001", volume,
  finality: "UNCONFIRMED", observed_at: "2026-10-12T01:00:00Z", last_checked_at: "2026-10-12T01:00:00Z",
});
const point = (hour: number, status = "READY" as "READY" | "GAP" | "WARM_UP"): Point => ({
  open_at: `2026-10-12T0${String(hour)}:00:00Z`,
  finality: status === "GAP" ? null : "UNCONFIRMED", seed_open_at: null,
  values: { ema20: { value: status === "READY" ? "100.500000000000000001" : null, unit: "USDT", status } },
});
function renderer() {
  const host = document.createElement("div"); document.body.append(host);
  return mountChart(host, "th", vi.fn());
}

it("projects only inside the renderer and preserves every exact source string", () => {
  const candles = [candle()], points = [point(0)], before = JSON.stringify({ candles, points });
  expect(renderer().draw(candles, points, new Set(["ema20"]), true)).toBeNull();
  expect(JSON.stringify({ candles, points })).toBe(before);
  expect(plots.series[0]?.setData.mock.calls[0]?.[0][0]).toMatchObject({ open: 100, close: 100.5 });
  expect(plots.added.map(({ kind }) => kind)).toEqual(["candle", "line"]);
});

it("keeps the built-in TradingView attribution link enabled", () => {
  renderer();
  const options = plots.createChart.mock.calls[0]?.[1];
  expect(options?.layout?.attributionLogo).toBe(true);
});

it("applies changed theme tokens without rebuilding chart data", () => {
  const host = document.createElement("div");
  host.style.setProperty("--chart-background", "#101828");
  host.style.setProperty("--chart-text", "#98a2b3");
  host.style.setProperty("--chart-grid", "#1d2939");
  host.style.setProperty("--chart-border", "#344054");
  host.style.setProperty("--chart-price-line", "#089981");
  host.style.setProperty("--chart-up", "#089981");
  host.style.setProperty("--chart-down", "#f23645");
  document.body.append(host);
  const view = mountChart(host, "th", vi.fn());
  view.applyTheme();
  expect(plots.chart.applyOptions).toHaveBeenLastCalledWith(expect.objectContaining({
    layout: { background: { color: "#101828" }, textColor: "#98a2b3" },
  }));
  expect(plots.series[0]?.applyOptions).toHaveBeenCalledOnce();
});

it("uses short Bangkok axis labels while keeping day boundaries readable", () => {
  renderer();
  const format = plots.createChart.mock.calls[0]?.[1].timeScale?.tickMarkFormatter;
  const midnightBangkok = (Date.parse("2026-10-12T17:00:00Z") / 1000) as UTCTimestamp;
  expect(format?.(midnightBangkok, TickMarkType.Time, "th")).toBe("00:00");
  expect(format?.(midnightBangkok, TickMarkType.DayOfMonth, "th")).toMatch(/13.*ต\.ค\./);
  expect(format?.(midnightBangkok, TickMarkType.Month, "th")?.length).toBeLessThan(12);
  expect(format?.(midnightBangkok, TickMarkType.Year, "th")).toBe("69");
});

it("returns to the latest candle when the crosshair leaves a candle", () => {
  const selected = vi.fn();
  const host = document.createElement("div");
  document.body.append(host);
  mountChart(host, "th", selected);
  const onMove = plots.chart.subscribeCrosshairMove.mock.calls[0]?.[0] as
    | ((event: { time?: number }) => void) | undefined;
  const time = Date.parse("2026-10-12T00:00:00Z") / 1000;
  onMove?.({ time });
  expect(selected).toHaveBeenLastCalledWith("2026-10-12T00:00:00.000Z");
  onMove?.({});
  expect(selected).toHaveBeenLastCalledWith(null);
});

it("shows the latest candle on the price axis without changing the exact source", () => {
  const row = candle();
  renderer().draw([row], [], new Set(), false);
  expect(plots.seriesOptions[0]).toMatchObject({ priceLineVisible: true, lastValueVisible: true });
  expect(row.close).toBe("100.500000000000000001");
});

it("pads the price scale while only sparse live candles are available", () => {
  const view = renderer();
  view.draw([candle()], [], new Set(), false);
  const options = plots.seriesOptions[0] as { autoscaleInfoProvider?: AutoscaleInfoProvider };
  expect(options.autoscaleInfoProvider?.(() => ({
    priceRange: { minValue: 100, maxValue: 110 },
  }))).toEqual({ priceRange: { minValue: 80, maxValue: 130 } });
});

it("uses whitespace for absent OHLC and never joins indicators across a gap or warm-up", () => {
  const points = [point(0), point(1, "GAP"), point(2), point(3, "WARM_UP"), point(4)];
  expect(renderer().draw([candle()], points, new Set(["ema20"]), true)).toBeNull();
  expect(plots.series[0]?.setData.mock.calls[0]?.[0][1]).toEqual({ time: Date.parse(points[1]!.open_at) / 1000 });
  const lineData = plots.series.slice(1).map(plot => plot.setData.mock.calls[0]?.[0]);
  expect(lineData).toHaveLength(3);
  expect(lineData.every(segment => segment?.length === 1)).toBe(true);
});

it.each(["0." + "0".repeat(400) + "1", "9".repeat(400), "NaN"])(
  "reports an unrenderable price without changing its exact source", amount => {
    const row = { ...candle(), open: amount };
    expect(renderer().draw([row], [], new Set(), false)).toBe("CHART_RENDER_LIMIT");
    expect(row.open).toBe(amount);
    expect(plots.series[0]?.setData.mock.calls.at(-1)?.[0]).toEqual([]);
  });

it("does not project volume into a chart series", () => {
  const row = candle("9".repeat(400));
  expect(renderer().draw([row], [], new Set(), false)).toBeNull();
  expect(row.volume).toBe("9".repeat(400));
  expect(plots.added).toEqual([{ kind: "candle", pane: undefined }]);
});

it("removes unverified lines and closes the library subscriptions on teardown", () => {
  const view = renderer(), points = [point(0)], enabled = new Set(["ema20"]);
  view.draw([candle()], points, enabled, true);
  view.draw([candle()], points, enabled, false);
  expect(plots.chart.removeSeries).toHaveBeenCalledTimes(1);
  view.remove();
  expect(plots.chart.unsubscribeCrosshairMove).toHaveBeenCalledOnce();
  expect(plots.chart.remove).toHaveBeenCalledOnce();
});
