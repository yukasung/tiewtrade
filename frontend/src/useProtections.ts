import { useInfiniteQuery, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { ApiRequestError } from "./auth";
import { useDurableAttempt } from "./useDurableAttempt";
import { protectionJournal, type ProtectionAttempt } from "./protectionJournal";
import { fetchProtections, fetchProtectionRequests, fetchProtectionKey, fetchProtectionRequest, postProtection, protectionKey, type ProtectionRequest } from "./protections";
import { manualKey } from "./manualOrders";
export function useProtections(owner: string, episode: string | null, visible: boolean) {
  const query = useInfiniteQuery({ queryKey: [...protectionKey(owner), episode], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => fetchProtections(episode!, pageParam, signal),
    enabled: !!episode && visible, getNextPageParam: page => page.next_cursor ?? undefined,
    refetchInterval: visible ? 1000 : false, refetchIntervalInBackground: false });
  useEffect(() => { if (query.hasNextPage && !query.isFetchingNextPage && visible) void query.fetchNextPage(); }, [query.hasNextPage, query.isFetchingNextPage, query.fetchNextPage, visible]);
  return { query, rows: query.data?.pages.flatMap(p => p.protections) ?? [], ready: query.isSuccess && !query.isError && !query.hasNextPage && !query.isFetchingNextPage };
}
export function useProtectionAttempt(owner: string, visible: boolean) {
  const client = useQueryClient();
  const [lastId, setLastId] = useState<string | null>(null);
  const discovery = useInfiniteQuery({ queryKey: [...protectionKey(owner), "unresolved"], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => fetchProtectionRequests(pageParam, signal), getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: visible, refetchInterval: visible ? 1000 : false, refetchIntervalInBackground: false });
  useEffect(() => { if (discovery.hasNextPage && !discovery.isFetchingNextPage && visible) void discovery.fetchNextPage(); }, [discovery.hasNextPage, discovery.isFetchingNextPage, discovery.fetchNextPage, visible]);
  const options = useMemo(() => ({ scope: owner, visible, journal: protectionJournal,
    queryKey: (a: ProtectionAttempt | null) => [...protectionKey(owner), "attempt", a?.action, a?.key],
    fetch: (a: ProtectionAttempt, signal: AbortSignal) => fetchProtectionKey(a.key, a.action, signal),
    post: (a: ProtectionAttempt) => postProtection(a.action, a.target, a.payload, a.key),
    matches: (v: ProtectionRequest, a: ProtectionAttempt) => v.mode === "PAPER" && v.idempotency_key === a.key && v.action === a.action && v.episode_id === a.payload.expected_episode_id && (a.action === "CREATE" || v.protection_id === a.target),
    terminal: (v: ProtectionRequest) => v.state !== "PENDING",
    received: (c: QueryClient, receipt: ProtectionRequest) => { setLastId(receipt.request_id); void c.invalidateQueries({ queryKey: protectionKey(owner) }); void c.invalidateQueries({ queryKey: manualKey(owner) }); },
    refusal: (e: ApiRequestError) => e.status === 422 || e.status === 409 && e.message === "PROTECTION_EPISODE_CLOSED",
  }), [owner, visible]);
  const recovery = useDurableAttempt(options);
  useEffect(() => {
    if (recovery.lookup.data && recovery.lookup.data.state !== "PENDING") {
      setLastId(recovery.lookup.data.request_id);
      recovery.finish(recovery.lookup.data);
      void client.invalidateQueries({ queryKey: manualKey(owner) });
      void client.invalidateQueries({ queryKey: protectionKey(owner) });
    }
  }, [recovery.lookup.data, recovery.finish, client, owner]);
  const result = useQuery({ queryKey: [...protectionKey(owner), "result", lastId],
    queryFn: ({ signal }) => fetchProtectionRequest(lastId!, signal), enabled: !!lastId && visible,
    refetchInterval: query => visible && query.state.data?.state === "PENDING" ? 1000 : false,
    refetchIntervalInBackground: false });
  const pending = discovery.data?.pages.flatMap(p => p.requests) ?? [];
  return { ...recovery, discovery, pending, result, recovered: discovery.isSuccess && !discovery.isError && !discovery.hasNextPage && !discovery.isFetchingNextPage };
}
