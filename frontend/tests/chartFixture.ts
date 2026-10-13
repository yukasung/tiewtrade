import type { CandleHistory, ChartHistory, ChartLive } from "../src/chart/api";

export function candleHistory(): CandleHistory {
  return { base: "BTC", quote: "USDT", timeframe: "1h",
    requested: { start: "2026-10-11T00:00:00Z", end: "2026-10-12T00:00:00Z" },
    observed: null, rows: [], gaps: [], coverage: "INCOMPLETE",
    observed_at: "2026-10-12T00:00:00Z", refresh_pending: false, status: null, failure_code: null };
}

export const chartSeries = { base: "BTC", quote: "USDT", timeframe: "1h" as const };

export function chartPage(revision = "a", cursor: string | null = null): ChartHistory {
  return {
    source: "primary_spot", ...chartSeries, formula_version: "indicators-v2", dataset_revision: revision,
    as_of: "2026-10-12T00:00:00Z", calculation_start: "2025-10-12T00:00:00Z",
    calculation_end: "2026-10-12T00:00:00Z", result_start: "2026-10-11T00:00:00Z",
    result_end: "2026-10-12T00:00:00Z", rows: [], candles: [], display_proof: "test-proof",
    next_cursor: cursor, refresh: { required: false, target: null, more_required: false,
      queue_status: null, failure_code: null, observed_at: "2026-10-12T00:00:00Z" },
  };
}

export function chartLive(): ChartLive {
  return {
    source: "primary_spot", ...chartSeries, rows: [], status: "NO_DATA", reason: null,
    server_time: "2026-10-12T00:00:00Z", epoch: "1", revision: null,
    event_at: null, received_at: null, history_end: null,
  };
}
