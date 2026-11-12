import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { createPortal, flushSync } from "react-dom";
import { Dropdown } from "./components/ui/Dropdown";
import { Alert } from "./components/ui/Alert";
import { Button } from "./components/ui/Button";
import { fetchStopRequestByKey, fetchStopStatus, postStop, stopKey, type StopMode, type StopReceipt } from "./killSwitch";
import { ApiRequestError } from "./auth";
import { clearJournal, clearJournalForKnownFailure } from "./killSwitchJournal";
import { killSwitchText as t } from "./killSwitchMessages";
import { StopSummaryModal } from "./StopSummaryModal";
import { fetchRisk, riskKey } from "./riskLimits";

/** Resolve a persisted hint against durable server truth; never submit from recovery. */
async function recoverStoredStop(mode: StopMode, key: string): Promise<StopReceipt> {
  const receipt = await fetchStopRequestByKey(mode, key);
  if (receipt.mode !== mode || receipt.action !== "STOP" || !["REQUEST_PENDING", "APPLIED", "REJECTED"].includes(receipt.state)) {
    throw new Error("stop receipt scope or state unavailable");
  }
  return receipt;
}

/** Only an exact missing receipt permits same-key retry; an invalid key can retire. */
function recoveryErrorKind(error: unknown): "missing" | "invalid-key" | "unknown" {
  if (!(error instanceof ApiRequestError)) return "unknown";
  if (error.status === 404 && error.message === "TRADING_STOP_REQUEST_NOT_FOUND") return "missing";
  return error.status === 422 ? "invalid-key" : "unknown";
}

