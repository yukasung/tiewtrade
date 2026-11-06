import type { components } from "./api-types";
import { send } from "./auth";
import { createSafeRequest } from "./apiRequest";
export type RiskMode = "PAPER" | "LIVE";
export type RiskSnapshot = components["schemas"]["RiskLimitView"];
export type RiskReceipt = components["schemas"]["RiskRequestView"];
export type RiskEffects = components["schemas"]["RiskEffectPage"];
export type RiskPayload = components["schemas"]["RiskExpectedScope"] | components["schemas"]["RiskLimitMutation"];
export type RiskAction = RiskReceipt["action"];
export const riskKey = (owner: string, mode: RiskMode) => ["risk-limit", owner, mode] as const;
const path = (mode: RiskMode) => `/${mode === "PAPER" ? "paper" : "live"}/risk-limit`;
const safe = createSafeRequest({
  allowedCodes: ["RISK_INPUT_INVALID", "RISK_SOURCE_UNAVAILABLE", "RISK_REVISION_CONFLICT", "RISK_SCOPE_CONFLICT", "RISK_REQUEST_CONFLICT", "RISK_REQUEST_NOT_FOUND", "RISK_EFFECT_CURSOR_INVALID"],
  fallbackCode: "RISK_REQUEST_FAILED",
  statusFallbacks: new Map([[403, "RISK_AUTHORIZATION_REQUIRED"], [429, "RISK_RATE_LIMITED"]]),
  preserveAbort: true,
  preserveRetryAfter: true,
});

export const fetchRisk = (mode: RiskMode, signal?: AbortSignal) => safe(send<RiskSnapshot>(path(mode), undefined, undefined, "GET", signal));
export const fetchRiskKey = (mode: RiskMode, key: string, signal?: AbortSignal) => safe(send<RiskReceipt>(`${path(mode)}/requests/by-key/${encodeURIComponent(key)}`, undefined, undefined, "GET", signal));
export const fetchRiskReceipt = (mode: RiskMode, id: string, signal?: AbortSignal) => safe(send<RiskReceipt>(`${path(mode)}/requests/${encodeURIComponent(id)}`, undefined, undefined, "GET", signal));
export const fetchRiskEffects = (mode: RiskMode, stop: string, cursor: string | null, signal?: AbortSignal) => safe(send<RiskEffects>(`${path(mode)}/stops/${encodeURIComponent(stop)}/effects?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, "GET", signal));
export const postRisk = (mode: RiskMode, action: RiskAction, payload: RiskPayload, key: string, code?: string) => safe(send<RiskReceipt>(`${path(mode)}${action === "INCREASE" ? "/increase" : action === "RESET" ? "/reset" : ""}`, payload, code, "POST", undefined, { "Idempotency-Key": key }));
export const riskTerminal = (value: RiskReceipt) => value.state === "APPLIED" || value.state === "REJECTED";
