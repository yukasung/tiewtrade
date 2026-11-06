import { sessionJournal } from "./attemptJournal";
export { JournalUnavailable } from "./attemptJournal";
import type { ExpectedEpisode, NewManualOrder } from "./manualOrders";

const prefix = "tiewtrade.manual-order.v1:";
type Scope = { version: 1; owner: string; mode: "PAPER"; key: string };
export type ManualAttempt = Scope & (
  { action: "NEW"; payload: NewManualOrder } |
  { action: "CANCEL"; orderId: string; payload: ExpectedEpisode }
);
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
function valid(value: unknown, owner: string): value is ManualAttempt {
  if (!record(value) || value.version !== 1 || value.owner !== owner || value.mode !== "PAPER" ||
      typeof value.key !== "string" || !/^[0-9a-f-]{36}$/i.test(value.key) || !record(value.payload)) return false;
  const { protection, protection_allocations, ...p } = value.payload;
  if (protection !== undefined && protection !== null) {
    if (p.side !== "BUY" || !record(protection) ||
        Object.keys(protection).some(k => !["take_profit_price", "stop_loss_price"].includes(k)) ||
        ![protection.take_profit_price, protection.stop_loss_price].some(x => typeof x === "string" && x.length > 0) ||
        ![protection.take_profit_price, protection.stop_loss_price].every(x => x === undefined || x === null || typeof x === "string")) return false;
  }
  if (protection_allocations !== undefined) {
    if (p.side !== "SELL" || !Array.isArray(protection_allocations) || !protection_allocations.every(a => record(a) &&
      Object.keys(a).length === 3 && typeof a.protection_id === "string" && typeof a.quantity === "string" &&
      Number.isSafeInteger(a.expected_revision) && (a.expected_revision as number) >= 1)) return false;
  }
  if (typeof p.expected_wallet_id !== "string" || typeof p.expected_episode_id !== "string") return false;
  if (value.action === "CANCEL") return typeof value.orderId === "string" && Object.keys(p).length === 2;
  if (value.action !== "NEW" || typeof p.base !== "string" || p.quote !== "USDT") return false;
  if (p.kind === "MARKET" && p.side === "BUY") return typeof p.quote_budget === "string" && Object.keys(p).length === 7;
  if (p.kind === "MARKET" && p.side === "SELL") return typeof p.base_quantity === "string" && Object.keys(p).length === 7;
  return p.kind === "LIMIT" && (p.side === "BUY" || p.side === "SELL") && typeof p.base_quantity === "string" &&
    typeof p.limit_price === "string" && p.time_in_force === "GTC" && Object.keys(p).length === 9;
}
const journal = sessionJournal<ManualAttempt>(prefix, value => value.owner, valid);
export const readAttempt = journal.read;
export const writeAttempt = journal.write;
export const clearAttempt = journal.clear;
