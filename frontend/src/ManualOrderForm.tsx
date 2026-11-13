import { useState } from "react";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import { Tabs } from "./components/ui/Tabs";
import { manualOrderText as t } from "./manualOrderMessages";
import type { Protection } from "./protections";
import { MarketValue } from "./components/MarketValue";
import { protectionText as pt } from "./protectionMessages";
import type { ExpectedEpisode, NewManualOrder } from "./manualOrders";

/** Layout adapted from references/admin-template/src/components/form/form-elements/DefaultInputs.tsx. */
export function ManualOrderForm({ bases, base, onBase, scope, canSubmit, disabled = false, mode = "PAPER",
  showPairSelector = true, fixedSide, submitLabel, protections = [], protectionsReady = true, protectionEnabled = false, onSubmit }: {
  bases: string[]; base: string; onBase: (base: string) => void; scope: ExpectedEpisode | null;
  mode?: "PAPER" | "LIVE"; canSubmit: (side: "BUY" | "SELL") => boolean; disabled?: boolean;
  protections?: Protection[]; protectionsReady?: boolean; protectionEnabled?: boolean;
  showPairSelector?: boolean; fixedSide?: "SELL"; submitLabel?: string; onSubmit: (value: NewManualOrder) => void;
}) {
  const [selectedSide, setSelectedSide] = useState<"BUY" | "SELL">("BUY");
  const side = fixedSide ?? selectedSide;
  const [kind, setKind] = useState<"MARKET" | "LIMIT">("MARKET");
  const [amount, setAmount] = useState("");
  const [price, setPrice] = useState("");
  const [tp, setTp] = useState("");
  const [sl, setSl] = useState("");
  const [selected, setSelected] = useState<Record<string, { quantity: string; revision: number }>>({});
  const budget = kind === "MARKET" && side === "BUY";
  const hasProtectionPrices = Boolean(tp || sl);
  const showProtectionFields = side === "BUY" && (protectionEnabled || hasProtectionPrices);
  const protectionUnavailable = side === "BUY" && hasProtectionPrices && !protectionEnabled;
  return <form className="space-y-6" onSubmit={event => {
    event.preventDefault();
    if (disabled || protectionUnavailable || !canSubmit(side) || !scope || !base || (side === "SELL" && !protectionsReady)) return;
    const attachments = side === "BUY" && protectionEnabled && hasProtectionPrices ? { protection: { take_profit_price: tp || null, stop_loss_price: sl || null } } :
      side === "SELL" && Object.values(selected).some(v => v.quantity !== "") ? { protection_allocations: Object.entries(selected).filter(([, value]) => value.quantity !== "").map(([id, value]) => ({ protection_id: id, quantity: value.quantity, expected_revision: value.revision })) } : {};
    const common = { ...scope, base, quote: "USDT" as const, side, ...attachments };
    onSubmit(kind === "LIMIT" ? { ...common, kind, base_quantity: amount, limit_price: price, time_in_force: "GTC" } :
      side === "BUY" ? { ...common, kind, side, quote_budget: amount } : { ...common, kind, side, base_quantity: amount });
  }}>
    {showPairSelector && <div><Label htmlFor="manual-pair">{t("pair")}</Label>
      <Select id="manual-pair" value={base} disabled={disabled} onChange={event => { onBase(event.target.value); setAmount(""); setPrice(""); setTp(""); setSl(""); setSelected({}); }} required>
        <option value="">{t("choosePair")}</option>
        {bases.map(asset => <option key={asset} value={asset}>{asset}/USDT</option>)}
      </Select></div>}
    <div className="grid grid-cols-1 gap-4">
      {!fixedSide && <div><Label>{t("side")}</Label><Tabs id="manual-side" controls="manual-order-fields" label={t("side")}
        items={[{ id: "BUY", label: t("BUY") }, { id: "SELL", label: t("SELL") }]} active={side} disabled={disabled}
        onChange={value => { setSelectedSide(value); setAmount(""); setTp(""); setSl(""); setSelected({}); }}/></div>}
      <div><Label>{t("kind")}</Label><Tabs id="manual-kind" controls="manual-order-fields" label={t("kind")}
        items={[{ id: "MARKET", label: t("MARKET") }, { id: "LIMIT", label: t("LIMIT") }]} active={kind} disabled={disabled}
        onChange={value => { setKind(value); setAmount(""); setPrice(""); }}/></div>
    </div>
    <div id="manual-order-fields" role="tabpanel" className="space-y-6"><div><Label htmlFor="manual-amount">{t(budget ? "budget" : "quantity")}{!budget && base ? ` (${base})` : ""}</Label>
      <Input id="manual-amount" inputMode="decimal" autoComplete="off" required disabled={disabled} maxLength={256} value={amount} onChange={event => setAmount(event.target.value)} /></div>
    {kind === "LIMIT" && <><div><Label htmlFor="manual-price">{t("price")}</Label>
      <Input id="manual-price" inputMode="decimal" autoComplete="off" required maxLength={256} disabled={disabled} value={price} onChange={event => setPrice(event.target.value)} /></div><p>{t("GTC")}</p></>}</div>
    {showProtectionFields && <div className="space-y-4">
      <div><Label htmlFor="entry-tp">{pt("tp")}</Label><Input id="entry-tp" inputMode="decimal" autoComplete="off" maxLength={256} disabled={disabled} value={tp} onChange={e => setTp(e.target.value)}/></div>
      <div><Label htmlFor="entry-sl">{pt("sl")}</Label><Input id="entry-sl" inputMode="decimal" autoComplete="off" maxLength={256} disabled={disabled} value={sl} onChange={e => setSl(e.target.value)}/></div>
    </div>}
    {protectionUnavailable && <p role="alert">{pt("unavailable")}</p>}
    {side === "SELL" && protections.filter(p => !p.conflicted && ["ARMED", "ARMING", "FAILED"].includes(p.state)).map(p => <div key={p.protection_id}>
      <Label htmlFor={`release-${p.protection_id}`}>{pt("release")} (<MarketValue amount={p.quantity} unit={p.base}/>; TP {p.take_profit_price ? <MarketValue amount={p.take_profit_price} unit="USDT"/> : "—"}; SL {p.stop_loss_price ? <MarketValue amount={p.stop_loss_price} unit="USDT"/> : "—"})</Label>
      <Input id={`release-${p.protection_id}`} inputMode="decimal" autoComplete="off" maxLength={256} disabled={disabled} value={selected[p.protection_id]?.quantity ?? ""} onChange={e => setSelected(previous => ({ ...previous, [p.protection_id]: { quantity: e.target.value, revision: p.revision } }))}/>
    </div>)}
    {side === "SELL" && Object.values(selected).some(v => v.quantity !== "") && <p role="note" className="text-sm text-warning-600 dark:text-warning-400">{pt("warning")}</p>}
    <p id="manual-safety-note" className="text-sm text-gray-500 dark:text-gray-400">{t("sellCheck")}</p>
    <Button className="w-full" type="submit" disabled={disabled || protectionUnavailable || (side === "SELL" && !protectionsReady) || !scope || !base || !amount || (kind === "LIMIT" && !price) || !canSubmit(side)} aria-describedby="manual-safety-note">{submitLabel ?? t(mode === "LIVE" ? "unavailable" : "submit")}</Button>
  </form>;
}
