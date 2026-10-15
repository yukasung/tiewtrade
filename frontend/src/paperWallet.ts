import type { components } from "./api-types";
import { ApiRequestError, send } from "./auth";

export type PaperCommandView = components["schemas"]["PaperCommandView"];
export type PaperWalletEnvelope = components["schemas"]["PaperWalletEnvelope"];
export type PaperWalletMutation = components["schemas"]["PaperWalletMutation"];

const documentedCodes = new Set([
  "ACTIVITY_UNKNOWN",
  "EPISODE_CONFLICT",
  "IDEMPOTENCY_CONFLICT",
  "INITIAL_CAPITAL_INVALID",
  "INITIAL_CAPITAL_TOO_SMALL",
  "PAPER_WALLET_INPUT_REJECTED",
  "PAPER_WALLET_DEPENDENCY_UNAVAILABLE",
  "RESET_UNSAFE",
  "WALLET_EXISTS",
]);

async function safe<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (cause: unknown) {
    const apiError = cause instanceof ApiRequestError ? cause : null;
    throw new ApiRequestError(
      apiError !== null && documentedCodes.has(apiError.message)
        ? apiError.message
        : "PAPER_WALLET_REQUEST_FAILED",
      apiError?.status ?? 0,
      apiError?.retryAt ?? null,
    );
  }
}

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
