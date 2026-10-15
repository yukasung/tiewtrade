import type { components } from "./api-types";

export type SupportedBase = components["schemas"]["PriceRow"]["base"];

export const supportedBases = ["BTC", "ETH"] as const satisfies readonly SupportedBase[];
export const supportedBaseSet: ReadonlySet<string> = new Set(supportedBases);
