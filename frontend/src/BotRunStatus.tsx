import { useQuery } from "@tanstack/react-query";
import type { components } from "./api-types";
import { send } from "./auth";
import { Badge } from "./components/ui/Badge";
import { Alert } from "./components/ui/Alert";
import { Button } from "./components/ui/Button";
import { BotStopControls } from "./KillSwitchControls";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { manualOrderLocale } from "./manualOrderMessages";
import { paperBotText } from "./paperBotMessages";
import { protectionText } from "./protectionMessages";

type BotStatus = components["schemas"]["BotStatusView"];
type Mode = BotStatus["mode"];

export function BotRunStatus({ owner, mode, compact = false }: { owner: string; mode: Mode; compact?: boolean }) {
  const query = useQuery({
    queryKey: ["bot-status", owner, mode],
    queryFn: ({ signal }) =>
      send<BotStatus>(`/${mode === "PAPER" ? "paper" : "live"}/bots/status`, undefined, undefined, "GET", signal),
    retry: false,
    refetchInterval: 2000,
  });
  const run = query.isSuccess ? query.data : null;
  const status = run?.status;
  if (query.isError) return <div role="alert" className="space-y-2">
    <Alert variant="warning" title={paperBotText("statusUnavailable")} message={paperBotText("statusRetry")}/>
    <Button size="sm" variant="outline" onClick={() => void query.refetch()}>{paperBotText("retry")}</Button>
    {compact && (query.data?.run_id || query.data?.pending_request_id) &&
      <BotStopControls owner={owner} mode={mode} compact/>}
  </div>;
  if (!run || (!status && !run.pending_request_id)) return null;
  const showStatusBadge = mode !== "PAPER" || status !== "PAUSED";
  const readinessMessage = status === "PAUSED"
    && run.readiness_reason?.startsWith("BOT_CANDLE_")
    && run.readiness_reason !== "BOT_CANDLE_UNCONFIRMED"
    ? paperBotText("awaitingData") : null;
  if (compact) return <div className="space-y-3">
    {(run.pending_request_id || showStatusBadge) && <div role="status"><Badge color={status === "RUNNING" ? "success" : "light"}>
      {run.pending_request_id ? paperBotText("requestPending") : status ? paperBotText(status) : ""}
    </Badge></div>}
    {run.stop_reason && <p className="text-sm text-gray-500 dark:text-gray-400">{paperBotText(run.stop_reason)}</p>}
    <BotStopControls owner={owner} mode={mode} compact/>
    {readinessMessage && <p className="text-sm text-gray-500 dark:text-gray-400">{readinessMessage}</p>}
  </div>;
  return (
    <div className="space-y-3">
    {run.pending_request_id && <div role="status">
      <Badge color="light">{paperBotText("requestPending")}</Badge>
    </div>}
    {run.snapshot_at && <p className="text-sm text-gray-500 dark:text-gray-400">
      {paperBotText("snapshotAt")} <MarketTime value={run.snapshot_at} locale={manualOrderLocale()}/>
      {query.isFetching && <> · {paperBotText("updating")}</>}
    </p>}
    {status && <div className="flex flex-wrap items-center gap-2" role="status">
      <span className="text-sm text-gray-500 dark:text-gray-400">{paperBotText("runStatus")}</span>
      {showStatusBadge && <Badge color={status === "RUNNING" ? "success" : status === "STOPPED" ? "warning" : "light"}>
        {paperBotText(status)}
      </Badge>}
      {run?.stop_reason && <span className="text-sm text-gray-500 dark:text-gray-400">
        {paperBotText(run.stop_reason)}
      </span>}
      {status === "PAUSED" && <span className="text-sm text-gray-500 dark:text-gray-400">{paperBotText("sourceNotReady")}</span>}
      {readinessMessage && <span className="text-sm text-gray-500 dark:text-gray-400">{readinessMessage}</span>}
    </div>}
    <p className="text-sm text-gray-500 dark:text-gray-400">{paperBotText("exposureNotice")}</p>
    {run.pinned_configuration && <div className="space-y-1 text-sm">
      <strong>{paperBotText("pinnedConfig")}</strong>
      <p>{run.pinned_configuration.base}/USDT · {run.pinned_configuration.timeframe}</p>
      <p>{paperBotText("budget")}: <MarketValue amount={run.pinned_configuration.capital_per_entry} unit="USDT"/></p>
      <p>{paperBotText("entries")}: {run.open_entries}/{"max_entries" in run.pinned_configuration ? run.pinned_configuration.max_entries : 1}</p>
      <p>{paperBotText("basketTarget")}: {run.basket_target ? <MarketValue amount={run.basket_target} unit="USDT"/> : "—"}</p>
    </div>}
    {!run.exposure_available && <p role="status" className="text-sm text-gray-500 dark:text-gray-400">{paperBotText("exposureUnavailable")}</p>}
    {run.exposure_available && <div className="space-y-2 text-sm">
      <strong>{paperBotText("holdings")}</strong>
      {(run.positions ?? []).length === 0 && <p>{paperBotText("noHoldings")}</p>}
      <ul>{(run.positions ?? []).map(position => <li key={`${position.base}:${position.quote}`}>
        {position.base}/{position.quote}: <MarketValue amount={position.quantity} unit={position.base}/>
      </li>)}</ul>
    </div>}
    {(run.protections ?? []).length > 0 && <div className="space-y-2 text-sm">
      <strong>{protectionText("title")} · {protectionText("remaining")}</strong>
      <ul>{run.protections.map(protection => <li key={protection.protection_id}>
        <MarketValue amount={protection.quantity} unit={protection.base}/> · {protectionText(protection.state)}
        {protection.conflicted && <> · {protectionText("conflict")}</>}
      </li>)}</ul>
    </div>}
    {run.protections_more && <p role="status" className="text-sm text-gray-500 dark:text-gray-400">{paperBotText("moreProtections")}</p>}
    <BotStopControls owner={owner} mode={mode}/>
    </div>
  );
}
