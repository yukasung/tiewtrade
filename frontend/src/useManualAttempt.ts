import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiRequestError } from "./auth";
import { clearAttempt, readAttempt, writeAttempt, type ManualAttempt } from "./manualOrderJournal";
import { fetchRequestKey, manualKey, postCancelOrder, postNewOrder, requestTerminal, type ManualRequest } from "./manualOrders";

export function useManualAttempt(owner: string, visible: boolean) {
  const client = useQueryClient();
  const [stored] = useState(() => { try { return { attempt: readAttempt(owner), failed: false }; } catch { return { attempt: null, failed: true }; } });
  const [attempt, setAttempt] = useState(stored.attempt);
  const [storageError, setStorageError] = useState(stored.failed);
  const [refusedAttemptKey, setRefusedAttemptKey] = useState("");
  const gate = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const key = [...manualKey(owner), attempt?.payload.expected_episode_id ?? null, "attempt", attempt?.action, attempt?.key] as const;
  const lookup = useQuery({ queryKey: key, enabled: !!attempt && visible,
    queryFn: async ({ signal }) => {
      if (!attempt) throw new Error("missing attempt");
      const value = await fetchRequestKey(attempt.key, attempt.action, signal);
      if (value.mode !== "PAPER" || value.idempotency_key !== attempt.key || value.action !== attempt.action ||
          value.episode_id !== attempt.payload.expected_episode_id || value.wallet_id !== attempt.payload.expected_wallet_id ||
          (attempt.action === "CANCEL" && value.order_id !== attempt.orderId)) throw new Error("request scope mismatch");
      return value;
    },
    refetchInterval: query => visible && (!query.state.data || !requestTerminal(query.state.data)) ? 1000 : false,
    refetchIntervalInBackground: false,
  });
  const clearResolvedAttempt = useCallback((expectedKey: string) => {
    try {
      clearAttempt(owner, expectedKey);
      setAttempt(null);
    } catch {
      setStorageError(true);
    }
  }, [owner]);
  const mutation = useMutation({ mutationFn: (value: ManualAttempt) => value.action === "NEW" ? postNewOrder(value.payload, value.key) : postCancelOrder(value.orderId, value.payload, value.key),
    onSuccess: (value, sent) => {
      if (!mounted.current) return;
      if (value.mode !== "PAPER" || value.idempotency_key !== sent.key || value.action !== sent.action ||
          value.wallet_id !== sent.payload.expected_wallet_id || value.episode_id !== sent.payload.expected_episode_id) return;
      client.setQueryData([...manualKey(owner), sent.payload.expected_episode_id, "attempt", sent.action, sent.key], value);
      void client.invalidateQueries({ queryKey: manualKey(owner) });
      void client.invalidateQueries({ queryKey: ["paper-wallet", owner] });
    },
    onError: (error, sent) => {
      // Only documented input refusals or permanent closure proof resolve an attempt.
      // Transport failures, lookup404 and generic409 preserve the recovery identity.
      if (!mounted.current || !(error instanceof ApiRequestError)) return;
      const episodeClosed = error.status === 409 && error.message === "MANUAL_ORDER_EPISODE_CLOSED";
      const inputRejected = error.status === 422 &&
        ["MANUAL_ORDER_INPUT_REJECTED", "ORDER_UNSUPPORTED"].includes(error.message);
      if (!episodeClosed && !inputRejected) return;
      if (episodeClosed) {
        setRefusedAttemptKey(sent.key);
        void client.invalidateQueries({ queryKey: manualKey(owner) });
      }
      clearResolvedAttempt(sent.key);
    },
    onSettled: () => { gate.current = false; },
  });
  const finish = useCallback((value: ManualRequest) => {
    if (!attempt || value.idempotency_key !== attempt.key || !requestTerminal(value)) return;
    clearResolvedAttempt(attempt.key);
  }, [attempt, clearResolvedAttempt]);
  const send = (value: ManualAttempt, retry = false) => {
    if (gate.current || storageError || value.owner !== owner) return;
    try {
      const existing = readAttempt(owner);
      if (existing && (!retry || existing.key !== value.key || JSON.stringify(existing) !== JSON.stringify(value))) return;
      writeAttempt(value); // synchronous write + read-back precedes the POST, including retry.
      setAttempt(value);
      gate.current = true;
      mutation.mutate(value);
    } catch { setStorageError(true); }
  };
  const error = mutation.error instanceof ApiRequestError ? mutation.error : null;
  return { attempt, storageError, refusedAttemptKey, send, lookup, finish, busy: mutation.isPending, error };
}
