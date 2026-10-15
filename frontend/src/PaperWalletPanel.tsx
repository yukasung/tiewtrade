import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { Me } from "./auth";
import { ApiRequestError } from "./auth";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import {
  createPaperWallet,
  fetchPaperCommand,
  fetchPaperWallet,
  type PaperWalletMutation,
} from "./paperWallet";
import { paperWalletLocale, paperWalletText as t } from "./paperWalletMessages";
import "./PaperWalletPanel.css";

type Attempt = {
  idempotencyKey: string;
  payload: PaperWalletMutation;
  commandId?: string;
};

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
  const walletKey = ["paper-wallet", identity.user_id] as const;
  const [capital, setCapital] = useState("");
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [commandFailure, setCommandFailure] = useState<string | null>(null);

  const walletQuery = useQuery({
    queryKey: walletKey,
    queryFn: ({ signal }) => fetchPaperWallet(signal),
  });
  const mutation = useMutation({
    mutationFn: (request: Attempt) =>
      createPaperWallet(request.payload, request.idempotencyKey),
    onSuccess: command => {
      if (command.state === "SUCCEEDED") {
        void client.invalidateQueries({ queryKey: walletKey });
        setAttempt(null);
        setCapital("");
        return;
      }
      setAttempt(current =>
        current === null ? current : { ...current, commandId: command.command_id },
      );
    },
    onError: error => {
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
      void client.invalidateQueries({ queryKey: walletKey });
      setAttempt(null);
      setCapital("");
    } else if (commandState === "REJECTED") {
      setCommandFailure(commandQuery.data?.failure_code ?? "PAPER_WALLET_REJECTED");
      setAttempt(null);
    }
  }, [client, commandQuery.data?.failure_code, commandState, walletKey]);

  const wallet = walletQuery.data?.wallet;
  const uncertain = mutation.isError && attempt !== null;
  const actionError = mutation.isError
    ? failure(mutation.error)
    : commandFailure !== null
      ? failure(new ApiRequestError(commandFailure, 409))
      : commandQuery.isError
        ? failure(commandQuery.error)
        : null;
  const pending = attempt !== null && !mutation.isError && !commandQuery.isError;

  function submit(retry: boolean): void {
    const request = retry && attempt !== null
      ? attempt
      : {
          idempotencyKey: globalThis.crypto.randomUUID(),
          payload: { initial_capital: capital },
        };
    if (!retry) setCommandFailure(null);
    setAttempt(request);
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
            <div><dt>{t("mode")}</dt><dd><strong>{wallet.mode}</strong></dd></div>
            <div><dt>{t("balance")}</dt><dd><MarketValue amount={wallet.balance.amount} unit={wallet.balance.currency} grouped /></dd></div>
            <div><dt>{t("capital")}</dt><dd><MarketValue amount={wallet.initial_capital.amount} unit={wallet.initial_capital.currency} grouped /></dd></div>
            <div><dt>{t("episode")}</dt><dd>{wallet.sequence}</dd></div>
            <div><dt>{t("started")}</dt><dd><MarketTime value={wallet.started_at} locale={paperWalletLocale} /></dd></div>
            <div><dt>{t("snapshot")}</dt><dd><MarketTime value={wallet.snapshot_at} locale={paperWalletLocale} /></dd></div>
          </dl>
          <Button disabled aria-describedby="paper-wallet-reset-reason">
            {t("reset")}
          </Button>
          <p id="paper-wallet-reset-reason">{t("resetUnavailable")}</p>
        </div>
      ) : walletQuery.data !== undefined ? (
        <form
          className="paper-wallet-form"
          onSubmit={event => {
            event.preventDefault();
            submit(false);
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
      {pending && <p role="status">{t("pending")}</p>}
      {actionError !== null && <p className="paper-wallet-error" role="alert">{actionError}</p>}
      {(uncertain || commandQuery.isError) && (
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            if (commandQuery.isError && attempt?.commandId !== undefined) {
              void commandQuery.refetch();
            } else {
              submit(true);
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
        disabled={walletQuery.isFetching}
        onClick={() => void walletQuery.refetch()}
      >
        {t("refresh")}
      </Button>
    </ComponentCard>
  );
}
