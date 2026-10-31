import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { navigateAccountPage } from "./accountNavigation";
import { CandlestickChartPanel } from "./CandlestickChartPanel";
import { ManualOrderForm } from "./ManualOrderForm";
import { ManualRequestStatus } from "./ManualRequestStatus";
import { PaperOrderList } from "./PaperOrderList";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
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
  useEffect(() => {
    if (visible && discovery.hasNextPage && !discovery.isFetchingNextPage) void discovery.fetchNextPage();
  }, [visible, discovery.hasNextPage, discovery.isFetchingNextPage, discovery.fetchNextPage]);
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
  const recoveryVisible = discovery.isError || recovery.storageError || Boolean(recovery.error) ||
    Boolean(recovery.attempt && recovery.lookup.isError && !attemptData);
  const recoveryNotice = recoveryVisible ? <div className="space-y-2 text-sm" aria-live="polite">
      {recovery.error?.status === 422 && !recovery.attempt && <p role="alert">{t("safeFailure")}</p>}
      {recovery.error?.message === "MANUAL_ORDER_EPISODE_CLOSED" && !recovery.attempt && <p role="alert">{t("episodeClosed")}</p>}
      {recovery.storageError && <p role="alert">{t("storage")}</p>}
      {discovery.isError && <p role="alert">{t("recoveryError")}</p>}
      <div className="flex flex-wrap gap-2">
        {discovery.isError && <Button size="sm" type="button" disabled={discovery.isFetching} onClick={() => void discovery.refetch()}>{t("check")}</Button>}
      </div>
      {recovery.attempt && !attemptData && <div className="space-y-2" role="status">
        <p>{t("unknown")}</p>
        {recovery.error?.status === 429 && <p>{t("limited")} {recovery.error.retryAt && <MarketTime value={recovery.error.retryAt} locale={manualOrderLocale()}/>}</p>}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" type="button" disabled={recovery.busy || recovery.lookup.isFetching} onClick={() => void recovery.lookup.refetch()}>{t("check")}</Button>
          <Button size="sm" type="button" disabled={recovery.busy || recovery.storageError || !recovered || !!attemptData} onClick={() => recovery.send(recovery.attempt!, true)}>{t("retry")}</Button>
        </div>
      </div>}
    </div> : null;
  const form = <section aria-labelledby="manual-form-heading" className="space-y-5">
    <div><h2 id="manual-form-heading" className="text-lg font-semibold">{t("form")}</h2><p className="text-sm text-gray-500 dark:text-gray-400">{t("pendingNotice")}</p></div>
    <dl className="grid grid-cols-2 gap-3 rounded-xl border border-gray-200 p-3 text-sm dark:border-gray-800">
      <div><dt className="text-gray-500 dark:text-gray-400">{t("available")}</dt><dd className="font-semibold">{wallet?.available_quote == null ? t("unavailable") : <MarketValue amount={wallet.available_quote} unit="USDT" grouped/>}</dd></div>
      <div><dt className="text-gray-500 dark:text-gray-400">{t("riskSummary")}</dt><dd className="font-semibold">{risk.data?.amount == null ? t("unavailable") : <MarketValue amount={risk.data.amount} unit="USDT" grouped/>}</dd>
        {risk.isSuccess && risk.data.amount === null && <a href="/trading-account" onClick={navigateAccountPage} className="mt-1 inline-flex text-sm font-medium text-brand-500 hover:text-brand-600">{t("manageRisk")}</a>}
      </div>
    </dl>
    {(snapshot.isError || catalog.isError || risk.isError) && <p role="alert">{t("loadError")}</p>}
    {data && !data.admission_ready && <div role="status" className="rounded-xl border border-warning-200 bg-warning-50 p-3 text-sm dark:border-warning-900/40 dark:bg-warning-900/10"><p>{t("blocked")}</p><ul className="mt-2 space-y-1">{data.admission_reasons.map(reason => <li key={reason}>• {manualCode(reason)}</li>)}</ul></div>}
    {risk.data && (risk.data.latched || risk.data.stop_id) && <div role="alert" className="rounded-xl border border-error-200 bg-error-50 p-3 text-sm dark:border-error-900/40 dark:bg-error-900/10">
      <p className="font-medium">{t("riskStopStatus")}</p>
      <p>{riskCode(risk.data.stop_progress ?? risk.data.reason)}</p>
    </div>}
    {recoveryNotice}
    {recentResult && (recentResult.intake_failure_code || recentResult.command_failure_code) && <p role="alert">{t("failure")}: {manualCode(recentResult.intake_failure_code ?? recentResult.command_failure_code)}</p>}
    {data && wallet === null && <p>{t("noWallet")}</p>}
    <ManualOrderForm key={draftKey} bases={bases} base={base} onBase={changeBase} showPairSelector={false} scope={scope} canSubmit={canSubmit} disabled={blocked} onSubmit={payload => recovery.send({ version: 1, mode: "PAPER", owner, action: "NEW", key: globalThis.crypto.randomUUID(), payload })}/>
    <div hidden aria-hidden="true">
      {Object.entries(tracked).map(([id, episode]) => <ManualRequestStatus key={id} owner={owner} request={id} episode={episode} visible={visible} onTerminal={completeTracked} showSnapshot={false}/>)}
    </div>
  </section>;
  return <TradingWorkspace mode="PAPER" bases={bases} base={base} onBase={changeBase}
    pairDisabled={blocked || catalog.isPending || catalog.isError}
    marketPrice={market?.price}
    chart={<CandlestickChartPanel userId={owner} base={base} onBaseChange={changeBase} embedded
      toolbarTargetId="paper-chart-toolbar" onMarketSnapshot={setMarketSnapshot}/>} form={form}
    orders={wallet ? <div className="trade-workspace-orders"><PaperOrderList key={wallet.episode_id} owner={owner} episode={wallet.episode_id} visible={visible} disabled={blocked || snapshot.isError || snapshot.isPending} onCancel={row => recovery.send({ version: 1, owner, mode: "PAPER", key: globalThis.crypto.randomUUID(), action: "CANCEL", orderId: row.order_id, payload: { expected_wallet_id: row.wallet_id, expected_episode_id: row.episode_id } })}/></div> : undefined}/>;
}
