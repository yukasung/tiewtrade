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
import { PaperWalletPanel } from "./PaperWalletPanel";
import { RiskLimitPanel } from "./RiskLimitPanel";
import { Alert } from "./components/ui/Alert";
import { Button } from "./components/ui/Button";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import "./TradingAccountPanel.css";
function failure(error: unknown): string {
  if (!(error instanceof ApiRequestError)) return t("uncertain");
  if (error.message === "TRADING_ACCOUNT_ACTIVITY_UNKNOWN")
    return t("immutable");
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
  const submitting = useRef(false);
  const mutation = useMutation({
    mutationFn: () => {
      if (use === "")
        throw new ApiRequestError("TRADING_ACCOUNT_INPUT_REJECTED", 422);
      return selectTradingUse({ use });
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
  const busy = mutation.isPending;
  const disabled = busy || stale || use === "" || account?.use !== null;
  return (
    <div className="trading-account-dashboard">
      <section
      className="trading-account-panel template-card rounded-2xl"
      aria-labelledby="trading-account-heading"
      data-testid="trading-account-panel"
    >
      <div className="trading-account-heading">
        <h2 id="trading-account-heading">{t("heading")}</h2>
        <Button
          size="sm"
          variant="outline"
          disabled={query.isFetching || busy}
          onClick={() => {
            void query.refetch();
          }}
        >
          {t("refresh")}
        </Button>
      </div>
      <div className="trading-account-body">
      <p className="trading-account-limitation">{t("limitation")}</p>
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
              <Alert
                variant="info"
                title={t("paperReadyTitle")}
                message={t("paperReady")}
                showLink
                linkHref="/security"
                linkText={t("prepareLive")}
                onLinkClick={navigateAccountPage}
              />
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
                </fieldset>
                <Button type="submit" disabled={disabled}>
                  {t(busy ? "selecting" : "select")}
                </Button>
              </form>
            </>
          ) : (
            <div className="trading-account-use">
              <h3>{t(account.use === "BOT" ? "bot" : "manual")}</h3>
              <Button size="sm" variant="outline" disabled aria-describedby="trading-account-change-reason">
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
      </div>
      </section>
      <div className="trading-account-support-grid">
        <div className="trading-account-wallet"><PaperWalletPanel identity={identity} /></div>
        <div className="trading-account-risk"><RiskLimitPanel owner={identity.user_id} mode="PAPER" /></div>
      </div>
    </div>
  );
}
