import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { ApiRequestError, type Me } from "./auth";
import { navigateAccountPage } from "./accountNavigation";
import { keyText, keyState, keyTime } from "./apiKeyMessages";
import {
  fetchTradingAccount,
  selectTradingUse,
  type SelectTradingUseRequest,
  type TradingAccountView,
} from "./tradingAccount";
import { tradingAccountText as t } from "./tradingAccountMessages";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import "./TradingAccountPanel.css";
function failure(error: unknown): string {
  if (!(error instanceof ApiRequestError)) return t("uncertain");
  if (error.message === "TRADING_ACCOUNT_ACTIVITY_UNKNOWN")
    return t("immutable");
  if (error.message === "TRADING_ACCOUNT_KEY_UNAVAILABLE")
    return t("unavailable");
  switch (error.status) {
    case 401:
      return t("unauthorized");
    case 403:
      return t("forbidden");
    case 400:
    case 422:
      return t("invalid");
    case 409:
      return t("unavailable");
    case 429:
      return t("limited");
    default:
      return t("uncertain");
  }
}
export function TradingAccountPanel({ identity }: { identity: Me }) {
  const client = useQueryClient();
  const queryKey = ["trading-account", identity.user_id];
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => fetchTradingAccount(signal),
  });
  const [use, setUse] = useState<SelectTradingUseRequest["use"] | "">("");
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const code = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const mutation = useMutation({
    mutationFn: () => {
      try {
        if (use === "")
          throw new ApiRequestError("TRADING_ACCOUNT_INPUT_REJECTED", 422);
        return selectTradingUse({ use }, code.current?.value ?? "");
      } finally {
        if (code.current) code.current.value = "";
      }
    },
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey, exact: true });
      const confirmed = client.getQueryState<TradingAccountView>(queryKey);
      if (confirmed?.status === "success" && confirmed.data?.use === use) {
        setNotice(t("selected"));
      }
    },
    onError: (error) => setActionError(failure(error)),
    onSettled: () => {
      submitting.current = false;
      mutation.reset();
    },
  });
  const stale = query.isError || query.fetchStatus === "paused";
  const account = query.data;
  const active = account?.key?.status === "ACTIVE";
  const busy = mutation.isPending;
  const disabled =
    busy ||
    stale ||
    !active ||
    use === "" ||
    !identity.totp_enabled ||
    account?.use !== null;
  return (
    <section
      className="trading-account-panel"
      aria-labelledby="trading-account-heading"
      data-testid="trading-account-panel"
    >
      <div className="trading-account-heading">
        <h2 id="trading-account-heading">{t("heading")}</h2>
        <Button
          disabled={query.isFetching || busy}
          onClick={() => {
            void query.refetch();
          }}
        >
          {t("refresh")}
        </Button>
      </div>
      <p>{t("limitation")}</p>
      {query.isPending && <p role="status">{t("loading")}</p>}
      {stale && <p role="alert">{t("stale")}</p>}
      {account && (
        <>
          <div className="trading-account-summary">
            {account.key ? (
              <>
                <h3>
                  {account.key.label}{" "}
                  <code>
                    {keyText("tail", { tail: account.key.public_tail })}
                  </code>
                </h3>
                <p aria-live="polite">{keyState(account.key.status)}</p>
                <p>
                  {keyText("created", { at: keyTime(account.key.created_at) })}
                </p>
              </>
            ) : (
              <p aria-live="polite">{t("disconnected")}</p>
            )}
          </div>
          {account.use === null ? (
            <>
              <p>{t("unselected")}</p>
              {!active ? (
                <p>{t("keyRequired")}</p>
              ) : !identity.totp_enabled ? (
                <p>
                  <a href="/security" onClick={navigateAccountPage}>{t("totpRequired")}</a>
                </p>
              ) : (
                <form
                  aria-label={t("select")}
                  onSubmit={(event) => {
                    event.preventDefault();
                    if (disabled || submitting.current) return;
                    submitting.current = true;
                    setNotice(null);
                    setActionError(null);
                    mutation.mutate();
                  }}
                >
                  <p id="trading-account-totp-help">{t("totpHelp")}</p>
                  <fieldset
                    className="trading-account-fields"
                    disabled={busy || stale}
                  >
                    <Label htmlFor="trading-account-use">
                      {t("use")}
                      <Select
                        id="trading-account-use"
                        name="use"
                        required
                        value={use}
                        onChange={(event) =>
                          setUse(
                            event.target.value === "BOT"
                              ? "BOT"
                              : event.target.value === "MANUAL"
                                ? "MANUAL"
                                : "",
                          )
                        }
                      >
                        <option value="" disabled>
                          {t("placeholder")}
                        </option>
                        <option value="MANUAL">{t("manual")}</option>
                        <option value="BOT">{t("bot")}</option>
                      </Select>
                    </Label>
                    <Label htmlFor="trading-account-code">
                      {t("totp")}
                      <Input
                        id="trading-account-code"
                        name="totp"
                        ref={code}
                        required
                        inputMode="numeric"
                        pattern="[0-9]{6}"
                        maxLength={6}
                        autoComplete="one-time-code"
                        aria-invalid={actionError !== null}
                        aria-describedby={
                          actionError
                            ? "trading-account-totp-help trading-account-error"
                            : "trading-account-totp-help"
                        }
                      />
                    </Label>
                  </fieldset>
                  <Button type="submit" disabled={disabled}>
                    {t(busy ? "selecting" : "select")}
                  </Button>
                </form>
              )}
            </>
          ) : (
            <div>
              <h3>{t(account.use === "BOT" ? "bot" : "manual")}</h3>
              <Button disabled aria-describedby="trading-account-change-reason">
                {t("change")}
              </Button>
              <p id="trading-account-change-reason">{t("immutable")}</p>
            </div>
          )}
        </>
      )}
      {actionError && (
        <p id="trading-account-error" role="alert">
          {actionError}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
