import { send } from "./auth";
import { createSafeRequest } from "./apiRequest";
import type { RiskEffects } from "./riskLimits";

export type StopMode = "PAPER" | "LIVE";
export type StopStatus = {
  active_causes: Array<"USER" | "SYSTEM" | "LOSS_LIMIT">;
  mode: StopMode; stop_id: string | null; cause: "USER" | "SYSTEM" | "LOSS_LIMIT" | "PLATFORM" | null;
  generation: number | null; revision: number; summary_revision: number; progress: "STOPPING" | "STOPPED" | "PROBLEMS" | null;
  target_set_complete: boolean; target_count: number; pending_count: number; failed_count: number;
  platform_stop_id: string | null; platform_reason: string | null; resume_ready: boolean;
  reconciliation_revision: number | null; capability: "AVAILABLE" | "LIVE_EXECUTION_UNAVAILABLE";
};
export type StopReceipt = { request_id: string; stop_id: string; mode: StopMode | "PLATFORM"; action: "STOP" | "RESUME"; cause: string; generation: number; revision: number; state: "REQUEST_PENDING" | "APPLIED" | "REJECTED"; failure_code: string | null; recorded_at: string };
export type StopSummary = { status: StopStatus; positions: Array<{ base: string; quote: string; quantity: string }>; snapshot_revision: number; reconciled_at: string | null };
export type PlatformStopStatus = { stop_id: string | null; revision: number; summary_revision: number; reconciliation_revision: number; reason: string | null; progress: "STOPPING" | "STOPPED" | "PROBLEMS" | null; discovery_complete: boolean; owner_count: number; pending_count: number; failed_count: number; can_resume: boolean };

const path = (mode: StopMode) => `/${mode === "PAPER" ? "paper" : "live"}/kill-switch`;
const safe = createSafeRequest({
  allowedCodes: ["TRADING_STOP_UNAVAILABLE", "TRADING_STOP_NOT_FOUND", "TRADING_STOP_REQUEST_NOT_FOUND", "TRADING_STOP_IDEMPOTENCY_CONFLICT", "PLATFORM_NOT_AUTHORIZED", "PLATFORM_OWNER_REQUIRED"],
  fallbackCode: "TRADING_STOP_REQUEST_FAILED",
  preserveAbort: true,
  preserveRetryAfter: false,
});

export const stopKey = (owner: string, mode: StopMode) => ["kill-switch", owner, mode] as const;
export const fetchStopStatus = (mode: StopMode, signal?: AbortSignal) => safe(send<StopStatus>(path(mode), undefined, undefined, "GET", signal));
export const postStop = (mode: StopMode, key: string) => safe(send<StopReceipt>(`${path(mode)}/stop`, undefined, undefined, "POST", undefined, { "Idempotency-Key": key }));
export const fetchStopRequestByKey = (mode: StopMode, key: string) => safe(send<StopReceipt>(`${path(mode)}/requests/by-key/${encodeURIComponent(key)}?action=STOP`, undefined, undefined, "GET"));
export const fetchStopRequestById = (mode: StopMode, requestId: string, signal?: AbortSignal) => safe(send<StopReceipt>(`${path(mode)}/requests/${encodeURIComponent(requestId)}`, undefined, undefined, "GET", signal));
export const fetchStopSummary = (mode: StopMode, stop: string, signal?: AbortSignal) => safe(send<StopSummary>(`${path(mode)}/stops/${encodeURIComponent(stop)}/resume-summary`, undefined, undefined, "GET", signal));
export const fetchStopEffects = (mode: StopMode, stop: string, cursor: string | null, signal?: AbortSignal) => safe(send<RiskEffects>(`${path(mode)}/stops/${encodeURIComponent(stop)}/effects?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, "GET", signal));
export const postResume = (mode: StopMode, summary: StopSummary, key: string) => safe(send<StopReceipt>(`${path(mode)}/resume`, { expected_stop_id: summary.status.stop_id, expected_revision: summary.status.revision, expected_summary_revision: summary.snapshot_revision, expected_reconciliation_revision: summary.status.reconciliation_revision ?? 0 }, undefined, "POST", undefined, { "Idempotency-Key": key }));
export const fetchPlatformStop = (signal?: AbortSignal) => safe(send<PlatformStopStatus>("/admin/kill-switch", undefined, undefined, "GET", signal));
export const fetchPlatformRequestById = (requestId: string, signal?: AbortSignal) => safe(send<StopReceipt>(`/admin/kill-switch/requests/${encodeURIComponent(requestId)}`, undefined, undefined, "GET", signal));
export const postPlatformStop = (reason: string, key: string) => safe(send<StopReceipt>("/admin/kill-switch/stop", { reason }, undefined, "POST", undefined, { "Idempotency-Key": key }));
export const postPlatformResume = (status: PlatformStopStatus, key: string) => safe(send<StopReceipt>("/admin/kill-switch/resume", { expected_stop_id: status.stop_id, expected_revision: status.revision, expected_summary_revision: status.summary_revision, expected_reconciliation_revision: status.reconciliation_revision }, undefined, "POST", undefined, { "Idempotency-Key": key }));
