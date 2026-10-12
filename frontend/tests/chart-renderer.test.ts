import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mountChart } from "../src/chart/renderer";
import type { Candle, Point } from "../src/chart/api";

type Datum = { time: number; value?: number; open?: number; close?: number };
type Setter = (rows: Datum[]) => void;
const plots = vi.hoisted(() => {
  const series: { setData: ReturnType<typeof vi.fn<Setter>> }[] = [];
  const chart = {
    addSeries: vi.fn(() => { const plot = { setData: vi.fn<Setter>() }; series.push(plot); return plot; }),
    removeSeries: vi.fn(), subscribeCrosshairMove: vi.fn(), unsubscribeCrosshairMove: vi.fn(), remove: vi.fn(),
  };
  return { series, chart };
});
vi.mock("lightweight-charts", () => ({ createChart: () => plots.chart,
  CandlestickSeries: "candle", HistogramSeries: "volume", LineSeries: "line" }));
beforeEach(() => { plots.series.length = 0; vi.clearAllMocks(); });
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
  expect(plots.series[1]?.setData.mock.calls[0]?.[0][0]).toMatchObject({ value: 0 });
});

it("uses whitespace for absent OHLC and never joins indicators across a gap or warm-up", () => {
  const points = [point(0), point(1, "GAP"), point(2), point(3, "WARM_UP"), point(4)];
  expect(renderer().draw([candle()], points, new Set(["ema20"]), true)).toBeNull();
  expect(plots.series[0]?.setData.mock.calls[0]?.[0][1]).toEqual({ time: Date.parse(points[1]!.open_at) / 1000 });
  expect(plots.series[1]?.setData.mock.calls[0]?.[0][1]).not.toHaveProperty("value");
  const lineData = plots.series.slice(2).map(plot => plot.setData.mock.calls[0]?.[0]);
  expect(lineData).toHaveLength(3);
  expect(lineData.every(segment => segment?.length === 1)).toBe(true);
});

it.each(["0." + "0".repeat(400) + "1", "9".repeat(400), "NaN"])(
  "reports an unrenderable quantity without changing its exact source", amount => {
    const row = candle(amount);
    expect(renderer().draw([row], [], new Set(), false)).toBe("CHART_RENDER_LIMIT");
    expect(row.volume).toBe(amount);
    expect(plots.series[0]?.setData.mock.calls.at(-1)?.[0]).toEqual([]);
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
