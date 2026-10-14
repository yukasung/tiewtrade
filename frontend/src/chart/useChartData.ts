import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiRequestError } from "../auth";
import { live, type Candle, type ChartLive, type Series } from "./api";
import { useChartPages } from "./useChartPages";

/** Candle-only chart: the indicator reader and its proof endpoint are never started. */
export function useChartData(user: string, series: Series) {
  const client = useQueryClient();
  const [visible, setVisible] = useState(document.visibilityState !== "hidden" && globalThis.navigator.onLine);
  const [retryAt, setRetryAt] = useState(0);
  const cooldown = useRef(0), seenErrors = useRef(new WeakSet<ApiRequestError>());
  const rateError = useRef<ApiRequestError>();
  const key = ["chart-candles-live", user, series.base, series.quote, series.timeframe] as const;
  const preview = useQuery<ChartLive & { retained?: Candle[] }>({ queryKey: key, enabled: false, retry: false, gcTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false, networkMode: "always",
    queryFn: async ({ signal }) => {
      const snapshot = await live(series, AbortSignal.any([signal, AbortSignal.timeout(3000)]));
      if (signal.aborted) throw signal.reason;
      const previous = client.getQueryData<ChartLive & { retained?: Candle[] }>(key);
      const retained = new Map((previous?.retained ?? []).map(row => [row.open_at, row]));
      for (const row of snapshot.rows) {
        const existing = retained.get(row.open_at);
        if (!existing || Date.parse(row.observed_at) >= Date.parse(existing.observed_at)) retained.set(row.open_at, row);
      }
      return { ...snapshot, retained: [...retained.values()].sort((a, b) => Date.parse(a.open_at) - Date.parse(b.open_at))
        .slice(-120).map(row => Date.parse(row.end_at) <= Date.parse(snapshot.server_time)
          ? { ...row, finality: "UNCONFIRMED" as const } : row) };
    },
  });
  const browsing = useChartPages(user, series, Boolean(preview.error || rateError.current), cooldown.current);
  const sourceError = browsing.error ?? preview.error;
  if (sourceError instanceof ApiRequestError && sourceError.status === 429) rateError.current = sourceError;
  const error = sourceError ?? rateError.current;
  if (error instanceof ApiRequestError && error.retryAt && !seenErrors.current.has(error)) {
    seenErrors.current.add(error);
    const delay = Date.parse(error.retryAt) - Date.now();
    if (Number.isFinite(delay)) cooldown.current = Math.max(cooldown.current, globalThis.performance.now() + Math.max(0, delay));
  }
  const actions = useRef({ preview, browsing, error }); actions.current = { preview, browsing, error };
  useEffect(() => {
    const remaining = cooldown.current - globalThis.performance.now();
    if (remaining <= 0) return;
    setRetryAt(cooldown.current);
    const timer = globalThis.setTimeout(() => setRetryAt(0), remaining + 1);
    return () => globalThis.clearTimeout(timer);
  }, [error]);
  useEffect(() => {
    const read = () => {
      const current = actions.current;
      if (document.visibilityState === "hidden" || !globalThis.navigator.onLine ||
          current.preview.isFetching || current.error ||
          globalThis.performance.now() < cooldown.current) return;
      void current.preview.refetch();
    };
    const start = globalThis.setTimeout(read, 0);
    const interval = globalThis.setInterval(read, 2000);
    const visibility = () => {
      const active = document.visibilityState !== "hidden" && globalThis.navigator.onLine;
      setVisible(active);
      if (!active) void client.cancelQueries({ queryKey: key });
      else read();
    };
    document.addEventListener("visibilitychange", visibility);
    globalThis.addEventListener("online", visibility);
    globalThis.addEventListener("offline", visibility);
    return () => {
      globalThis.clearTimeout(start); globalThis.clearInterval(interval);
      document.removeEventListener("visibilitychange", visibility);
      globalThis.removeEventListener("online", visibility);
      globalThis.removeEventListener("offline", visibility);
      void client.cancelQueries({ queryKey: key });
    };
  }, [client, user, series.base, series.quote, series.timeframe]);
  useEffect(() => {
    if (error instanceof ApiRequestError && error.status === 401) {
      void client.cancelQueries({ queryKey: key });
      actions.current.browsing.cancel();
    }
  }, [error, client, user, series.base, series.quote, series.timeframe]);
  // A new native candle boundary triggers one bounded latest-page read. Historical
  // browsing stays in place; no indicator recalculation or proof is involved.
  useEffect(() => {
    const end = preview.data?.rows.at(-1)?.open_at;
    const latest = browsing.latest;
    const lastStored = latest?.rows.at(-1)?.open_at;
    if (end && latest && (!lastStored || Date.parse(end) > Date.parse(lastStored)) && !error && visible) {
      browsing.refreshLatest(end);
    }
  }, [preview.data, browsing.latest, browsing.loading, error, visible]);
  return { preview, browsing, error, visible,
    cooldownActive: globalThis.performance.now() < Math.max(cooldown.current, retryAt, browsing.retryAt ?? 0),
    retry: () => {
      if (!visible || globalThis.performance.now() < cooldown.current) return;
      rateError.current = undefined;
      browsing.retry();
      void preview.refetch();
    },
  };
}
