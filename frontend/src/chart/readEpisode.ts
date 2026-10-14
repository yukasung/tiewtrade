import { ApiRequestError } from "../auth";
import { history, type ChartHistory, type HistoryParameters } from "./api";

export type ChartRead = { pages: ChartHistory[] };
type Reader = (parameters: HistoryParameters, signal: AbortSignal) => Promise<ChartHistory>;

export function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { globalThis.clearTimeout(timer);
      reject(signal.reason instanceof Error ? signal.reason : new DOMException("Aborted", "AbortError")); };
    const timer = globalThis.setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, milliseconds);
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}

/** One finite logical read includes all pages, readiness waits and its single 409 restart. */
export async function readEpisode(
  initial: HistoryParameters, signal: AbortSignal, reader: Reader = history,
  clock: () => number = () => globalThis.performance.now(),
): Promise<ChartRead> {
  const started = clock();
  let attempts = 0, restarted = false;
  let pages: ChartHistory[] = [];
  let parameters = initial;
  while (!signal.aborted) {
    const remaining = 300_000 - (clock() - started);
    if (attempts >= 12 || remaining <= 0) break;
    attempts += 1;
    const timeout = AbortSignal.timeout(Math.max(1, Math.floor(Math.min(30_000, remaining))));
    try {
      const page = await reader(parameters, AbortSignal.any([signal, timeout]));
      if (signal.aborted) throw signal.reason;
      if (timeout.aborted) throw timeout.reason;
      if (clock() - started >= 300_000) throw new ApiRequestError("CHART_READ_BUDGET_EXHAUSTED", 503);
      const first = pages[0];
      if (!first && "base" in initial && (page.base !== initial.base ||
          page.quote !== initial.quote || page.timeframe !== initial.timeframe)) {
        throw new ApiRequestError("CHART_INVALID_RESPONSE", 503);
      }
      if (page.formula_version !== "indicators-v2" ||
          page.rows.length > 1000 || page.candles.length > 1000 ||
          (first && (first.dataset_revision !== page.dataset_revision || first.as_of !== page.as_of ||
          first.formula_version !== page.formula_version || first.base !== page.base ||
          first.quote !== page.quote || first.timeframe !== page.timeframe))) {
        throw new ApiRequestError("CHART_INVALID_RESPONSE", 503);
      }
      pages.push(page);
      if (!page.next_cursor) return { pages };
      parameters = { cursor: page.next_cursor };
    } catch (error) {
      if (signal.aborted) throw signal.reason;
      if (error instanceof ApiRequestError && error.status === 409 && !restarted) {
        restarted = true;
        pages = [];
        parameters = initial;
        continue;
      }
      if (error instanceof ApiRequestError && error.status === 503 &&
          (error.message === "INDICATOR_DATA_NOT_READY" || error.message === "INDICATOR_BUSY") &&
          !pages.length && !("cursor" in parameters)) {
        const minimumSpacing = error.message === "INDICATOR_BUSY" ? 2000 : 10_000;
        const spacing = Math.max(minimumSpacing, error.retryAt ? Date.parse(error.retryAt) - Date.now() : 0);
        if (spacing >= 300_000 - (clock() - started) || attempts >= 12) break;
        await wait(spacing, signal);
        continue;
      }
      throw error;
    }
  }
  if (signal.aborted) throw signal.reason;
  throw new ApiRequestError("CHART_READ_BUDGET_EXHAUSTED", 503);
}
