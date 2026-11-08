import { useCallback, useEffect, useState } from "react";
import { orderTerminal, type ExpectedEpisode, type PaperOrder } from "./manualOrders";
import { manualOrderText as mo } from "./manualOrderMessages";
import { PaperOrderRow, usePaperOrders } from "./PaperOrderList";
import { Tabs } from "./components/ui/Tabs";
import { protectionInHistory, protectionHasResidual, protectionNeedsAttention, type Protection } from "./protections";
import { useProtectionAttempt } from "./useProtections";
import { protectionText as t } from "./protectionMessages";
import { OrderStatus } from "./components/OrderStatus";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Modal } from "./components/ui/Modal";
import { Badge } from "./components/ui/Badge";
import { Alert } from "./components/ui/Alert";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/Table";

type Draft = { base: string; scope: string; target?: string; revision?: number; quantity: string; tp: string; sl: string };
const terminal = (row: Protection) => ["CLOSED", "CANCELED"].includes(row.state);
const cellClass = "px-5 py-4 text-start text-sm";
/** Table/tabs follow PaperOrderList and references/admin-template/src/components/tables/BasicTables/BasicTableOne.tsx.
 * Form/details use the existing shared template Modal; these are app-monitored protections, not venue OCO orders. */
export function PaperTradingActivity({ owner, base, scope, rows, visible, disabled, ready, error, available, enabled, view, onViewChange, ordersDisabled, onCancelOrder }: {
  view: "OPEN" | "HISTORY"; onViewChange: (view: "OPEN" | "HISTORY") => void;
  ordersDisabled: boolean; onCancelOrder: (row: PaperOrder) => void;
  owner: string; base: string; scope: ExpectedEpisode; rows: Protection[]; visible: boolean; disabled: boolean; ready: boolean; error: boolean; available: string | null; enabled: boolean;
}) {
  const recovery = useProtectionAttempt(owner, visible);
  const orders = usePaperOrders(owner, scope.expected_episode_id, visible);
  const [draft, setDraft] = useState<Draft | null>(null);
  const close = useCallback(() => setDraft(null), []);
  const [selection, setSelection] = useState<{ id: string; scope: string } | null>(null);
  const closeDetails = useCallback(() => setSelection(null), []);
  const blocked = disabled || !ready || !recovery.recovered || recovery.storageError || !!recovery.attempt || recovery.busy || recovery.pending.length > 0;
  const known = new Set(["WAITING_ENTRY", "ARMING", "ARMED", "EXITING", "CLOSED", "CANCELED", "FAILED"]);
  const shown = rows.filter(r => r.mode === "PAPER" && r.wallet_id === scope.expected_wallet_id && r.episode_id === scope.expected_episode_id);
  const scopeKey = JSON.stringify([owner, scope.expected_wallet_id, scope.expected_episode_id]);
  const details = selection?.scope === scopeKey ? shown.find(row => row.protection_id === selection.id) : undefined;
  useEffect(() => { if (selection && !details) setSelection(null); }, [selection, details]);
  useEffect(() => { setDraft(null); setSelection(null); }, [view, scopeKey]);
  const visibleRows = shown.filter(row => view === "HISTORY" ? protectionInHistory(row) : !protectionInHistory(row));
  const orderRows = orders.rows.filter(row => view === "HISTORY" ? orderTerminal(row.status) : !orderTerminal(row.status));
  const complete = ready && !error && orders.query.isSuccess && !orders.query.isError && !orders.query.hasNextPage && !orders.query.isFetchingNextPage;
  return <section aria-labelledby="trading-activity-heading">
    <h2 id="trading-activity-heading" className="sr-only">{mo("orders")}</h2>
    <header className="paper-order-toolbar">
      <Tabs id="trading-activity-view" controls="trading-activity-content" label={mo("orders")}
        items={[{ id: "OPEN", label: mo("openOrders") }, { id: "HISTORY", label: mo("orderHistory") }]} active={view} onChange={onViewChange}/>
      <Button type="button" size="sm" disabled={view !== "OPEN" || blocked || !enabled || !base} onClick={() => setDraft({ base, scope: scopeKey, quantity: available ?? "", tp: "", sl: "" })}>{t("create")}</Button>
    </header>
    <div id="trading-activity-content" role="tabpanel" aria-labelledby={`trading-activity-view-${view === "OPEN" ? 0 : 1}`}>
    {shown.some(protectionNeedsAttention) && <p role="status" className="px-5 text-sm text-warning-700 dark:text-warning-400">{t("attention")}</p>}
    {orders.query.isError && <p role="alert">{mo("loadError")}</p>}
    {orders.query.isPending && <p role="status">{mo("recovering")}</p>}
    {(error || recovery.discovery.isError) && <p role="alert">{t("unavailable")}</p>}
    {recovery.storageError && <p role="alert">{t("storage")}</p>}
    {(recovery.error || recovery.result.data?.state === "REJECTED") && <p role="alert">{t("failed")}</p>}
    {recovery.pending.length > 0 && !recovery.attempt && <p role="status">{t("pending")}</p>}
    {recovery.attempt && <div className="space-y-2" role="status"><p>{t(recovery.lookup.data ? "pending" : "unknown")}</p>
      <Button type="button" size="sm" disabled={recovery.lookup.isFetching} onClick={() => void recovery.lookup.refetch()}>{t("check")}</Button>
      <Button type="button" size="sm" disabled={recovery.busy || recovery.storageError || !recovery.recovered || !!recovery.lookup.data} onClick={() => recovery.send(recovery.attempt!, true)}>{t("retry")}</Button></div>}
    {!enabled && <p role="status">{t("unavailable")}</p>}
    {!ready && !error && <p role="status">{t("loading")}</p>}
    <div id="trading-activity-table" className="max-w-full overflow-x-auto">
      <Table className="whitespace-nowrap"><TableHeader className="border-b border-gray-100 dark:border-white/5"><TableRow>
        {(["pair", "recordType", "status", "quantity", "executionCoverage", "conditions", "snapshot", "actions"] as const).map(name => <TableHead key={name} scope="col" className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">{t(name)}</TableHead>)}
      </TableRow></TableHeader><TableBody className="divide-y divide-gray-100 dark:divide-white/5">
        {orderRows.map(row => <PaperOrderRow key={`order:${row.order_id}`} row={row} disabled={ordersDisabled || orders.query.isError} onCancel={onCancelOrder}/>)}
        {visibleRows.map(row => <TableRow key={`protection:${row.protection_id}`}>
          <TableCell className={cellClass}>{row.base}/{row.quote}</TableCell>
          <TableCell className={cellClass}><span>{t("title")}</span><div className="text-sm text-gray-500 dark:text-gray-400">{t("conditionRecord")}</div></TableCell>
          <TableCell className={cellClass}>
            <Badge color={row.conflicted || row.state === "FAILED" ? "error" : "primary"}>{known.has(row.state) ? t(row.state as "ARMED") : t("unavailable")}</Badge>
            {(row.conflicted || !row.market_ready || row.failure_code) && <p role="alert">{t(row.conflicted ? "conflict" : row.failure_code ? "failed" : "unavailable")}</p>}
            {row.exit_order_id && <OrderStatus status={row.exit_order_state ?? row.exit_command_state ?? null}/>}
          </TableCell>
          <TableCell className={cellClass}><MarketValue amount={row.quantity} unit={row.base}/></TableCell>
          <TableCell className={cellClass}>
            <div>{t("covered")}: <MarketValue amount={row.protected_quantity} unit={row.base}/></div>
            {row.step_residual_quantity === null && <p>{t("coverageUnknown")}</p>}
            {protectionHasResidual(row) && <div className="mt-1 text-sm text-warning-700 dark:text-warning-400">
              <p>{t("uncoveredResidual")}: <MarketValue amount={row.step_residual_quantity!} unit={row.base}/></p><p>{t("noAutoSale")}</p>
            </div>}
          </TableCell>
          <TableCell className={cellClass}>
            <div>{t("tp")}: {row.take_profit_price ? <MarketValue amount={row.take_profit_price} unit={row.quote}/> : "—"}</div>
            <div>{t("sl")}: {row.stop_loss_price ? <MarketValue amount={row.stop_loss_price} unit={row.quote}/> : "—"}</div>
          </TableCell>
          <TableCell className={cellClass}><MarketTime value={row.snapshot_at}/></TableCell>
          <TableCell className={cellClass}><div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setSelection({ id: row.protection_id, scope: scopeKey })}>{t("details")}</Button>
            {!terminal(row) && <>
              <Button size="sm" disabled={blocked || !enabled || row.state === "EXITING"} onClick={() => setDraft({ base: row.base, scope: scopeKey, target: row.protection_id, revision: row.revision, quantity: row.quantity, tp: row.take_profit_price ?? "", sl: row.stop_loss_price ?? "" })}>{t("edit")}</Button>
              <Button size="sm" variant="outline" disabled={blocked || row.state === "EXITING"} onClick={() => recovery.send({ version: 1, owner, mode: "PAPER", key: window.crypto.randomUUID(), action: "CANCEL", target: row.protection_id, payload: { ...scope, expected_revision: row.revision } })}>{t("cancel")}</Button>
            </>}
          </div></TableCell>
        </TableRow>)}
        {orderRows.length === 0 && visibleRows.length === 0 && complete && <TableRow><TableCell className="paper-order-empty" colSpan={8}>{t(view === "OPEN" ? "emptyActivity" : "emptyActivityHistory")}</TableCell></TableRow>}
        {!complete && !error && !orders.query.isError && <TableRow><TableCell className={cellClass} colSpan={8}>{mo("incompleteResults")}</TableCell></TableRow>}
      </TableBody></Table>
    </div>
    {orders.query.hasNextPage && <div className="paper-order-pagination"><Button size="sm" variant="outline" disabled={orders.query.isFetching} onClick={() => void orders.query.fetchNextPage()}>{mo("more")}</Button></div>}
    </div>
    <Modal isOpen={!!details} onClose={closeDetails} titleId="protection-details-title" closeLabel={t("close")}>
      {details && <div className="space-y-4">
        <h3 id="protection-details-title" className="text-lg font-semibold">{t("details")}: {details.base}/{details.quote}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">{t("monitoringNotice")}</p>
        <p>{known.has(details.state) ? t(details.state as "ARMED") : t("unavailable")}</p>
        <MarketTime value={details.snapshot_at}/>
        {(details.conflicted || !details.market_ready || details.failure_code) && <p role="alert">{t(details.conflicted ? "conflict" : details.failure_code ? "failed" : "unavailable")}</p>}
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt>{t("remaining")}</dt><dd><MarketValue amount={details.quantity} unit={details.base}/></dd></div>
          <div><dt>{t("covered")}</dt><dd><MarketValue amount={details.protected_quantity} unit={details.base}/></dd></div>
          <div><dt>{t("stepResidual")}</dt><dd>{details.step_residual_quantity === null ? t("coverageUnknown") : <MarketValue amount={details.step_residual_quantity} unit={details.base}/>}</dd></div>
          <div><dt>{t("tp")}</dt><dd>{details.take_profit_price ? <MarketValue amount={details.take_profit_price} unit={details.quote}/> : "—"}</dd></div>
          <div><dt>{t("sl")}</dt><dd>{details.stop_loss_price ? <MarketValue amount={details.stop_loss_price} unit={details.quote}/> : "—"}</dd></div>
        </dl>
        {protectionHasResidual(details) && <Alert variant="warning" title={t("stepResidual")} message={t("residualWarning")}/>}
        {details.exit_order_id && <div className="space-y-2">
          <p className="break-all">{t("exit")}: {details.exit_order_id}</p>
          <OrderStatus status={details.exit_order_state ?? details.exit_command_state ?? null}/>
          <p>{t("exitQuantity")}: {details.exit_quantity == null ? mo("unavailable") : <MarketValue amount={details.exit_quantity} unit={details.base}/>}</p>
          {details.exit_filled_quantity != null && <p>{t("exitFilled")}: <MarketValue amount={details.exit_filled_quantity} unit={details.base}/></p>}
        </div>}
        <Button size="sm" variant="outline" onClick={closeDetails}>{t("close")}</Button>
      </div>}
    </Modal>
    <Modal isOpen={draft !== null && draft.scope === scopeKey} onClose={close} titleId="protection-form-title" closeLabel={t("close")}>
      {draft && <form className="space-y-5 p-6" onSubmit={event => {
        event.preventDefault(); if (draft.scope !== scopeKey || view !== "OPEN" || blocked || !enabled) return;
        const common = { ...scope, quantity: draft.quantity, take_profit_price: draft.tp || null, stop_loss_price: draft.sl || null };
        recovery.send(draft.target ? { version: 1, owner, mode: "PAPER", key: window.crypto.randomUUID(), action: "REPLACE", target: draft.target, payload: { ...common, expected_revision: draft.revision! } } : { version: 1, owner, mode: "PAPER", key: window.crypto.randomUUID(), action: "CREATE", payload: { ...common, base: draft.base } });
        close();
      }}>
        <h3 id="protection-form-title" className="text-lg font-semibold">{t(draft.target ? "edit" : "create")}</h3>
        <div><Label htmlFor="protection-quantity">{t("quantity")} ({draft.base})</Label><Input id="protection-quantity" value={draft.quantity} inputMode="decimal" autoComplete="off" maxLength={256} required onChange={e => setDraft({ ...draft, quantity: e.target.value })}/></div>
        <div><Label htmlFor="protection-tp">{t("tp")}</Label><Input id="protection-tp" value={draft.tp} inputMode="decimal" autoComplete="off" maxLength={256} onChange={e => setDraft({ ...draft, tp: e.target.value })}/></div>
        <div><Label htmlFor="protection-sl">{t("sl")}</Label><Input id="protection-sl" value={draft.sl} inputMode="decimal" autoComplete="off" maxLength={256} onChange={e => setDraft({ ...draft, sl: e.target.value })}/></div>
        <Button type="submit" disabled={blocked || !enabled || !draft.quantity || (!draft.tp && !draft.sl)}>{t("save")}</Button>
      </form>}
    </Modal>
  </section>;
}
