import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { OrderStatus } from "./components/OrderStatus";
import { manualCode, manualOrderLocale, manualOrderText as t } from "./manualOrderMessages";
import { fetchRequest, manualKey, requestTerminal, type ManualRequest } from "./manualOrders";

export function RequestSnapshot({ value }: { value: ManualRequest }) {
  const summary = value.request_summary;
  return <article className="space-y-4 rounded-xl border border-gray-200 p-4 dark:border-gray-800" aria-label={`${t("order")} ${value.order_id}`}>
    <p className="break-all">{value.action === "CANCEL" ? t("cancel") : t("form")}: {value.order_id}</p>
    <p className="text-sm break-all">{t("episode")}: {value.episode_id}</p>
    {summary && <p>{summary.base}/{summary.quote} {t(summary.side)} {t(summary.kind)} <MarketValue amount={summary.base_quantity ?? summary.quote_budget ?? ""} unit={summary.base_quantity === null ? summary.quote : summary.base}/>{summary.limit_price !== null && <> · <MarketValue amount={summary.limit_price} unit={summary.quote}/> {t("GTC")}</>}</p>}
    <dl className="flex flex-wrap gap-4" role="status" aria-live="polite" aria-atomic="true">
      <div><dt>{t("intake")}</dt><dd><OrderStatus status={value.intake_state}/></dd></div>
      <div><dt>{t("command")}</dt><dd><OrderStatus status={value.command_state}/></dd></div>
      <div><dt>{t("status")}</dt><dd><OrderStatus status={value.order_state}/></dd></div>
    </dl>
    {(value.intake_failure_code || value.command_failure_code) && <p role="alert">{t("failure")}: {manualCode(value.intake_failure_code ?? value.command_failure_code)}</p>}
    <p className="text-sm">{t("snapshot")} <MarketTime value={value.snapshot_at} locale={manualOrderLocale()}/></p>
  </article>;
}
export function ManualRequestStatus({ owner, episode, request, visible, onTerminal }: {
  owner: string; episode: string; request: string; visible: boolean; onTerminal?: (value: ManualRequest) => void;
}) {
  const client = useQueryClient();
  const notified = useRef(false);
  const query = useQuery({ queryKey: [...manualKey(owner), episode, "request", request],
    enabled: visible, queryFn: async ({ signal }) => {
      const value = await fetchRequest(request, signal);
      if (value.mode !== "PAPER" || value.episode_id !== episode || value.request_id !== request) throw new Error("request scope mismatch");
      return value;
    }, refetchInterval: q => visible && (!q.state.data || !requestTerminal(q.state.data)) ? 1000 : false,
    refetchIntervalInBackground: false,
  });
  useEffect(() => {
    if (!query.data || !requestTerminal(query.data) || notified.current) return;
    notified.current = true;
    void client.invalidateQueries({ queryKey: [...manualKey(owner), episode, "orders"] });
    void client.invalidateQueries({ queryKey: [...manualKey(owner), "trade"] });
    void client.invalidateQueries({ queryKey: ["paper-wallet", owner] });
    onTerminal?.(query.data);
  }, [query.data, client, owner, episode, onTerminal]);
  return <>{query.isError && <p role="alert">{t("loadError")}</p>}{query.data && <RequestSnapshot value={query.data}/>}</>;
}
