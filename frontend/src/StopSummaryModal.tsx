import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type RefObject } from "react";
import { Button } from "./components/ui/Button";
import { Modal } from "./components/ui/Modal";
import { fetchStopEffects, fetchStopRequestById, fetchStopSummary, postResume, stopKey, type StopMode, type StopSummary } from "./killSwitch";
import { clearJournal, clearJournalForKnownFailure, readJournal, updateJournalFromReceipt, writeJournal, type PendingJournal } from "./killSwitchJournal";
import { killSwitchText as t } from "./killSwitchMessages";
import { RiskStopEffects } from "./RiskStopEffects";

export function StopSummaryModal({ owner, mode, stopId, open, onClose, returnFocusRef }: { owner: string; mode: StopMode; stopId: string | null; open: boolean; onClose: () => void; returnFocusRef: RefObject<HTMLButtonElement> }) {
  const client = useQueryClient();
  const storage = `tiewtrade.kill-switch.resume.v1:${owner}:${mode}`;
  const [recovery, setRecovery] = useState<ResumeJournal | null>(() => readJournal<ResumeJournal>(storage));
  const summary = useQuery({ queryKey: ["kill-switch-summary", owner, mode, stopId], queryFn: ({ signal }) => fetchStopSummary(mode, stopId ?? "", signal), enabled: open && stopId !== null });
  const resume = useMutation({ mutationFn: async () => {
    if (!summary.data) throw new Error("summary unavailable");
    const intent = recovery ?? { key: window.crypto.randomUUID(), summary: summary.data };
    writeJournal(storage, intent);
    try {
      const result = await postResume(mode, intent.summary, intent.key);
      setRecovery(updateJournalFromReceipt(storage, intent, result));
      return result;
    } catch (error) {
      if (clearJournalForKnownFailure(error, storage)) setRecovery(null);
      throw error;
    }
  }, onSuccess: async result => {
    await client.invalidateQueries({ queryKey: stopKey(owner, mode) });
    await client.invalidateQueries({ queryKey: ["kill-switch-summary", owner, mode, stopId] });
    if (result.state === "APPLIED") onClose();
  } });
  const pendingRequest = recovery?.requestId ?? resume.data?.request_id ?? null;
  const receipt = useQuery({ queryKey: ["kill-switch-resume", owner, mode, pendingRequest], queryFn: ({ signal }) => fetchStopRequestById(mode, pendingRequest ?? "", signal), enabled: pendingRequest !== null, refetchInterval: query => query.state.data?.state === "REQUEST_PENDING" ? 1000 : false });
  const receiptState = receipt.data?.state;
  useEffect(() => { if (open && stopId === null) onClose(); }, [onClose, open, stopId]);
  useEffect(() => {
    if (receiptState === "APPLIED") onClose();
    if (receiptState && receiptState !== "REQUEST_PENDING") {
      clearJournal(storage);
      setRecovery(null);
      void client.invalidateQueries({ queryKey: stopKey(owner, mode) });
      void client.invalidateQueries({ queryKey: ["kill-switch-summary", owner, mode, stopId] });
    }
  }, [client, mode, onClose, owner, receiptState, stopId, storage]);
  return <Modal isOpen={open} onClose={onClose} titleId={`stop-summary-${mode}`} closeLabel={t("close")} returnFocusRef={returnFocusRef}>
    <h2 id={`stop-summary-${mode}`}>{t("summary")} — {mode}</h2>
    {summary.isLoading && <p role="status">{t("loading")}</p>}
    {summary.data && <>
      <p>{summary.data.status.progress ? t(summary.data.status.progress) : "—"} · {t("pending")}: {summary.data.status.pending_count} · {t("failed")}: {summary.data.status.failed_count}</p>
      <p>{t("reconciledAt")}: {summary.data.reconciled_at ?? "—"}</p>
      {mode === "LIVE" && <p role="status">{t("liveUnavailable")}</p>}
      <h3>{t("positions")}</h3>
      {summary.data.positions.length === 0 ? <p>{t("noPositions")}</p> : <ul>{summary.data.positions.map(position => <li key={`${position.base}-${position.quote}`}>{position.base}/{position.quote}: {position.quantity}</li>)}</ul>}
      {mode === "PAPER" && stopId && <RiskStopEffects owner={owner} mode={mode} stop={stopId} revision={summary.data.snapshot_revision} visible={open} queryPrefix={["kill-switch", owner, mode]} fetchPage={(cursor, signal) => fetchStopEffects(mode, stopId, cursor, signal)} />}
      {!summary.data.status.resume_ready && <p>{t("resumeUnavailable")}</p>}
      {(resume.isPending || receiptState === "REQUEST_PENDING") && <p role="status">{t("resumePending")}</p>}
      {(resume.isError || receiptState === "REJECTED") && <p role="alert">{receipt.data?.failure_code ?? t("requestFailed")}</p>}
      <div className="kill-switch-modal-actions">
        <Button onClick={() => resume.mutate()} disabled={!summary.data.status.resume_ready || resume.isPending || receiptState === "REQUEST_PENDING"}>{t("resume")}</Button>
        <Button variant="outline" onClick={onClose}>{t("close")}</Button>
      </div>
    </>}
  </Modal>;
}

type ResumeJournal = PendingJournal<{ key: string; summary: StopSummary }>;
