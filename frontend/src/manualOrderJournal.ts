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
  const p = value.payload;
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
