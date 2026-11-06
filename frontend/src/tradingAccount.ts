import type { components } from "./api-types";
import { send } from "./auth";
import { createSafeRequest } from "./apiRequest";
export type TradingAccountView = components["schemas"]["TradingAccountView"];
export type SelectTradingUseRequest =
  components["schemas"]["SelectTradingUseRequest"];
const codes = [
  "TRADING_ACCOUNT_ACTIVITY_UNKNOWN",
  "TRADING_ACCOUNT_INPUT_REJECTED",
];
/** Preserve documented codes/status only; never retain raw proxy/server errors. */
const safe = createSafeRequest({
  allowedCodes: codes,
  fallbackCode: "TRADING_ACCOUNT_REQUEST_FAILED",
  preserveAbort: false,
  preserveRetryAfter: true,
});

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
): Promise<TradingAccountView> {
  return safe(send<TradingAccountView>("/trading-account/use", input));
}
