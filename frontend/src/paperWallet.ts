import type { components } from "./api-types";
import { send } from "./auth";
import { createSafeRequest } from "./apiRequest";

export type PaperCommandView = components["schemas"]["PaperCommandView"];
export type PaperWalletEnvelope = components["schemas"]["PaperWalletEnvelope"];
export type PaperWalletMutation = components["schemas"]["PaperWalletMutation"];
export type PaperWalletReset = components["schemas"]["PaperWalletReset"];

const documentedCodes = [
  "ACTIVITY_UNKNOWN",
  "EPISODE_CONFLICT",
  "IDEMPOTENCY_CONFLICT",
  "INITIAL_CAPITAL_INVALID",
  "INITIAL_CAPITAL_TOO_SMALL",
  "PAPER_WALLET_INPUT_REJECTED",
  "PAPER_WALLET_DEPENDENCY_UNAVAILABLE",
  "RESET_UNSAFE",
  "WALLET_EXISTS",
];

const safe = createSafeRequest({
  allowedCodes: documentedCodes,
  fallbackCode: "PAPER_WALLET_REQUEST_FAILED",
  preserveAbort: false,
  preserveRetryAfter: true,
});

export function fetchPaperWallet(signal?: AbortSignal): Promise<PaperWalletEnvelope> {
  return safe(send<PaperWalletEnvelope>("/paper-wallet", undefined, undefined, "GET", signal));
}

export function createPaperWallet(
  input: PaperWalletMutation,
  idempotencyKey: string,
): Promise<PaperCommandView> {
  return safe(
    send<PaperCommandView>("/paper-wallet", input, undefined, "POST", undefined, {
      "Idempotency-Key": idempotencyKey,
    }),
  );
}

export function resetPaperWallet(
  input: PaperWalletReset,
  idempotencyKey: string,
): Promise<PaperCommandView> {
  return safe(
    send<PaperCommandView>("/paper-wallet/reset", input, undefined, "POST", undefined, {
      "Idempotency-Key": idempotencyKey,
    }),
  );
}

export function fetchPaperCommand(
  commandId: string,
  signal?: AbortSignal,
): Promise<PaperCommandView> {
  return safe(
    send<PaperCommandView>(
      `/paper-wallet/commands/${encodeURIComponent(commandId)}`,
      undefined,
      undefined,
      "GET",
      signal,
    ),
  );
}
