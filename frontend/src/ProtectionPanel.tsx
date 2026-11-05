import { useCallback, useState } from "react";
import type { ExpectedEpisode } from "./manualOrders";
import type { Protection } from "./protections";
import { useProtectionAttempt } from "./useProtections";
import { protectionText as t } from "./protectionMessages";
import { OrderStatus } from "./components/OrderStatus";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Modal } from "./components/ui/Modal";
import { Badge } from "./components/ui/Badge";
import { ComponentCard } from "./components/ui/ComponentCard";

type Draft = { target?: string; revision?: number; quantity: string; tp: string; sl: string };
/** Form controls/modal follow references/admin-template/src/components/form and components/ui/modal. */
export function ProtectionPanel({ owner, base, scope, rows, visible, disabled, ready, error, available, enabled }: {
  owner: string; base: string; scope: ExpectedEpisode; rows: Protection[]; visible: boolean; disabled: boolean; ready: boolean; error: boolean; available: string | null; enabled: boolean;
}) {
  const recovery = useProtectionAttempt(owner, visible);
  const [draft, setDraft] = useState<Draft | null>(null);
  const close = useCallback(() => setDraft(null), []);
  const blocked = disabled || !ready || !recovery.recovered || recovery.storageError || !!recovery.attempt || recovery.busy || recovery.pending.length > 0;
  const known = new Set(["WAITING_ENTRY", "ARMING", "ARMED", "EXITING", "CLOSED", "CANCELED", "FAILED"]);
  const shown = rows.filter(r => r.base === base && r.episode_id === scope.expected_episode_id);
  return <ComponentCard title={t("title")} headingId="protections-title" headerAction={<Button type="button" size="sm" disabled={blocked || !enabled || !base} onClick={() => setDraft({ quantity: available ?? "", tp: "", sl: "" })}>{t("create")}</Button>}>
    {!enabled && <p role="status">{t("unavailable")}</p>}
    {(error || recovery.discovery.isError) && <p role="alert">{t("unavailable")}</p>}
    {recovery.storageError && <p role="alert">{t("storage")}</p>}
    {(recovery.error || recovery.result.data?.state === "REJECTED") && <p role="alert">{t("failed")}</p>}
    {recovery.pending.length > 0 && !recovery.attempt && <p role="status">{t("pending")}</p>}
    {recovery.attempt && <div className="space-y-2" role="status"><p>{t(recovery.lookup.data ? "pending" : "unknown")}</p>
      <Button type="button" size="sm" disabled={recovery.lookup.isFetching} onClick={() => void recovery.lookup.refetch()}>{t("check")}</Button>
      <Button type="button" size="sm" disabled={recovery.busy || recovery.storageError || !recovery.recovered || !!recovery.lookup.data} onClick={() => recovery.send(recovery.attempt!, true)}>{t("retry")}</Button></div>}
    {shown.length === 0 && ready && <p>{t("empty")}</p>}
    <ul className="space-y-3">{shown.map(row => <li key={row.protection_id} className="border-b border-gray-200 py-4 last:border-0 dark:border-gray-800">
      <div className="flex flex-wrap items-center gap-3"><Badge color={row.conflicted || row.state === "FAILED" ? "error" : "primary"}>{known.has(row.state) ? t(row.state as "ARMED") : t("unavailable")}</Badge>
        <span>{row.base}/{row.quote}</span><MarketTime value={row.snapshot_at}/></div>
      {(row.conflicted || !row.market_ready || row.failure_code) && <p role="alert">{t(row.conflicted ? "conflict" : row.failure_code ? "failed" : "unavailable")}</p>}
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div><dt>{t("remaining")}</dt><dd><MarketValue amount={row.quantity} unit={row.base}/></dd></div>
        <div><dt>{t("covered")}</dt><dd><MarketValue amount={row.protected_quantity} unit={row.base}/></dd></div>
        <div><dt>{t("tp")}</dt><dd>{row.take_profit_price ? <MarketValue amount={row.take_profit_price} unit="USDT"/> : "—"}</dd></div>
        <div><dt>{t("sl")}</dt><dd>{row.stop_loss_price ? <MarketValue amount={row.stop_loss_price} unit="USDT"/> : "—"}</dd></div>
      </dl>
      {row.exit_order_id && <div className="mt-3 space-y-2"><p className="break-all">{t("exit")}: {row.exit_order_id}</p><OrderStatus status={row.exit_order_state ?? row.exit_command_state ?? null}/>{row.exit_filled_quantity != null && <p>{t("exitFilled")}: <MarketValue amount={row.exit_filled_quantity} unit={row.base}/></p>}</div>}
      <div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" disabled={blocked || !enabled || ["EXITING", "CLOSED", "CANCELED"].includes(row.state)} onClick={() => setDraft({ target: row.protection_id, revision: row.revision, quantity: row.quantity, tp: row.take_profit_price ?? "", sl: row.stop_loss_price ?? "" })}>{t("edit")}</Button>
        <Button type="button" size="sm" variant="outline" disabled={blocked || ["EXITING", "CLOSED", "CANCELED"].includes(row.state)} onClick={() => recovery.send({ version: 1, owner, mode: "PAPER", key: window.crypto.randomUUID(), action: "CANCEL", target: row.protection_id, payload: { ...scope, expected_revision: row.revision } })}>{t("cancel")}</Button></div>
    </li>)}</ul>
    <Modal isOpen={draft !== null} onClose={close} titleId="protection-form-title" closeLabel={t("close")}>
      {draft && <form className="space-y-5 p-6" onSubmit={event => {
        event.preventDefault(); if (blocked || !enabled) return;
        const common = { ...scope, quantity: draft.quantity, take_profit_price: draft.tp || null, stop_loss_price: draft.sl || null };
        recovery.send(draft.target ? { version: 1, owner, mode: "PAPER", key: window.crypto.randomUUID(), action: "REPLACE", target: draft.target, payload: { ...common, expected_revision: draft.revision! } } : { version: 1, owner, mode: "PAPER", key: window.crypto.randomUUID(), action: "CREATE", payload: { ...common, base } });
        close();
      }}>
        <h3 id="protection-form-title" className="text-lg font-semibold">{t(draft.target ? "edit" : "create")}</h3>
        <div><Label htmlFor="protection-quantity">{t("quantity")} ({base})</Label><Input id="protection-quantity" value={draft.quantity} inputMode="decimal" autoComplete="off" maxLength={256} required onChange={e => setDraft({ ...draft, quantity: e.target.value })}/></div>
        <div><Label htmlFor="protection-tp">{t("tp")}</Label><Input id="protection-tp" value={draft.tp} inputMode="decimal" autoComplete="off" maxLength={256} onChange={e => setDraft({ ...draft, tp: e.target.value })}/></div>
        <div><Label htmlFor="protection-sl">{t("sl")}</Label><Input id="protection-sl" value={draft.sl} inputMode="decimal" autoComplete="off" maxLength={256} onChange={e => setDraft({ ...draft, sl: e.target.value })}/></div>
        <Button type="submit" disabled={blocked || !enabled || !draft.quantity || (!draft.tp && !draft.sl)}>{t("save")}</Button>
      </form>}
    </Modal>
  </ComponentCard>;
}
