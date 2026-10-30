import type { ReactNode } from "react";
import { MarketValue } from "./components/MarketValue";
import { Badge } from "./components/ui/Badge";
import { Select } from "./components/ui/Select";
import { manualOrderText as t } from "./manualOrderMessages";

const displayedPrice = (value: string) => /^-?\d+$/.test(value) ? `${value}.00` : value;

/** Layout follows the information hierarchy of an exchange workspace and the TailAdmin theme tokens. */
export function TradingWorkspace({ mode, bases, base, onBase, marketPrice,
  pairDisabled = false, chart, form, details, orders }: {
  mode: "PAPER" | "LIVE";
  bases: string[];
  base: string;
  onBase: (base: string) => void;
  marketPrice?: string | null | undefined;
  pairDisabled?: boolean;
  chart: ReactNode;
  form: ReactNode;
  details?: ReactNode | undefined;
  orders?: ReactNode | undefined;
}) {
  return <section className={`trade-workspace ${orders ? "trade-workspace-with-orders" : "trade-workspace-without-orders"}`}
    aria-label={t(mode === "PAPER" ? "paper" : "live")}>
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
        <div id={`${mode.toLowerCase()}-chart-toolbar`} className="trade-chart-toolbar"/>
      </div>
      <dl className="trade-market-summary">
        <div><dt>{t("latestPrice")}</dt><dd>{marketPrice && base
          ? <MarketValue amount={displayedPrice(marketPrice)} unit="" grouped/> : t("unavailable")}</dd></div>
      </dl>
    </header>
    <div className="trade-workspace-chart">{chart}</div>
    <aside className="trade-workspace-form">{form}{details}</aside>
    {orders}
  </section>;
}
