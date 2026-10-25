import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState, type FormEvent, type RefObject } from "react";
import { ApiRequestError } from "./auth";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { Modal } from "./components/ui/Modal";
import { Select } from "./components/ui/Select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/Table";
import {
  addSupportedSymbol,
  readSupportedSymbols,
  readSymbolImpact,
  removeSupportedSymbol,
  type Catalog,
  type CatalogEntry,
} from "./supportedSymbols";
import { supportedSymbolI18n, supportedSymbolText as t } from "./supportedSymbolMessages";
import "./SupportedSymbolPanel.css";

const catalogKey = ["supported-symbols"] as const;
const TRANSITIONAL_STATUSES = new Set(["REQUESTED", "PREPARING"]);
const FAST_POLL_INTERVAL_MS = 1_000;
const STABLE_POLL_INTERVAL_MS = 5_000;

function catalogPollInterval(catalog: Catalog | undefined): number {
  if (!catalog) return FAST_POLL_INTERVAL_MS;
  const pending = catalog.entries.some(entry =>
    TRANSITIONAL_STATUSES.has(entry.status) || entry.cleanup?.status === "PENDING"
  );
  return pending ? FAST_POLL_INTERVAL_MS : STABLE_POLL_INTERVAL_MS;
}

function message(error: unknown): string {
  if (error instanceof ApiRequestError && error.message === "CATALOG_REVISION_CONFLICT") {
    return t("revisionConflict");
  }
  return error instanceof Error ? error.message : t("unknownError");
}

export function SupportedSymbolPanel() {
  const client = useQueryClient();
  const catalog = useQuery({
    queryKey: catalogKey,
    queryFn: ({ signal }) => readSupportedSymbols(signal),
    refetchInterval: query => catalogPollInterval(query.state.data),
  });
  const [addOpen, setAddOpen] = useState(false);
  const [removing, setRemoving] = useState<CatalogEntry | null>(null);
  const addButton = useRef<HTMLButtonElement>(null);
  const removeButton = useRef<HTMLElement | null>(null);
  const closeAdd = useCallback(() => setAddOpen(false), []);
  const closeRemove = useCallback(() => setRemoving(null), []);
  const refresh = useCallback(async () => {
    await client.invalidateQueries({ queryKey: catalogKey });
  }, [client]);

  if (catalog.isPending) return <p role="status">{t("loading")}</p>;
  if (catalog.isError) return <p role="alert">{message(catalog.error)}</p>;

  return (
    <ComponentCard title={t("heading")} headingId="supported-symbol-heading"
      desc={t("revision", { revision: catalog.data.revision })}>
      <div className="symbol-toolbar">
        <p>{t("activeOnly")}</p>
        <Button ref={addButton} onClick={() => setAddOpen(true)} disabled={!catalog.data.mutations_enabled}>
          {t("add")}
        </Button>
      </div>
      {!catalog.data.mutations_enabled ? <p role="status" className="symbol-warning">{t("gateClosed")}</p> : null}
      <div className="symbol-table-wrap">
        <Table>
          <TableHeader><TableRow>
            <TableHead scope="col">{t("pair")}</TableHead><TableHead scope="col">{t("status")}</TableHead>
            <TableHead scope="col">Revision</TableHead><TableHead scope="col">{t("cleanup")}</TableHead>
            <TableHead scope="col" aria-label={t("actions")} />
          </TableRow></TableHeader>
          <TableBody>
            {catalog.data.entries.length === 0 ? <TableRow><TableCell colSpan={5}>{t("empty")}</TableCell></TableRow> : null}
            {catalog.data.entries.map(entry => <TableRow key={`${entry.base}-${entry.quote}`}>
              <TableCell>{entry.base}/{entry.quote}</TableCell>
              <TableCell><span className={`symbol-badge status-${entry.status.toLowerCase()}`}>{entry.status}</span></TableCell>
              <TableCell>{entry.revision}</TableCell>
              <TableCell>{entry.cleanup === null || entry.cleanup === undefined ? "—" : (
                <span className={`symbol-badge cleanup-${entry.cleanup.status.toLowerCase()}`}>
                  {entry.cleanup.orders_unresolved > 0
                    ? t("pendingCleanup", { status: entry.cleanup.status, count: entry.cleanup.orders_unresolved })
                    : entry.cleanup.status}
                </span>
              )}</TableCell>
              <TableCell>{entry.status === "ACTIVE" ? <Button size="sm" variant="outline" onClick={event => { removeButton.current = event.currentTarget; setRemoving(entry); }}>{t("remove")}</Button> : null}</TableCell>
            </TableRow>)}
          </TableBody>
        </Table>
      </div>
      {addOpen ? <AddModal isOpen onClose={closeAdd} revision={catalog.data.revision} onDone={refresh} returnFocusRef={addButton} /> : null}
      {removing !== null ? <RemoveModal entry={removing} onClose={closeRemove} revision={catalog.data.revision} onDone={refresh} returnFocusRef={removeButton} /> : null}
    </ComponentCard>
  );
}

