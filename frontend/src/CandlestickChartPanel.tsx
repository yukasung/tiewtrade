import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiRequestError } from "./auth";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { Select } from "./components/ui/Select";
import { chartI18n } from "./chartMessages";
import { mountChart, type ChartRenderer } from "./chart/renderer";
import { useChartData } from "./chart/useChartData";
import { candleTimeline } from "./chart/candleTimeline";
import { anchoredRange } from "./chart/viewport";
import type { Series, Timeframe } from "./chart/api";
import { activeBases, useMarketCatalog } from "./marketCatalog";
import { TradeHistoryPlaceholder, TradingOrderPlaceholder } from "./TradingWorkspacePlaceholders";
import "./CandlestickChartPanel.css";

const timeframes: Timeframe[] = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"];
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

export type ChartMarketSnapshot = { base: string; price: string; observedAt: string };

export function CandlestickChartPanel({ userId, base: controlledBase, onBaseChange, embedded = false,
  onMarketSnapshot, toolbarTargetId }: {
  userId: string;
  base?: string;
  onBaseChange?: (base: string) => void;
  embedded?: boolean;
  onMarketSnapshot?: (snapshot: ChartMarketSnapshot | null) => void;
  toolbarTargetId?: string;
}) {
  const [localBase, setLocalBase] = useState("BTC");
  const base = controlledBase ?? localBase;
  const setBase = onBaseChange ?? setLocalBase;
  const catalog = useMarketCatalog();
  const supportedBases = useMemo(() => activeBases(catalog.data), [catalog.data]);
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [selected, setSelected] = useState<number | null>(null);
  const [renderLimit, setRenderLimit] = useState<string | null>(null);
  const [toolbarTarget, setToolbarTarget] = useState<HTMLElement | null>(null);
  const host = useRef<HTMLDivElement>(null), renderer = useRef<ChartRenderer>();
  const historyViewportInitialized = useRef(false);
  const drawing = useRef(false);
  const preservePageRange = useRef(false);
  const renderedSlotCount = useRef(0);
  const renderedTimes = useRef<number[]>([]);
  const series: Series = { base, quote: "USDT", timeframe };
  const state = useChartData(userId, series, supportedBases.includes(base));
  const browsing = state.browsing;
  const browsingActions = useRef(browsing); browsingActions.current = browsing;
  const history = browsing.page ?? browsing.latest;
  const timeline = useMemo(() => candleTimeline(history), [history]);
  const rows = history?.rows ?? [];
  const preview = belongsToSeries(state.preview.data, series) ? state.preview.data : undefined;
  const displayed = useMemo(() => {
    const merged = new Map(rows.map(row => [row.open_at, row]));
    if (!browsing.page) for (const row of preview?.retained ?? []) {
      if (!merged.has(row.open_at) && (!history || Date.parse(row.open_at) >= Date.parse(history.requested.start))) {
        merged.set(row.open_at, row);
      }
    }
    if (!browsing.page) for (const row of preview?.rows ?? []) {
      const existing = merged.get(row.open_at);
      if (!existing || (existing.finality !== "CLOSED" && Date.parse(row.observed_at) >= Date.parse(existing.observed_at))) {
        merged.set(row.open_at, row);
      }
    }
    return [...merged.values()].sort((a, b) => Date.parse(a.open_at) - Date.parse(b.open_at));
  }, [rows, preview, browsing.page]);
  const selectionTimes = useMemo(() => [...new Set([...timeline.map(Date.parse),
    ...displayed.map(row => Date.parse(row.open_at))])].sort((a, b) => a - b), [displayed, timeline]);
  const selectedTime = selected ?? (displayed.length ? Date.parse(displayed.at(-1)!.open_at) : undefined);
  const candle = displayed.find(row => Date.parse(row.open_at) === selectedTime);
  const selectedGap = selectedTime !== undefined && history?.gaps.some(gap =>
    selectedTime >= Date.parse(gap.start) && selectedTime < Date.parse(gap.end));
  const summaryCandle = candle ?? (selected === null ? displayed.at(-1) : undefined);
  const summaryPrice = summaryCandle?.close;
  const summaryObservedAt = summaryCandle?.observed_at;
  const error = state.error;

  useEffect(() => {
    if (!toolbarTargetId) { setToolbarTarget(null); return; }
    setToolbarTarget(document.getElementById(toolbarTargetId));
  }, [toolbarTargetId]);

  useEffect(() => {
    if (supportedBases.length && !supportedBases.includes(base)) {
      setBase(supportedBases[0]!);
      setSelected(null);
    }
  }, [base, supportedBases]);

  useEffect(() => {
    onMarketSnapshot?.(summaryPrice && summaryObservedAt ? {
      base,
      price: summaryPrice,
      observedAt: summaryObservedAt,
    } : null);
  }, [base, onMarketSnapshot, summaryPrice, summaryObservedAt]);

  useEffect(() => {
    if (!host.current) return;
    historyViewportInitialized.current = false;
    renderedTimes.current = [];
    renderer.current = mountChart(host.current, chartLocale, iso => setSelected(iso === null ? null : Date.parse(iso)));
    const scale = renderer.current.chart.timeScale();
    let timer: ReturnType<typeof globalThis.setTimeout> | undefined;
    let navigationRequested = false;
    const requestNavigation = () => { navigationRequested = true; };
    const element = host.current;
    element.addEventListener("pointerdown", requestNavigation);
    element.addEventListener("wheel", requestNavigation, { passive: true });
    const changed = (range: { from: number; to: number } | null) => {
      if (drawing.current || !range || !navigationRequested) return;
      globalThis.clearTimeout(timer);
      timer = globalThis.setTimeout(() => {
        navigationRequested = false;
        const current = browsingActions.current;
        if (current.loading || current.error) return;
        const count = renderedSlotCount.current;
        if (!count) return;
        const direction = range.from < 100 ? "older" : range.to > count - 100 ? "newer" : null;
        const page = current.page ?? current.latest;
        const boundary = direction === "older" ? page?.older_before : page?.newer_after;
        if (direction && boundary) { preservePageRange.current = true; current.navigate(direction); }
      }, 250);
    };
    scale.subscribeVisibleLogicalRangeChange(changed);
    return () => { globalThis.clearTimeout(timer); scale.unsubscribeVisibleLogicalRangeChange(changed);
      element.removeEventListener("pointerdown", requestNavigation); element.removeEventListener("wheel", requestNavigation);
      renderer.current?.remove(); renderer.current = undefined; };
  }, [base, timeframe]);
  useEffect(() => {
    const applyTheme = () => renderer.current?.applyTheme();
    window.addEventListener("tiewtrade-theme-change", applyTheme);
    return () => window.removeEventListener("tiewtrade-theme-change", applyTheme);
  }, []);
  useEffect(() => {
    const view = renderer.current;
    if (!view) return;
    const range = view.chart.timeScale().getVisibleLogicalRange();
    const preserved = range && (historyViewportInitialized.current || preservePageRange.current)
      ? anchoredRange(range, renderedTimes.current, selectionTimes) : null;
    drawing.current = true;
    renderedSlotCount.current = selectionTimes.length;
    const result = view.draw(displayed, [], noIndicators, false, timeline);
    setRenderLimit(result);
    // Preserve a user-adjusted viewport across data updates. On first load,
    // include empty logical slots so sparse data remains readable without stretching.
    if (!result && selectionTimes.length) {
      if (preserved) {
        view.chart.timeScale().setVisibleLogicalRange(preserved);
      } else {
        view.chart.timeScale().setVisibleLogicalRange(initialViewport(selectionTimes.length));
        if (history) historyViewportInitialized.current = true;
      }
    }
    if (!result) renderedTimes.current = selectionTimes;
    drawing.current = false;
  }, [displayed, base, timeframe, selectionTimes.length, history, timeline]);

  const changeSeries = (base: string, timeframe: Timeframe) => {
    preservePageRange.current = false;
    setBase(base); setTimeframe(timeframe); setSelected(null);
  };
  const resetViewport = () => {
    preservePageRange.current = false;
    if (browsing.page) { browsing.reset(); historyViewportInitialized.current = false; return; }
    if (!selectionTimes.length) return;
    renderer.current?.chart.timeScale().setVisibleLogicalRange(initialViewport(selectionTimes.length));
  };
  const controls = <div className="chart-controls">
    {!embedded && <div><Select id="chart-pair" aria-label={t("pair")} value={base}
      onChange={event => changeSeries(event.target.value, timeframe)}>
        {supportedBases.map(pair => <option key={pair} value={pair}>{pair}/USDT</option>)}</Select></div>}
    <div><Select id="chart-timeframe" aria-label={t("timeframe")} value={timeframe}
        onChange={event => changeSeries(base, event.target.value as Timeframe)}>
        {timeframes.map(value => <option key={value}>{value}</option>)}</Select></div>
    <Button size="sm" className="chart-reset-button" onClick={resetViewport}
      disabled={!selectionTimes.length}>{t("reset")}</Button>
  </div>;
  return <section className={`candlestick-panel ${embedded ? "candlestick-embedded" : "trading-workspace"}`} aria-label={t("heading")}
    data-testid="candlestick-chart">
    {toolbarTarget && createPortal(controls, toolbarTarget)}
    {!toolbarTargetId && <header className="trading-market-bar">
      {!embedded && <div className="trading-market-identity">
        <strong>{base}/USDT</strong><span>{t("market")}</span>
      </div>}
      {controls}
    </header>}
    <div className="trading-chart-area">
      {error && <p role="alert">{t(`errors.${error instanceof ApiRequestError ? error.message : "unknown"}`,
        { defaultValue: t("errors.unknown") })}</p>}
      {error && <Button onClick={state.retry} disabled={state.cooldownActive || !state.visible ||
        browsing.loading || state.preview.isFetching}>{t("retry")}</Button>}
      {!error && browsing.page && browsing.page.coverage !== "PRESENT" && <Button onClick={browsing.retry}
        disabled={browsing.loading || globalThis.performance.now() < (browsing.retryAt ?? 0)}>{t("retry")}</Button>}
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
          {" · "}{t(selectedGap ? "GAP" : selected !== null ? "selectionOutside" : "missing")}</p>
      </div>}
    </div>
    {!embedded && <TradingOrderPlaceholder/>}
    {!embedded && <TradeHistoryPlaceholder/>}
  </section>;
}
