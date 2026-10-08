import { useRealtimePrices } from "./useRealtimePrices";
import { realtimePriceI18n, realtimePriceText as t } from "./realtimePriceMessages";
import { MarketTime, MarketValue } from "./components/MarketValue";
import "./RealtimePricePanel.css";
export function RealtimePricePanel() {
    const { view, delivery } = useRealtimePrices();
    const time = (value: string) => <MarketTime value={value} locale={realtimePriceI18n.language}/>;
    return <section className="realtime-price-panel" aria-labelledby="realtime-price-heading" data-testid="realtime-prices">
  <h2 id="realtime-price-heading">{t("heading")}</h2>
  <p>{t("disclaimer")}</p>
  <p role="status" aria-live="polite">{t(delivery)}</p>
  {view && <><p>{t("checked")}: {time(view.server_time)}</p><p>{t("delivery")}: {t(view.delivery_status)}</p>
   <ul className="realtime-price-list">{view.rows.map(row => <li key={`${row.source}:${row.base}:${row.quote}`} data-testid={`price-${row.base}`}>
    <h3>{row.base}/{row.quote}</h3>
    <p>{row.amount === null ? t("missing") : <MarketValue amount={row.amount} unit={row.quote}/>}</p>
    <p>{t(row.readiness)}</p>
    <p>{t("trade")}: {row.trade_at === null ? t("missing") : time(row.trade_at)}</p>
    <p>{t("reason")}: <span>{t(`reasons.${row.reason}`, { defaultValue: t("unknownReason") })}</span></p>
    {row.alert_due && <p className="realtime-price-warning">{t("marketWarning")}</p>}
   </li>)}</ul></>}
 </section>;
}
