import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "./api-types";
import { ApiRequestError, send } from "./auth";
import { JournalUnavailable } from "./attemptJournal";
import { strategyJournal, paperTestStrategy, rsiStepStrategy, type StrategyAttempt } from "./strategyJournal";
import { fetchStopStatus, stopKey } from "./killSwitch";
import { StopSummaryModal } from "./StopSummaryModal";
import { BotRunStatus } from "./BotRunStatus";
import { MarketValue } from "./components/MarketValue";
import { Alert } from "./components/ui/Alert";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import { manualOrderText as t } from "./manualOrderMessages";
import { manualKey } from "./manualOrders";
import { paperBotText as bt } from "./paperBotMessages";

type Status = components["schemas"]["BotStatusView"];
type Catalog = components["schemas"]["StrategyCatalogView"];
type Config = components["schemas"]["StrategyConfigurationView"] | components["schemas"]["PaperTestConfigurationView"];
type Receipt = components["schemas"]["BotReceiptView"];

/** TailAdmin FormElements/InputField/SelectInputs; business state remains server-owned. */
export function PaperBotPanel({ owner, base = "BTC", available, loading }: {
  owner: string; base?: string; available: string | null; loading: boolean;
}) {
  const queries = useQueryClient();
  const [budget, setBudget] = useState("");
  const [strategy, setStrategy] = useState(rsiStepStrategy);
  const [count, setCount] = useState(10);
  const [timeframe, setTimeframe] = useState("5m");
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [stopSummaryOpen, setStopSummaryOpen] = useState(false);
  const stopSummaryTrigger = useRef<HTMLButtonElement>(null);
  const [journal, setJournal] = useState(() => {
    try { return { attempt: strategyJournal.read(owner), blocked: false }; }
    catch { return { attempt: null, blocked: true }; }
  });
  const status = useQuery({ queryKey: ["bot-status", owner, "PAPER"],
    queryFn: ({ signal }) => send<Status>("/paper/bots/status", undefined, undefined, "GET", signal),
    retry: false, refetchInterval: 2000 });
  const stop = useQuery({ queryKey: stopKey(owner, "PAPER"),
    queryFn: ({ signal }) => fetchStopStatus("PAPER", signal), retry: false, refetchInterval: 1000 });
  const catalog = useQuery({ queryKey: ["bot-strategy-catalog", owner],
    queryFn: ({ signal }) => send<Catalog>("/paper/bots/strategy", undefined, undefined, "GET", signal),
    retry: false, staleTime: 60000 });
  const exposure = status.isSuccess && status.data.exposure_available
    ? JSON.stringify(status.data.positions) : null;
  const previousExposure = useRef<{ owner: string; value: string } | null>(null);
  useEffect(() => {
    if (exposure === null || exposure === undefined) return;
    const previous = previousExposure.current;
    previousExposure.current = { owner, value: exposure };
    if (previous?.owner === owner && previous.value !== exposure) {
      void queries.invalidateQueries({ queryKey: [...manualKey(owner), "trade"] });
    }
  }, [exposure, owner, queries]);
  const replacement = status.data?.replacement;
  const pinned = journal.attempt?.payload ?? (replacement ? undefined : status.data?.pinned_configuration);
  const selectedStrategy = pinned && "strategy_name" in pinned ? pinned.strategy_name : pinned ? rsiStepStrategy : strategy;
  const isTestStrategy = selectedStrategy === paperTestStrategy;
  const strategies = [...new Set([...(catalog.data?.strategies ?? [rsiStepStrategy]), ...(pinned && selectedStrategy ? [selectedStrategy] : [])])];
  const locked = busy || journal.attempt !== null || Boolean(status.data?.run_id && !replacement || status.data?.pending_request_id);
  const validBudget = /^(?:0|[1-9]\d*)(?:\.\d{1,18})?$/.test(budget) && /[1-9]/.test(budget);
  const readinessLoaded = status.isSuccess && stop.isSuccess;
  const stopBlocked = Boolean(readinessLoaded && !replacement && (stop.data?.active_causes?.length || stop.data?.platform_stop_id));
  const canStart = readinessLoaded && !stopBlocked && status.isSuccess && status.data.can_start && catalog.isSuccess
    && catalog.data.timeframes.includes(timeframe as Catalog["timeframes"][number])
    && (catalog.data.strategies ?? [rsiStepStrategy]).includes(strategy)
    && validBudget && (base === "BTC" || base === "ETH") && !loading && available !== null;
  const balance = available !== null ? <MarketValue amount={available} unit="USDT" grouped/>
    : loading ? bt("loading") : t("unavailable");

  useEffect(() => {
    const attempt = journal.attempt;
    if (!attempt || !status.isSuccess) return;
    const controller = new AbortController();
    void send<Receipt>(`/paper/bots/requests/by-key/${attempt.key}`, undefined, undefined, "GET", controller.signal)
      .then(receipt => {
        if (controller.signal.aborted || receipt.pending) return;
        strategyJournal.clear(owner, attempt.key);
        setJournal({ attempt: null, blocked: false });
        setError(receipt.failure_code);
      }).catch(() => { /* Keep the original identity for explicit recovery. */ });
    return () => controller.abort();
  }, [owner, journal.attempt, status.isSuccess, status.data?.run_id, status.data?.pending_request_id]);

  async function submit() {
    if (inFlight.current || journal.blocked || (!journal.attempt && !canStart)) return;
    inFlight.current = true; setBusy(true); setError(null);
    let attempt: StrategyAttempt | null = journal.attempt;
    try {
      if (attempt === null) {
        attempt = { version: 1, owner, key: globalThis.crypto.randomUUID(), configKey: globalThis.crypto.randomUUID(),
          payload: isTestStrategy ? { strategy_name: paperTestStrategy, base, timeframe, capital_per_entry: budget }
            : { base, timeframe, capital_per_entry: budget, max_entries: count },
          ...(replacement ? { replacement } : {}) };
        strategyJournal.write(attempt); setJournal({ attempt, blocked: false });
      } else {
        try {
          const receipt = await send<Receipt>(`/paper/bots/requests/by-key/${attempt.key}`, undefined, undefined, "GET");
          if (!receipt.pending) {
            strategyJournal.clear(owner, attempt.key); setJournal({ attempt: null, blocked: false });
            setError(receipt.failure_code);
          }
          await queries.invalidateQueries({ queryKey: ["bot-status", owner, "PAPER"] });
          return;
        } catch (failure) {
          if (!(failure instanceof ApiRequestError && failure.status === 404)) throw failure;
        }
      }
      if (attempt.reference === undefined) {
        const config = await send<Config>("/paper/bots/configurations", attempt.payload, undefined, "POST", undefined,
          { "Idempotency-Key": attempt.configKey });
        attempt = { ...attempt, reference: config.reference };
        strategyJournal.write(attempt); setJournal({ attempt, blocked: false });
      }
      const receipt = await send<Receipt>("/paper/bots/requests", { strategy_config_ref: attempt.reference,
        ...(attempt.replacement ? { replacement: attempt.replacement } : {}) }, undefined, "POST", undefined,
        { "Idempotency-Key": attempt.key });
      if (!receipt.pending) {
        strategyJournal.clear(owner, attempt.key); setJournal({ attempt: null, blocked: false });
        setError(receipt.failure_code);
      }
      await queries.invalidateQueries({ queryKey: ["bot-status", owner, "PAPER"] });
    } catch (failure) {
      if (failure instanceof JournalUnavailable) setJournal(value => ({ ...value, blocked: true }));
      else if (failure instanceof ApiRequestError && failure.status >= 400 && failure.status < 500
          && failure.status !== 408 && failure.status !== 429 && attempt !== null) {
        try { strategyJournal.clear(owner, attempt.key); setJournal({ attempt: null, blocked: false }); }
        catch { setJournal(value => ({ ...value, blocked: true })); }
      }
      setError("UNKNOWN");
    } finally { inFlight.current = false; setBusy(false); }
  }

  const showStop = Boolean(status.data?.pending_request_id ||
    (status.data?.run_id && status.data.pinned_configuration &&
      status.data.status !== "STOPPED" && status.data.status !== "RETIRED" && !replacement));

  const stopped = status.data?.status === "STOPPED";
  const stoppedMessage = status.data?.exposure_available === false ? bt("stoppedCheckHoldings")
    : status.data?.positions?.length ? bt("stoppedWithHoldings") : null;

  const showSettingsNotice = readinessLoaded && !showStop && !stopped;
  const noticeDescription = showSettingsNotice || (!showStop && stopped && stoppedMessage) ? "paper-bot-notice" : undefined;

  const readFailed = status.isError || stop.isError || catalog.isError;
  const retryReads = () => {
    if (status.isError) void status.refetch();
    if (stop.isError) void stop.refetch();
    if (catalog.isError) void catalog.refetch();
  };

  const failureText = error === "BOT_NOT_READY" ? bt("startNotReady")
    : error === "BOT_RISK_UNAVAILABLE" ? bt("startRiskUnavailable")
    : error === "BOT_PAIR_UNAVAILABLE" ? bt("startPairUnavailable") : bt("inputError");

  return <section aria-labelledby="paper-bot-title" className="space-y-4">
    <h2 id="paper-bot-title" className="border-b border-gray-200 pb-3 text-sm font-semibold dark:border-gray-800">{bt("title")}</h2>
    {status.data?.run_id && !status.data.pinned_configuration && !showStop && !stopped &&
      <BotRunStatus owner={owner} mode="PAPER"/>}
    <div>
      <Label htmlFor="paper-bot-strategy">{bt("strategy")}</Label>
      <Select id="paper-bot-strategy" value={selectedStrategy} disabled={locked || !catalog.isSuccess}
        onChange={event => { setStrategy(event.target.value); setTimeframe(event.target.value === paperTestStrategy ? "" : "5m"); }}>
        {strategies.map(name =>
          <option key={name} value={name}>{name === paperTestStrategy ? "Paper Test Entry · ATR TP/SL" : "RSI Step Grid · EMA20/50"}</option>)}
      </Select>
    </div>
    <dl className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1 text-sm" aria-live="polite">
      <dt className="text-gray-500 dark:text-gray-400">{t("available")}</dt>
      <dd className="font-medium tabular-nums">{balance}</dd>
    </dl>
    <p className="text-sm">{bt("pair")}: {pinned?.base ?? base}/USDT</p>
    <div>
      <Label htmlFor="paper-bot-budget">{bt("budget")}</Label>
      <Input id="paper-bot-budget" type="text" inputMode="decimal" autoComplete="off" maxLength={128}
        value={pinned?.capital_per_entry ?? budget} onChange={event => setBudget(event.target.value)}
        disabled={locked} aria-describedby={noticeDescription}/>
    </div>
    {!isTestStrategy && <div>
      <Label htmlFor="paper-bot-count">{bt("maxEntries")}</Label>
      <Select id="paper-bot-count" value={pinned && "max_entries" in pinned ? pinned.max_entries ?? count : count} disabled={locked}
        onChange={event => setCount(Number(event.target.value))}>
        {Array.from({ length: 10 }, (_, index) => index + 1).map(value => <option key={value} value={value}>{value}</option>)}
      </Select>
    </div>}
    <div>
      <Label htmlFor="paper-bot-timeframe">{bt("timeframe")}</Label>
      <Select id="paper-bot-timeframe" value={pinned?.timeframe ?? timeframe} disabled={locked || !catalog.isSuccess}
        onChange={event => setTimeframe(event.target.value)}>
        {isTestStrategy && <option value="">—</option>}
        {(catalog.data?.timeframes ?? ["5m"]).map(value => <option key={value} value={value}>{value}</option>)}
      </Select>
    </div>
    <div role="group" aria-label={bt("title")}>
    {showStop ? <BotRunStatus owner={owner} mode="PAPER" compact/> : <Button type="button" onClick={() => void submit()} disabled={busy || journal.blocked || (!journal.attempt && !canStart)} className="w-full" aria-describedby={noticeDescription}>
      {busy ? bt("submitting") : journal.attempt ? bt("recoverStart") : bt("start")}
    </Button>}
    </div>
    {!showStop && <>
    {stopped && stoppedMessage && <p id="paper-bot-notice" role="status" className="text-sm text-gray-500 dark:text-gray-400">{stoppedMessage}</p>}
    {stopBlocked && <div role="status" className="space-y-2">
      {!stopped && <Alert variant="warning" title={bt("accountStopped")} message={bt("resumeBeforeStart")}/>}
      {stop.data?.stop_id && <Button ref={stopSummaryTrigger} variant="outline" size="sm"
        onClick={() => setStopSummaryOpen(true)}>{bt("reviewStop")}</Button>}
    </div>}
    <StopSummaryModal owner={owner} mode="PAPER" stopId={stop.data?.stop_id ?? null}
      open={stopSummaryOpen} onClose={() => setStopSummaryOpen(false)} returnFocusRef={stopSummaryTrigger}/>
    {readFailed && <div role="alert" className="space-y-2 text-sm">
      <p>{bt("statusUnavailable")}</p>
      <Button size="sm" variant="outline" disabled={status.isFetching || stop.isFetching || catalog.isFetching}
        onClick={retryReads}>{bt("retry")}</Button>
    </div>}
    {error && !stopBlocked && <p role="alert" className="text-sm text-error-600">{failureText}</p>}
    {journal.blocked && <p role="alert" className="text-sm text-error-600">{bt("storageError")}</p>}
    {showSettingsNotice && <div id="paper-bot-notice"><Alert variant="info" title={bt(status.data?.unavailable_reason ? "unavailable" : "pinnedConfig")} message={bt("notice")}/></div>}
    </>}
  </section>;
}
