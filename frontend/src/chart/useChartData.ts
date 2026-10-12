import { skipToken, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiRequestError, send } from "../auth";
import { live, verify, type ChartLive, type Series, type Window } from "./api";
import { readEpisode, wait } from "./readEpisode";

export function useChartData(user: string, series: Series, window?: Window) {
  const client = useQueryClient();
  const [nonce, setNonce] = useState(0);
  const [visible, setVisible] = useState(document.visibilityState !== "hidden" && globalThis.navigator.onLine);
  const [tick, setTick] = useState(0);
  const successfulAt = useRef(-Infinity), proofAt = useRef(-Infinity);
  const rebuilt = useRef<string | null>(null);
  const cooldown = useRef(0);
  const liveDue = useRef(0);
  const episodeKey = ["chart", user, "primary_spot", series.base, series.quote, series.timeframe, window, nonce] as const;
  const query = useQuery({ queryKey: episodeKey, enabled: false, retry: false, gcTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false, networkMode: "always",
    queryFn: async ({ signal }) => {
      const result = await readEpisode({ ...series, ...window }, signal);
      successfulAt.current = globalThis.performance.now();
      proofAt.current = successfulAt.current;
      return result;
    },
  });
  const first = query.data?.pages[0];
  const proofKey = [...episodeKey, "proof", first?.dataset_revision] as const;
  const proof = useQuery({ queryKey: proofKey, enabled: false, retry: false, gcTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false, networkMode: "always",
    queryFn: async ({ signal }) => {
      if (!first) throw new Error("CHART_INVALID_RESPONSE");
      const bounded = AbortSignal.any([signal, AbortSignal.timeout(30_000)]);
      const result = await verify(first.display_proof, bounded);
      if (bounded.aborted) throw bounded.reason;
      if (result.status === "MATCHED") proofAt.current = globalThis.performance.now();
      return result;
    },
  });
  const preview = useQuery<ChartLive>({ queryKey: [...episodeKey, "live"], enabled: false, retry: false, gcTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false, networkMode: "always",
    queryFn: ({ signal }) => live(series, AbortSignal.any([signal, AbortSignal.timeout(3000)])),
  });
  const refreshState = useQuery<boolean>({ queryKey: [...episodeKey, "refresh"], enabled: false,
    queryFn: skipToken, retry: false, gcTime: 0, refetchOnWindowFocus: false, refetchOnReconnect: false });
  const stopped = Boolean(query.error || proof.error || preview.error || refreshState.error);
  const actions = useRef({ query, proof, preview, first, refreshState });
  actions.current = { query, proof, preview, first, refreshState };

  useEffect(() => {
    if (stopped) void client.cancelQueries({ queryKey: episodeKey });
  }, [client, stopped, user, series.base, series.quote, series.timeframe, window?.start, window?.end, nonce]);

  useEffect(() => {
    successfulAt.current = -Infinity; proofAt.current = -Infinity;
    rebuilt.current = null;
    // Allow the cancelled server reader its approved 2s cleanup window before
    // starting another reader on mount/remount or a new series. This is not a 429 retry.
    liveDue.current = globalThis.performance.now() + 4000;
    const start = globalThis.setTimeout(() => {
      if (document.visibilityState !== "hidden" && globalThis.navigator.onLine) {
        void actions.current.query.refetch();
        liveDue.current = globalThis.performance.now() + 2000;
        void actions.current.preview.refetch();
      }
    }, 2000);
    return () => { globalThis.clearTimeout(start); void client.cancelQueries({ queryKey: episodeKey }); };
    // episodeKey is determined by these scalar UI selections.
  }, [client, user, series.base, series.quote, series.timeframe, window?.start, window?.end, nonce]);

  useEffect(() => {
    const visibility = () => {
      const active = document.visibilityState !== "hidden" && globalThis.navigator.onLine;
      setVisible(active);
      proofAt.current = -Infinity;
      if (!active) void client.cancelQueries({ queryKey: episodeKey });
      else if (!actions.current.query.isFetching && !actions.current.query.error &&
          !actions.current.proof.error && !actions.current.refreshState.error && Date.now() >= cooldown.current) {
        liveDue.current = globalThis.performance.now() + 2000;
        void actions.current.preview.refetch();
        if (actions.current.first) void actions.current.proof.refetch();
        else void actions.current.query.refetch();
      }
    };
    document.addEventListener("visibilitychange", visibility);
    globalThis.addEventListener("online", visibility);
    globalThis.addEventListener("offline", visibility);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      globalThis.removeEventListener("online", visibility);
      globalThis.removeEventListener("offline", visibility);
    };
  }, [client, user, series.base, series.quote, series.timeframe, window?.start, window?.end, nonce]);

  useEffect(() => {
    if (!visible || stopped) return;
    const timer = globalThis.setInterval(() => {
      setTick(value => value + 1);
      const { query, proof, preview, first, refreshState } = actions.current;
      if (!preview.isFetching && !preview.error && globalThis.performance.now() >= liveDue.current) {
        liveDue.current = globalThis.performance.now() + 2000;
        void preview.refetch();
      }
      if (first && !query.isFetching && !proof.isFetching && !refreshState.isFetching &&
          !query.error && !proof.error &&
          globalThis.performance.now() - proofAt.current >= 15_000 && proof.data?.status !== "CHANGED" &&
          proof.data?.status !== "UNVERIFIABLE") void proof.refetch();
    }, 1000);
    return () => globalThis.clearInterval(timer);
  }, [visible, stopped]);

  useEffect(() => {
    if (!visible || stopped || query.isFetching || proof.isFetching || refreshState.isFetching ||
        query.error || proof.error || !first) return;
    const sourceChanged = proof.data?.status === "CHANGED";
    const ended = preview.data?.history_end;
    const newEligible = !window && ended && ended > first.calculation_end;
    const reason = sourceChanged ? first.dataset_revision : newEligible ? ended : null;
    if (reason && rebuilt.current !== reason) {
      rebuilt.current = reason;
      void query.refetch();
    }
  }, [visible, stopped, first, proof.data, proof.error, proof.isFetching, refreshState.isFetching, preview.data, query, window]);

  useEffect(() => {
    if (!query.data || query.isFetching) return;
    // A successful bundle proves itself; remove proof results for the superseded read.
    void client.resetQueries({ queryKey: proofKey, exact: true });
  }, [client, query.dataUpdatedAt]);

  for (const error of [query.error, proof.error, preview.error]) {
    if (error instanceof ApiRequestError && error.retryAt) cooldown.current = Math.max(cooldown.current, Date.parse(error.retryAt));
  }
  const retry = () => { if (Date.now() >= cooldown.current) setNonce(value => value + 1); };
  const refresh = async () => {
    const target = first?.refresh.target;
    if (!target || query.isFetching || refreshState.isFetching || Date.now() < cooldown.current) return;
    const key = [...episodeKey, "refresh"];
    await client.fetchQuery({ queryKey: key, retry: false, gcTime: 0, queryFn: async ({ signal }) => {
      const posted = await send<{ accepted: boolean }>("/market-data/candles/requests", target, undefined, "POST",
        AbortSignal.any([signal, AbortSignal.timeout(30_000)]));
      if (posted.accepted) {
        const started = globalThis.performance.now();
        for (let count = 0; count < 6; count += 1) {
          await wait(10_000, signal);
          const remaining = 60_000 - (globalThis.performance.now() - started);
          if (remaining <= 0) throw new ApiRequestError("CHART_READ_BUDGET_EXHAUSTED", 503);
          const params = new URLSearchParams({ ...target, limit: "1000" });
          const result = await send<{ status: string | null }>(`/market-data/candles?${params}`, undefined, undefined, "GET",
            AbortSignal.any([signal, AbortSignal.timeout(Math.min(3000, remaining))]));
          if (result.status === "COMPLETE") break;
          if (result.status === "FAILED" || result.status === "UNAVAILABLE") throw new ApiRequestError("CHART_DELIVERY_FAILED", 503);
          if (count === 5) throw new ApiRequestError("CHART_READ_BUDGET_EXHAUSTED", 503);
        }
      }
      return true;
    } });
    retry();
  };
  void tick; // local elapsed-time tick; no financial calculation or finality inference.
  const valid = visible && !stopped && !query.isFetching && !proof.isFetching && !refreshState.isFetching &&
    proof.data?.status !== "CHANGED" && proof.data?.status !== "UNVERIFIABLE" &&
    globalThis.performance.now() - proofAt.current <= 45_000;
  return { query, proof, preview, refreshState, visible, valid, stopped, retry, refresh, cooldown: cooldown.current };
}
