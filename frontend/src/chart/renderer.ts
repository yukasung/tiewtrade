import {
  CandlestickSeries, LineSeries, TickMarkType, createChart,
  type AutoscaleInfoProvider, type IChartApi, type ISeriesApi, type Time, type UTCTimestamp,
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
const axisTime = (time: Time, type: TickMarkType, locale: string) => {
  const date = typeof time === "number" ? new Date(time * 1000) : typeof time === "string"
    ? new Date(`${time}T00:00:00Z`) : new Date(Date.UTC(time.year, time.month - 1, time.day));
  const options: Intl.DateTimeFormatOptions = { timeZone: "Asia/Bangkok" };
  if (type === TickMarkType.Year) {
    return new Intl.DateTimeFormat(locale, { ...options, year: "2-digit" })
      .formatToParts(date).find(part => part.type === "year")?.value ?? "";
  }
  else if (type === TickMarkType.Month) { options.month = "short"; options.year = "2-digit"; }
  else if (type === TickMarkType.DayOfMonth) { options.day = "numeric"; options.month = "short"; }
  else {
    options.hour = "2-digit"; options.minute = "2-digit"; options.hourCycle = "h23";
    if (type === TickMarkType.TimeWithSeconds) options.second = "2-digit";
  }
  return new Intl.DateTimeFormat(locale, options).format(date);
};

export type ChartRenderer = {
  chart: IChartApi;
  draw(candles: Candle[], points: Point[], enabled: Set<string>, indicatorsValid: boolean): string | null;
  applyTheme(): void;
  remove(): void;
};
export function mountChart(element: HTMLElement, locale: string, selected: (iso: string | null) => void): ChartRenderer {
  const style = globalThis.getComputedStyle(element);
  const token = (name: string) => style.getPropertyValue(name).trim();
  const colors = ["--chart-indicator-1", "--chart-indicator-2", "--chart-indicator-3",
    "--chart-indicator-4", "--chart-indicator-5"].map(token);
  const chart = createChart(element, {
    autoSize: true, height: 580,
    layout: { attributionLogo: true, background: { color: token("--chart-background") }, textColor: token("--chart-text") },
    grid: { vertLines: { color: token("--chart-grid") }, horzLines: { color: token("--chart-grid") } },
    rightPriceScale: { borderColor: token("--chart-border") },
    crosshair: { horzLine: { labelVisible: false } },
    localization: { locale, timeFormatter: (time: Time) => thaiTime(time, locale) },
    timeScale: { timeVisible: true, borderColor: token("--chart-border"),
      tickMarkFormatter: (time: Time, type: TickMarkType) => axisTime(time, type, locale) },
  });
  let sparseCandles = false;
  const sparseAutoscale: AutoscaleInfoProvider = original => {
    const info = original();
    if (!sparseCandles || !info?.priceRange) return info;
    const { minValue, maxValue } = info.priceRange;
    const span = maxValue - minValue;
    const padding = span > 0 ? span * 2 : Math.max(Math.abs(maxValue), 1) * 0.001;
    return { ...info, priceRange: { minValue: minValue - padding, maxValue: maxValue + padding } };
  };
  const candlesSeries = chart.addSeries(CandlestickSeries, { priceLineVisible: true, lastValueVisible: true,
    priceLineColor: token("--chart-price-line"),
    autoscaleInfoProvider: sparseAutoscale,
    upColor: token("--chart-up"), downColor: token("--chart-down"),
    wickUpColor: token("--chart-up"), wickDownColor: token("--chart-down"),
    borderUpColor: token("--chart-up"), borderDownColor: token("--chart-down") });
  const lines: ISeriesApi<"Line">[] = [];
  let previousPoints: Point[] | undefined;
  let previousEnabled: Set<string> | undefined;
  let previousValid = false;
  const listener = (event: { time?: Time }) => {
    selected(typeof event.time === "number" ? new Date(event.time * 1000).toISOString() : null);
  };
  chart.subscribeCrosshairMove(listener);
  return {
    chart,
    applyTheme() {
      chart.applyOptions({
        layout: { background: { color: token("--chart-background") }, textColor: token("--chart-text") },
        grid: { vertLines: { color: token("--chart-grid") }, horzLines: { color: token("--chart-grid") } },
        rightPriceScale: { borderColor: token("--chart-border") },
        timeScale: { borderColor: token("--chart-border") },
      });
      candlesSeries.applyOptions({ priceLineColor: token("--chart-price-line"),
        upColor: token("--chart-up"), downColor: token("--chart-down"),
        wickUpColor: token("--chart-up"), wickDownColor: token("--chart-down"),
        borderUpColor: token("--chart-up"), borderDownColor: token("--chart-down") });
    },
    draw(candles, points, enabled, indicatorsValid) {
      sparseCandles = candles.length < 10;
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
      } catch {
        for (const line of lines.splice(0)) chart.removeSeries(line);
        previousValid = false;
        candlesSeries.setData([]);
        return "CHART_RENDER_LIMIT";
      }
      if (previousValid === indicatorsValid && previousPoints === points && previousEnabled === enabled) return null;
      for (const line of lines.splice(0)) chart.removeSeries(line);
      previousPoints = points; previousEnabled = enabled; previousValid = indicatorsValid;
      if (!indicatorsValid) return null;
      let color = 0;
      for (const name of enabled) {
        const pane = name.startsWith("ema") ? 0 : name.startsWith("rsi") ? 1 : 2;
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
