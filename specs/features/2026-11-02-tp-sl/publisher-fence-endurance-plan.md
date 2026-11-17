# NC-F17-FENCE-02 — instrumented internal20 four-hour run

สถานะ: **Approved — owner requested เริ่มทำทั้งหมดเลยได้ไหม after the full plan/adaptation/tests/4h estimate**
2026-11-15. Existing F17 validation amendment and branch; no Git authorization.

## Requirements / exact execution

Run exactly once after affected safety checks: PAPER_INTERNAL20_V1 W3,20owners,
400baselineorders,20workers,282cycles/owner,28200commands,2commands/s outside original
seven fault windows;14400measured seconds. Exact existing w3_fault_schedule.json
including workerrestart/connectionchurn/dedicatedRedisoutage, same financial/global/
snapshot/rebuild/finaltail/pool/RSS criteria,5s leases/guards/fences/financial formulas.
Current internal processing500ms/2s acceptance and original250ms/1s target reported;
other existing snapshot/rebuild/recovery60s bounds unchanged. No excluded slow data.

Keep previously approved NC_F17_CLOCK_01 runtime: at most1confirmed rolled-back
future-input recovery event/1retry/1s, active measured window only; visible warning.
No new order/financial retry, lease reacquire, clock tolerance or increased deadlines.
Enable lease+fence observers together for this exact long-run combination, otherwise
retain SMOKE-only restrictions and original no-observer behavior. Missing required
observer/clock flags or other profiles/worker modes/controlled delays fail early.

Observer remains read-only with unchanged bounds/SQL/retention/cleanup and explicit
snapshot association fields. Pin all sources/config/schema/coordinator before the
single120s/7sample preflight, before fixture DB/Redis. One fresh owned DB and labelled
Redis, no owner/Live actions. Expected4h15–30min execution after preparation; total
outer cap18000s(5h) from preflight incl setup/final verification/normalcleanup. Fixed
measurement stays14400s; outer cap never extends cycle/recovery/lease/SLA deadlines.
Stop/report on first Failed/Incomplete; no automatic replacement. Keep prior grades.

## Implementation / reuse before source changes

- Extend existing load-observer option validation narrowly: original20 W3 only when
  both observers and existing approved clock recovery are explicitly on. SMOKE still
  rejects clock recovery; W1/W2/release/worker modes stay rejected for this observer.
- Trace actual original readiness-guard calls within the selected task, without
  adding guard calls. Aggregate actual guard count across publications, so one
  clock retry's two checks do not become false evidence mismatch. Preserve task
  isolation, actual return/errors and M1 missing-evidence handling.
- Trace session wrapper must skip its optional precommit clock probe after an
  explicit completed rollback; emit a distinct normal-rollback-exit observation,
  not a commit claim. Never reopen a rolled-back transaction for observation.
  After successful retry still observe its own real normal commit/session exit.
- Keep the recovery controller/policy/production session/guard unchanged. Reuse
  old hold-lock/readonly/cancel/race/pool/clock tests. Add exact option matrix and
  real-PG combined recovery/observer proof (one logical input, two guard calls,
  no postrollback probe, confirmed final commit, foreign tasks cannot add counts).
- Private coordinator reuse: root/ownedRedis/preflight receipt binding, W3 args,
  exact fault schedule/hash,18000s outer budget and progress on the owned run.
  No unrelated process changes. Actual full snapshot/rebuild/global/financial checks
  must finish; if late-stage evidence fails retain Incomplete, not partial Passed.

## Validation / checkpoints

Feature: scoped Ruff/format/mypy/whitespace; affected real-PG clock/lease/load/fence/
owned-pool default and negative options, original-once/rollback/commit/cancel proof.
Use unchanged safety evidence; no required CI substituted by local tests.
Batch: this single instrumented W3 with exact duration/28200commands/7fault evidence,
financial/positions/snapshot/rebuild/tail/resources and diagnostics. Report its
instrumented candidate/runtime explicitly, not a retroactive old/no-observer pass.
If used, report clock recovery warning. All numerical criteria remain unchanged;
observer overhead cannot justify exclusion or waivers.
Release:100account/opening/bot/notification/Live dependencies remain separate; this
alone cannot mark F17Completed. No commit/push/PR/CI/merge. After run collect full
result/limits/cleanup and stop/report, even if early failure; next fix requires
an evidence-backed scope and normal review/refactor gates.

## Execution checkpoint — 2026-11-16

[One approved W3 result](evidence/endurance20-20261115/fence02-w3-checkpoint.md):
**Incomplete**,14400.000637s measured/28200commands completed,15353.547435s total.
Final-tail24.061s and4820snapshots returned;13owner replays returned,14th exceeded
unchanged60s budget during read_execution_inputs,remaining6NotRun. Finalfinancial/
global/resource/aggregate acceptance NotRun. Publisher144249returned/0lease errors,
clockrecovery0; fence sampler TimeoutError1/0successful samples,joined. No root-cause
fix claimed. Independent cleanup0connections/locks,DB/Redisabsent,sourcesunchanged.
192targeted safety/static evidence retained. Stop/report; no secondrun/Git/CI.
F17 notCompleted; next is scoped short replay/sampler investigation,not automatic4h.
