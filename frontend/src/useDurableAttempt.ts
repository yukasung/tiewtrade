import { useMutation, useQuery, useQueryClient, type QueryClient, type QueryKey } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiRequestError } from "./auth";
import type { AttemptJournal } from "./attemptJournal";

type Options<T extends { key: string }, R> = {
  scope: string;
  visible: boolean;
  journal: AttemptJournal<T>;
  queryKey: (attempt: T | null) => QueryKey;
  fetch: (attempt: T, signal: AbortSignal) => Promise<R>;
  post: (attempt: T) => Promise<R>;
  matches: (receipt: R, attempt: T) => boolean;
  terminal: (receipt: R) => boolean;
  received: (client: QueryClient, receipt: R, attempt: T) => void;
  refusal: (error: ApiRequestError, attempt: T) => boolean;
};

/** Used by manual orders and risk settings; an unknown response never generates a new identity. */
export function useDurableAttempt<T extends { key: string }, R>(options: Options<T, R>) {
  const { scope, journal } = options;
  const client = useQueryClient();
  const [stored] = useState(() => {
    try { return { attempt: journal.read(scope), failed: false }; }
    catch { return { attempt: null, failed: true }; }
  });
  const [attempt, setAttempt] = useState<T | null>(stored.attempt);
  const [storageError, setStorageError] = useState(stored.failed);
  const [refusedAttemptKey, setRefusedAttemptKey] = useState("");
  const gate = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const lookup = useQuery({
    queryKey: options.queryKey(attempt),
    enabled: attempt !== null && options.visible,
    queryFn: async ({ signal }) => {
      if (attempt === null) throw new Error("missing durable attempt");
      const value = await options.fetch(attempt, signal);
      if (!options.matches(value, attempt)) throw new Error("request scope mismatch");
      return value;
    },
    refetchInterval: query => options.visible && (!query.state.data || !options.terminal(query.state.data)) ? 1000 : false,
    refetchIntervalInBackground: false,
  });
  const clearResolved = useCallback((key: string) => {
    try { journal.clear(scope, key); setAttempt(null); }
    catch { setStorageError(true); }
  }, [journal, scope]);
  const mutation = useMutation({
    mutationFn: options.post,
    onSuccess: (value, sent) => {
      if (!mounted.current || !options.matches(value, sent)) return;
      client.setQueryData(options.queryKey(sent), value);
      options.received(client, value, sent);
    },
    onError: (error, sent) => {
      if (!mounted.current || !(error instanceof ApiRequestError) || !options.refusal(error, sent)) return;
      setRefusedAttemptKey(sent.key);
      clearResolved(sent.key);
    },
    onSettled: () => { gate.current = false; },
  });
  const finish = useCallback((value: R) => {
    if (attempt === null || !options.matches(value, attempt) || !options.terminal(value)) return;
    clearResolved(attempt.key);
  }, [attempt, options.matches, options.terminal, clearResolved]);
  const discard = useCallback((key: string) => {
    try {
      const existing = journal.read(scope);
      if (existing === null || existing.key !== key) return false;
      journal.clear(scope, key);
      setAttempt(null);
      return true;
    } catch {
      setStorageError(true);
      return false;
    }
  }, [journal, scope]);
  const send = (value: T, retry = false) => {
    if (gate.current || storageError) return false;
    try {
      const existing = journal.read(scope);
      if (existing && (!retry || existing.key !== value.key || JSON.stringify(existing) !== JSON.stringify(value))) return false;
      journal.write(value); // Write and read-back synchronously precede every POST.
      setAttempt(value);
      gate.current = true;
      mutation.mutate(value);
      return true;
    } catch { setStorageError(true); return false; }
  };
  const error = mutation.error instanceof ApiRequestError ? mutation.error : null;
  return { attempt, storageError, refusedAttemptKey, send, lookup, finish, discard, busy: mutation.isPending, error };
}
