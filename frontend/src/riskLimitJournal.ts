import { sessionJournal } from "./attemptJournal";
import type { RiskAction, RiskMode, RiskPayload } from "./riskLimits";
export type RiskAttempt = { version: 1; owner: string; mode: RiskMode; key: string; action: RiskAction; payload: RiskPayload };
export const riskScope = (owner: string, mode: RiskMode) => `${owner}:${mode}`;
const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
function valid(value: unknown, scope: string): value is RiskAttempt {
  if (!record(value) || Object.keys(value).length !== 6 || value.version !== 1 || typeof value.owner !== "string" ||
      (value.mode !== "PAPER" && value.mode !== "LIVE") || riskScope(value.owner, value.mode) !== scope ||
      typeof value.key !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.key) || !record(value.payload)) return false;
  const p = value.payload;
  if (!Number.isSafeInteger(p.expected_revision) || (p.expected_revision as number) < 0 ||
      !Object.hasOwn(p, "expected_wallet_id") || !Object.hasOwn(p, "expected_episode_id")) return false;
  if (value.mode === "PAPER" ? typeof p.expected_wallet_id !== "string" || typeof p.expected_episode_id !== "string" : p.expected_wallet_id !== null || p.expected_episode_id !== null) return false;
  if (value.action === "RESET") return Object.keys(p).length === 3;
  return ["SET", "DECREASE", "INCREASE"].includes(String(value.action)) && typeof p.amount === "string" && Object.keys(p).length === 4;
}
export const riskJournal = sessionJournal<RiskAttempt>("tiewtrade.risk-limit.v1:", value => riskScope(value.owner, value.mode), valid);
