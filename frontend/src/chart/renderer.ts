import {
  CandlestickSeries, HistogramSeries, LineSeries, createChart,
  type IChartApi, type ISeriesApi, type Time, type UTCTimestamp,
} from "lightweight-charts";
import type { Candle, Point } from "./api";

/** NC-41: the only price/quantity/indicator -> Number boundary. Never return these to data code. */
function projection(exact: string): number {
  if (!/^-?\d+(?:\.\d+)?$/.test(exact)) throw new Error("CHART_RENDER_LIMIT");
  const value = Number(exact);
  if (!Number.isFinite(value) || (value === 0 && /[1-9]/.test(exact.split(/[eE]/)[0] ?? ""))) {
    throw new Error("CHART_RENDER_LIMIT");
  }
  return value;
}
export function chartTime(iso: string): UTCTimestamp {
  return (Date.parse(iso) / 1000) as UTCTimestamp;
}
const thaiTime = (time: Time, locale: string) => typeof time === "number"
  ? new Intl.DateTimeFormat(locale, { timeZone: "Asia/Bangkok", dateStyle: "short", timeStyle: "short" })
    .format(new Date(time * 1000)) : typeof time === "string" ? time : `${time.year}-${time.month}-${time.day}`;

export type ChartRenderer = {
  chart: IChartApi;
  draw(candles: Candle[], points: Point[], enabled: Set<string>, indicatorsValid: boolean): string | null;
  remove(): void;
};
export function mountChart(element: HTMLElement, locale: string, selected: (iso: string) => void): ChartRenderer {
  const style = globalThis.getComputedStyle(element);
  const token = (name: string) => style.getPropertyValue(name).trim();
  const colors = ["--account-brand", "--app-warning-ink", "--account-muted-color",
    "--account-focus-color", "--account-line"].map(token);
  const chart = createChart(element, {
    autoSize: true, height: 580,
    layout: { attributionLogo: true, background: { color: token("--account-surface") }, textColor: token("--account-ink") },
    grid: { vertLines: { color: token("--color-gray-100") }, horzLines: { color: token("--color-gray-100") } },
    rightPriceScale: { borderColor: token("--color-gray-200") },
    crosshair: { horzLine: { labelVisible: false } },
    localization: { locale, timeFormatter: (time: Time) => thaiTime(time, locale) },
    timeScale: { timeVisible: true, tickMarkFormatter: (time: Time) => thaiTime(time, locale) },
  });
  const candlesSeries = chart.addSeries(CandlestickSeries, { priceLineVisible: false, lastValueVisible: false,
    upColor: token("--color-success-500"), downColor: token("--color-error-500"),
    wickUpColor: token("--color-success-500"), wickDownColor: token("--color-error-500"),
    borderUpColor: token("--color-success-500"), borderDownColor: token("--color-error-500") });
  const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" },
    priceLineVisible: false, lastValueVisible: false, color: token("--account-muted-color") }, 1);
  const lines: ISeriesApi<"Line">[] = [];
  let previousPoints: Point[] | undefined;
  let previousEnabled: Set<string> | undefined;
  let previousValid = false;
  const listener = (event: { time?: Time }) => {
    if (typeof event.time === "number") selected(new Date(event.time * 1000).toISOString());
  };
  chart.subscribeCrosshairMove(listener);
  return {
    chart,
    draw(candles, points, enabled, indicatorsValid) {
      const slots = new Map<string, Candle>(candles.map(candle => [candle.open_at, candle]));
      try {
        const times = [...new Set([...candles.map(row => row.open_at), ...points.map(row => row.open_at)])].sort();
        candlesSeries.setData(times.map(iso => {
          const candle = slots.get(iso), time = chartTime(iso);
          if (!candle) return { time };
          const open = projection(candle.open), high = projection(candle.high);
          const low = projection(candle.low), close = projection(candle.close);
          if (low > high || low > open || low > close || high < open || high < close) throw new Error("CHART_RENDER_LIMIT");
          return { time, open, high, low, close };
        }));
        volume.setData(times.map(iso => {
          const candle = slots.get(iso), time = chartTime(iso);
          return candle ? { time, value: projection(candle.volume) } : { time };
        }));
      } catch {
        for (const line of lines.splice(0)) chart.removeSeries(line);
        previousValid = false;
        candlesSeries.setData([]); volume.setData([]);
        return "CHART_RENDER_LIMIT";
      }
      if (previousValid === indicatorsValid && previousPoints === points && previousEnabled === enabled) return null;
      for (const line of lines.splice(0)) chart.removeSeries(line);
      previousPoints = points; previousEnabled = enabled; previousValid = indicatorsValid;
      if (!indicatorsValid) return null;
      let color = 0;
      for (const name of enabled) {
        const pane = name.startsWith("ema") ? 0 : name.startsWith("rsi") ? 2 : name.startsWith("macd") ? 3 : 4;
        // Separate segments ensure that the library never joins an indicator across unavailable slots.
        let segment: { time: UTCTimestamp; value: number }[] = [];
        const flush = () => {
          if (!segment.length) return;
          const line = chart.addSeries(LineSeries, { color: colors[color % colors.length] ?? colors[0]!,
            lineWidth: 1, lastValueVisible: false, priceLineVisible: false }, pane);
          line.setData(segment); lines.push(line); segment = [];
        };
        try {
          for (const point of points) {
            const value = point.values[name];
            if (!value || value.value === null || value.status !== "READY") { flush(); continue; }
            segment.push({ time: chartTime(point.open_at), value: projection(value.value) });
          }
          flush(); color += 1;
        } catch {
          for (const line of lines.splice(0)) chart.removeSeries(line);
          return "CHART_RENDER_LIMIT";
        }
      }
      return null;
    },
    remove() { chart.unsubscribeCrosshairMove(listener); chart.remove(); },
  };
}
