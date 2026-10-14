import { expect, it } from "vitest";
import { candleTimeline } from "../src/chart/candleTimeline";
import { candleHistory } from "./chartFixture";
import type { CandlePage } from "../src/chart/api";
const page: CandlePage = { ...candleHistory(), display_start: "2026-07-12T00:00:00Z",
  display_end: "2026-10-12T00:00:00Z", earliest_known: true, older_before: null, newer_after: null };
it("uses native UTC calendar months including leap February", () => {
  expect(candleTimeline({ ...page, timeframe: "1M", requested: { start: "2024-01-01T00:00:00Z", end: "2024-04-01T00:00:00Z" } }))
    .toEqual(["2024-01-01T00:00:00.000Z", "2024-02-01T00:00:00.000Z", "2024-03-01T00:00:00.000Z"]);
});
it("bounds empty history rendering and preserves weekly slots", () => {
  expect(candleTimeline({ ...page, timeframe: "1m", requested: { start: "2020-01-01T00:00:00Z", end: "2026-01-01T00:00:00Z" } })).toHaveLength(1000);
  expect(candleTimeline({ ...page, timeframe: "1w", requested: { start: "2026-10-05T00:00:00Z", end: "2026-10-19T00:00:00Z" } })).toHaveLength(2);
});
