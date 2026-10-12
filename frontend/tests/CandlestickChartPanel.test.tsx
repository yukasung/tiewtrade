import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CandlestickChartPanel } from "../src/CandlestickChartPanel";
import { useChartData } from "../src/chart/useChartData";
import type { ChartRenderer } from "../src/chart/renderer";
import { chartLive, chartPage } from "./chartFixture";

vi.mock("../src/chart/useChartData", () => ({ useChartData: vi.fn() }));
vi.mock("../src/chart/renderer", () => ({ mountChart: () => ({
  chart: { timeScale: () => ({ getVisibleRange: () => null }) },
  draw: () => null, remove: () => undefined,
} as unknown as ChartRenderer) }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function state(pending: boolean, stopped: boolean) {
  return {
    query: { isPending: pending, isFetching: false, data: pending ? undefined : { pages: [chartPage()] }, error: null },
    proof: { isFetching: false, data: undefined, error: null },
    preview: { data: chartLive(), error: stopped ? new Error("delivery unavailable") : null },
    refreshState: { isFetching: false, error: null },
    visible: true, valid: false, stopped, cooldown: 0, retry: vi.fn(), refresh: vi.fn(),
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
