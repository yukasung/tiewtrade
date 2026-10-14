import type { CandlePage } from "./api";

/** Display-only UTC slots, bounded by the candle page contract; no financial calculation. */
export function candleTimeline(page: CandlePage | undefined): string[] {
  if (!page) return [];
  const slots: string[] = [];
  const end = Date.parse(page.requested.end);
  const fixed = { "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800 };
  let time = Date.parse(page.requested.start);
  while (time < end && slots.length < 1000) {
    slots.push(new Date(time).toISOString());
    if (page.timeframe === "1M") {
      const next = new Date(time); next.setUTCMonth(next.getUTCMonth() + 1); time = next.getTime();
    } else time += fixed[page.timeframe] * 1000;
  }
  return slots;
}
