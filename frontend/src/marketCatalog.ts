import { useQuery } from "@tanstack/react-query";
import type { components } from "./api-types";
import { send } from "./auth";

export type MarketCatalog = components["schemas"]["PublicCatalogResponse"];
export type CatalogPair = components["schemas"]["CatalogPairView"];

export const marketCatalogQueryKey = ["market-catalog"] as const;

export async function fetchMarketCatalog(signal?: AbortSignal): Promise<MarketCatalog> {
  return send<MarketCatalog>("/market-catalog", undefined, undefined, "GET", signal);
}

export function useMarketCatalog() {
  return useQuery({
    queryKey: marketCatalogQueryKey,
    queryFn: ({ signal }) => fetchMarketCatalog(signal),
    staleTime: 0,
  });
}

export function activeBases(catalog: MarketCatalog | undefined): string[] {
  return catalog?.active_pairs.map(([base]) => base) ?? [];
}

export function activePairSet(catalog: MarketCatalog): ReadonlySet<string> {
  return new Set(catalog.active_pairs.map(([base, quote]) => `${base}/${quote}`));
}
