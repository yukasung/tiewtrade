# NC-F17-CLOCK-01 implementation checkpoint — 2026-11-15

สถานะ: Implementation and targeted safety validation complete; awaiting owner-directed code review.
[Approved plan](../../publisher-clock-recovery-plan.md). No replacement4h, publication or opening.

## Behavior and scope

Five harness/test paths only; [source bridge](clock-recovery-source-bridge.json).
Production/frontend/migrations unchanged. Explicit --publisher-clock-recovery is
accepted only for internal20 V1 W3 parent, defaultoff. Root/campaign validate before
output/preflight; no worker forwarding. Runtime revision/caps/approval path emitted
in manifests and recovery evidence. Old no-retry results are not regraded.

Recovery is armed only within the measured window and bound to its publisher task;
ContextVar inheritance does not authorize unrelated child publications. The original
future/stale guard still runs once per attempt with actual immutable arguments.
No later clock read/message matching/evidence-file decision/backdating/tolerance.

One eligible event per campaign, one additional attempt,1s monotonic rejection-to-
confirmed-commit bound. Explicit active-root rollback must return successfully and
the authorized session must exit before a fresh session regenerates the same logical
tick/input/writer identity from a fresh DB sample. Commit ambiguity/cancellation,
rollback or close failure, missing evidence, another source failure or second incident
cannot cause another publication. Normal/default publisher has no added SQL or retry.

Separate bounded artifact retains first rejection after recent64 eviction, actual
clock delta, attempted identities, rollback/exit/commit times and type-only errors.
Every attempt/wait remains in the original window; no financial POST/command retry.
Transient recovery state is test-only campaign control, not durable session/business
data. Hook/context restoration is covered; production stateless architecture unchanged.

## Test evidence (incremental; groups overlap, do not add counts)

| Group | Actual result | Scope |
|---|---|---|
| Initial recovery proof |27Passed|Real PG explicit rollback/context compatibility and one valid retry; early negative eligibility/CLI cases|
| Publisher/default/profile regression |145Passed|Expanded real-PG negative cases plus existing readiness, heartbeat, profile and campaign tests|
| Metadata/boundary/orchestration impact |110Passed|Clock delta/tick evidence,1s boundaries, malformed evidence and existing cancellation/cycle/orchestration regressions|
| Publisher-task binding |58Passed/1Failed|New unauthorized-child rejection passed; external-cancel test setup had not explicitly bound its intended publisher task|
| Corrected setup and child regression |2Passed|Bind intended task exactly as runner does, keep cancellation assertion; always cancel/join test task; unauthorized-child rejection still passes|

Current59unique recovery cases are covered incrementally by the58retained successful
cases plus the corrected cancellation case (the2-case replacement overlaps the child
case). Source did not change after the task-binding run; only that test's setup/join
changed. No weakened assertion or removed safety case. Original failed log retained;
its unobserved-task warning is resolved by deterministic join in the corrected test.

Real PostgreSQL checks include rollback-released source lock witnessed from a separate
connection, unchanged source/price rows before retry, unchanged owner ledger/orders/
positions/reservations, one accepted source input, same tick/owner/generation, actual
committed-but-unknown replies without extra retry, cancellation/timeouts and missing
transaction/failed evidence. Controlled test-only clock injection does not reproduce
or repair the physical VM/OS clock cause. Callback identity/foreign-task/default/
setup/window boundaries and ring eviction are checked. Parent fixture DBs and scratch
fixtures removed normally; latest parent DB independently verified absent.

Ruff check, format check and mypy Passed on all5affected files; whitespace Passed.
Local logs: validation-artifacts/f17-clock-recovery-tests-20261115/attempt-*.log.
No full suite/CI/endurance repeat; relevant unchanged production safety evidence from
PR75 is retained. Tests are not evidence of passing a4h replacement.

## Reviewer focus / remaining gates

Review explicit rollback vs suppressed shared cleanup errors, commit-ambiguity and
1s timeout boundaries, exact exception/task identity, no baseline/foreign-task recovery,
and completeness of preserved failure evidence/manifest revision. The conservative
one-event cap can still stop another4h attempt if the environment repeats the fault.
Underlying OS/VM cause remains unconfirmed. Safety tests do not promise completion.

Next owner instruction: review code for this scoped correction. Follow review/fix and
separate refactor authorization, then obtain the plan's stepD execution authorization
before one fresh4h replacement. No commit/push/merge in this checkpoint. Original4h20
Incomplete, original100/other historical grades and opening/dependencies retained;
F17 notCompleted.
