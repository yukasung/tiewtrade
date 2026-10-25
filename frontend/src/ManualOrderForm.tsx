import { useState } from "react";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Select } from "./components/ui/Select";
import { manualOrderText as t } from "./manualOrderMessages";
import type { ExpectedEpisode, NewManualOrder } from "./manualOrders";

/** Layout adapted from references/admin-template/src/components/form/form-elements/DefaultInputs.tsx. */
export function ManualOrderForm({ bases, base, onBase, scope, canSubmit, disabled = false, mode = "PAPER", onSubmit }: {
  bases: string[]; base: string; onBase: (base: string) => void; scope: ExpectedEpisode | null;
  mode?: "PAPER" | "LIVE"; canSubmit: (side: "BUY" | "SELL") => boolean; disabled?: boolean; onSubmit: (value: NewManualOrder) => void;
}) {
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [kind, setKind] = useState<"MARKET" | "LIMIT">("MARKET");
  const [amount, setAmount] = useState("");
  const [price, setPrice] = useState("");
  const budget = kind === "MARKET" && side === "BUY";
  return <form className="space-y-6" onSubmit={event => {
    event.preventDefault();
    if (disabled || !canSubmit(side) || !scope || !base) return;
    const common = { ...scope, base, quote: "USDT" as const, side };
    onSubmit(kind === "LIMIT" ? { ...common, kind, base_quantity: amount, limit_price: price, time_in_force: "GTC" } :
      side === "BUY" ? { ...common, kind, side, quote_budget: amount } : { ...common, kind, side, base_quantity: amount });
  }}>
    <div><Label htmlFor="manual-pair">{t("pair")}</Label>
      <Select id="manual-pair" value={base} disabled={disabled} onChange={event => { onBase(event.target.value); setAmount(""); setPrice(""); }} required>
        <option value="">{t("choosePair")}</option>
        {bases.map(asset => <option key={asset} value={asset}>{asset}/USDT</option>)}
      </Select></div>
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
      <div><Label htmlFor="manual-side">{t("side")}</Label><Select id="manual-side" value={side} disabled={disabled} onChange={event => {
        setSide(event.target.value as "BUY" | "SELL"); setAmount("");
      }}><option value="BUY">{t("BUY")}</option><option value="SELL">{t("SELL")}</option></Select></div>
      <div><Label htmlFor="manual-kind">{t("kind")}</Label><Select id="manual-kind" value={kind} disabled={disabled} onChange={event => {
        setKind(event.target.value as "MARKET" | "LIMIT"); setAmount(""); setPrice("");
      }}><option value="MARKET">{t("MARKET")}</option><option value="LIMIT">{t("LIMIT")}</option></Select></div>
    </div>
    <div><Label htmlFor="manual-amount">{t(budget ? "budget" : "quantity")}{!budget && base ? ` (${base})` : ""}</Label>
      <Input id="manual-amount" inputMode="decimal" autoComplete="off" required disabled={disabled} maxLength={256} value={amount} onChange={event => setAmount(event.target.value)} /></div>
    {kind === "LIMIT" && <><div><Label htmlFor="manual-price">{t("price")}</Label>
      <Input id="manual-price" inputMode="decimal" autoComplete="off" required maxLength={256} disabled={disabled} value={price} onChange={event => setPrice(event.target.value)} /></div><p>{t("GTC")}</p></>}
    <p id="manual-safety-note" className="text-sm text-gray-500 dark:text-gray-400">{t("sellCheck")}</p>
    <Button type="submit" disabled={disabled || !scope || !base || !amount || (kind === "LIMIT" && !price) || !canSubmit(side)} aria-describedby="manual-safety-note">{t(mode === "LIVE" ? "unavailable" : "submit")}</Button>
  </form>;
}
