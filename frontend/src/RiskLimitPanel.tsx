import { useQuery, type QueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { ApiRequestError } from "./auth";
import { MarketValue } from "./components/MarketValue";
import { Alert } from "./components/ui/Alert";
import { Badge } from "./components/ui/Badge";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { Disclosure } from "./components/ui/Disclosure";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Modal } from "./components/ui/Modal";
import { manualKey } from "./manualOrders";
import { parseRiskLimitAmount } from "./riskLimitAmount";
import { riskJournal, riskScope, type RiskAttempt } from "./riskLimitJournal";
import { riskCode, riskLimitI18n, riskText as t } from "./riskLimitMessages";
import {
  fetchRisk,
  fetchRiskKey,
  fetchRiskReceipt,
  postRisk,
  riskKey,
  riskTerminal,
  type RiskAction,
  type RiskMode,
  type RiskReceipt,
  type RiskSnapshot,
} from "./riskLimits";
import { RiskStopEffects } from "./RiskStopEffects";
import { useDurableAttempt } from "./useDurableAttempt";

const subscribeLanguage = (changed: () => void) => {
  riskLimitI18n.on("languageChanged", changed);
  return () => { riskLimitI18n.off("languageChanged", changed); };
};

const matches = (receipt: RiskReceipt, attempt: RiskAttempt) =>
  receipt.mode === attempt.mode && receipt.action === attempt.action &&
  receipt.idempotency_key === attempt.key &&
  receipt.expected_revision === attempt.payload.expected_revision &&
  receipt.expected_wallet_id === attempt.payload.expected_wallet_id &&
  receipt.expected_episode_id === attempt.payload.expected_episode_id;

const refusal = (error: ApiRequestError) =>
  error.status === 422 && error.message === "RISK_INPUT_INVALID";

const snapshotIdentity = (snapshot: RiskSnapshot) =>
  `${snapshot.revision}:${snapshot.wallet_id ?? "-"}:${snapshot.episode_id ?? "-"}`;

const attemptIdentity = (attempt: RiskAttempt) => [
  attempt.payload.expected_revision,
  attempt.payload.expected_wallet_id ?? "-",
  attempt.payload.expected_episode_id ?? "-",
].join(":");

type PreparedIncrease = Readonly<
  | { kind: "new"; amount: string; identity: string }
  | { kind: "retry"; amount: string }
>;

export function RiskLimitPanel({ owner, mode, visible = true }: {
  owner: string;
  mode: RiskMode;
  visible?: boolean;
}) {
  return <RiskForScope key={`${owner}:${mode}`} owner={owner} mode={mode} visible={visible}/>;
}

