import { sessionJournal } from "./attemptJournal";
import type { ProtectionAction, ProtectionCreate, ProtectionReplace, ProtectionCancel } from "./protections";
export type ProtectionAttempt = { version: 1; owner: string; mode: "PAPER"; key: string; action: ProtectionAction; target?: string; payload: ProtectionCreate | ProtectionReplace | ProtectionCancel };
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
function valid(v: unknown, owner: string): v is ProtectionAttempt {
  if (!record(v) || v.version !== 1 || v.owner !== owner || v.mode !== "PAPER" || typeof v.key !== "string" || !/^[0-9a-f-]{36}$/i.test(v.key) || !record(v.payload)) return false;
  if (Object.keys(v).some(k => !["version", "owner", "mode", "key", "action", "target", "payload"].includes(k))) return false;
  const p = v.payload;
  if (typeof p.expected_wallet_id !== "string" || typeof p.expected_episode_id !== "string") return false;
  if (v.action !== "CREATE" && (typeof v.target !== "string" || !Number.isSafeInteger(p.expected_revision) || (p.expected_revision as number) < 1)) return false;
  if (v.action === "CANCEL") return Object.keys(p).length === 3;
  if (v.action !== "CREATE" && v.action !== "REPLACE") return false;
  if (typeof p.quantity !== "string" || (v.action === "CREATE" && typeof p.base !== "string")) return false;
  if (![p.take_profit_price, p.stop_loss_price].some(x => typeof x === "string" && x.length > 0)) return false;
  return Object.keys(p).every(k => ["expected_wallet_id", "expected_episode_id", "expected_revision", "base", "quantity", "take_profit_price", "stop_loss_price"].includes(k)) && [p.take_profit_price, p.stop_loss_price].every(x => x === undefined || x === null || typeof x === "string");
}
export const protectionJournal = sessionJournal<ProtectionAttempt>("tiewtrade.protection.v1:", v => v.owner, valid);
