import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CandlestickChartPanel } from "../src/CandlestickChartPanel";
import { useChartData } from "../src/chart/useChartData";
import type { ChartRenderer } from "../src/chart/renderer";
import { candleHistory, chartLive } from "./chartFixture";

const scale = vi.hoisted(() => ({ getVisibleLogicalRange: vi.fn<() => { from: number; to: number } | null>(() => null), getVisibleRange: vi.fn(() => null),
  setVisibleLogicalRange: vi.fn(), setVisibleRange: vi.fn(), subscribeVisibleLogicalRangeChange: vi.fn(),
  unsubscribeVisibleLogicalRangeChange: vi.fn() }));
const draw = vi.hoisted(() => vi.fn<ChartRenderer["draw"]>(() => null));
vi.mock("../src/chart/useChartData", () => ({ useChartData: vi.fn() }));
vi.mock("../src/chart/renderer", () => ({ mountChart: () => ({ chart: { timeScale: () => scale },
  draw, remove: vi.fn(), applyTheme: vi.fn() }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); scale.getVisibleLogicalRange.mockReturnValue(null); });
const candle = () => ({ open_at: "2026-10-12T00:00:00Z", end_at: "2026-10-12T01:00:00Z",
  open: "100", high: "101", low: "99", close: "100.5", volume: "2", finality: "UNCONFIRMED" as const,
  observed_at: "2026-10-12T00:30:00Z", last_checked_at: "2026-10-12T00:30:00Z" });
function state() {
  return { preview: { data: chartLive(), isFetching: false }, error: null, visible: true,
    cooldownActive: false, retry: vi.fn(), browsing: { latest: { ...candleHistory(), rows: [candle()],
      display_start: "2026-07-12T00:00:00Z", display_end: "2026-10-12T01:00:00Z", earliest_known: true,
      older_before: null, newer_after: null }, navigate: vi.fn(), reset: vi.fn(), retry: vi.fn() },
  } as unknown as ReturnType<typeof useChartData>;
}
it("renders exact candle data without indicator points or controls", () => {
  vi.mocked(useChartData).mockReturnValue(state()); render(<CandlestickChartPanel userId="one"/>);
  expect(draw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.5");
  expect(draw.mock.calls.at(-1)?.[1]).toEqual([]);
  expect(draw.mock.calls.at(-1)?.[2].size).toBe(0);
  expect(screen.queryByRole("checkbox")).toBeNull();
  expect(screen.getByTestId("chart-summary").textContent).toContain("100.5");
});
it("keeps newer history when live is older, and deduplicates newer live", () => {
  const current = state(); current.preview.data!.rows = [{ ...candle(), close: "100.1", observed_at: "2026-10-12T00:20:00Z" }];
  vi.mocked(useChartData).mockReturnValue(current); const panel = render(<CandlestickChartPanel userId="one"/>);
  expect(draw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.5");
  current.preview.data = { ...current.preview.data!, rows: [{ ...candle(), close: "100.8", observed_at: "2026-10-12T00:40:00Z" }] };
  panel.rerender(<CandlestickChartPanel userId="one"/>);
  expect(draw.mock.calls.at(-1)?.[0]).toHaveLength(1);
  expect(draw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.8");
});
it("never downgrades closed history with a live preview", () => {
  const current = state(); current.browsing.latest!.rows[0]!.finality = "CLOSED";
  current.preview.data!.rows = [{ ...candle(), close: "100.9", observed_at: "2026-10-12T02:00:00Z" }];
  vi.mocked(useChartData).mockReturnValue(current); render(<CandlestickChartPanel userId="one"/>);
  expect(draw.mock.calls.at(-1)?.[0][0]?.close).toBe("100.5");
});
it("does not append live candles while browsing an older page", () => {
  const current = state(); current.browsing.page = { ...current.browsing.latest! };
  current.preview.data!.rows = [{ ...candle(), open_at: "2026-10-12T02:00:00Z" }];
  vi.mocked(useChartData).mockReturnValue(current); render(<CandlestickChartPanel userId="one"/>);
  expect(draw.mock.calls.at(-1)?.[0]).toHaveLength(1);
});
it("reset only changes viewport, and supports weekly/monthly selection", () => {
  const current = state(); vi.mocked(useChartData).mockReturnValue(current);
  render(<CandlestickChartPanel userId="one"/>);
  fireEvent.click(screen.getByRole("button", { name: /รีเซ็ต/ }));
  expect(current.retry).not.toHaveBeenCalled(); expect(current.browsing.retry).not.toHaveBeenCalled();
  expect(scale.setVisibleLogicalRange).toHaveBeenCalled();
  expect(screen.getByRole("option", { name: "1w" })).toBeTruthy();
  fireEvent.change(document.querySelector("#chart-timeframe")!, { target: { value: "1M" } });
  expect(vi.mocked(useChartData).mock.calls.at(-1)?.[1].timeframe).toBe("1M");
});
it("offers only the supported pairs and defaults to BTC", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  render(<CandlestickChartPanel userId="one"/>);
  const pair = screen.getByRole<HTMLSelectElement>("combobox", { name: "คู่เทรด" });
  expect([...pair.options].map(option => option.textContent)).toEqual(["BTC/USDT", "ETH/USDT"]);
  expect(pair.value).toBe("BTC");
  expect(vi.mocked(useChartData).mock.calls.at(-1)?.[1].base).toBe("BTC");
});
it("blocks manual retry during cooldown", () => {
  const current = state(); current.error = new Error("unavailable"); current.cooldownActive = true;
  vi.mocked(useChartData).mockReturnValue(current); const panel = render(<CandlestickChartPanel userId="one"/>);
  const button = screen.getByRole("button", { name: /ลองใหม่/ });
  fireEvent.click(button); expect(current.retry).not.toHaveBeenCalled();
  current.cooldownActive = false; panel.rerender(<CandlestickChartPanel userId="one"/>);
  fireEvent.click(button); expect(current.retry).toHaveBeenCalledOnce();
});


it("keeps volume available as exact text inside the chart without a volume pane", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  render(<CandlestickChartPanel userId="fixture" />);
  const summary = within(screen.getByTestId("chart-summary"));
  expect(summary.getByText("2 BTC", { exact: true }).textContent).toBe("2 BTC");
  expect(screen.getAllByText("2 BTC", { exact: true })).toHaveLength(1);
});


it("does not expose indicator controls or values in the chart UI", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.queryByRole("group", { name: "Indicator" })).toBeNull();
  for (const name of ["EMA20", "EMA50", "EMA200", "RSI14", "ATR14"]) {
    expect(screen.queryByText(name, { exact: true })).toBeNull();
  }
  expect(draw.mock.calls.at(-1)?.[2].size).toBe(0);
  expect(draw.mock.calls.at(-1)?.[3]).toBe(false);
});


