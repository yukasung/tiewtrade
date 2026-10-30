import type { ReactNode } from "react";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Badge } from "./components/ui/Badge";
import { Select } from "./components/ui/Select";
import { manualOrderLocale, manualOrderText as t } from "./manualOrderMessages";

/** Layout follows the information hierarchy of an exchange workspace and the TailAdmin theme tokens. */
export function TradingWorkspace({ mode, bases, base, onBase, marketPrice, marketObservedAt,
  marketStatus, pairDisabled = false, chart, form, details, orders }: {
  mode: "PAPER" | "LIVE";
  bases: string[];
  base: string;
  onBase: (base: string) => void;
  marketPrice?: string | null | undefined;
  marketObservedAt?: string | null | undefined;
  marketStatus: string;
  pairDisabled?: boolean;
  chart: ReactNode;
  form: ReactNode;
  details?: ReactNode | undefined;
  orders?: ReactNode | undefined;
}) {
  return <section className="trade-workspace" aria-label={t(mode === "PAPER" ? "paper" : "live")}>
    <header className="trade-workspace-bar">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <Badge color={mode === "PAPER" ? "primary" : "warning"}>{mode}</Badge>
        <div className="min-w-40">
          <Select id={`${mode.toLowerCase()}-workspace-pair`} aria-label={t("pair")} value={base}
            disabled={pairDisabled} onChange={event => onBase(event.target.value)}>
            <option value="">{t("choosePair")}</option>
            {bases.map(asset => <option key={asset} value={asset}>{asset}/USDT</option>)}
          </Select>
        </div>
      </div>
      <dl className="trade-market-summary">
        <div><dt>{t("latestPrice")}</dt><dd>{marketPrice && base
          ? <MarketValue amount={marketPrice} unit="USDT" grouped/> : t("unavailable")}</dd></div>
        <div><dt>{t("marketStatus")}</dt><dd>{marketStatus}</dd></div>
        <div><dt>{t("marketObserved")}</dt><dd>{marketObservedAt
          ? <MarketTime value={marketObservedAt} locale={manualOrderLocale()}/> : t("unavailable")}</dd></div>
      </dl>
    </header>
    <div className="trade-workspace-main">
      <div className="trade-workspace-chart">{chart}</div>
      <aside className="trade-workspace-form">{form}</aside>
    </div>
    {orders}
    {details}
  </section>;
}
