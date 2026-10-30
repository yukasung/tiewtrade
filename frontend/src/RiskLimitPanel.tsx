import { useQuery, type QueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { ApiRequestError } from "./auth";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Alert } from "./components/ui/Alert";
import { Badge } from "./components/ui/Badge";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Modal } from "./components/ui/Modal";
import { manualKey } from "./manualOrders";
import { riskJournal, riskScope, type RiskAttempt } from "./riskLimitJournal";
import { riskCode, riskLimitI18n, riskLocale, riskText as t } from "./riskLimitMessages";
import { fetchRisk, fetchRiskKey, fetchRiskReceipt, postRisk, riskKey, riskTerminal, type RiskAction, type RiskMode, type RiskReceipt } from "./riskLimits";
import { RiskStopEffects } from "./RiskStopEffects";
import { useDurableAttempt } from "./useDurableAttempt";
const subscribeLanguage = (changed: () => void) => { riskLimitI18n.on("languageChanged", changed); return () => { riskLimitI18n.off("languageChanged", changed); }; };
const matches = (receipt: RiskReceipt, attempt: RiskAttempt) => receipt.mode === attempt.mode && receipt.action === attempt.action &&
  receipt.idempotency_key === attempt.key && receipt.expected_revision === attempt.payload.expected_revision &&
  receipt.expected_wallet_id === attempt.payload.expected_wallet_id && receipt.expected_episode_id === attempt.payload.expected_episode_id;