function StopControl({ owner, mode, settingsTarget, settingsTrigger, closeSettings }: {
  owner: string;
  mode: StopMode;
  settingsTarget: HTMLDivElement | null;
  settingsTrigger: RefObject<HTMLButtonElement>;
  closeSettings: () => void;
}) {
  const client = useQueryClient();
  const [details, setDetails] = useState(false);
  const closeDetails = useCallback(() => setDetails(false), []);
  const journal = `tiewtrade.kill-switch.stop.v1:${owner}:${mode}`;
  const [initial] = useState(() => {
    try { return { key: window.localStorage.getItem(journal), unavailable: false }; }
    catch { return { key: null, unavailable: true }; }
  });
  const [unknown, setUnknown] = useState(initial.key !== null);
  const [storageUnavailable, setStorageUnavailable] = useState(initial.unavailable);
  const attemptKey = useRef<string | null>(initial.key);
  const recoveryNeeded = useRef(initial.key !== null);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const retireAttempt = useCallback(() => {
    if (!mounted.current) return;
    if (!clearJournal(journal)) setStorageUnavailable(true);
    attemptKey.current = null;
    recoveryNeeded.current = false;
    setUnknown(false);
  }, [journal]);
  const status = useQuery({ queryKey: stopKey(owner, mode), queryFn: ({ signal }) => fetchStopStatus(mode, signal), refetchInterval: 1000, refetchOnWindowFocus: true });
  const recovery = useQuery({ queryKey: ["kill-switch", owner, "recovery", mode, initial.key],
    queryFn: () => recoverStoredStop(mode, initial.key!), enabled: initial.key !== null,
    retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  useEffect(() => {
    if (!recoveryNeeded.current || attemptKey.current !== initial.key) return;
    if (recovery.data) {
      // The old request is durably received. Resolve it independently of the
      // next explicit STOP, including MANUAL accounts that never resume.
      retireAttempt();
      void client.invalidateQueries({ queryKey: stopKey(owner, mode) });
    } else {
      const failure = recoveryErrorKind(recovery.error);
      if (failure === "invalid-key") retireAttempt();
      else if (failure === "missing") {
        // A delayed commit may still appear: keep the key for explicit retry.
        recoveryNeeded.current = false;
      }
    }
  }, [recovery.data, recovery.error, initial.key, retireAttempt, client, owner, mode]);
  const restoring = recoveryNeeded.current && recovery.isPending;
  const mutation = useMutation({ mutationFn: async () => {
    const requireCurrentScope = () => {
      if (!mounted.current) throw new DOMException("stop scope changed", "AbortError");
    };
    const settle = (receipt: StopReceipt) => { retireAttempt(); return receipt; };
    try {
      let key = attemptKey.current;
      if (recoveryNeeded.current && key !== null) {
        try {
          const receipt = await recoverStoredStop(mode, key);
          requireCurrentScope();
          return settle(receipt);
        } catch (error) {
          const failure = recoveryErrorKind(error);
          if (failure === "invalid-key") key = null;
          else if (failure !== "missing") throw error;
          // Missing may still commit: keep its key. Invalid cannot identify an intent.
        }
        recoveryNeeded.current = false;
      }
      key ??= window.crypto.randomUUID();
      attemptKey.current = key;
      try { window.localStorage.setItem(journal, key); }
      catch { setStorageUnavailable(true); }
      requireCurrentScope();
      return settle(await postStop(mode, key));
    } catch (error) {
      if (!mounted.current) throw error;
      // A failed recovery GET does not establish the outcome of the old STOP.
      const outcomeKnown = !recoveryNeeded.current && clearJournalForKnownFailure(error, journal);
      if (outcomeKnown) attemptKey.current = null;
      setUnknown(!outcomeKnown);
      throw error;
    }
  }, onSuccess: () => { if (mounted.current) return client.invalidateQueries({ queryKey: stopKey(owner, mode) }); } });
  const label = mode === "PAPER" ? t("paperStop") : t("liveStop");
  const actionText = restoring ? t("checkingPrevious") : label;
  const actionLabel = `${label} — ${t("retry")}`;
  return <>
    {settingsTarget && createPortal(<section className="kill-switch-settings-group" aria-label={mode}>
      <strong>{mode}</strong>
      <div className="kill-switch-control" role="group" aria-label={t("modeStatus", { mode })}>
        <span role="status" className="kill-switch-state">{status.data?.progress ? t(status.data.progress) : status.isLoading ? t("loading") : "—"}{status.data?.pending_count ? ` (${status.data.pending_count} ${t("pending")})` : ""}</span>
        {(unknown || storageUnavailable) && <div role="alert" className="kill-switch-unknown">
          {unknown && <p>{t("requestFailed")}</p>}
          {storageUnavailable && <p>{t("storageUnavailable")}</p>}
        </div>}
      </div>
      <Button size="sm" variant={mode === "LIVE" ? "outline" : "primary"} disabled={mutation.isPending || restoring || unknown}
        onClick={() => { closeSettings(); settingsTrigger.current?.focus(); mutation.mutate(); }} aria-label={label}>{actionText}</Button>
      {(status.data?.stop_id || details) && <Button size="sm" variant="outline" onClick={() => {
        flushSync(closeSettings);
        setDetails(true);
      }}>{t("details")}</Button>}
      {unknown && <Button size="sm" variant="outline" disabled={mutation.isPending || restoring} aria-label={actionLabel}
        onClick={() => { closeSettings(); settingsTrigger.current?.focus(); mutation.mutate(); }}>{t("retry")}</Button>}
      {!status.data?.stop_id && !details && !unknown && <p>{t("noStopDetails")}</p>}
    </section>, settingsTarget)}
    <StopSummaryModal owner={owner} mode={mode} stopId={status.data?.stop_id ?? null} open={details} onClose={closeDetails} returnFocusRef={settingsTrigger} />
  </>;
}

export function KillSwitchControls({ owner, navigationScope }: { owner: string; navigationScope?: string }) {
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState<HTMLDivElement | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const close = useCallback(() => setOpen(false), []);
  useLayoutEffect(close, [owner, navigationScope, close]);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1280px)");
    const resize = () => {
      const restore = target?.contains(document.activeElement);
      flushSync(close);
      if (restore) trigger.current?.focus();
    };
    window.addEventListener("popstate", close);
    media.addEventListener("change", resize);
    return () => {
      window.removeEventListener("popstate", close);
      media.removeEventListener("change", resize);
    };
  }, [close, target]);
  return <div className="kill-switch-controls" aria-label="Kill switch">
      <StopControl key={`${owner}:PAPER`} owner={owner} mode="PAPER" settingsTarget={target} settingsTrigger={trigger} closeSettings={close}/>
    <StopControl key={`${owner}:LIVE`} owner={owner} mode="LIVE" settingsTarget={target} settingsTrigger={trigger} closeSettings={close}/>
    <div className="kill-switch-settings">
      <Button ref={trigger} variant="outline" className="account-icon-button" aria-label={t("settings")} title={t("settings")}
        aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}>
        <span className="navigation-icon icon-settings" aria-hidden="true" />
      </Button>
      <Dropdown open={open} keepMounted onClose={close} trigger={trigger} id={id} className="kill-switch-settings-panel">
        <div ref={setTarget} role="group" aria-label={t("settings")} />
      </Dropdown>
    </div>
  </div>;
}

export function KillSwitchBanner({ owner }: { owner: string }) {
  const status = useQuery({ queryKey: stopKey(owner, "PAPER"), queryFn: ({ signal }) => fetchStopStatus("PAPER", signal), refetchInterval: 1000, refetchOnWindowFocus: true });
  const risk = useQuery({ queryKey: riskKey(owner, "PAPER"), queryFn: ({ signal }) => fetchRisk("PAPER", signal), refetchInterval: 1000, refetchOnWindowFocus: true });
  const platform = status.data?.platform_stop_id;
  const activeCauses = status.data?.active_causes ?? [];
  const loss = risk.data?.latched || activeCauses.includes("LOSS_LIMIT");
  const system = activeCauses.includes("SYSTEM");
  if (!platform && !loss && !system) return null;
  return <div className="kill-switch-banner">
    {platform && <Alert variant="warning" title={t("platformTitle")} message={`${t("platformMessage")}${status.data?.platform_reason ? `: ${status.data.platform_reason}` : ""}`} />}
    {loss && <Alert variant="warning" title={t("lossTitle")} message={t("lossMessage")} />}
    {system && <Alert variant="warning" title={t("systemTitle")} message={t("systemMessage")} />}
  </div>;
}
