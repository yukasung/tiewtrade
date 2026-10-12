import type { components } from "../api-types";
import { ApiRequestError, send } from "../auth";

export type ChartHistory = components["schemas"]["ChartHistoryView"];
export type ChartLive = components["schemas"]["ChartLiveView"];
export type ChartProof = components["schemas"]["ChartProofView"];
export type Candle = components["schemas"]["CandleView"];
export type Point = components["schemas"]["IndicatorPointView"];
export type Timeframe = components["schemas"]["Timeframe"];
export type Series = { base: string; quote: string; timeframe: Timeframe };
export type Window = { start: string; end: string };
export type HistoryParameters = (Series & Partial<Window>) | { cursor: string };

/** Bound bytes before JSON decoding or caching, including responses without Content-Length. */
async function get<T>(path: string, parameters: object, signal: AbortSignal): Promise<T> {
  const query = new URLSearchParams(parameters as Record<string, string>);
  const response = await fetch(`/api/market-data/chart/${path}?${query}`, {
    credentials: "same-origin", signal,
  });
  const reader = response.body?.getReader();
  if (!reader) throw new ApiRequestError("CHART_INVALID_RESPONSE", 503);
  const chunks: Uint8Array[] = [];
  let size = 0;
  let complete = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) { complete = true; break; }
      size += value.byteLength;
      if (size > 2 * 1024 * 1024) throw new ApiRequestError("INDICATOR_RESOURCE_LIMIT", 503);
      chunks.push(value);
    }
  } finally {
    try { if (!complete) await reader.cancel(); }
    catch { /* An aborted/errored body can reject cancellation; preserve the read failure. */ }
    finally { reader.releaseLock(); }
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let body: unknown;
  try { body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new ApiRequestError("CHART_INVALID_RESPONSE", 503); }
  if (!response.ok) {
    const detail = (body as { detail?: unknown })?.detail;
    throw new ApiRequestError(typeof detail === "string" ? detail : "CHART_DELIVERY_FAILED",
      response.status, response.headers.get("Retry-After"));
  }
  return body as T;
}

export function history(parameters: HistoryParameters, signal: AbortSignal): Promise<ChartHistory> {
  return get("history", parameters, signal);
}
export function live(series: Series, signal: AbortSignal): Promise<ChartLive> {
  return get("live", series, signal);
}
export function verify(display_proof: string, signal: AbortSignal): Promise<ChartProof> {
  return send("/market-data/chart/verify", { display_proof }, undefined, "POST", signal);
}
