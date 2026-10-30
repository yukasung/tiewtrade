import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Me } from "./auth";
import { ApiRequestError } from "./auth";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Modal } from "./components/ui/Modal";
import {
  createPaperWallet,
  fetchPaperCommand,
  fetchPaperWallet,
  type PaperWalletMutation,
  type PaperWalletReset,
  resetPaperWallet,
} from "./paperWallet";
import { paperWalletLocale, paperWalletText as t } from "./paperWalletMessages";
import "./PaperWalletPanel.css";

type Attempt =
  | { action: "CREATE"; idempotencyKey: string; payload: PaperWalletMutation; commandId?: string }
  | { action: "RESET"; idempotencyKey: string; payload: PaperWalletReset; commandId?: string };

function failure(error: unknown): string {
  if (!(error instanceof ApiRequestError)) return t("uncertain");
  switch (error.message) {
    case "INITIAL_CAPITAL_TOO_SMALL":
      return t("tooSmall");
    case "INITIAL_CAPITAL_INVALID":
    case "PAPER_WALLET_INPUT_REJECTED":
      return t("invalid");
    case "WALLET_EXISTS":
      return t("exists");
    case "IDEMPOTENCY_CONFLICT":
      return t("conflict");
    case "EPISODE_CONFLICT":
      return t("resetConflict");
    case "ACTIVITY_UNKNOWN":
      return t("resetUnavailable");
    case "RESET_UNSAFE":
      return t("resetUnsafe");
    default:
      if (error.status === 401) return t("unauthorized");
      if (error.status === 429) return t("limited");
      return t("uncertain");
  }
}

export function PaperWalletPanel({ identity }: { identity: Me }) {
  return <PaperWalletPanelForIdentity key={identity.user_id} identity={identity} />;
}

