import type { components } from "./api-types";
import { send } from "./auth";

export type Catalog = components["schemas"]["CatalogResponse"];
export type CatalogEntry = components["schemas"]["CatalogPairView"];
export type Impact = components["schemas"]["ImpactResponse"];

export function readSupportedSymbols(signal?: AbortSignal): Promise<Catalog> {
  return send<Catalog>("/admin/supported-symbols", undefined, undefined, "GET", signal);
}

export function readSymbolImpact(base: string, quote: string, signal?: AbortSignal): Promise<Impact> {
  return send<Impact>(`/admin/supported-symbols/${base}/${quote}/impact`, undefined, undefined, "GET", signal);
}

export function addSupportedSymbol(base: string, revision: number, code: string, idempotencyKey: string): Promise<unknown> {
  return send("/admin/supported-symbols", {
    base, quote: "USDT", expected_revision: revision, reason_code: "ADMIN_LIQUIDITY_REVIEWED",
  }, code, "POST", undefined, { "Idempotency-Key": idempotencyKey });
}

export function removeSupportedSymbol(base: string, quote: string, revision: number, code: string, idempotencyKey: string): Promise<unknown> {
  return send(`/admin/supported-symbols/${base}/${quote}`, {
    base, quote, expected_revision: revision, reason_code: "ADMIN_RISK_REVIEW",
  }, code, "DELETE", undefined, { "Idempotency-Key": idempotencyKey });
}
