import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Button } from "./components/ui/Button";
import { Input } from "./components/ui/Input";
import { Label } from "./components/ui/Label";
import { fetchPlatformRequestById, fetchPlatformStop, postPlatformResume, postPlatformStop, type PlatformStopStatus } from "./killSwitch";
import { clearJournal, clearJournalForKnownFailure, readJournal, updateJournalFromReceipt, writeJournal, type PendingJournal } from "./killSwitchJournal";
import { killSwitchText as t } from "./killSwitchMessages";

export function PlatformKillSwitchPanel({ owner, role }: { owner: string; role: "PLATFORM_ADMIN" | "PLATFORM_OWNER" }) {
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const stopJournal = `tiewtrade.kill-switch.platform-stop.v1:${owner}`;
  const resumeJournal = `tiewtrade.kill-switch.platform-resume.v1:${owner}`;
  const [stopRecovery, setStopRecovery] = useState<PlatformStopJournal | null>(() => readJournal<PlatformStopJournal>(stopJournal));
  const [resumeRecovery, setResumeRecovery] = useState<PlatformResumeJournal | null>(() => readJournal<PlatformResumeJournal>(resumeJournal));
  const status = useQuery({ queryKey: ["platform-kill-switch"], queryFn: ({ signal }) => fetchPlatformStop(signal), refetchInterval: 1000 });
  const stop = useMutation({ mutationFn: async () => {
    const intent = stopRecovery ?? { key: window.crypto.randomUUID(), reason };
    writeJournal(stopJournal, intent);
    try {
      const result = await postPlatformStop(intent.reason, intent.key);
      setStopRecovery(updateJournalFromReceipt(stopJournal, intent, result));
      return result;
    } catch (error) {
      if (clearJournalForKnownFailure(error, stopJournal)) setStopRecovery(null);
      throw error;
    }
  }, onSuccess: async () => { setReason(""); await client.invalidateQueries({ queryKey: ["platform-kill-switch"] }); } });
  const resume = useMutation({ mutationFn: async () => {
    if (!status.data) throw new Error("status unavailable");
    const intent = resumeRecovery?.status.stop_id === status.data.stop_id ? resumeRecovery : { key: window.crypto.randomUUID(), status: status.data };
    writeJournal(resumeJournal, intent);
    try {
      const result = await postPlatformResume(intent.status, intent.key);
      setResumeRecovery(updateJournalFromReceipt(resumeJournal, intent, result));
      return result;
    } catch (error) {
      if (clearJournalForKnownFailure(error, resumeJournal)) setResumeRecovery(null);
      throw error;
    }
  }, onSuccess: () => client.invalidateQueries({ queryKey: ["platform-kill-switch"] }) });
  const pendingId = resumeRecovery?.requestId ?? stopRecovery?.requestId ?? (resume.data?.state === "REQUEST_PENDING" ? resume.data.request_id : stop.data?.state === "REQUEST_PENDING" ? stop.data.request_id : null);
  const receipt = useQuery({ queryKey: ["platform-kill-switch-request", owner, pendingId], queryFn: ({ signal }) => fetchPlatformRequestById(pendingId ?? "", signal), enabled: pendingId !== null, refetchInterval: query => query.state.data?.state === "REQUEST_PENDING" ? 1000 : false });
  const receiptId = receipt.data?.request_id;
  const receiptState = receipt.data?.state;
  useEffect(() => {
    if (!receiptId || receiptState === "REQUEST_PENDING") return;
    if (stopRecovery?.requestId === receiptId) {
      clearJournal(stopJournal);
      setStopRecovery(null);
    }
    if (resumeRecovery?.requestId === receiptId) {
      clearJournal(resumeJournal);
      setResumeRecovery(null);
    }
    void client.invalidateQueries({ queryKey: ["platform-kill-switch"] });
  }, [client, receiptId, receiptState, resumeJournal, resumeRecovery?.requestId, stopJournal, stopRecovery?.requestId]);
  return <section className="component-card platform-kill-switch-panel">
    <h1>{t("adminTitle")}</h1>
    <p>{status.data?.progress ?? "—"} · {t("pending")}: {status.data?.pending_count ?? 0} · {t("failed")}: {status.data?.failed_count ?? 0}</p>
    <Label htmlFor="platform-stop-reason">{t("reason")}</Label>
    <Input id="platform-stop-reason" value={reason} maxLength={500} onChange={event => setReason(event.target.value)} />
    <div className="kill-switch-modal-actions">
      <Button disabled={reason.trim().length === 0 || stop.isPending || receiptState === "REQUEST_PENDING"} onClick={() => stop.mutate()}>{t("platformStop")}</Button>
      <Button variant="outline" disabled={role !== "PLATFORM_OWNER" || !status.data?.can_resume || resume.isPending || receiptState === "REQUEST_PENDING"} onClick={() => resume.mutate()}>{t("platformResume")}</Button>
    </div>
    {receiptState === "REQUEST_PENDING" && <p role="status">{t("resumePending")}</p>}
    {(stop.isError || resume.isError || receiptState === "REJECTED") && <p role="alert">{receipt.data?.failure_code ?? t("requestFailed")}</p>}
    {role !== "PLATFORM_OWNER" && <p>{t("ownerOnly")}</p>}
  </section>;
}

type PlatformStopJournal = PendingJournal<{ key: string; reason: string }>;
type PlatformResumeJournal = PendingJournal<{ key: string; status: PlatformStopStatus }>;
