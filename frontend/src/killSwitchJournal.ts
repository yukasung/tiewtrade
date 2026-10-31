import { ApiRequestError } from "./auth";
import type { StopReceipt } from "./killSwitch";

export type PendingJournal<T extends object> = T & { requestId?: string };

export function readJournal<T>(storageKey: string): T | null {
  try {
    const value = window.localStorage.getItem(storageKey);
    return value ? JSON.parse(value) as T : null;
  } catch {
    window.localStorage.removeItem(storageKey);
    return null;
  }
}

export function writeJournal<T>(storageKey: string, value: T): void {
  window.localStorage.setItem(storageKey, JSON.stringify(value));
}

export function clearJournal(storageKey: string): void {
  window.localStorage.removeItem(storageKey);
}

export function updateJournalFromReceipt<T extends object>(
  storageKey: string,
  intent: T,
  receipt: StopReceipt,
): PendingJournal<T> | null {
  if (receipt.state !== "REQUEST_PENDING") {
    clearJournal(storageKey);
    return null;
  }
  const pending = { ...intent, requestId: receipt.request_id };
  writeJournal(storageKey, pending);
  return pending;
}

export function clearJournalForKnownFailure(error: unknown, storageKey: string): boolean {
  const known = error instanceof ApiRequestError
    && error.status >= 400
    && error.status < 500
    && error.status !== 408;
  if (known) clearJournal(storageKey);
  return known;
}