function PaperWalletPanelForIdentity({ identity }: { identity: Me }) {
  const client = useQueryClient();
  const walletKey = useMemo(() => ["paper-wallet", identity.user_id] as const, [identity.user_id]);
  const [capital, setCapital] = useState("");
  const [resetCapital, setResetCapital] = useState("");
  const [resetTarget, setResetTarget] = useState<{ episodeId: string; sequence: number } | null>(null);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [commandFailure, setCommandFailure] = useState<string | null>(null);
  const resetButton = useRef<HTMLButtonElement>(null);

  const closeReset = useCallback(() => setResetTarget(null), []);
  const finishSuccessfulAttempt = useCallback(() => {
    void client.invalidateQueries({ queryKey: walletKey });
    setAttempt(null);
    setCapital("");
    setResetCapital("");
    setResetTarget(null);
  }, [client, walletKey]);
  const walletQuery = useQuery({
    queryKey: walletKey,
    queryFn: ({ signal }) => fetchPaperWallet(signal),
  });
  const mutation = useMutation({
    mutationFn: (request: Attempt) => request.action === "CREATE"
      ? createPaperWallet(request.payload, request.idempotencyKey)
      : resetPaperWallet(request.payload, request.idempotencyKey),
    onSuccess: command => {
      if (command.state === "SUCCEEDED") {
        finishSuccessfulAttempt();
        return;
      }
      setAttempt(current =>
        current === null ? current : { ...current, commandId: command.command_id },
      );
    },
    onError: error => {
      if (error instanceof ApiRequestError && error.message === "EPISODE_CONFLICT") {
        void client.invalidateQueries({ queryKey: walletKey });
        setResetTarget(null);
      }
      if (
        error instanceof ApiRequestError &&
        error.status >= 400 &&
        error.status < 500 &&
        error.status !== 429
      ) setAttempt(null);
    },
  });
  const commandQuery = useQuery({
    queryKey: ["paper-wallet-command", identity.user_id, attempt?.commandId],
    queryFn: ({ signal }) => fetchPaperCommand(attempt!.commandId!, signal),
    enabled: attempt?.commandId !== undefined,
    refetchInterval: query => attempt?.commandId !== undefined &&
      query.state.data?.state !== "SUCCEEDED" &&
      query.state.data?.state !== "REJECTED" ? 1000 : false,
  });

  const commandState = commandQuery.data?.state;
  useEffect(() => {
    if (commandState === "SUCCEEDED") {
      finishSuccessfulAttempt();
    } else if (commandState === "REJECTED") {
      const code = commandQuery.data?.failure_code ?? "PAPER_WALLET_REJECTED";
      setCommandFailure(code);
      if (code === "EPISODE_CONFLICT") void client.invalidateQueries({ queryKey: walletKey });
      setAttempt(null);
    }
  }, [client, commandQuery.data?.failure_code, commandState, finishSuccessfulAttempt, walletKey]);

  const wallet = walletQuery.data?.wallet;
  useEffect(() => {
    if (resetTarget !== null && wallet?.episode_id !== resetTarget.episodeId) {
      setResetTarget(null);
      setCommandFailure("EPISODE_CONFLICT");
    }
  }, [resetTarget, wallet?.episode_id]);
  const uncertain = mutation.isError && attempt !== null;
  const actionError = mutation.isError
    ? failure(mutation.error)
    : commandFailure !== null
      ? failure(new ApiRequestError(commandFailure, 409))
      : commandQuery.isError
        ? failure(commandQuery.error)
        : null;
  const pending = attempt !== null && !mutation.isError && !commandQuery.isError;
  const resetReason = wallet?.reset_reason === "RESET_UNSAFE"
    ? t("resetUnsafe")
    : wallet?.reset_reason === null || wallet?.reset_reason === undefined
      ? null
      : t("resetUnavailable");

  function submitCreate(): void {
    setCommandFailure(null);
    const request: Attempt = {
      action: "CREATE",
      idempotencyKey: globalThis.crypto.randomUUID(),
      payload: { initial_capital: capital },
    };
    setAttempt(request);
    mutation.mutate(request);
  }

  function submitReset(): void {
    if (resetTarget === null) return;
    if (wallet?.episode_id !== resetTarget.episodeId) {
      setResetTarget(null);
      setCommandFailure("EPISODE_CONFLICT");
      return;
    }
    setCommandFailure(null);
    const request: Attempt = {
      action: "RESET",
      idempotencyKey: globalThis.crypto.randomUUID(),
      payload: {
        initial_capital: resetCapital,
        expected_episode_id: resetTarget.episodeId,
      },
    };
    setAttempt(request);
    setResetTarget(null);
    mutation.mutate(request);
  }

  return (
    <ComponentCard
      className="paper-wallet-panel"
      headingId="paper-wallet-heading"
      title={t("heading")}
      desc={t("description")}
      data-testid="paper-wallet-panel"
    >
      {walletQuery.isPending && <p role="status">{t("loading")}</p>}
      {wallet !== null && wallet !== undefined ? (
        <div className="paper-wallet-summary">
          <dl>
            <div className="paper-wallet-stat paper-wallet-stat-primary"><dt>{t("balance")}</dt><dd><MarketValue amount={wallet.balance.amount} unit={wallet.balance.currency} grouped /></dd></div>
            <div className="paper-wallet-stat"><dt>{t("capital")}</dt><dd><MarketValue amount={wallet.initial_capital.amount} unit={wallet.initial_capital.currency} grouped /></dd></div>
            <div className="paper-wallet-stat"><dt>{t("mode")}</dt><dd><strong>{wallet.mode}</strong></dd></div>
            <div className="paper-wallet-stat"><dt>{t("episode")}</dt><dd>{wallet.sequence}</dd></div>
            <div className="paper-wallet-stat"><dt>{t("started")}</dt><dd><MarketTime value={wallet.started_at} locale={paperWalletLocale} /></dd></div>
            <div className="paper-wallet-stat"><dt>{t("snapshot")}</dt><dd><MarketTime value={wallet.snapshot_at} locale={paperWalletLocale} /></dd></div>
          </dl>
          <Button
            ref={resetButton}
            disabled={!wallet.reset_available || attempt !== null}
            aria-describedby={resetReason === null ? undefined : "paper-wallet-reset-reason"}
            onClick={() => setResetTarget({ episodeId: wallet.episode_id, sequence: wallet.sequence })}
          >
            {t("reset")}
          </Button>
          {resetReason !== null && <p id="paper-wallet-reset-reason">{resetReason}</p>}
        </div>
      ) : walletQuery.data !== undefined ? (
        <form
          className="paper-wallet-form"
          onSubmit={event => {
            event.preventDefault();
            submitCreate();
          }}
        >
          <Label htmlFor="paper-wallet-capital">
            {t("initialCapital")}
            <Input
              id="paper-wallet-capital"
              name="initial-capital"
              type="text"
              inputMode="decimal"
              autoComplete="off"
              required
              value={capital}
              disabled={attempt !== null}
              aria-describedby="paper-wallet-capital-help"
              onChange={event => setCapital(event.target.value)}
            />
          </Label>
          <p id="paper-wallet-capital-help">{t("capitalHelp")}</p>
          <Button type="submit" disabled={attempt !== null || capital === ""}>
            {t(mutation.isPending ? "creating" : "create")}
          </Button>
        </form>
      ) : null}
      {pending && <p role="status">{t(attempt?.action === "RESET" ? "resetting" : "pending")}</p>}
      {actionError !== null && <p className="paper-wallet-error" role="alert">{actionError}</p>}
      {(uncertain || commandQuery.isError) && (
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            if (commandQuery.isError && attempt?.commandId !== undefined) {
              void commandQuery.refetch();
            } else if (attempt !== null) {
              mutation.mutate(attempt);
            }
          }}
        >
          {t("retry")}
        </Button>
      )}
      {walletQuery.isError && (
        <p role="alert">{t(walletQuery.data === undefined ? "loadError" : "stale")}</p>
      )}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="paper-wallet-refresh"
        disabled={walletQuery.isFetching}
        onClick={() => void walletQuery.refetch()}
      >
        {t("refresh")}
      </Button>
      <Modal
        isOpen={resetTarget !== null}
        onClose={closeReset}
        titleId="paper-wallet-reset-title"
        closeLabel={t("resetDismiss")}
        returnFocusRef={resetButton}
      >
        <form
          className="paper-wallet-reset-form"
          onSubmit={event => {
            event.preventDefault();
            submitReset();
          }}
        >
          <h3 id="paper-wallet-reset-title">{t("resetTitle")}</h3>
          <p>{t("resetDescription", { episode: resetTarget?.sequence ?? "" })}</p>
          <Label htmlFor="paper-wallet-reset-capital">
            {t("resetCapital")}
            <Input
              id="paper-wallet-reset-capital"
              type="text"
              inputMode="decimal"
              autoComplete="off"
              required
              autoFocus
              value={resetCapital}
              disabled={attempt !== null}
              onChange={event => setResetCapital(event.target.value)}
            />
          </Label>
          <div className="paper-wallet-reset-actions">
            <Button type="button" variant="outline" onClick={closeReset}>
              {t("resetCancel")}
            </Button>
            <Button type="submit" disabled={attempt !== null || resetCapital === ""}>
              {t("resetConfirm")}
            </Button>
          </div>
        </form>
      </Modal>
    </ComponentCard>
  );
}
