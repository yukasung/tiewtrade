import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CandlestickChartPanel } from "../src/CandlestickChartPanel";
import { useChartData } from "../src/chart/useChartData";
import type { ChartRenderer } from "../src/chart/renderer";
import { chartLive, chartPage } from "./chartFixture";

const timeScale = vi.hoisted(() => ({
  getVisibleLogicalRange: vi.fn<() => { from: number; to: number } | null>(() => null),
  setVisibleLogicalRange: vi.fn(),
  scrollToRealTime: vi.fn(),
}));
vi.mock("../src/chart/useChartData", () => ({ useChartData: vi.fn() }));
vi.mock("../src/chart/renderer", () => ({ mountChart: () => ({
  chart: { timeScale: () => timeScale },
  draw: () => null, remove: () => undefined,
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

it("shows loading while the first request is scheduled, rather than empty data", () => {
  vi.mocked(useChartData).mockReturnValue(state(true, false));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.getByRole("status").textContent).toContain("ประวัติ: กำลังโหลด");
});

it("shows empty only after an empty bundle completes", () => {
  vi.mocked(useChartData).mockReturnValue(state(false, false));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.getByRole("status").textContent).toContain("ประวัติ: ไม่มีแท่งเทียนในช่วงนี้");
});

it("shows stopped when delivery errors cancel a pending history episode", () => {
  vi.mocked(useChartData).mockReturnValue(state(true, true));
  render(<CandlestickChartPanel userId="fixture" />);
  expect(screen.getByRole("status").textContent).toContain("ประวัติ: หยุดรอบอัตโนมัติแล้ว");
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
