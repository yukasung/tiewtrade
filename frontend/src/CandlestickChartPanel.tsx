import { useEffect, useMemo, useRef, useState } from "react";
import { ApiRequestError } from "./auth";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { Select } from "./components/ui/Select";
import { ComponentCard } from "./components/ui/ComponentCard";
import { chartI18n, chartText as t } from "./chartMessages";
import { mountChart, type ChartRenderer } from "./chart/renderer";
import { useChartData } from "./chart/useChartData";
import type { Series, Timeframe, Window } from "./chart/api";
import "./CandlestickChartPanel.css";

const pairs = ["BTC", "ETH", "SOL", "XRP", "DOGE"];
const timeframes: Timeframe[] = ["1m", "5m", "15m", "1h", "4h", "1d"];
const spans: Record<Timeframe, number> = { "1m": 60_000, "5m": 300_000, "15m": 900_000,
  "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000 };
const names = ["ema20", "ema50", "ema200", "rsi14", "macd_line", "macd_signal", "macd_histogram", "atr14"];
const initialVisibleSlots = 100, initialRightOffset = 5;

export function CandlestickChartPanel({ userId }: { userId: string }) {
  const [base, setBase] = useState("BTC");
  const [timeframe, setTimeframe] = useState<Timeframe>("1h");
  const [locale, setLocale] = useState(chartI18n.language);
  const [window, setWindow] = useState<Window>();
  const [selected, setSelected] = useState<number | null>(null);
  const [enabled, setEnabled] = useState(new Set(names.slice(0, 3)));
  const [renderLimit, setRenderLimit] = useState<string | null>(null);
  const host = useRef<HTMLDivElement>(null), renderer = useRef<ChartRenderer>();
  const historyViewportInitialized = useRef(false);
  const series: Series = { base, quote: "USDT", timeframe };
  const state = useChartData(userId, series, window);
  const first = state.query.data?.pages[0];
  const rows = useMemo(() => state.query.data?.pages.flatMap(page => page.candles) ?? [], [state.query.data]);
  const points = useMemo(() => state.query.data?.pages.flatMap(page => page.rows) ?? [], [state.query.data]);
  const liveRows = state.preview.data?.rows ?? [];
  const overlap = !!first && liveRows.some(row => row.open_at < first.calculation_end &&
    rows.some(history => history.open_at === row.open_at));
  const indicatorsValid = state.valid && !overlap && !renderLimit;
  const displayed = useMemo(() => [...rows, ...liveRows.filter(row => !first || row.open_at >= first.calculation_end)]
    .sort((a, b) => Date.parse(a.open_at) - Date.parse(b.open_at)), [rows, liveRows, first]);
  const selectionTimes = useMemo(() => [...new Set([...points.map(point => Date.parse(point.open_at)),
    ...displayed.map(row => Date.parse(row.open_at))])].sort((a, b) => a - b), [points, displayed]);
  const selectedIndex = selected === null ? selectionTimes.length - 1 : selectionTimes.indexOf(selected);
  const selectedTime = selected ?? selectionTimes[selectedIndex];
  const candle = displayed.find(row => Date.parse(row.open_at) === selectedTime);
  const point = points.find(point => Date.parse(point.open_at) === selectedTime);
  const error = state.query.error ?? state.proof.error ?? state.preview.error ?? state.refreshState.error;

  useEffect(() => {
    if (!host.current) return;
    historyViewportInitialized.current = false;
    renderer.current = mountChart(host.current, locale, iso => setSelected(Date.parse(iso)));
    return () => { renderer.current?.remove(); renderer.current = undefined; };
  }, [locale, base, timeframe]);
  useEffect(() => {
    const view = renderer.current;
    if (!view) return;
    const range = view.chart.timeScale().getVisibleLogicalRange();
    const result = view.draw(displayed, points, enabled, state.valid && !overlap);
    setRenderLimit(result);
    // Preserve a user-adjusted viewport across data updates. On first load,
    // include empty logical slots so sparse data remains readable without stretching.
    if (!result && selectionTimes.length) {
      if (first && historyViewportInitialized.current && range) {
        view.chart.timeScale().setVisibleLogicalRange(range);
      } else {
        view.chart.timeScale().setVisibleLogicalRange({
        from: selectionTimes.length - initialVisibleSlots,
        to: selectionTimes.length - 1 + initialRightOffset,
        });
        if (first) historyViewportInitialized.current = true;
      }
    }
  }, [displayed, points, enabled, state.valid, overlap, locale, base, timeframe, selectionTimes.length, first]);

  const changeSeries = (base: string, timeframe: Timeframe) => {
    setBase(base); setTimeframe(timeframe); setWindow(undefined); setSelected(null);
  };
  const older = () => {
    if (!first) return;
    const span = spans[timeframe];
    const start = Math.max(Date.parse(first.calculation_start), Date.parse(first.result_start) - 1000 * span);
    let end = Date.parse(first.result_end);
    if (end - start > 12_000 * span) {
      const visible = renderer.current?.chart.timeScale().getVisibleLogicalRange();
      if (visible && visible.from > 1000) {
        renderer.current?.chart.timeScale().setVisibleLogicalRange({ from: 0, to: 100 });
        return;
      }
      end = start + 12_000 * span;
    }
    setWindow({ start: new Date(start).toISOString(), end: new Date(end).toISOString() });
  };
  const latest = () => {
    setWindow(undefined); setSelected(null);
    if (!window) state.retry();
    renderer.current?.chart.timeScale().scrollToRealTime();
  };
  const toggle = (name: string) => setEnabled(current => {
    const updated = new Set(current);
    if (updated.has(name)) updated.delete(name); else updated.add(name);
    return updated;
  });
  const historyStatus = state.stopped ? "STOPPED" : state.query.isPending || state.query.isFetching ? "LOADING"
    : !first ? "EMPTY" : !rows.length ? "EMPTY" : rows.length < points.length ? "PARTIAL" : "MATCHED";
  const proofStatus = !state.visible ? (globalThis.navigator.onLine ? "HIDDEN" : "OFFLINE")
    : state.proof.isFetching ? "CHECKING" : indicatorsValid ? "MATCHED" : state.proof.data?.status ?? "UNVERIFIABLE";
  return <ComponentCard className="candlestick-panel" headingId="market-chart-heading" title={t("heading")} desc={t("disclaimer")} data-testid="candlestick-chart">
    <div className="chart-controls">
      <label>{t("pair")}<Select value={base} onChange={event => changeSeries(event.target.value, timeframe)}>
        {pairs.map(pair => <option key={pair} value={pair}>{pair}/USDT</option>)}</Select></label>
      <label>{t("timeframe")}<Select value={timeframe} onChange={event => changeSeries(base, event.target.value as Timeframe)}>
        {timeframes.map(value => <option key={value}>{value}</option>)}</Select></label>
      <label>{t("language")}<Select value={locale} onChange={event => {
        void chartI18n.changeLanguage(event.target.value); setLocale(event.target.value);
      }}><option value="th">ไทย</option><option value="en">English</option></Select></label>
      <Button type="button" onClick={latest}>{t("latest")}</Button>
      <Button type="button" disabled={!first || state.query.isFetching || first.result_start === first.calculation_start}
        onClick={older}>{t("older")}</Button>
      <Button type="button" disabled={state.query.isFetching || state.proof.isFetching ||
        state.refreshState.isFetching || state.cooldownActive} onClick={state.retry}>{t("retry")}</Button>
      <Button type="button" disabled={!first?.refresh.target || state.query.isFetching || state.proof.isFetching || state.refreshState.isFetching}
        onClick={() => { void state.refresh().catch(() => undefined); }}>{t("refresh")}</Button>
    </div>
    <fieldset className="chart-indicators"><legend>{t("indicators")}</legend>
      {names.map(name => <label key={name}><input type="checkbox" checked={enabled.has(name)}
        onChange={() => toggle(name)}/>{name.toUpperCase()}</label>)}
    </fieldset>
    <div role="status" aria-live="polite">
      <p>{t("history")}: {t(historyStatus)} · {t(proofStatus)}</p>
      <p>{t("preview")}: {t(!state.visible ? "OFFLINE" : state.preview.error ? "STOPPED" : state.preview.data?.status ?? "LOADING")}</p>
      {state.preview.data?.reason && <p>{t("reason")}: {t(`streamReasons.${state.preview.data.reason}`,
        { defaultValue: t("unknownReason") })}</p>}
      {first && <p>{t("asOf")}: <MarketTime value={first.as_of} locale={locale}/></p>}
      {state.preview.data && <p>{t("checked")}: <MarketTime value={state.preview.data.server_time} locale={locale}/></p>}
      {first?.refresh.required && <p>{t("REFRESH_REQUIRED")}</p>}
    </div>
    {error && <p role="alert">{t(`errors.${error instanceof ApiRequestError ? error.message : "unknown"}`,
      { defaultValue: t("errors.unknown") })}</p>}
    {renderLimit && <p role="alert">{t(renderLimit)}</p>}
    <p>{t("scale")}</p>
    <div ref={host} className="chart-canvas" data-testid="chart-canvas"/>
    <p className="chart-attribution"><a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">{t("attribution")}</a></p>
    <div className="chart-selection" aria-label={t("selected")}>
      <Button type="button" disabled={selectedIndex <= 0} onClick={() => {
        const time = selectionTimes[selectedIndex - 1]; if (time !== undefined) setSelected(time);
      }}>{t("previous")}</Button>
      <Button type="button" disabled={selectedIndex < 0 || selectedIndex >= selectionTimes.length - 1} onClick={() => {
        const time = selectionTimes[selectedIndex + 1]; if (time !== undefined) setSelected(time);
      }}>{t("next")}</Button>
      {candle ? <><p><MarketTime value={candle.open_at} locale={locale}/> · {t(candle.finality)}</p>
        <dl>{(["open", "high", "low", "close", "volume"] as const).map(name => <div key={name}>
          <dt>{t(name)}</dt><dd><MarketValue amount={candle[name]} unit={name === "volume" ? base : "USDT"}/></dd></div>)}
          {indicatorsValid && point && names.filter(name => enabled.has(name)).map(name => {
            const value = point.values[name];
            return <div key={name}><dt>{name.toUpperCase()}</dt><dd>{value?.value != null
              ? <MarketValue amount={value.value} unit={value.unit ?? ""}/> : t(value?.status ?? "missing")}</dd></div>;
          })}</dl></> : <p>{selectedTime !== undefined && <MarketTime value={new Date(selectedTime).toISOString()} locale={locale}/>}
            {t(point ? "GAP" : selected !== null ? "selectionOutside" : "missing")}</p>}
    </div>
  </ComponentCard>;
}
