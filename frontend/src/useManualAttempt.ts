import { useMemo } from "react";
import type { QueryClient } from "@tanstack/react-query";
import type { ApiRequestError } from "./auth";
import { clearAttempt, readAttempt, writeAttempt, type ManualAttempt } from "./manualOrderJournal";
import { fetchRequestKey, manualKey, postCancelOrder, postNewOrder, requestTerminal, type ManualRequest } from "./manualOrders";
import { useDurableAttempt } from "./useDurableAttempt";

const journal = { read: readAttempt, write: writeAttempt, clear: clearAttempt };
const matches = (value: ManualRequest, sent: ManualAttempt) => value.mode === "PAPER" &&
  value.idempotency_key === sent.key && value.action === sent.action &&
  value.wallet_id === sent.payload.expected_wallet_id && value.episode_id === sent.payload.expected_episode_id &&
  (sent.action !== "CANCEL" || value.order_id === sent.orderId);
export function useManualAttempt(owner: string, visible: boolean) {
  const options = useMemo(() => ({
    scope: owner, visible, journal,
    queryKey: (attempt: ManualAttempt | null) => [...manualKey(owner), attempt?.payload.expected_episode_id ?? null, "attempt", attempt?.action, attempt?.key],
    fetch: (attempt: ManualAttempt, signal: AbortSignal) => fetchRequestKey(attempt.key, attempt.action, signal),
    post: (value: ManualAttempt) => value.action === "NEW" ? postNewOrder(value.payload, value.key) : postCancelOrder(value.orderId, value.payload, value.key),
    matches, terminal: requestTerminal,
    received: (client: QueryClient) => {
      void client.invalidateQueries({ queryKey: manualKey(owner) });
      void client.invalidateQueries({ queryKey: ["paper-wallet", owner] });
    },
    refusal: (error: ApiRequestError) =>
      error.status === 409 && error.message === "MANUAL_ORDER_EPISODE_CLOSED" ||
      error.status === 422 && ["MANUAL_ORDER_INPUT_REJECTED", "ORDER_UNSUPPORTED"].includes(error.message),
  }), [owner, visible]);
  const recovery = useDurableAttempt(options);
  return { ...recovery, send: (value: ManualAttempt, retry = false) => {
    if (value.owner === owner) recovery.send(value, retry);
  } };
}
