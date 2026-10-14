import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useRef, useState } from "react";

import {
  addApiKey,
  deleteApiKey,
  fetchApiKeys,
  retryApiKey,
} from "./apiKeys";
import { keyText as t, keyTime, keyState } from "./apiKeyMessages";
import { ApiRequestError, type Me } from "./auth";
import { navigateAccountPage } from "./accountNavigation";
import "./ApiKeyPanel.css";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";

function failure(error: Error | null): string | null {
  if (error === null) return null;
  if (!(error instanceof ApiRequestError)) return t("uncertain");
  switch (error.status) {
    case 401:
      return t("unauthorized");
    case 403:
      return t("forbidden");
    case 400:
    case 422:
      return t("invalid");
    case 404:
      return t("missing");
    case 409:
      return t("conflict");
    case 429:
      return error.retryAt === null
        ? t("limitedUnknown")
        : t("limited", { at: keyTime(error.retryAt) });
    default:
      return t("uncertain");
  }
}

export function ApiKeyPanel({ identity }: { identity: Me }): JSX.Element {
  const client = useQueryClient();
  const queryKey = ["api-keys", identity.user_id];
  const accountQueryKey = ["trading-account", identity.user_id];
  const query = useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      const rows = await fetchApiKeys(signal);
      void client.invalidateQueries({
        queryKey: accountQueryKey,
        exact: true,
      });
      return rows;
    },
    refetchInterval: (current) =>
      current.state.error instanceof ApiRequestError &&
      current.state.error.status === 401
        ? false
        : 5000,
    refetchIntervalInBackground: false,
  });
  const name = useRef<HTMLInputElement>(null);
  const key = useRef<HTMLInputElement>(null);
  const secret = useRef<HTMLInputElement>(null);
  const code = useRef<HTMLInputElement>(null);
  const submitting = useRef(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [refreshUnconfirmed, setRefreshUnconfirmed] = useState(false);
  const refresh = async (): Promise<boolean> => {
    // Key reads invalidate the account query too. Await keys first, then the
    // final account request, so cancellation of an earlier refetch is not
    // mistaken for confirmation. Query invalidation can swallow fetch errors.
    await client.invalidateQueries({ queryKey, exact: true });
    await client.invalidateQueries({ queryKey: accountQueryKey, exact: true });
    const keysState = client.getQueryState(queryKey);
    const accountState = client.getQueryState(accountQueryKey);
    const fresh =
      keysState !== undefined &&
      [keysState, accountState].every(
        (state) =>
          state === undefined ||
          (state.status === "success" &&
            state.fetchStatus === "idle" &&
            !state.isInvalidated),
      );
    setRefreshUnconfirmed(!fresh);
    return fresh;
  };
  async function showNoticeAfterRefresh(
    message: "added" | "retried" | "deleted",
  ): Promise<void> {
    if (await refresh()) setNotice(t(message));
  }
  const add = useMutation({
    // ไม่มี variables: ห้ามส่งคำรับรองเข้า mutation cache แม้เป็นเพียงชั่วคราว
    mutationFn: () => {
      try {
        return addApiKey(
          {
            label: name.current?.value ?? "",
            key: key.current?.value ?? "",
            secret: secret.current?.value ?? "",
          },
          code.current?.value ?? "",
        );
      } finally {
        // clear ก่อน await: คำขอยังรอคำตอบหรือถูกปฏิเสธก็ต้องไม่มีค่ากรอกเหลือ
        for (const input of [key.current, secret.current, code.current])
          if (input) input.value = "";
      }
    },
    onSuccess: () => showNoticeAfterRefresh("added"),
    onSettled: () => {
      submitting.current = false;
    },
  });
  const retry = useMutation({
    mutationFn: retryApiKey,
    onSuccess: () => showNoticeAfterRefresh("retried"),
    onError: refresh,
  });
  const remove = useMutation({
    mutationFn: deleteApiKey,
    onSuccess: () => {
      setDeleting(null);
      return showNoticeAfterRefresh("deleted");
    },
    onError: refresh,
  });
  const busy = add.isPending || retry.isPending || remove.isPending;
  const actionError = add.error ?? retry.error ?? remove.error;
  const expired = [query.error, actionError].some(
    (error) => error instanceof ApiRequestError && error.status === 401,
  );
  const stale =
    query.isError || query.fetchStatus === "paused" || refreshUnconfirmed;
  const hasKey = (query.data?.length ?? 0) > 0;
  const selected = query.data?.find((item) => item.id === deleting);
  function resetFeedback(): void {
    add.reset();
    retry.reset();
    remove.reset();
    setNotice(null);
  }

  return (
    <section
      className="api-key-panel"
      aria-labelledby="api-key-heading"
      data-testid="api-key-panel"
    >
      <h2 id="api-key-heading">{t("heading")}</h2>
      <p>{t("oneKey")}</p>
      <aside className="api-key-guidance" aria-label={t("heading")}>
        <p>{t("spotWarning")}</p>
        <p>{t("whitelistWarning")}</p>
      </aside>
      {expired ? (
        <p role="alert">{t("unauthorized")}</p>
      ) : (
        <>
          {identity.totp_enabled ? (
            <form
              aria-label={t("add")}
              onSubmit={(event) => {
                event.preventDefault();
                if (busy || stale || hasKey || submitting.current) return;
                resetFeedback();
                submitting.current = true;
                add.mutate();
              }}
            >
              <p>{t("totpHelp")}</p>
              <fieldset
                className="api-key-fields"
                disabled={busy || stale || hasKey}
              >
                <Label htmlFor="api-key-name">
                  {t("name")}
                  <Input
                    id="api-key-name"
                    name="label"
                    ref={name}
                    required
                    maxLength={40}
                    autoComplete="off"
                  />
                </Label>
                <Label htmlFor="api-key-key">
                  {t("key")}
                  <Input
                    id="api-key-key"
                    name="key"
                    ref={key}
                    type="password"
                    required
                    maxLength={256}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </Label>
                <Label htmlFor="api-key-secret">
                  {t("secret")}
                  <Input
                    id="api-key-secret"
                    name="secret"
                    ref={secret}
                    type="password"
                    required
                    maxLength={256}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </Label>
                <Label htmlFor="api-key-code">
                  {t("totp")}
                  <Input
                    id="api-key-code"
                    name="totp"
                    ref={code}
                    required
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    autoComplete="one-time-code"
                  />
                </Label>
              </fieldset>
              <Button type="submit" disabled={busy || stale || hasKey}>
                {t(add.isPending ? "adding" : "add")}
              </Button>
            </form>
          ) : (
            <p>
              {t("totpRequired")} <a href="/security" onClick={navigateAccountPage}>{t("enableTotp")}</a>
            </p>
          )}
          {actionError !== null && notice === null && (
            <p role="alert">{failure(actionError)}</p>
          )}
          {notice !== null && !stale && <p role="status">{notice}</p>}
          <div className="api-key-list-heading">
            <h3>{t("list")}</h3>
            <Button
              type="button"
              disabled={busy || query.isFetching}
              onClick={() => {
                setNotice(null);
                void refresh();
              }}
            >
              {t("refresh")}
            </Button>
          </div>
          {query.isPending && <p role="status">{t("loading")}</p>}
          {stale && (
            <p role="alert">
              {t(refreshUnconfirmed ? "refreshUnconfirmed" : "stale")}
            </p>
          )}
          {query.data?.length === 0 && <p>{t("empty")}</p>}
          <ul className="api-key-list">
            {query.data?.map((item) => (
              <li key={item.id}>
                <div>
                  <h4>
                    {item.label}{" "}
                    <code>{t("tail", { tail: item.public_tail })}</code>
                  </h4>
                  <p className="api-key-state" aria-live="polite">
                    {keyState(item.status)}
                  </p>
                  {item.failure_code === "VERIFICATION_EXPIRED" && (
                    <p>{t("expired")}</p>
                  )}
                  {item.status === "REJECTED" &&
                    item.failure_code !== "VERIFICATION_EXPIRED" && (
                      <p>{t("badCredential")}</p>
                    )}
                  {item.status === "UNVERIFIABLE" && (
                    <p>
                      {t(
                        item.failure_code === "VENUE_REJECTED"
                          ? "manualRetry"
                          : "temporary",
                      )}
                    </p>
                  )}
                  <p>{t("created", { at: keyTime(item.created_at) })}</p>
                  {item.verified_at && (
                    <p>{t("verified", { at: keyTime(item.verified_at) })}</p>
                  )}
                  {item.not_before && (
                    <p>{t("waitUntil", { at: keyTime(item.not_before) })}</p>
                  )}
                  {item.next_attempt_at && (
                    <p>
                      {t("nextAttempt", { at: keyTime(item.next_attempt_at) })}
                    </p>
                  )}
                </div>
                <div className="api-key-actions">
                  {item.status === "UNVERIFIABLE" && (
                    <Button
                      type="button"
                      disabled={busy || stale || !item.may_retry}
                      onClick={() => {
                        if (busy || stale || !item.may_retry) return;
                        resetFeedback();
                        retry.mutate(item.id);
                      }}
                    >
                      {t("retry")}
                    </Button>
                  )}
                  <Button
                    type="button"
                    disabled={busy || stale}
                    onClick={() => {
                      resetFeedback();
                      setDeleting(item.id);
                    }}
                  >
                    {t("remove")}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
          {selected && (
            <fieldset className="api-key-confirmation" disabled={busy}>
              <legend>{t("confirmation")}</legend>
              <p>
                {t("deleteHelp", {
                  name: selected.label,
                  tail: selected.public_tail,
                })}
              </p>
              <Button
                type="button"
                disabled={busy || stale}
                onClick={() => {
                  if (!busy && !stale) {
                    resetFeedback();
                    remove.mutate(selected.id);
                  }
                }}
              >
                {t("confirmDelete")}
              </Button>
              <Button
                type="button"
                onClick={() => {
                  setDeleting(null);
                }}
              >
                {t("cancel")}
              </Button>
            </fieldset>
          )}
        </>
      )}
    </section>
  );
}