it("shows the selected candle's exact time, OHLCV and finality only on the chart", () => {
  const current = state();
  current.browsing.latest!.rows[0]!.open = "83262.00";
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
  expect(current.browsing.latest!.rows[0]!.open).toBe("83262.00");
});


it("omits manual chart controls and the scale note", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  render(<CandlestickChartPanel userId="fixture" />);
  for (const name of ["กลับช่วงล่าสุด", "เพิ่มประวัติก่อนหน้า", "ลองใหม่", "ขอ refresh ประวัติ",
    "แท่งก่อนหน้า", "แท่งถัดไป"]) {
    expect(screen.queryByRole("button", { name })).toBeNull();
  }
  expect(screen.queryByText(/สเกลภาพเป็นค่าประมาณ/)).toBeNull();
});


it("renders a disabled order placeholder without a form or default financial values", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  const panel = render(<CandlestickChartPanel userId="fixture" />);
  const order = within(screen.getByTestId("trading-order-placeholder"));
  expect(panel.container.querySelector("form")).toBeNull();
  for (const control of [...order.getAllByRole("button"), ...order.getAllByRole("textbox"),
    ...order.getAllByRole("combobox")]) {
    expect(control.hasAttribute("disabled")).toBe(true);
  }
  expect(order.getAllByRole("textbox").every(input => (input as HTMLInputElement).value === "")).toBe(true);
  expect(order.getByRole("button", { name: "ยังไม่เปิดใช้งาน" })).toBeTruthy();
});


it("renders semantic empty trading history without mock rows", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  render(<CandlestickChartPanel userId="fixture" />);
  const history = within(screen.getByTestId("trade-history-placeholder"));
  expect(history.getByRole("table")).toBeTruthy();
  expect(history.getAllByRole("columnheader")).toHaveLength(6);
  expect(history.getAllByRole("row")).toHaveLength(2);
  expect(history.getByText("ยังไม่มีข้อมูลออเดอร์หรือการเทรดจากระบบ", { exact: true })).toBeTruthy();
});


it("keeps chart content in Thai without visible market-bar labels", () => {
  vi.mocked(useChartData).mockReturnValue(state());
  const panel = render(<CandlestickChartPanel userId="fixture" />);
  const marketBar = within(panel.container.querySelector(".trading-market-bar") as HTMLElement);
  expect(screen.queryByRole("combobox", { name: "ภาษา" })).toBeNull();
  expect(marketBar.queryByText("กราฟแท่งเทียน", { exact: true })).toBeNull();
  expect(marketBar.queryByText("คู่เทรด", { exact: true })).toBeNull();
  expect(marketBar.queryByText("Timeframe", { exact: true })).toBeNull();
  expect(marketBar.getByRole("combobox", { name: "คู่เทรด" })).toBeTruthy();
  expect(marketBar.getByRole("combobox", { name: "Timeframe" })).toBeTruthy();
  expect(screen.getByText(/12 ต\.ค\. 2569/)).toBeTruthy();
});

it("does not paginate after programmatic range changes, but loads on user pan", () => {
  vi.useFakeTimers();
  try {
    const current = state(); current.browsing.latest!.older_before = "2026-10-11T00:00:00Z";
    vi.mocked(useChartData).mockReturnValue(current); render(<CandlestickChartPanel userId="one"/>);
    const changed = scale.subscribeVisibleLogicalRangeChange.mock.calls[0]![0] as (range: { from: number; to: number }) => void;
    changed({ from: 0, to: 99 }); vi.advanceTimersByTime(300);
    expect(current.browsing.navigate).not.toHaveBeenCalled();
    fireEvent.pointerDown(screen.getByTestId("chart-canvas"));
    changed({ from: 0, to: 99 }); vi.advanceTimersByTime(300);
    expect(current.browsing.navigate).toHaveBeenCalledWith("older");
  } finally { vi.useRealTimers(); }
});

it("keeps the user's fractional viewport when live data redraws", () => {
  const current = state(); vi.mocked(useChartData).mockReturnValue(current);
  const panel = render(<CandlestickChartPanel userId="one"/>);
  const range = { from: -12.75, to: 8.5 };
  scale.getVisibleLogicalRange.mockReturnValue(range);
  scale.setVisibleLogicalRange.mockClear();
  current.preview.data = { ...chartLive(), rows: [{ ...candle(), close: "100.8" }] };
  panel.rerender(<CandlestickChartPanel userId="one"/>);
  expect(scale.setVisibleLogicalRange).toHaveBeenLastCalledWith(range);
  expect(scale.setVisibleRange).not.toHaveBeenCalled();
});
