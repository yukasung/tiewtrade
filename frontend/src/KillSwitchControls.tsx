import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { Alert } from "./components/ui/Alert";
import { Button } from "./components/ui/Button";
import { fetchStopStatus, postStop, stopKey, type StopMode } from "./killSwitch";
import { clearJournal, clearJournalForKnownFailure } from "./killSwitchJournal";
import { killSwitchText as t } from "./killSwitchMessages";
import { StopSummaryModal } from "./StopSummaryModal";
import { fetchRisk, riskKey } from "./riskLimits";

function StopControl({ owner, mode }: { owner: string; mode: StopMode }) {
  const client = useQueryClient();
  const detailsTrigger = useRef<HTMLButtonElement>(null);
  const [details, setDetails] = useState(false);
  const closeDetails = useCallback(() => setDetails(false), []);
  const [unknown, setUnknown] = useState(false);
  const status = useQuery({ queryKey: stopKey(owner, mode), queryFn: ({ signal }) => fetchStopStatus(mode, signal), refetchInterval: 1000, refetchOnWindowFocus: true });
  const mutation = useMutation({ mutationFn: async () => {
    const journal = `tiewtrade.kill-switch.stop.v1:${owner}:${mode}`;
    const key = window.localStorage.getItem(journal) ?? window.crypto.randomUUID();
    window.localStorage.setItem(journal, key);
    try {
      const value = await postStop(mode, key);
      clearJournal(journal);
      setUnknown(false);
      return value;
    } catch (error) {
      const outcomeKnown = clearJournalForKnownFailure(error, journal);
      setUnknown(!outcomeKnown);
      throw error;
    }
  }, onSuccess: () => client.invalidateQueries({ queryKey: stopKey(owner, mode) }) });
  const label = mode === "PAPER" ? t("paperStop") : t("liveStop");
  return <div className="kill-switch-control">
    <Button size="sm" variant={mode === "LIVE" ? "outline" : "primary"} disabled={mutation.isPending} onClick={() => mutation.mutate()} aria-label={unknown ? `${label} — ${t("retry")}` : label}>{label}</Button>
    <span role="status" className="kill-switch-state">{status.data?.progress ? t(status.data.progress) : status.isLoading ? t("loading") : "—"}{status.data?.pending_count ? ` (${status.data.pending_count} ${t("pending")})` : ""}</span>
    {(status.data?.stop_id || details) && <Button ref={detailsTrigger} size="sm" variant="outline" onClick={() => setDetails(true)}>{t("details")}</Button>}
    {unknown && <span role="alert" className="kill-switch-unknown">{t("requestFailed")}</span>}
    <StopSummaryModal owner={owner} mode={mode} stopId={status.data?.stop_id ?? null} open={details} onClose={closeDetails} returnFocusRef={detailsTrigger} />
  </div>;
}

export function KillSwitchControls({ owner }: { owner: string }) {
  return <div className="kill-switch-controls" aria-label="Kill switch"><StopControl owner={owner} mode="PAPER"/><StopControl owner={owner} mode="LIVE"/></div>;
}

export function KillSwitchBanner({ owner }: { owner: string }) {
  const status = useQuery({ queryKey: stopKey(owner, "PAPER"), queryFn: ({ signal }) => fetchStopStatus("PAPER", signal), refetchInterval: 1000, refetchOnWindowFocus: true });
  const risk = useQuery({ queryKey: riskKey(owner, "PAPER"), queryFn: ({ signal }) => fetchRisk("PAPER", signal), refetchInterval: 1000, refetchOnWindowFocus: true });
  const platform = status.data?.platform_stop_id;
  const loss = risk.data?.latched;
  if (!platform && !loss) return null;
  return <div className="kill-switch-banner">
    {platform && <Alert variant="warning" title={t("platformTitle")} message={`${t("platformMessage")}${status.data?.platform_reason ? `: ${status.data.platform_reason}` : ""}`} />}
    {loss && <Alert variant="warning" title={t("lossTitle")} message={t("lossMessage")} />}
  </div>;
}
