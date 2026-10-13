import { skipToken, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiRequestError, send } from "../auth";
import { candles, live, verify, type ChartLive, type Series, type Window } from "./api";
import { readEpisode, wait } from "./readEpisode";

export function useChartData(user: string, series: Series, window?: Window) {
  const client = useQueryClient();
  const [nonce, setNonce] = useState(0);
  const [visible, setVisible] = useState(document.visibilityState !== "hidden" && globalThis.navigator.onLine);
  const [tick, setTick] = useState(0);
  const successfulAt = useRef(-Infinity), proofAt = useRef(-Infinity);
  const rebuilt = useRef<string | null>(null);
  const cooldown = useRef(0);
  const cooldownErrors = useRef(new WeakSet<ApiRequestError>());
  const liveDue = useRef(0);
  const readerCleanupUntil = useRef(0);
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
  const provisional = useQuery({ queryKey: [...episodeKey, "candles"], enabled: false, retry: false, gcTime: 0,
    refetchOnWindowFocus: false, refetchOnReconnect: false, networkMode: "always",
    queryFn: ({ signal }) => candles(series, window, AbortSignal.any([signal, AbortSignal.timeout(10_000)])),
  });
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
  const actions = useRef({ query, proof, preview, provisional, first, refreshState });
  actions.current = { query, proof, preview, provisional, first, refreshState };

  useEffect(() => {
    if (stopped) void client.cancelQueries({ queryKey: episodeKey });
  }, [client, stopped, user, series.base, series.quote, series.timeframe, window?.start, window?.end, nonce]);

  useEffect(() => {
    successfulAt.current = -Infinity; proofAt.current = -Infinity;
    rebuilt.current = null;
    // Only a cancelled history/proof reader needs the server cleanup window.
    liveDue.current = globalThis.performance.now() + 4000;
    const previewStart = globalThis.setTimeout(() => {
      if (document.visibilityState !== "hidden" && globalThis.navigator.onLine) {
        void actions.current.preview.refetch();
        void actions.current.provisional.refetch();
      }
    }, 0);
    const start = globalThis.setTimeout(() => {
      if (document.visibilityState !== "hidden" && globalThis.navigator.onLine) {
        void actions.current.query.refetch();
      }
    }, Math.max(0, readerCleanupUntil.current - globalThis.performance.now()));
    return () => {
      globalThis.clearTimeout(previewStart);
      globalThis.clearTimeout(start);
      if (client.isFetching({ queryKey: episodeKey, exact: true }) ||
          client.isFetching({ queryKey: [...episodeKey, "proof"] })) {
        readerCleanupUntil.current = globalThis.performance.now() + 2000;
      }
      void client.cancelQueries({ queryKey: episodeKey });
    };
    // episodeKey is determined by these scalar UI selections.
  }, [client, user, series.base, series.quote, series.timeframe, window?.start, window?.end, nonce]);

  useEffect(() => {
    const visibility = () => {
      const active = document.visibilityState !== "hidden" && globalThis.navigator.onLine;
      setVisible(active);
      proofAt.current = -Infinity;
      if (!active) void client.cancelQueries({ queryKey: episodeKey });
      else if (!actions.current.query.isFetching && !actions.current.query.error &&
          !actions.current.proof.error && !actions.current.refreshState.error &&
          globalThis.performance.now() >= cooldown.current) {
        liveDue.current = globalThis.performance.now() + 2000;
        void actions.current.preview.refetch();
        if (actions.current.first) void actions.current.proof.refetch();
        else {
          void actions.current.query.refetch();
          if (!actions.current.provisional.data && !actions.current.provisional.error &&
              !actions.current.provisional.isFetching) void actions.current.provisional.refetch();
        }
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

  for (const error of [query.error, proof.error, preview.error, refreshState.error, provisional.error]) {
    if (error instanceof ApiRequestError && error.retryAt && !cooldownErrors.current.has(error)) {
      cooldownErrors.current.add(error);
      const retryAt = Date.parse(error.retryAt);
      if (Number.isFinite(retryAt)) {
        const cooldownDuration = Math.max(0, retryAt - Date.now());
        cooldown.current = Math.max(cooldown.current, globalThis.performance.now() + cooldownDuration);
      }
    }
  }
  const cooldownActive = globalThis.performance.now() < cooldown.current;
  useEffect(() => {
    const cooldownRemaining = cooldown.current - globalThis.performance.now();
    if (cooldownRemaining <= 0) return;
    // Terminal errors intentionally stop network timers. Wake the view once at
    // Retry-After so the manual retry control does not remain disabled forever.
    const cooldownTimer = globalThis.setTimeout(() => setTick(value => value + 1), cooldownRemaining + 1);
    return () => globalThis.clearTimeout(cooldownTimer);
  }, [query.error, proof.error, preview.error, refreshState.error, provisional.error, nonce]);
  const retry = () => {
    if (globalThis.performance.now() >= cooldown.current) setNonce(value => value + 1);
  };
  const refresh = async () => {
    const target = first?.refresh.target;
    if (!target || query.isFetching || refreshState.isFetching ||
        globalThis.performance.now() < cooldown.current) return;
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
  return { query, proof, preview, provisional, refreshState, visible, valid, stopped, retry, refresh, cooldownActive };
}
