import { useEffect, useMemo, useRef, useState } from "react";
import { ApiRequestError } from "./auth";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { Select } from "./components/ui/Select";
import { ComponentCard } from "./components/ui/ComponentCard";
import { chartI18n } from "./chartMessages";
import { mountChart, type ChartRenderer } from "./chart/renderer";
import { useChartData } from "./chart/useChartData";
import type { Series, Timeframe } from "./chart/api";
import "./CandlestickChartPanel.css";

const pairs = ["BTC", "ETH", "SOL", "XRP", "DOGE"];
const timeframes: Timeframe[] = ["1m", "5m", "15m", "1h", "4h", "1d"];
const noIndicators = new Set<string>();
const chartLocale = "th";
const t = chartI18n.getFixedT(chartLocale);
const ohlcvLabels = { open: "O", high: "H", low: "L", close: "C", volume: "V" } as const;
const initialVisibleSlots = 100, initialRightOffset = 5;
const initialViewport = (slotCount: number) => ({
  from: slotCount - initialVisibleSlots,
  to: slotCount - 1 + initialRightOffset,
});
const belongsToSeries = (value: Series | undefined, series: Series) => Boolean(value &&
  value.base === series.base && value.quote === series.quote && value.timeframe === series.timeframe);

export function CandlestickChartPanel({ userId }: { userId: string }) {
  const [base, setBase] = useState("BTC");
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [selected, setSelected] = useState<number | null>(null);
  const [renderLimit, setRenderLimit] = useState<string | null>(null);
  const host = useRef<HTMLDivElement>(null), renderer = useRef<ChartRenderer>();
  const historyViewportInitialized = useRef(false);
  const series: Series = { base, quote: "USDT", timeframe };
  const state = useChartData(userId, series);
  const pages = useMemo(() => state.query.data?.pages.filter(page => belongsToSeries(page, series)) ?? [],
    [state.query.data, base, timeframe]);
  const first = pages[0];
  const provisional = belongsToSeries(state.provisional?.data, series) ? state.provisional.data : undefined;
  const preview = belongsToSeries(state.preview.data, series) ? state.preview.data : undefined;
  const rows = useMemo(() => pages.length ? pages.flatMap(page => page.candles) : provisional?.rows ?? [],
    [pages, provisional]);
  const points = useMemo(() => pages.flatMap(page => page.rows), [pages]);
  const liveRows = preview?.rows ?? [];
  const displayed = useMemo(() => {
    if (first) return [...rows, ...liveRows.filter(row => row.open_at >= first.calculation_end)]
      .sort((a, b) => Date.parse(a.open_at) - Date.parse(b.open_at));
    const merged = new Map(rows.map(row => [row.open_at, row]));
    for (const row of liveRows) merged.set(row.open_at, row);
    return [...merged.values()].sort((a, b) => Date.parse(a.open_at) - Date.parse(b.open_at));
  }, [rows, liveRows, first]);
  const selectionTimes = useMemo(() => [...new Set([...points.map(point => Date.parse(point.open_at)),
    ...displayed.map(row => Date.parse(row.open_at))])].sort((a, b) => a - b), [points, displayed]);
  const selectedTime = selected ?? selectionTimes.at(-1);
  const candle = displayed.find(row => Date.parse(row.open_at) === selectedTime);
  const point = points.find(point => Date.parse(point.open_at) === selectedTime);
  const summaryCandle = candle ?? (selected === null ? displayed.at(-1) : undefined);
  const error = state.query.error ?? state.proof.error ?? state.preview.error ?? state.refreshState.error ??
    (!first ? state.provisional?.error : null);

  useEffect(() => {
    if (!host.current) return;
    historyViewportInitialized.current = false;
    renderer.current = mountChart(host.current, chartLocale, iso => setSelected(iso === null ? null : Date.parse(iso)));
    return () => { renderer.current?.remove(); renderer.current = undefined; };
  }, [base, timeframe]);
  useEffect(() => {
    const view = renderer.current;
    if (!view) return;
    const range = view.chart.timeScale().getVisibleLogicalRange();
    const result = view.draw(displayed, points, noIndicators, false);
    setRenderLimit(result);
    // Preserve a user-adjusted viewport across data updates. On first load,
    // include empty logical slots so sparse data remains readable without stretching.
    if (!result && selectionTimes.length) {
      if (first && historyViewportInitialized.current && range) {
        view.chart.timeScale().setVisibleLogicalRange(range);
      } else {
        view.chart.timeScale().setVisibleLogicalRange(initialViewport(selectionTimes.length));
        if (first) historyViewportInitialized.current = true;
      }
    }
  }, [displayed, points, base, timeframe, selectionTimes.length, first]);

  const changeSeries = (base: string, timeframe: Timeframe) => {
    setBase(base); setTimeframe(timeframe); setSelected(null);
  };
  const resetViewport = () => {
    if (!selectionTimes.length) return;
    renderer.current?.chart.timeScale().setVisibleLogicalRange(initialViewport(selectionTimes.length));
  };
  return <ComponentCard className="candlestick-panel" headingId="market-chart-heading" title={t("heading")} desc={t("disclaimer")} data-testid="candlestick-chart">
    <div className="chart-controls">
      <label>{t("pair")}<Select value={base} onChange={event => changeSeries(event.target.value, timeframe)}>
        {pairs.map(pair => <option key={pair} value={pair}>{pair}/USDT</option>)}</Select></label>
      <label>{t("timeframe")}<Select value={timeframe} onChange={event => changeSeries(base, event.target.value as Timeframe)}>
        {timeframes.map(value => <option key={value}>{value}</option>)}</Select></label>
      <Button onClick={resetViewport} disabled={!selectionTimes.length}>{t("reset")}</Button>
    </div>
    {error && <p role="alert">{t(`errors.${error instanceof ApiRequestError ? error.message : "unknown"}`,
      { defaultValue: t("errors.unknown") })}</p>}
    {renderLimit && <p role="alert">{t(renderLimit)}</p>}
    <div className="chart-frame">
      <div className="chart-chart-header" data-testid="chart-summary">
        <div className="chart-chart-title"><strong>{base}/USDT</strong><span>· {timeframe} · {t("market")}</span></div>
        {summaryCandle && <div className="chart-candle-meta"><MarketTime value={summaryCandle.open_at} locale={chartLocale}/>
          <span>·</span><span className={`chart-finality chart-finality-${summaryCandle.finality.toLowerCase()}`}>
            {t(summaryCandle.finality)}</span></div>}
        {summaryCandle && <div className="chart-ohlc">
          {(["open", "high", "low", "close", "volume"] as const).map(name =>
            <span key={name}><span className="chart-ohlc-label" aria-label={t(name)}>{ohlcvLabels[name]}</span>{" "}
              <MarketValue amount={summaryCandle[name]} unit={name === "volume" ? base : "USDT"} grouped/></span>)}
        </div>}
      </div>
      <div ref={host} className="chart-canvas" data-testid="chart-canvas"/>
    </div>
    {!candle && selectedTime !== undefined && <div className="chart-selection" aria-label={t("selected")}>
      <p><MarketTime value={new Date(selectedTime).toISOString()} locale={chartLocale}/>
        {" · "}{t(point ? "GAP" : selected !== null ? "selectionOutside" : "missing")}</p>
    </div>}
  </ComponentCard>;
}
