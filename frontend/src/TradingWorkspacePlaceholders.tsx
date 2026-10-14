import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/Table";
import { Tabs } from "./components/ui/Tabs";
import { chartI18n } from "./chartMessages";

const t = chartI18n.getFixedT("th");

export function TradingOrderPlaceholder() {
  return <aside className="trading-order-panel" aria-labelledby="trading-order-heading"
    data-testid="trading-order-placeholder">
    <div className="trading-placeholder-heading">
      <h3 id="trading-order-heading">{t("workspace.orderHeading")}</h3>
      <span>{t("workspace.unavailable")}</span>
    </div>
    <Tabs label={t("workspace.orderSide")} items={[t("workspace.buy"), t("workspace.sell")]}
      active={t("workspace.buy")}/>
    <div className="trading-order-fields">
      <Label htmlFor="placeholder-order-type">{t("workspace.orderType")}</Label>
      <Select id="placeholder-order-type" disabled value="LIMIT" aria-describedby="trading-order-note">
        <option value="LIMIT">Limit</option>
      </Select>
      <Label htmlFor="placeholder-price">{t("workspace.price")}</Label>
      <Input id="placeholder-price" disabled inputMode="decimal" placeholder="USDT"
        aria-describedby="trading-order-note"/>
      <Label htmlFor="placeholder-quantity">{t("workspace.quantity")}</Label>
      <Input id="placeholder-quantity" disabled inputMode="decimal" placeholder="BTC"
        aria-describedby="trading-order-note"/>
      <Label htmlFor="placeholder-total">{t("workspace.total")}</Label>
      <Input id="placeholder-total" disabled inputMode="decimal" placeholder="USDT"
        aria-describedby="trading-order-note"/>
    </div>
    <Button className="trading-placeholder-action" disabled>{t("workspace.unavailable")}</Button>
    <p id="trading-order-note" className="trading-placeholder-note">{t("workspace.orderNotice")}</p>
  </aside>;
}

export function TradeHistoryPlaceholder() {
  const headings = ["date", "pairColumn", "side", "price", "quantity", "status"] as const;
  return <section className="trading-history-panel" aria-labelledby="trade-history-heading"
    data-testid="trade-history-placeholder">
    <div className="trading-history-heading">
      <h3 id="trade-history-heading" className="sr-only">{t("workspace.historyHeading")}</h3>
      <Tabs label={t("workspace.historyTabs")}
        items={[t("workspace.openOrders"), t("workspace.orderHistory"), t("workspace.tradeHistory")]}
        active={t("workspace.openOrders")}/>
    </div>
    <div className="trading-table-scroll">
      <Table>
        <TableHeader><TableRow>
          {headings.map(name => <TableHead key={name} scope="col">{t(`workspace.${name}`)}</TableHead>)}
        </TableRow></TableHeader>
        <TableBody><TableRow>
          <TableCell colSpan={headings.length} className="trading-history-empty">
            {t("workspace.historyEmpty")}
          </TableCell>
        </TableRow></TableBody>
      </Table>
    </div>
  </section>;
}
