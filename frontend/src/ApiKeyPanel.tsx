import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { type JSX, useEffect, useRef, useState } from "react";

import {
  addApiKey,
  deleteApiKey,
  fetchApiKeys,
  retryApiKey,
  type KeyView,
} from "./apiKeys";
import { keyText as t, keyTime } from "./apiKeyMessages";
import { ApiRequestError, type Me } from "./auth";
import "./ApiKeyPanel.css";

/** เปลี่ยนผู้ใช้ = เปลี่ยน cache ทั้งก้อน · ไม่เก็บ cache เมื่อออกจากหน้าจอ */
export function ApiKeyPanel({ identity }: { identity: Me }): JSX.Element {
  return <KeySession key={identity.user_id} identity={identity} />;
}

function KeySession({ identity }: { identity: Me }): JSX.Element {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, gcTime: 0 },
          mutations: { retry: false, gcTime: 0, networkMode: "always" },
        },
      }),
  );
  useEffect(
    () => () => {
      client.clear();
    },
    [client],
  );
  return (
    <QueryClientProvider client={client}>
      <KeyWorkspace identity={identity} />
    </QueryClientProvider>
  );
}

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

function stateOf(item: KeyView): string {
  switch (item.status) {
    case "PENDING":
      return t("pending");
    case "ACTIVE":
      return t("active");
    case "REJECTED":
      return t("rejected");
    case "UNVERIFIABLE":
      return t("unverifiable");
    default:
      return t("unknown");
  }
}

function KeyWorkspace({ identity }: { identity: Me }): JSX.Element {
  const client = useQueryClient();
  const queryKey = ["api-keys", identity.user_id];
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => fetchApiKeys(signal),
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
  const refresh = (): void => {
    void client.invalidateQueries({ queryKey });
  };
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
    onSuccess: () => {
      setNotice(t("added"));
      refresh();
    },
    onSettled: () => {
      submitting.current = false;
    },
  });
  const retry = useMutation({
    mutationFn: retryApiKey,
    onSuccess: () => {
      setNotice(t("retried"));
      refresh();
    },
    onError: refresh,
  });
  const remove = useMutation({
    mutationFn: deleteApiKey,
    onSuccess: () => {
      setDeleting(null);
      setNotice(t("deleted"));
      refresh();
    },
    onError: refresh,
  });
  const busy = add.isPending || retry.isPending || remove.isPending;
  const actionError = add.error ?? retry.error ?? remove.error;
  const expired = [query.error, actionError].some(
    (error) => error instanceof ApiRequestError && error.status === 401,
  );
  const stale = query.isError || query.fetchStatus === "paused";
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
                if (busy || submitting.current) return;
                resetFeedback();
                submitting.current = true;
                add.mutate();
              }}
            >
              <p>{t("totpHelp")}</p>
              <fieldset className="api-key-fields" disabled={busy}>
                <label htmlFor="api-key-name">
                  {t("name")}
                  <input
                    id="api-key-name"
                    name="label"
                    ref={name}
                    required
                    maxLength={40}
                    autoComplete="off"
                  />
                </label>
                <label htmlFor="api-key-key">
                  {t("key")}
                  <input
                    id="api-key-key"
                    name="key"
                    ref={key}
                    type="password"
                    required
                    maxLength={256}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </label>
                <label htmlFor="api-key-secret">
                  {t("secret")}
                  <input
                    id="api-key-secret"
                    name="secret"
                    ref={secret}
                    type="password"
                    required
                    maxLength={256}
                    autoComplete="off"
                    spellCheck={false}
                  />
                </label>
                <label htmlFor="api-key-code">
                  {t("totp")}
                  <input
                    id="api-key-code"
                    name="totp"
                    ref={code}
                    required
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    autoComplete="one-time-code"
                  />
                </label>
              </fieldset>
              <button type="submit" disabled={busy}>
                {t(add.isPending ? "adding" : "add")}
              </button>
            </form>
          ) : (
            <p>
              {t("totpRequired")} <a href="#totp-panel">{t("enableTotp")}</a>
            </p>
          )}
          {actionError !== null && notice === null && (
            <p role="alert">{failure(actionError)}</p>
          )}
          {notice !== null && <p role="status">{notice}</p>}
          <div className="api-key-list-heading">
            <h3>{t("list")}</h3>
            <button
              type="button"
              disabled={busy || query.isFetching}
              onClick={() => {
                void query.refetch();
              }}
            >
              {t("refresh")}
            </button>
          </div>
          {query.isPending && <p role="status">{t("loading")}</p>}
          {stale && <p role="alert">{t("stale")}</p>}
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
                    {stateOf(item)}
                  </p>
                  {item.failure_code === "VERIFICATION_EXPIRED" && (
                    <p>{t("expired")}</p>
                  )}
                  {item.status === "REJECTED" &&
                    item.failure_code !== "VERIFICATION_EXPIRED" && (
                      <p>{t("badCredential")}</p>
                    )}
                  {item.status === "UNVERIFIABLE" && (
                    <p>{t(item.failure_code === "VENUE_REJECTED" ? "manualRetry" : "temporary")}</p>
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
                    <button
                      type="button"
                      disabled={busy || stale || !item.may_retry}
                      onClick={() => {
                        if (busy || stale || !item.may_retry) return;
                        resetFeedback();
                        retry.mutate(item.id);
                      }}
                    >
                      {t("retry")}
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={busy || stale}
                    onClick={() => {
                      resetFeedback();
                      setDeleting(item.id);
                    }}
                  >
                    {t("remove")}
                  </button>
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
              <button
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
              </button>
              <button
                type="button"
                onClick={() => {
                  setDeleting(null);
                }}
              >
                {t("cancel")}
              </button>
            </fieldset>
          )}
        </>
      )}
    </section>
  );
}
