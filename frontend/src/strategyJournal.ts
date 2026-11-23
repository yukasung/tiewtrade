import { sessionJournal } from "./attemptJournal";
import type { components } from "./api-types";
import { isRecord } from "./isRecord";

export const paperTestStrategy = "paper-green-atr-test";
export const rsiStepStrategy = "rsi-step-grid-ema-single-tp";
type CommonSettings = { base: string; timeframe: string; capital_per_entry: string };
export type StrategySettings = CommonSettings & (
  { max_entries: number; strategy_name?: never } |
  { strategy_name: typeof paperTestStrategy; max_entries?: never }
);
export type StrategyAttempt = {
  version: 1; owner: string; key: string; configKey: string;
  payload: StrategySettings; reference?: string;
  replacement?: components["schemas"]["BotReplacementInput"];
};
const uuid = /^[0-9a-f-]{36}$/i;
function valid(value: unknown, owner: string): value is StrategyAttempt {
  if (!isRecord(value) || value.version !== 1 || value.owner !== owner
      || typeof value.key !== "string" || !uuid.test(value.key)
      || typeof value.configKey !== "string" || !uuid.test(value.configKey)
      || !isRecord(value.payload)) return false;
  if (Object.keys(value).some(key => !["version", "owner", "key", "configKey", "payload", "reference", "replacement"].includes(key))) return false;
  if (value.replacement !== undefined) {
    const proof = value.replacement;
    if (!isRecord(proof) || typeof proof.run_id !== "string" || !uuid.test(proof.run_id)
        || !(proof.stop_id === null || typeof proof.stop_id === "string" && uuid.test(proof.stop_id))
        || !(proof.stop_revision === null || typeof proof.stop_revision === "number" && Number.isSafeInteger(proof.stop_revision) && proof.stop_revision > 0)
        || Object.keys(proof).some(key => !["run_id", "run_revision", "stop_id", "stop_revision", "summary_revision", "reconciliation_revision"].includes(key))) return false;
    if (![proof.run_revision, proof.summary_revision, proof.reconciliation_revision].every(v => typeof v === "number" && Number.isSafeInteger(v) && v >= 0)
        || typeof proof.run_revision !== "number" || proof.run_revision < 1) return false;
  }
  const p = value.payload;
  return Object.keys(p).length === 4 && (p.base === "BTC" || p.base === "ETH")
    && typeof p.timeframe === "string" && typeof p.capital_per_entry === "string"
    && p.capital_per_entry.length > 0 && p.capital_per_entry.length <= 128
    && (p.strategy_name === paperTestStrategy || typeof p.max_entries === "number" && Number.isInteger(p.max_entries)
      && p.max_entries >= 1 && p.max_entries <= 10)
    && (value.reference === undefined || (typeof value.reference === "string"
      && new RegExp(`^${p.strategy_name === paperTestStrategy ? "paper-test" : "f21"}:[0-9a-f-]{36}$`, "i").test(value.reference)));
}
export const strategyJournal = sessionJournal<StrategyAttempt>("tiewtrade.strategy-start.v1:", value => value.owner, valid);
