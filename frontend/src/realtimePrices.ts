import type { components } from "./api-types";
import { ApiRequestError, send } from "./auth";
export type PricesView = components["schemas"]["PricesView"];
export const priceQueryKey = ["market-data", "prices"] as const;
const bases = new Set(["BTC", "ETH", "SOL", "XRP", "DOGE"]);
function record(value: unknown): value is Record<string, unknown> {
    return value !== null && typeof value === "object" && !Array.isArray(value);
}
function time(value: unknown): boolean {
    return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value));
}
/** Reject untrusted transport data without retaining raw payload/error text. */
export function decodePrices(value: unknown): PricesView {
    const invalid = () => new ApiRequestError("PRICE_DELIVERY_FAILED", 0);
    if (!record(value) || value.schema_version !== 1 || !time(value.server_time) || !["CONNECTED", "RECOVERING"].includes(String(value.delivery_status)) || !Array.isArray(value.rows) || value.rows.length !== 5)
        throw invalid();
    const seen = new Set<string>();
    for (const row of value.rows) {
        if (!record(row) || typeof row.base !== "string" || !bases.has(row.base) || seen.has(row.base) || row.quote !== "USDT" || row.source !== "primary_spot" || (row.amount !== null && (typeof row.amount !== "string" || !/^\d+(?:\.\d+)?$/.test(row.amount))) || !["MISSING", "RECOVERING", "STALE", "READY"].includes(String(row.readiness)) || typeof row.reason !== "string" || !/^[A-Z_]+$/.test(row.reason) || typeof row.alert_due !== "boolean")
            throw invalid();
        for (const key of ["revision", "generation"])
            if (typeof row[key] !== "string" || !/^\d{1,20}$/.test(row[key]))
                throw invalid();
        for (const key of ["trade_at", "received_at", "valid_until", "unavailable_since"])
            if (row[key] !== null && !time(row[key]))
                throw invalid();
        seen.add(row.base);
    }
    return value as PricesView;
}
function reference(value: string): string {
    const [second, fraction = ""] = value.replace(/(?:Z|\+00:00)$/, "").split(".");
    return `${second}.${fraction.padEnd(6, "0")}`;
}
/** Whole-view guards preserve quote and delivery ordering together. */
export function acceptPrices(current: PricesView | undefined, next: PricesView): PricesView {
    if (!current)
        return next;
    if (reference(next.server_time) < reference(current.server_time))
        return current;
    for (const row of next.rows) {
        const old = current.rows.find((item) => item.base === row.base && item.source === row.source);
        if (old && (BigInt(row.generation) < BigInt(old.generation) || (row.generation === old.generation && BigInt(row.revision) < BigInt(old.revision))))
            return current;
    }
    return next;
}
export async function fetchPrices(signal: AbortSignal): Promise<PricesView> {
    try {
        return decodePrices(await send<unknown>("/market-data/prices", undefined, undefined, "GET", signal));
    }
    catch (error) {
        throw new ApiRequestError("PRICE_DELIVERY_FAILED", error instanceof ApiRequestError ? error.status : 0);
    }
}