function AddModal({ isOpen, onClose, revision, onDone, returnFocusRef }: {
  isOpen: boolean; onClose: () => void; revision: number; onDone: () => Promise<void>;
  returnFocusRef: RefObject<HTMLElement | null>;
}) {
  const [base, setBase] = useState("");
  const [code, setCode] = useState("");
  const idempotencyKey = useRef(globalThis.crypto.randomUUID());
  const mutation = useMutation({ mutationFn: () => addSupportedSymbol(base.trim().toUpperCase(), revision, code, idempotencyKey.current), onSuccess: async () => { await onDone(); onClose(); } });
  const submit = (event: FormEvent) => { event.preventDefault(); mutation.mutate(); };
  return <Modal isOpen={isOpen} onClose={onClose} titleId="add-symbol-title" closeLabel={t("close")} returnFocusRef={returnFocusRef}>
    <h2 id="add-symbol-title">{t("addTitle")}</h2><p>{t("addHelp")}</p>
    <form onSubmit={submit} className="symbol-form">
      <Label htmlFor="symbol-base">{t("base")}</Label><Input id="symbol-base" value={base} onChange={e => setBase(e.target.value)} maxLength={16} required />
      <Label htmlFor="add-reason">{t("reason")}</Label><Select id="add-reason" value="ADMIN_LIQUIDITY_REVIEWED" disabled><option value="ADMIN_LIQUIDITY_REVIEWED">{t("liquidityReviewed")}</option></Select>
      <Label htmlFor="add-totp">{t("freshTotp")}</Label><Input id="add-totp" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} required />
      {mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}
      <div className="symbol-actions"><Button variant="outline" onClick={onClose}>{t("cancel")}</Button><Button type="submit" disabled={mutation.isPending || !base.trim() || !code}>{t("confirmAdd")}</Button></div>
    </form>
  </Modal>;
}

function RemoveModal({ entry, onClose, revision, onDone, returnFocusRef }: {
  entry: CatalogEntry | null; onClose: () => void; revision: number; onDone: () => Promise<void>;
  returnFocusRef: RefObject<HTMLElement | null>;
}) {
  const [code, setCode] = useState("");
  const idempotencyKey = useRef(globalThis.crypto.randomUUID());
  const impact = useQuery({ queryKey: ["symbol-impact", entry?.base, entry?.quote], queryFn: ({ signal }) => readSymbolImpact(entry!.base, entry!.quote, signal), enabled: entry !== null });
  const mutation = useMutation({ mutationFn: () => removeSupportedSymbol(entry!.base, entry!.quote, revision, code, idempotencyKey.current), onSuccess: async () => { await onDone(); onClose(); } });
  return <Modal isOpen={entry !== null} onClose={onClose} titleId="remove-symbol-title" closeLabel={t("close")} returnFocusRef={returnFocusRef}>
    <h2 id="remove-symbol-title">{t("removeTitle", { pair: `${entry?.base}/${entry?.quote}` })}</h2>
    <p className="symbol-danger">{t("removeWarning")}</p>
    {impact.isPending ? <p role="status">{t("impactLoading")}</p> : impact.isError ? <p role="alert">{message(impact.error)}</p> : impact.data ? <dl className="impact-grid">
      <div><dt>{t("bots")}</dt><dd>{impact.data.bots}</dd></div><div><dt>{t("openOrders")}</dt><dd>{impact.data.open_entry_orders}</dd></div>
      <div><dt>{t("protectiveOrders")}</dt><dd>{impact.data.protective_orders}</dd></div><div><dt>{t("reduceRiskOrders")}</dt><dd>{impact.data.reduce_risk_orders}</dd></div>
      <div><dt>{t("positions")}</dt><dd>{impact.data.positions}</dd></div><div><dt>{t("snapshot")}</dt><dd>{new Date(impact.data.snapshot_at).toLocaleString(supportedSymbolI18n.language)}</dd></div>
    </dl> : null}
    {impact.data !== undefined && !impact.data.complete ? <p className="symbol-warning">{t("incomplete")}</p> : null}
    <form onSubmit={event => { event.preventDefault(); mutation.mutate(); }} className="symbol-form">
      <Label htmlFor="remove-reason">{t("reason")}</Label><Select id="remove-reason" value="ADMIN_RISK_REVIEW" disabled><option value="ADMIN_RISK_REVIEW">{t("riskReviewed")}</option></Select>
      <Label htmlFor="remove-totp">{t("freshTotp")}</Label><Input id="remove-totp" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} required />
      {mutation.isError ? <p role="alert">{message(mutation.error)}</p> : null}
      <div className="symbol-actions"><Button variant="outline" onClick={onClose}>{t("cancel")}</Button><Button type="submit" disabled={mutation.isPending || impact.isPending || !code}>{t("confirmRemove")}</Button></div>
    </form>
  </Modal>;
}
