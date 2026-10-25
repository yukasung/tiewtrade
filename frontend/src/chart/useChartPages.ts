import { useEffect, useRef, useState } from "react";
import { ApiRequestError } from "../auth";
import { candlePage, type CandlePage, type PageDirection, type Series } from "./api";

/** Five bounded pages per user/series, one request at a time; never cache across users. */
export function useChartPages(user: string, series: Series, halted = false, blockedUntil = 0, startEnabled = true) {
  const identity = `${user}/${series.base}/${series.quote}/${series.timeframe}`;
  const [state, setState] = useState<{ identity: string; latest?: CandlePage | undefined; page?: CandlePage | undefined;
    error?: unknown; loading: boolean; retryAt: number }>({ identity, loading: false, retryAt: 0 });
  const controller = useRef<AbortController>();
  const cache = useRef(new Map<string, CandlePage>());
  const selected = useRef<PageDirection>({});
  const epoch = useRef(0);
  const cooldown = useRef(0);
  const refreshedBoundary = useRef<string>();

  const load = async (direction: PageDirection, force = false, background = false) => {
    if (controller.current || document.visibilityState === "hidden" || !globalThis.navigator.onLine ||
        (halted && !force) || globalThis.performance.now() < Math.max(cooldown.current, blockedUntil)) return;
    const key = JSON.stringify(direction), currentEpoch = epoch.current;
    if (!background) selected.current = direction;
    const historical = Boolean(direction.before || direction.after);
    const cached = cache.current.get(key);
    if (cached && !force) {
      cache.current.delete(key); cache.current.set(key, cached);
      setState(previous => ({ ...previous, identity, page: historical ? cached : undefined, error: undefined }));
      return;
    }
    const request = new AbortController(); controller.current = request;
    setState(previous => ({ ...previous, identity, loading: true, error: undefined }));
    try {
      const result = await candlePage(series, direction, AbortSignal.any([request.signal, AbortSignal.timeout(10_000)]));
      if (currentEpoch !== epoch.current || request.signal.aborted) return;
      cache.current.set(key, result);
      while (cache.current.size > 5) cache.current.delete(cache.current.keys().next().value!);
      setState(previous => ({ ...previous, identity, loading: false,
        latest: historical ? previous.latest : result,
        page: background ? previous.page : historical ? result : undefined }));
    } catch (error) {
      if (currentEpoch !== epoch.current || request.signal.aborted) return;
      if (error instanceof ApiRequestError && error.retryAt) {
        cooldown.current = Math.max(cooldown.current, globalThis.performance.now() + Math.max(0, Date.parse(error.retryAt) - Date.now()));
      }
      setState(previous => ({ ...previous, identity, loading: false, error, retryAt: cooldown.current }));
    } finally {
      if (controller.current === request) controller.current = undefined;
    }
  };
  const actions = useRef({ load, halted, error: state.error }); actions.current = { load, halted, error: state.error };
  useEffect(() => {
    epoch.current += 1; cache.current.clear(); selected.current = {};
    refreshedBoundary.current = undefined;
    setState({ identity, loading: false, retryAt: cooldown.current });
    const timer = globalThis.setTimeout(() => {
      if (startEnabled && !actions.current.halted) void actions.current.load({});
    }, 0);
    const suspend = () => {
      if (document.visibilityState === "hidden" || !globalThis.navigator.onLine) {
        controller.current?.abort(); controller.current = undefined;
        setState(previous => ({ ...previous, loading: false }));
      } else if (!actions.current.halted && !actions.current.error) {
        void actions.current.load(selected.current, true);
      }
    };
    document.addEventListener("visibilitychange", suspend); globalThis.addEventListener("offline", suspend);
    globalThis.addEventListener("online", suspend);
    return () => {
      globalThis.clearTimeout(timer); epoch.current += 1;
      controller.current?.abort(); controller.current = undefined;
      document.removeEventListener("visibilitychange", suspend); globalThis.removeEventListener("offline", suspend);
      globalThis.removeEventListener("online", suspend);
    };
  }, [identity, startEnabled]);
  const current = state.identity === identity ? state : undefined;
  useEffect(() => {
    const remaining = state.retryAt - globalThis.performance.now();
    if (remaining <= 0) return;
    const timer = globalThis.setTimeout(() => setState(previous => ({ ...previous, retryAt: 0 })), remaining + 1);
    return () => globalThis.clearTimeout(timer);
  }, [state.retryAt]);
  return { ...current,
    cancel: () => { controller.current?.abort(); controller.current = undefined; },
    refreshLatest: (boundary: string) => {
      if (refreshedBoundary.current === boundary || controller.current || current?.error || halted ||
          globalThis.performance.now() < Math.max(cooldown.current, blockedUntil)) return;
      refreshedBoundary.current = boundary;
      void load({}, true, true);
    },
    navigate: (direction: "older" | "newer") => {
      if (current?.error) return;
      const page = current?.page ?? current?.latest;
      const boundary = direction === "older" ? page?.older_before : page?.newer_after;
      if (boundary) void load(direction === "older" ? { before: boundary } : { after: boundary });
    },
    reset: () => { selected.current = {}; controller.current?.abort(); controller.current = undefined;
      setState(previous => ({ ...previous, page: undefined, loading: false, error: undefined })); },
    retry: () => { void load(selected.current, true); },
  };
}
