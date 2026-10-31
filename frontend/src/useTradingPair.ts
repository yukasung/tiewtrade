import { useCallback, useState } from "react";
import type { ChartMarketSnapshot } from "./CandlestickChartPanel";

/** Keeps the shared pair selector and chart snapshot in the same fail-closed scope. */
export function useTradingPair() {
  const [base, setBase] = useState("");
  const [marketSnapshot, setMarketSnapshot] = useState<ChartMarketSnapshot | null>(null);
  const changeBase = useCallback((nextBase: string) => {
    setMarketSnapshot(null);
    setBase(nextBase);
  }, []);
  const market = marketSnapshot?.base === base ? marketSnapshot : null;
  return { base, changeBase, market, setMarketSnapshot };
}
