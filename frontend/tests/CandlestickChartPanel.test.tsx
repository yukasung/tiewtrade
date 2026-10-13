import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CandlestickChartPanel } from "../src/CandlestickChartPanel";
import { useChartData } from "../src/chart/useChartData";
import type { ChartRenderer } from "../src/chart/renderer";
import { candleHistory, chartLive, chartPage } from "./chartFixture";

const timeScale = vi.hoisted(() => ({
  getVisibleLogicalRange: vi.fn<() => { from: number; to: number } | null>(() => null),
  setVisibleLogicalRange: vi.fn(),
  scrollToRealTime: vi.fn(),
}));
const rendererDraw = vi.hoisted(() => vi.fn<ChartRenderer["draw"]>(() => null));
vi.mock("../src/chart/useChartData", () => ({ useChartData: vi.fn() }));
vi.mock("../src/chart/renderer", () => ({ mountChart: () => ({
  chart: { timeScale: () => timeScale },
  draw: rendererDraw, remove: () => undefined,
} as unknown as ChartRenderer) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const candle = () => ({
  open_at: "2026-10-12T00:00:00Z", end_at: "2026-10-12T01:00:00Z",
  open: "100", high: "101", low: "99", close: "100.5", volume: "2",
  finality: "UNCONFIRMED" as const, observed_at: "2026-10-12T01:00:00Z",
  last_checked_at: "2026-10-12T01:00:00Z",
});

function state(pending: boolean, stopped: boolean, withCandle = false, pointCount = 0, withPreview = false) {
  const page = chartPage();
  if (withCandle) page.candles.push(candle());
  for (let index = 0; index < pointCount; index += 1) page.rows.push({
    open_at: new Date(Date.parse("2026-10-07T01:00:00Z") + index * 3_600_000).toISOString(),
    finality: "UNCONFIRMED", seed_open_at: null, values: {},
  });
  const preview = chartLive();
  if (withPreview) preview.rows.push(candle());
  return {
    query: { isPending: pending, isFetching: false, data: pending ? undefined : { pages: [page] }, error: null },
    proof: { isFetching: false, data: undefined, error: null },
    preview: { data: preview, error: stopped ? new Error("delivery unavailable") : null },
    refreshState: { isFetching: false, error: null },
    visible: true, valid: false, stopped, cooldownActive: false, retry: vi.fn(), refresh: vi.fn(),
  } as unknown as ReturnType<typeof useChartData>;
}

it("does not show the persistent status block while the first request is scheduled", () => {
  vi.mocked(useChartData).mockReturnValue(state(true, false));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.queryByRole("status")).toBeNull();
});

it("deduplicates provisional/live candles and hands off atomically to corrected bundle candles", () => {
  const initial = state(true, false, false, 0, true);
  const history = { ...candleHistory(), rows: [{ ...candle(), close: "100.1" }] };
  initial.provisional = { data: history, error: null } as ReturnType<typeof useChartData>["provisional"];
  vi.mocked(useChartData).mockReturnValue(initial);
  const panel = render(<CandlestickChartPanel userId="fixture" />);
  expect(rendererDraw.mock.calls.at(-1)?.[0]).toHaveLength(1);
  expect(rendererDraw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.5");
  expect(rendererDraw.mock.calls.at(-1)?.[3]).toBe(false);
  const coherent = state(false, false, true);
  coherent.provisional = initial.provisional;
  coherent.query.data!.pages[0]!.candles[0]!.close = "100.7";
  vi.mocked(useChartData).mockReturnValue(coherent);
  panel.rerender(<CandlestickChartPanel userId="fixture" />);
  expect(rendererDraw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.7");
  coherent.provisional = { data: { ...history, rows: [{ ...candle(), close: "100.2" }] }, error: null } as ReturnType<typeof useChartData>["provisional"];
  panel.rerender(<CandlestickChartPanel userId="fixture" />);
  expect(rendererDraw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.7");
});

it("does not show a persistent empty-history status", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.queryByRole("status")).toBeNull();
});

it("keeps volume available as exact text inside the chart without a volume pane", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  render(<CandlestickChartPanel userId="fixture" />);
  const summary = within(screen.getByTestId("chart-summary"));
  expect(summary.getByText("2 BTC", { exact: true }).textContent).toBe("2 BTC");
  expect(screen.getAllByText("2 BTC", { exact: true })).toHaveLength(1);
});

it("does not expose indicator controls or values in the chart UI", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.queryByRole("group", { name: "Indicator" })).toBeNull();
  for (const name of ["EMA20", "EMA50", "EMA200", "RSI14", "ATR14"]) {
    expect(screen.queryByText(name, { exact: true })).toBeNull();
  }
  expect(rendererDraw.mock.calls.at(-1)?.[2].size).toBe(0);
  expect(rendererDraw.mock.calls.at(-1)?.[3]).toBe(false);
});