function RiskForScope({ owner, mode, visible }: {
  owner: string;
  mode: RiskMode;
  visible: boolean;
}) {
  useSyncExternalStore(subscribeLanguage, () => riskLimitI18n.resolvedLanguage ?? "th");
  const id = useId();
  const [draft, setDraft] = useState("");
  const [draftIdentity, setDraftIdentity] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [forcedStale, setForcedStale] = useState(false);
  const [preparedIncrease, setPreparedIncrease] = useState<PreparedIncrease | null>(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [code, setCode] = useState("");
  const [receiptId, setReceiptId] = useState<string | null>(null);
  const [awaitingRevision, setAwaitingRevision] = useState<number | null>(null);
  const codeRef = useRef<string | undefined>();
  const feedback = useRef<HTMLDivElement>(null);
  const focusFeedback = useRef(false);
  const saveButton = useRef<HTMLButtonElement>(null);
  const resetButton = useRef<HTMLButtonElement>(null);

  const closeIncrease = useCallback(() => {
    setPreparedIncrease(null);
    setCode("");
    codeRef.current = undefined;
  }, []);
  const closeReset = useCallback(() => setResetOpen(false), []);
  useEffect(() => () => { codeRef.current = undefined; }, []);

  const options = useMemo(() => ({
    scope: riskScope(owner, mode),
    visible,
    journal: riskJournal,
    queryKey: (attempt: RiskAttempt | null) => [
      ...riskKey(owner, mode), "attempt", attempt?.payload.expected_wallet_id,
      attempt?.payload.expected_episode_id, attempt?.payload.expected_revision, attempt?.key,
    ],
    fetch: (attempt: RiskAttempt, signal: AbortSignal) => fetchRiskKey(mode, attempt.key, signal),
    post: (attempt: RiskAttempt) => {
      const proof = codeRef.current;
      codeRef.current = undefined;
      return postRisk(mode, attempt.action, attempt.payload, attempt.key, proof);
    },
    matches,
    terminal: riskTerminal,
    refusal,
    received: (client: QueryClient) => {
      void client.invalidateQueries({ queryKey: riskKey(owner, mode) });
      void client.invalidateQueries({ queryKey: manualKey(owner) });
      void client.invalidateQueries({ queryKey: ["paper-wallet", owner] });
    },
  }), [owner, mode, visible]);
  const recovery = useDurableAttempt(options);
  const discardAttempt = recovery.discard;
  const result = recovery.lookup.data;
  const finish = recovery.finish;

  useEffect(() => {
    if (!result || !riskTerminal(result)) return;
    setReceiptId(result.receipt_id);
    if (result.state === "APPLIED") {
      if (result.applied_revision === null) setForcedStale(true);
      else setAwaitingRevision(result.applied_revision);
    } else if (
      result.failure_code === "RISK_REVISION_CONFLICT" ||
      result.failure_code === "RISK_SCOPE_CONFLICT"
    ) {
      setForcedStale(true);
    }
    finish(result);
  }, [result, finish]);

  const completed = useQuery({
    queryKey: [...riskKey(owner, mode), "receipt", receiptId],
    enabled: visible && receiptId !== null,
    queryFn: ({ signal }) => fetchRiskReceipt(mode, receiptId!, signal),
  });
  const snapshot = useQuery({
    queryKey: [...riskKey(owner, mode), "snapshot"],
    queryFn: ({ signal }) => fetchRisk(mode, signal),
    enabled: visible,
    refetchInterval: visible ? 1000 : false,
    refetchIntervalInBackground: false,
  });
  const data = snapshot.data;
  const identity = data ? snapshotIdentity(data) : null;
  const pendingAttempt = recovery.attempt;
  const pendingAmount = pendingAttempt && "amount" in pendingAttempt.payload
    ? pendingAttempt.payload.amount
    : null;
  const pendingParsed = pendingAmount === null ? null : parseRiskLimitAmount(pendingAmount);
  const authoritativeParsed = data?.amount ? parseRiskLimitAmount(data.amount) : null;
  const fulfilledAmount = pendingParsed !== null && authoritativeParsed !== null &&
    pendingParsed.coefficient === authoritativeParsed.coefficient;

  useEffect(() => {
    if (!pendingAttempt || pendingAmount === null) return;
    setDraft(pendingAmount);
    setDraftIdentity(attemptIdentity(pendingAttempt));
    setDirty(true);
  }, [pendingAttempt?.key, pendingAmount]);

  useEffect(() => {
    if (
      !pendingAttempt || !data || identity === null ||
      !(recovery.lookup.error instanceof ApiRequestError) ||
      recovery.lookup.error.message !== "RISK_REQUEST_NOT_FOUND" ||
      (attemptIdentity(pendingAttempt) === identity && !fulfilledAmount)
    ) return;
    if (!discardAttempt(pendingAttempt.key)) return;
    setDraft(data.amount ?? "");
    setDraftIdentity(identity);
    setDirty(false);
    setForcedStale(false);
    setReceiptId(null);
    setPreparedIncrease(null);
    setCode("");
    codeRef.current = undefined;
  }, [data, discardAttempt, fulfilledAmount, identity, pendingAttempt, recovery.lookup.error]);

  useEffect(() => {
    if (!data || dirty || recovery.attempt || awaitingRevision !== null || preparedIncrease) return;
    setDraft(data.amount ?? "");
    setDraftIdentity(snapshotIdentity(data));
  }, [data, dirty, recovery.attempt, awaitingRevision, preparedIncrease]);

  useEffect(() => {
    if (!data || awaitingRevision === null || data.revision < awaitingRevision) return;
    setDraft(data.amount ?? "");
    setDraftIdentity(snapshotIdentity(data));
    setDirty(false);
    setForcedStale(false);
    setAwaitingRevision(null);
    setReceiptId(null);
  }, [data, awaitingRevision]);

  useEffect(() => {
    if (!recovery.attempt || !focusFeedback.current) return;
    feedback.current?.focus();
    focusFeedback.current = false;
  }, [recovery.attempt]);

  const parsedDraft = parseRiskLimitAmount(draft);
  const parsedCurrent = authoritativeParsed;
  const action: Exclude<RiskAction, "RESET"> | null = !data || !parsedDraft ? null
    : data.amount === null ? "SET"
    : !parsedCurrent ? null
    : parsedDraft.coefficient < parsedCurrent.coefficient ? "DECREASE"
    : parsedDraft.coefficient > parsedCurrent.coefficient ? "INCREASE"
    : null;
  const draftStale = forcedStale || Boolean(
    !pendingAttempt && dirty && draftIdentity !== null && identity !== null && draftIdentity !== identity,
  );
  const formBusy = recovery.busy || awaitingRevision !== null;
  const authorizationOnly = result?.state === "AUTHORIZATION_ONLY";
  const recoveryReady = Boolean(
    pendingAttempt && !formBusy && (
      authorizationOnly || (!result && !recovery.lookup.isPending)
    ),
  );
  const scopeReady = mode === "LIVE" || data?.wallet_id != null && data.episode_id != null;
  const blocked = recovery.storageError || formBusy || !data || snapshot.isError ||
    snapshot.isPending || !scopeReady || draftStale || pendingAttempt !== null;
  const saveDisabled = pendingAttempt ? !recoveryReady : blocked || action === null;
  const shown = result ?? completed.data;
  const statusColor: "warning" | "error" = data?.latched ? "error" : "warning";
  const stopProblem = Boolean(
    data?.stop_id && (data.stop_alert_due || (data.failed_count ?? 0) > 0 ||
      data.stop_progress === "PROBLEMS"),
  );

  const sendAttempt = (nextAction: RiskAction, amount?: string, proof?: string) => {
    if (!data || pendingAttempt || formBusy || recovery.storageError || !scopeReady || draftStale) return false;
    const scope = {
      expected_revision: data.revision,
      expected_wallet_id: data.wallet_id,
      expected_episode_id: data.episode_id,
    };
    const intent: RiskAttempt = {
      version: 1,
      owner,
      mode,
      key: globalThis.crypto.randomUUID(),
      action: nextAction,
      payload: nextAction === "RESET" ? scope : { ...scope, amount: amount! },
    };
    codeRef.current = nextAction === "INCREASE" ? proof : undefined;
    const sent = recovery.send(intent);
    if (!sent) {
      codeRef.current = undefined;
      return false;
    }
    setReceiptId(null);
    focusFeedback.current = true;
    return true;
  };

  const submitDraft = () => {
    if (pendingAttempt) {
      if (!recoveryReady) return;
      if (mode === "LIVE" && pendingAttempt.action === "INCREASE" && !authorizationOnly) {
        if (pendingAmount !== null) setPreparedIncrease({ kind: "retry", amount: pendingAmount });
        return;
      }
      retryAttempt();
      return;
    }
    if (saveDisabled || !action || !parsedDraft || !identity) return;
    if (mode === "LIVE" && action === "INCREASE") {
      setPreparedIncrease({ kind: "new", amount: parsedDraft.canonical, identity });
      return;
    }
    sendAttempt(action, parsedDraft.canonical);
  };

  const submitIncrease = () => {
    if (!preparedIncrease || code === "") return;
    const sent = preparedIncrease.kind === "retry"
      ? retryAttempt(code)
      : identity !== null && preparedIncrease.identity === identity &&
        sendAttempt("INCREASE", preparedIncrease.amount, code);
    if (sent) {
      // The mutation adapter consumes codeRef asynchronously; only user cancellation clears it here.
      setPreparedIncrease(null);
      setCode("");
    }
  };

  const submitReset = () => {
    const sent = pendingAttempt?.action === "RESET"
      ? recoveryReady && retryAttempt()
      : sendAttempt("RESET");
    if (sent) setResetOpen(false);
  };

  function retryAttempt(proof?: string) {
    if (!pendingAttempt || !recoveryReady || recovery.storageError) return false;
    codeRef.current = mode === "LIVE" && pendingAttempt.action === "INCREASE" && !authorizationOnly
      ? proof
      : undefined;
    const sent = recovery.send(pendingAttempt, true);
    if (!sent) codeRef.current = undefined;
    return sent;
  };

  const useLatest = () => {
    void snapshot.refetch().then(refreshed => {
      if (!refreshed.data) return;
      setDraft(refreshed.data.amount ?? "");
      setDraftIdentity(snapshotIdentity(refreshed.data));
      setDirty(false);
      setForcedStale(false);
      setReceiptId(null);
    });
  };

  const help = pendingAttempt ? null
    : draftStale ? t("draftStale")
    : dirty && parsedDraft === null ? t("invalidAmount")
    : dirty && action === null ? t("unchanged")
    : data?.amount === null && !dirty ? t("unset")
    : null;
  const helpId = `${id}-amount-help`;
  const recoveryStatusId = `${id}-recovery-status`;

  return <ComponentCard title={`${t("title")} · ${t(mode)}`} headingId={`${id}-heading`}>
    {snapshot.isPending && <p role="status">{t("loading")}</p>}
    {snapshot.isError && <div className="space-y-3">
      <Alert variant="error" title={t("title")} message={t("loadError")}/>
      <Button disabled={snapshot.isFetching} onClick={() => void snapshot.refetch()}>{t("refresh")}</Button>
    </div>}
    {data?.pause_alert_due && <Alert variant="warning" title={t("pause")} message={t("pauseNotice")}/>}
    {data?.stop_alert_due && <Alert variant="warning" title={t("stopAlert")} message={t("stopAlertNotice")}/>}
    {data && data.reason !== "READY" && data.reason !== "RISK_LIMIT_UNSET" && !data.latched &&
      <Alert variant="warning" title={riskCode(data.reason)} message={t("unavailableNotice")}/>}
    {data?.latched && <div className="space-y-3">
      <Alert variant="error" title={t("latch")} message={t("latchNotice")}/>
      {data.stop_progress !== "STOPPED" || data.target_set_complete !== true || data.pending_count !== 0
        ? <p role="status" className="text-sm text-gray-500 dark:text-gray-400">{t("stopWorking")}</p>
        : null}
      <Button ref={resetButton} variant="outline" disabled={formBusy || recovery.storageError || (
        pendingAttempt !== null && (pendingAttempt.action !== "RESET" || !recoveryReady)
      )} onClick={() => setResetOpen(true)}>{t("RESET")}</Button>
    </div>}
    {data && <>
      {data.reason !== "READY" &&
        <div role="status"><Badge color={statusColor}>{riskCode(data.reason)}</Badge></div>}
      <form onSubmit={event => { event.preventDefault(); submitDraft(); }} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1">
          <Label htmlFor={`${id}-amount`}>{t("limit")}</Label>
          <Input
            id={`${id}-amount`}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            required
            maxLength={256}
            value={draft}
            disabled={formBusy || pendingAttempt !== null}
            aria-invalid={dirty && parsedDraft === null ? true : undefined}
            aria-describedby={pendingAttempt ? recoveryStatusId : help ? helpId : undefined}
            onChange={event => {
              setDraft(event.target.value);
              setDirty(true);
              setReceiptId(null);
            }}
          />
          {help && <p id={helpId} role={draftStale || parsedDraft === null ? "alert" : "status"} className="mt-2 text-sm text-gray-500 dark:text-gray-400">{help}</p>}
        </div>
        <Button ref={saveButton} type="submit" disabled={saveDisabled} aria-describedby={pendingAttempt ? recoveryStatusId : undefined}>{t("save")}</Button>
      </form>
      {draftStale && <Button variant="outline" disabled={snapshot.isFetching} onClick={useLatest}>{t("useLatest")}</Button>}
    </>}

    <div ref={feedback} tabIndex={-1} role="region" aria-label={t("recovery")}>
      {recovery.storageError && <Alert variant="error" title={t("recovery")} message={t("storage")}/>}
      {pendingAttempt && <p id={recoveryStatusId} role="status" className="sr-only">
        {recoveryReady ? t("finishPrevious") : t("checkingPrevious")}
      </p>}
      {!pendingAttempt && shown?.state === "REJECTED" && !draftStale &&
        <Alert variant="error" title={t("saveFailed")} message={t("checkValue")}/>}
    </div>

    {stopProblem && data?.stop_id && <Disclosure title={`${t("stop")}: ${riskCode(data.stop_progress)}`} defaultOpen>
      <p>{t("targetCount")}: {data.target_count ?? t("unavailable")} · {t("pending")}: {data.pending_count ?? t("unavailable")} · {t("failed")}: {data.failed_count ?? t("unavailable")}</p>
      {data.target_set_complete !== true && <p role="status">{t("incomplete")}</p>}
      <RiskStopEffects key={`${data.stop_id}:${data.effects_revision}`} owner={owner} mode={mode} stop={data.stop_id} revision={data.effects_revision ?? null} visible={visible}/>
    </Disclosure>}

    <Modal isOpen={preparedIncrease !== null} onClose={closeIncrease} titleId={`${id}-increase`} closeLabel={t("close")} returnFocusRef={saveButton}>
      <form onSubmit={event => { event.preventDefault(); submitIncrease(); }} className="space-y-6">
        <h3 id={`${id}-increase`} className="text-lg font-semibold text-gray-800 dark:text-white/90">{t("INCREASE")} · {t(mode)}</h3>
        <p>{t("freshCode")}</p>
        {preparedIncrease && <p>{t("newLimit")}: <MarketValue amount={preparedIncrease.amount} unit="USDT"/></p>}
        <div>
          <Label htmlFor={`${id}-code`}>{t("totp")}</Label>
          <Input id={`${id}-code`} required type="password" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)}/>
        </div>
        {preparedIncrease?.kind === "new" && preparedIncrease.identity !== identity && <p role="alert">{t("draftStale")}</p>}
        <div className="flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={closeIncrease}>{t("cancel")}</Button>
          <Button type="submit" disabled={code === "" || (
            preparedIncrease?.kind === "new"
              ? blocked || preparedIncrease.identity !== identity
              : !recoveryReady
          )}>{t("confirm")}</Button>
        </div>
      </form>
    </Modal>

    <Modal isOpen={resetOpen} onClose={closeReset} titleId={`${id}-reset`} closeLabel={t("close")} returnFocusRef={resetButton}>
      <form onSubmit={event => { event.preventDefault(); submitReset(); }} className="space-y-6">
        <h3 id={`${id}-reset`} className="text-lg font-semibold text-gray-800 dark:text-white/90">{t("RESET")} · {t(mode)}</h3>
        <p>{t("resetWarning")}</p>
        <div className="flex flex-wrap justify-end gap-3">
          <Button variant="outline" onClick={closeReset}>{t("cancel")}</Button>
          <Button type="submit" disabled={formBusy || !scopeReady || draftStale || recovery.storageError || (
            pendingAttempt !== null && (pendingAttempt.action !== "RESET" || !recoveryReady)
          )}>{t("confirm")}</Button>
        </div>
      </form>
    </Modal>
  </ComponentCard>;
}
