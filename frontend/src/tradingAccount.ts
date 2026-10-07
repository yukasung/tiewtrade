import type { components } from "./api-types";
import { ApiRequestError, send } from "./auth";
export type TradingAccountView = components["schemas"]["TradingAccountView"];
export type SelectTradingUseRequest =
  components["schemas"]["SelectTradingUseRequest"];
const codes = new Set([
  "TRADING_ACCOUNT_ACTIVITY_UNKNOWN",
  "TRADING_ACCOUNT_KEY_UNAVAILABLE",
  "TRADING_ACCOUNT_INPUT_REJECTED",
]);
/** Preserve documented codes/status only; never retain raw proxy/server errors. */
async function safe<T>(request: Promise<T>): Promise<T> {
  try {
    return await request;
  } catch (cause: unknown) {
    throw new ApiRequestError(
      cause instanceof ApiRequestError && codes.has(cause.message)
        ? cause.message
        : "TRADING_ACCOUNT_REQUEST_FAILED",
      cause instanceof ApiRequestError ? cause.status : 0,
      cause instanceof ApiRequestError ? cause.retryAt : null,
    );
  }
}
export function fetchTradingAccount(
  signal?: AbortSignal,
): Promise<TradingAccountView> {
  return safe(
    send<TradingAccountView>(
      "/trading-account",
      undefined,
      undefined,
      "GET",
      signal,
    ),
  );
}
export function selectTradingUse(
  input: SelectTradingUseRequest,
  code: string,
): Promise<TradingAccountView> {
  return safe(send<TradingAccountView>("/trading-account/use", input, code));
}