const refusal = (error: ApiRequestError) => error.status === 422 && error.message === "RISK_INPUT_INVALID";
export function RiskLimitPanel({ owner, mode, visible = true }: { owner: string; mode: RiskMode; visible?: boolean }) {
  return <RiskForScope key={`${owner}:${mode}`} owner={owner} mode={mode} visible={visible}/>;
}
function RiskForScope({ owner, mode, visible }: { owner: string; mode: RiskMode; visible: boolean }) {
  useSyncExternalStore(subscribeLanguage, () => riskLimitI18n.resolvedLanguage ?? "th");
  const id = useId();
  const [action, setAction] = useState<RiskAction | null>(null);
  const [amount, setAmount] = useState("");
  const [code, setCode] = useState("");
  const [receiptId, setReceiptId] = useState<string | null>(null);
  // Only the transient transport adapter sees the code. Mutation variables contain no secret.
  const codeRef = useRef<string | undefined>();
  const feedback = useRef<HTMLDivElement>(null);
  const focusFeedback = useRef(false);
  useEffect(() => {
    if (action === null && focusFeedback.current) { feedback.current?.focus(); focusFeedback.current = false; }
  }, [action]);
  const close = useCallback(() => { setAction(null); setAmount(""); setCode(""); codeRef.current = undefined; }, []);
  useEffect(() => () => { codeRef.current = undefined; }, []);
  const options = useMemo(() => ({
    scope: riskScope(owner, mode), visible, journal: riskJournal,
    queryKey: (attempt: RiskAttempt | null) => [...riskKey(owner, mode), "attempt", attempt?.payload.expected_wallet_id, attempt?.payload.expected_episode_id, attempt?.payload.expected_revision, attempt?.key],
    fetch: (attempt: RiskAttempt, signal: AbortSignal) => fetchRiskKey(mode, attempt.key, signal),
    post: (attempt: RiskAttempt) => { const proof = codeRef.current; codeRef.current = undefined; return postRisk(mode, attempt.action, attempt.payload, attempt.key, proof); },
    matches, terminal: riskTerminal, refusal,
    received: (client: QueryClient) => {
      void client.invalidateQueries({ queryKey: riskKey(owner, mode) });
      void client.invalidateQueries({ queryKey: manualKey(owner) });
      void client.invalidateQueries({ queryKey: ["paper-wallet", owner] });
    },
  }), [owner, mode, visible]);
  const recovery = useDurableAttempt(options);
  const result = recovery.lookup.data;
  const finish = recovery.finish;
  useEffect(() => {
    if (result && riskTerminal(result)) { setReceiptId(result.receipt_id); finish(result); }
  }, [result, finish]);
  const completed = useQuery({ queryKey: [...riskKey(owner, mode), "receipt", receiptId], enabled: visible && receiptId !== null,
    queryFn: ({ signal }) => fetchRiskReceipt(mode, receiptId!, signal) });
  const snapshot = useQuery({ queryKey: [...riskKey(owner, mode), "snapshot"], queryFn: ({ signal }) => fetchRisk(mode, signal), enabled: visible,
    refetchInterval: visible ? 1000 : false, refetchIntervalInBackground: false });
  const data = snapshot.data;
  const blocked = recovery.storageError || recovery.busy || recovery.attempt !== null || !data || snapshot.isError || snapshot.isPending;
  const scopeReady = mode === "LIVE" || data?.wallet_id != null && data.episode_id != null;
  const submit = () => {
    if (!data || !action || blocked || !scopeReady) return;
    const scope = { expected_revision: data.revision, expected_wallet_id: data.wallet_id, expected_episode_id: data.episode_id };
    const intent: RiskAttempt = { version: 1, owner, mode, key: globalThis.crypto.randomUUID(), action,
      payload: action === "RESET" ? scope : { ...scope, amount } };
    codeRef.current = action === "INCREASE" ? code : undefined;
    if (!recovery.send(intent)) codeRef.current = undefined;
    focusFeedback.current = true;
    setAction(null); setAmount(""); setCode("");
  };
  // The adapter consumes the transient code once; it is never stored as mutation data.
  const shown = result ?? completed.data;
  return <ComponentCard title={`${t("title")} · ${t(mode)}`} headingId={`${id}-heading`}>
    <Badge color={mode === "PAPER" ? "primary" : "warning"}>{t(mode)}</Badge>
    {snapshot.isPending && <p role="status">{t("loading")}</p>}
    {snapshot.isError && <Alert variant="error" title={t("title")} message={t("loadError")}/>}
    {data?.amount === null && <p role="status">{t("unset")}</p>}
    {data?.latched && <Alert variant="error" title={t("latch")} message={t("latchNotice")}/>}
    {data?.pause_alert_due && <Alert variant="warning" title={t("pause")} message={t("pauseNotice")}/>}
    {data?.stop_alert_due && <Alert variant="warning" title={t("stopAlert")} message={t("stopAlertNotice")}/>}
    {data && <>
      <p role="status">{riskCode(data.reason)}</p>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2">
        {([["limit", data.amount], ["loss", data.loss], ["allowance", data.current_allowance], ["realized", data.adjusted_realized]] as const).map(([label, value]) => <div key={label}><dt className="text-sm text-gray-500 dark:text-gray-400">{t(label)}</dt><dd>{value == null ? t("unavailable") : <MarketValue amount={value} unit="USDT" grouped/>}</dd></div>)}
        <div><dt>{t("baseline")}</dt><dd>{data.baseline_at ? <MarketTime value={data.baseline_at} locale={riskLocale()}/> : t("noBaseline")}</dd></div>
        <div><dt>{t("source")}</dt><dd>{data.source_revision ?? t("unavailable")}</dd></div>
        {mode === "PAPER" && <div><dt>{t("episode")}</dt><dd className="break-all text-sm">{data.episode_id ?? t("unavailable")}</dd></div>}
        {([["snapshot", data.snapshot_at], ["evaluated", data.evaluated_at], ["input", data.input_ready_at], ["unavailableSince", data.unavailable_since]] as const).map(([label, value]) => <div key={label}><dt>{t(label)}</dt><dd className="text-sm">{value ? <MarketTime value={value} locale={riskLocale()}/> : t("unavailable")}</dd></div>)}
      </dl>
    </>}
    <div className="flex flex-wrap gap-3">
      {data && (data.amount === null ? ["SET"] as const : ["DECREASE", "INCREASE", "RESET"] as const).map(value => <Button key={value} disabled={blocked || !scopeReady} variant={value === "SET" ? "primary" : "outline"} onClick={() => setAction(value)}>{t(value)}</Button>)}
      <Button variant="outline" disabled={snapshot.isFetching} onClick={() => void snapshot.refetch()}>{t("refresh")}</Button>
    </div>
    <div ref={feedback} tabIndex={-1} role="region" aria-label={t("recovery")}>
    {recovery.storageError && <Alert variant="error" title={t("recovery")} message={t("storage")}/>}
    {recovery.error && <p role="alert">{riskCode(recovery.error.message)} {recovery.error.retryAt && <MarketTime value={recovery.error.retryAt} locale={riskLocale()}/>}</p>}
    {recovery.attempt && <div className="space-y-4" role="status">
      <h3 className="text-base font-medium">{t("recovery")}</h3>
      <p>{shown ? riskCode(shown.state) : t("unknown")}</p>
      <p>{t(recovery.attempt.action)} {"amount" in recovery.attempt.payload && <MarketValue amount={recovery.attempt.payload.amount} unit="USDT"/>}</p>
      <p className="break-all text-sm">{t("key")}: {recovery.attempt.key}</p>
      {recovery.attempt.action === "INCREASE" && !result && <div><Label htmlFor={`${id}-retry-code`}>{t("totp")}</Label><Input id={`${id}-retry-code`} value={code} type="password" inputMode="numeric" autoComplete="one-time-code" onChange={e => setCode(e.target.value)}/></div>}
      <div className="flex flex-wrap gap-3"><Button disabled={recovery.busy || recovery.lookup.isFetching} onClick={() => void recovery.lookup.refetch()}>{t("check")}</Button>
        <Button disabled={recovery.busy || recovery.storageError || result != null && result.state !== "AUTHORIZATION_ONLY"} onClick={() => {
          codeRef.current = result?.state === "AUTHORIZATION_ONLY" ? undefined : code || undefined;
          if (!recovery.send(recovery.attempt!, true)) codeRef.current = undefined;
          setCode("");
        }}>{t("retry")}</Button></div>
    </div>}
    {!recovery.attempt && shown && <p role="status">{riskCode(shown.state)} {shown.failure_code && riskCode(shown.failure_code)}</p>}
    </div>
    {data?.stop_id && <div className="space-y-4">
      <h3 className="text-base font-medium">{t("stop")}: {riskCode(data.stop_progress === "STOPPED" && (data.target_set_complete !== true || data.pending_count !== 0) ? "STOPPING" : data.stop_progress)}</h3>
      <p>{t("targetCount")}: {data.target_count ?? t("unavailable")} · {t("pending")}: {data.pending_count ?? t("unavailable")} · {t("failed")}: {data.failed_count ?? t("unavailable")}</p>
      {data.target_set_complete !== true && <p role="status">{t("incomplete")}</p>}
      <RiskStopEffects key={`${data.stop_id}:${data.effects_revision}`} owner={owner} mode={mode} stop={data.stop_id} revision={data.effects_revision ?? null} visible={visible}/>
    </div>}
    <Modal isOpen={action !== null} onClose={close} titleId={`${id}-confirm`} closeLabel={t("close")}>
      <form onSubmit={event => { event.preventDefault(); submit(); }} className="space-y-6">
        <h3 id={`${id}-confirm`} className="text-lg font-semibold text-gray-800 dark:text-white/90">{action && t(action)} · {t(mode)}</h3>
        <p>{t(action === "RESET" ? "resetWarning" : "confirmChange")}</p>
        {action !== "RESET" && <div><Label htmlFor={`${id}-amount`}>{t("amount")}</Label><Input id={`${id}-amount`} required type="text" inputMode="decimal" value={amount} onChange={event => setAmount(event.target.value)} maxLength={256}/></div>}
        {action === "INCREASE" && <div><p className="mb-4 text-sm">{t("freshCode")}</p><Label htmlFor={`${id}-code`}>{t("totp")}</Label><Input id={`${id}-code`} required type="password" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)}/></div>}
        <div className="flex flex-wrap justify-end gap-3"><Button variant="outline" onClick={close}>{t("cancel")}</Button><Button type="submit" disabled={blocked || !scopeReady}>{t("confirm")}</Button></div>
      </form>
    </Modal>
  </ComponentCard>;
}
