import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { CandlestickChartPanel } from "./CandlestickChartPanel";
import { RiskLimitPanel } from "./RiskLimitPanel";
import { ManualOrderForm } from "./ManualOrderForm";
import { ManualRequestStatus, RequestSnapshot } from "./ManualRequestStatus";
import { PaperOrderList } from "./PaperOrderList";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { TradingWorkspace } from "./TradingWorkspace";
import { activeBases, fetchMarketCatalog } from "./marketCatalog";
import { manualCode, manualOrderLocale, manualOrderText as t } from "./manualOrderMessages";
import { fetchRequests, fetchTrade, manualKey, requestTerminal, type ManualRequest } from "./manualOrders";
import { useManualAttempt } from "./useManualAttempt";
import { fetchRisk, riskKey } from "./riskLimits";
import { riskCode } from "./riskLimitMessages";
import { useTradingPair } from "./useTradingPair";

function useVisible() {
  const [visible, setVisible] = useState(() => document.visibilityState !== "hidden");
  useEffect(() => { const changed = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", changed); return () => document.removeEventListener("visibilitychange", changed);
  }, []);
  return visible;
}
export function PaperTradePage({ owner }: { owner: string }) { return <PaperTradeForOwner key={owner} owner={owner}/>; }
function PaperTradeForOwner({ owner }: { owner: string }) {
  const visible = useVisible();
  const { base, changeBase, market, setMarketSnapshot } = useTradingPair();
  const [completedDraft, setCompletedDraft] = useState("");
  const [showDetails, setShowDetails] = useState(false);
  const [recentResult, setRecentResult] = useState<ManualRequest | null>(null);
  // These are client tracking identities, never copies of server order/request state.
  const [tracked, setTracked] = useState<Record<string, string>>({});
  const recovery = useManualAttempt(owner, visible);
  const catalog = useQuery({ queryKey: [...manualKey(owner), "catalog"], queryFn: ({ signal }) => fetchMarketCatalog(signal), enabled: visible,
    refetchInterval: visible ? 5000 : false, refetchIntervalInBackground: false });
  const snapshot = useQuery({ queryKey: [...manualKey(owner), "trade", base], queryFn: ({ signal }) => fetchTrade(base, signal), enabled: visible, placeholderData: keepPreviousData,
    refetchInterval: visible ? 5000 : false, refetchIntervalInBackground: false });
  const risk = useQuery({ queryKey: [...riskKey(owner, "PAPER"), "snapshot"], queryFn: ({ signal }) => fetchRisk("PAPER", signal), enabled: visible,
    refetchInterval: visible ? 1000 : false, refetchIntervalInBackground: false });
  const discovery = useInfiniteQuery({ queryKey: [...manualKey(owner), "all-episodes", "unresolved"], initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => fetchRequests(pageParam, signal), getNextPageParam: page => page.next_cursor ?? undefined, enabled: visible });
  const recovered = discovery.isSuccess && !discovery.isError && !discovery.hasNextPage && !discovery.isFetching;
  const attemptData = recovery.lookup.data;
  const completeTracked = useCallback((value: ManualRequest) => {
    setRecentResult(value);
    setTracked(previous => {
      if (!(value.request_id in previous)) return previous;
      const next = { ...previous }; delete next[value.request_id]; return next;
    });
  }, []);
  useEffect(() => {
    const rows = discovery.data?.pages.flatMap(p => p.requests) ?? [];
    if (attemptData) rows.push(attemptData);
    if (rows.length === 0) return;
    const terminal = rows.find(requestTerminal);
    if (terminal) setRecentResult(terminal);
    setTracked(previous => {
      const next = { ...previous }; let changed = false;
      for (const row of rows) {
        if (row.mode === "PAPER" && !requestTerminal(row) && next[row.request_id] === undefined) { next[row.request_id] = row.episode_id; changed = true; }
      }
      return changed ? next : previous;
    });
  }, [discovery.data, attemptData]);
  const finishAttempt = recovery.finish;
  useEffect(() => {
    if (attemptData && requestTerminal(attemptData)) {
      setRecentResult(attemptData);
      setCompletedDraft(attemptData.idempotency_key);
      finishAttempt(attemptData);
    }
  }, [attemptData, finishAttempt]);
  const data = snapshot.data;
  const wallet = data?.mode === "PAPER" ? data.wallet : null;
  const scope = wallet ? { expected_wallet_id: wallet.wallet_id, expected_episode_id: wallet.episode_id } : null;
  // Remount only the local form when its scope or resolved attempt changes.
  // The recovery journal keeps the original payload independently of this key.
  const draftKey = `${scope?.expected_wallet_id}:${scope?.expected_episode_id}:${base}:${completedDraft}:${recovery.refusedAttemptKey}`;
  const blocked = !recovered || recovery.storageError || !!recovery.attempt || recovery.busy;
  const fresh = data?.mode === "PAPER" && !snapshot.isError && !snapshot.isPending && !snapshot.isFetching && !catalog.isError && catalog.isSuccess && data.base === (base || null);
  const canSubmit = (side: "BUY" | "SELL") => !!fresh && !blocked && !!wallet && (data?.admission_ready === true ||
    (side === "SELL" && wallet.source_availability === "READY" && data.admission_reasons.every(reason => ["MANUAL_USE_REQUIRED", "CATALOG_PAIR_REMOVED", "RISK_LIMIT_UNSET", "RISK_LOSS_LIMIT_REACHED", "RISK_SOURCE_UNAVAILABLE", "RISK_PRICE_UNAVAILABLE"].includes(reason))));
  const bases = [...new Set([...activeBases(catalog.data), ...(wallet?.base_balances.map(b => b.asset) ?? [])])];
  const recoveryVisible = discovery.isPending || discovery.isError || discovery.hasNextPage || recovery.storageError || recovery.attempt !== null ||
    Boolean(recovery.error) || Object.keys(tracked).length > 0;
  const recoveryPanel = recoveryVisible ? <ComponentCard title={t("recovery")} headingId="manual-recovery-heading">
      {recovery.error?.status === 422 && !recovery.attempt && <p role="alert">{t("safeFailure")}</p>}
      {recovery.error?.message === "MANUAL_ORDER_EPISODE_CLOSED" && !recovery.attempt && <p role="alert">{t("episodeClosed")}</p>}
      {recovery.storageError && <p role="alert">{t("storage")}</p>}
      {discovery.isPending && <p role="status">{t("recovering")}</p>}
      {discovery.isError && <p role="alert">{t("recoveryError")}</p>}
      <Button type="button" disabled={discovery.isFetching} onClick={() => void discovery.refetch()}>{t("check")}</Button>
      {discovery.hasNextPage && <Button type="button" disabled={discovery.isFetching} onClick={() => void discovery.fetchNextPage()}>{t("more")}</Button>}
      {recovery.attempt && <div className="space-y-4" role="status">
        {attemptData ? <RequestSnapshot value={attemptData}/> : <p>{t("unknown")}</p>}
        {recovery.attempt.action === "NEW" && <p>{recovery.attempt.payload.base}/{recovery.attempt.payload.quote} {t(recovery.attempt.payload.side)} {t(recovery.attempt.payload.kind)} <MarketValue amount={"quote_budget" in recovery.attempt.payload ? recovery.attempt.payload.quote_budget : recovery.attempt.payload.base_quantity} unit={"quote_budget" in recovery.attempt.payload ? "USDT" : recovery.attempt.payload.base}/>{"limit_price" in recovery.attempt.payload && <> · <MarketValue amount={recovery.attempt.payload.limit_price} unit="USDT"/> {t("GTC")}</>}</p>}
        <p className="break-all">{recovery.attempt.action} · {recovery.attempt.key} · {t("episode")}: {recovery.attempt.payload.expected_episode_id}</p>
        {recovery.error?.status === 429 && <p>{t("limited")} {recovery.error.retryAt && <MarketTime value={recovery.error.retryAt} locale={manualOrderLocale()}/>}</p>}
        <Button type="button" disabled={recovery.busy || recovery.lookup.isFetching} onClick={() => void recovery.lookup.refetch()}>{t("check")}</Button>
        <Button type="button" disabled={recovery.busy || recovery.storageError || !recovered || !!attemptData} onClick={() => recovery.send(recovery.attempt!, true)}>{t("retry")}</Button>
      </div>}
      {Object.entries(tracked).map(([id, episode]) => <ManualRequestStatus key={id} owner={owner} request={id} episode={episode} visible={visible} onTerminal={completeTracked}/>)}
    </ComponentCard> : null;
  const details = <div className="trade-workspace-details space-y-4">
    <Button variant="outline" onClick={() => setShowDetails(value => !value)} aria-expanded={showDetails}>
      {t(showDetails ? "hideDetails" : "riskDetails")}
    </Button>
    {showDetails && <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <ComponentCard title={t("balance")} headingId="manual-wallet-heading">
        {snapshot.isError && <p role="alert">{t("loadError")}</p>}
        {wallet && <dl className="space-y-4">
          <div><dt>{t("balance")}</dt><dd><MarketValue amount={wallet.balance} unit="USDT" grouped/></dd></div>
          <div><dt>{t("reserved")}</dt><dd>{wallet.reserved_quote === null ? t("unavailable") : <MarketValue amount={wallet.reserved_quote} unit="USDT" grouped/>}</dd></div>
          <div><dt>{t("available")}</dt><dd>{wallet.available_quote === null ? t("unavailable") : <MarketValue amount={wallet.available_quote} unit="USDT" grouped/>}</dd></div>
          {wallet.base_balances.map(row => <div key={row.asset}><dt>{row.asset}</dt><dd>{t("held")}: <MarketValue amount={row.held} unit={row.asset}/> · {t("reserved")}: <MarketValue amount={row.reserved} unit={row.asset}/> · {t("available")}: <MarketValue amount={row.available} unit={row.asset}/></dd></div>)}
          <div><dt>{t("use")}</dt><dd>{data?.account_use ?? t("unavailable")}</dd></div>
          <div><dt>{t("episode")}</dt><dd className="break-all">{wallet.episode_id}</dd></div>
        </dl>}
        {data && <p className="text-sm">{t("snapshot")} <MarketTime value={data.snapshot_at} locale={manualOrderLocale()}/></p>}
        <Button type="button" onClick={() => { void snapshot.refetch(); void catalog.refetch(); void risk.refetch(); }} disabled={snapshot.isFetching || catalog.isFetching || risk.isFetching}>{t("refresh")}</Button>
      </ComponentCard>
      <RiskLimitPanel owner={owner} mode="PAPER" visible={visible}/>
    </div>}
    {recoveryPanel}
  </div>;
  const form = <section aria-labelledby="manual-form-heading" className="space-y-5">
    <div><h2 id="manual-form-heading" className="text-lg font-semibold">{t("form")}</h2><p className="text-sm text-gray-500 dark:text-gray-400">{t("pendingNotice")}</p></div>
    <dl className="grid grid-cols-2 gap-3 rounded-xl border border-gray-200 p-3 text-sm dark:border-gray-800">
      <div><dt className="text-gray-500 dark:text-gray-400">{t("available")}</dt><dd className="font-semibold">{wallet?.available_quote == null ? t("unavailable") : <MarketValue amount={wallet.available_quote} unit="USDT" grouped/>}</dd></div>
      <div><dt className="text-gray-500 dark:text-gray-400">{t("riskSummary")}</dt><dd className="font-semibold">{risk.data?.amount == null ? t("unavailable") : <MarketValue amount={risk.data.amount} unit="USDT" grouped/>}</dd></div>
    </dl>
    {(snapshot.isError || catalog.isError || risk.isError) && <p role="alert">{t("loadError")}</p>}
    {data && !data.admission_ready && <div role="status" className="rounded-xl border border-warning-200 bg-warning-50 p-3 text-sm dark:border-warning-900/40 dark:bg-warning-900/10"><p>{t("blocked")}</p><ul className="mt-2 space-y-1">{data.admission_reasons.map(reason => <li key={reason}>• {manualCode(reason)}</li>)}</ul></div>}
    {risk.data && (risk.data.latched || risk.data.stop_id) && <div role="alert" className="rounded-xl border border-error-200 bg-error-50 p-3 text-sm dark:border-error-900/40 dark:bg-error-900/10">
      <p className="font-medium">{t("riskStopStatus")}</p>
      <p>{riskCode(risk.data.stop_progress ?? risk.data.reason)}</p>
    </div>}
    {recentResult && <RequestSnapshot value={recentResult}/>}
    {data && wallet === null && <p>{t("noWallet")}</p>}
    <p className="text-sm text-gray-500 dark:text-gray-400">{t("episodeDraftNotice")}</p>
    <ManualOrderForm key={draftKey} bases={bases} base={base} onBase={changeBase} showPairSelector={false} scope={scope} canSubmit={canSubmit} disabled={blocked} onSubmit={payload => recovery.send({ version: 1, mode: "PAPER", owner, action: "NEW", key: globalThis.crypto.randomUUID(), payload })}/>
  </section>;
  return <TradingWorkspace mode="PAPER" bases={bases} base={base} onBase={changeBase}
    pairDisabled={blocked || catalog.isPending || catalog.isError}
    marketPrice={market?.price} marketObservedAt={market?.observedAt ?? data?.market_observed_at}
    marketStatus={fresh ? t("marketReady") : t("marketLoading")}
    chart={<CandlestickChartPanel userId={owner} base={base} onBaseChange={changeBase} embedded onMarketSnapshot={setMarketSnapshot}/>} form={form}
    details={details}
    orders={wallet ? <div className="trade-workspace-orders"><PaperOrderList key={wallet.episode_id} owner={owner} episode={wallet.episode_id} visible={visible} disabled={blocked || snapshot.isError || snapshot.isPending} onCancel={row => recovery.send({ version: 1, owner, mode: "PAPER", key: globalThis.crypto.randomUUID(), action: "CANCEL", orderId: row.order_id, payload: { expected_wallet_id: row.wallet_id, expected_episode_id: row.episode_id } })}/></div> : undefined}/>;
}