it("shows the selected candle's exact time, OHLCV and finality only on the chart", () => {
  const current = state(false, false, true);
  current.query.data!.pages[0]!.candles[0]!.open = "83262.00";
  vi.mocked(useChartData).mockReturnValue(current);
  render(<CandlestickChartPanel userId="fixture" />);
  const summary = within(screen.getByTestId("chart-summary"));
  expect(summary.getByText("BTC/USDT")).toBeTruthy();
  expect(summary.getByText("· 1h · Binance TH Spot")).toBeTruthy();
  expect(summary.getByText("83,262.00 USDT")).toBeTruthy();
  expect(summary.getByText("100.5 USDT")).toBeTruthy();
  expect(summary.getByText("2 BTC")).toBeTruthy();
  expect(summary.getByText("ยังไม่มีหลักฐานยืนยัน CLOSED")).toBeTruthy();
  expect(summary.getByText(/12 ต\.ค\. 2569/)).toBeTruthy();
  expect(screen.getAllByText("100.5 USDT", { exact: true })).toHaveLength(1);
  expect(current.query.data!.pages[0]!.candles[0]!.open).toBe("83262.00");
});

it("keeps actionable errors after removing the persistent status block", () => {
  vi.mocked(useChartData).mockReturnValue(state(true, true));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByRole("alert")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "ลองใหม่" })).toBeNull();
});

it("omits manual chart controls and the scale note", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  render(<CandlestickChartPanel userId="fixture" />);
  for (const name of ["กลับช่วงล่าสุด", "เพิ่มประวัติก่อนหน้า", "ลองใหม่", "ขอ refresh ประวัติ",
    "แท่งก่อนหน้า", "แท่งถัดไป"]) {
    expect(screen.queryByRole("button", { name })).toBeNull();
  }
  expect(screen.queryByText(/สเกลภาพเป็นค่าประมาณ/)).toBeNull();
});

it("resets the chart viewport with the Thai reset button", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true, 120));
  render(<CandlestickChartPanel userId="fixture" />);
  timeScale.setVisibleLogicalRange.mockClear();

  fireEvent.click(screen.getByRole("button", { name: "รีเซ็ตกราฟ" }));

  expect(timeScale.setVisibleLogicalRange).toHaveBeenCalledOnce();
  expect(timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 20, to: 124 });
  expect(screen.getAllByRole("combobox").map(control => (control as HTMLSelectElement).value))
    .toEqual(["BTC", "1h"]);
});

it("disables chart reset until chart slots are available", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.getByRole("button", { name: "รีเซ็ตกราฟ" }).hasAttribute("disabled")).toBe(true);
});

it("keeps the chart in Thai without a language selector", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.queryByRole("combobox", { name: "ภาษา" })).toBeNull();
  expect(screen.getByRole("heading", { name: "กราฟแท่งเทียน" })).toBeTruthy();
  expect(screen.getByText(/12 ต\.ค\. 2569/)).toBeTruthy();
});

it("shows a TradingView-style latest viewport on first data load", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: -99, to: 5 });
});

it("anchors the initial viewport to the latest combined chart slots", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true, 120));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 20, to: 124 });
});

it("replaces a provisional preview viewport when the first history bundle arrives", () => {
  timeScale.getVisibleLogicalRange
    .mockReturnValueOnce(null)
    .mockReturnValue({ from: -99, to: 5 });
  vi.mocked(useChartData).mockReturnValue(state(true, false, false, 0, true));
  const panel = render(<CandlestickChartPanel userId="fixture" />);
  expect(timeScale.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: -99, to: 5 });

  vi.mocked(useChartData).mockReturnValue(state(false, false, true, 120));
  panel.rerender(<CandlestickChartPanel userId="fixture" />);
  expect(timeScale.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: 20, to: 124 });
});

it("preserves logical spacing when chart data updates", () => {
  const range = { from: -150, to: 1 };
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  const panel = render(<CandlestickChartPanel userId="fixture" />);
  expect(timeScale.setVisibleLogicalRange).toHaveBeenLastCalledWith({ from: -99, to: 5 });

  timeScale.getVisibleLogicalRange.mockReturnValue(range);
  vi.mocked(useChartData).mockReturnValue(state(false, false, true, 0, true));
  panel.rerender(<CandlestickChartPanel userId="fixture" />);
  expect(timeScale.setVisibleLogicalRange).toHaveBeenLastCalledWith(range);
});

it("keeps the live preview visible while the new timeframe history loads", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false, true));
  const panel = render(<CandlestickChartPanel userId="fixture" />);
  rendererDraw.mockClear();

  vi.mocked(useChartData).mockReturnValue(state(true, false, false, 0, true));
  fireEvent.change(panel.container.querySelectorAll("select")[1]!, { target: { value: "1m" } });
  expect(rendererDraw.mock.calls.at(-1)?.[0]).toHaveLength(1);
  expect(rendererDraw.mock.calls.at(-1)?.[1]).toEqual([]);

  vi.mocked(useChartData).mockReturnValue(state(false, false, true, 120, true));
  panel.rerender(<CandlestickChartPanel userId="fixture" />);
  expect(rendererDraw.mock.calls.at(-1)?.[0].length).toBeGreaterThan(0);
  expect(rendererDraw.mock.calls.at(-1)?.[1]).toHaveLength(120);
});
