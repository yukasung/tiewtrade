import type { components } from "./api-types";
import { send } from "./auth";
import { createSafeRequest } from "./apiRequest";
export type Protection = components["schemas"]["ProtectionView"];
export type ProtectionRequest = components["schemas"]["ProtectionRequestView"];
export type ProtectionCreate = components["schemas"]["ProtectionCreateInput"];
export type ProtectionReplace = components["schemas"]["ProtectionReplaceInput"];
export type ProtectionCancel = components["schemas"]["ProtectionCancelInput"];
export type ProtectionAction = "CREATE" | "REPLACE" | "CANCEL";
export const protectionKey = (owner: string) => ["protections", owner, "PAPER"] as const;
const safe = createSafeRequest({
  allowedCodes: ["ORDER_CONFLICT", "ORDER_INPUT_INVALID", "PROTECTION_INPUT_REJECTED", "PROTECTION_NOT_FOUND", "PROTECTION_EPISODE_CLOSED", "ORDER_SAFETY_UNAVAILABLE"],
  fallbackCode: "PROTECTION_UNAVAILABLE",
  preserveAbort: true,
  preserveRetryAfter: true,
});

export const fetchProtections = (episode: string, cursor: string | null, signal?: AbortSignal) => safe(send<components["schemas"]["ProtectionPage"]>(`/paper/protections?episode_id=${encodeURIComponent(episode)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, "GET", signal));
export const fetchProtectionRequests = (cursor: string | null, signal?: AbortSignal) => safe(send<components["schemas"]["ProtectionRequestPage"]>(`/paper/protection-requests?state=unresolved${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, undefined, undefined, "GET", signal));
export const fetchProtectionKey = (key: string, action: ProtectionAction, signal?: AbortSignal) => safe(send<ProtectionRequest>(`/paper/protection-requests/by-key/${encodeURIComponent(key)}?action=${action}`, undefined, undefined, "GET", signal));
export const postProtection = (action: ProtectionAction, target: string | undefined, payload: ProtectionCreate | ProtectionReplace | ProtectionCancel, key: string) => safe(send<ProtectionRequest>(action === "CREATE" ? "/paper/protections" : `/paper/protections/${encodeURIComponent(target ?? "")}/${action.toLowerCase()}`, payload, undefined, "POST", undefined, { "Idempotency-Key": key }));

export const fetchProtectionRequest = (id: string, signal?: AbortSignal) => safe(send<ProtectionRequest>(`/paper/protection-requests/${encodeURIComponent(id)}`, undefined, undefined, "GET", signal));
