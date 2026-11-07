# NC-SET4-09 — Bound parent polling while preserving command checks

สถานะ: **Approved A — harness, targeted tests and one diagnostic**
วันที่: 2026-11-06
ขอบเขต: opt-in test harness only; no production change or full W1

## Evidence and problem

NC08 completed288 checkpoints and32 owner comparisons. In all4 pairs writer means
were lower with polling; this does not support blaming writer slowdown on polling
in that experiment. The polling parent nevertheless spent84.9–87.5% of measured
reader transaction time acquiring connections and had81.6–146.9ms loop-delay peaks.
It performed no command submissions, so it did not reproduce the actual parent mix.
See [NC08](checkpoint-runtime-drift-plan.md) and the Batch evidence ledger.

Read-only inspection of `backend/tests/infra/execution_market/profile_workload.py`:
- `_run` creates one ENGINE engine used for submissions, replay, cancellation and
  command/status reads. Source/API/migrator/scan engines are separate.
- `run_scheduled_cycles` starts one task per owner with its existing schedule and
  one60s cycle budget. At100 owners, many owners may be waiting simultaneously.
- `wait_command` and `wait_status` each acquire a new owner session on every read,
  release it, then sleep0.25s. There is no read-specific admission limit.
- `submit_new` commits submission, waits for command result, checks failure, waits
  for the expected projection, then records completion. `cycle` follows the same
  pattern for cancel and checks replay success. Those conditions must remain.
- Current observed ENGINE pool defaults are5 base +10 overflow. This is a bounded
  pool, not100 simultaneous connections; excess tasks wait at pool acquisition.

Existing180s parent traces, not full-campaign totals:

| Prior diagnostic | wait_command transactions / pool share | wait_status transactions / pool share | submit_new transactions / pool share |
|---|---:|---:|---:|
| heartbeat diagnostic2 | 11801 /70.7% | 6362 /70.5% | 1039 /21.2% |
| checkpoint diagnostic1 | 16399 /74.0% | 8647 /74.7% | 1004 /22.9% |

These are summed overlapping transaction times, not elapsed campaign time.
Replay/cancel submission transactions often inherit the `cycle` trace label because
storage aliases are bound in module scope; do not infer phase precision absent
from the evidence. Pool waiting is real but a starvation/root-cause claim is not
proved. This proposal tests one bounded harness change, not a proven optimization.

## Option A — opt-in read concurrency4, safety checks, one existing diagnostic

Introduce an explicit `--parent-poll-limit 4` option for the standalone diagnostic
SMOKE profile only, requiring R8/heartbeat/diagnostics/final-tail options. Default
is unset and preserves existing behavior. Do not silently enable it for W1/W2/W3/W4,
BASELINE or other callers. Reject unsupported values/profiles before allocating
engines, creating data or starting workers. No arbitrary tunable CLI range.

Create one `asyncio.Semaphore(4)` for the parent run. Pass it explicitly through the
relevant harness callers to `wait_command` and `wait_status` as optional keyword
state; default None preserves current callers. It is ephemeral test coordination,
not shared/persistent business/session state. No module-global registry, new DB
credential, new pool or process is needed. Confirm the actual ENGINE configuration
is5+10 for this profile; mismatch stops rather than deriving a new limit.

Why4: a single proposed candidate below the base pool size5, leaving headroom
relative to base capacity and at most4 polling sessions against total capacity15.
This is not an optimized value or a guarantee of SQLAlchemy admission fairness;
other transactions, task scheduling and the database can still delay submissions.
No sweep/adaptive tuning of this number is authorized.

For each read attempt:
1. Start/retain the existing outer command/status60s budget and enclosing cycle60s
   deadline. Time spent waiting for the semaphore counts against both. Do not
   restart a deadline when a permit/connection becomes available.
2. Acquire the permit **before** opening `user_session(..., role=ENGINE)`; record
   permit wait independently of connection wait. Never hold a DB connection while
   waiting for this permit.
3. Perform the same existing owner-scoped command or projection SELECT, with the
   same return/failure/status rules. Release the session/transaction before the
   permit, including errors and cancellation.
4. Release the permit before the unchanged0.25s sleep. Successful/failed command
   behavior stays the same; no extra retry, swallowed error, fabricated completion,
   cached status or skipped projection check. Submission/replay/cancel writes do
   not take a polling permit and keep their transaction/idempotency behavior.

Apply the gate during SMOKE's baseline preparation and measured cycles so its
lifetime cannot accidentally switch between owners. The unset BASELINE command
remains unchanged. Do not move business execution into this parent or join/merge
queries as part of this change.

## Reuse and implementation boundary

- `profile_workload.py`: reuse wait_command/wait_status, submit_new, cycle,
  seed_baseline, run_scheduled_cycles and existing scheduling/60s cancellation.
  Add only the optional argument plumbing and one small shared polling-session
  context helper to avoid duplicating permit/session/error handling. Search existing
  helpers before writing it. `bounded_map` supplies the existing semaphore pattern,
  but wrapping an entire60s waiter in bounded_map would hold a permit while sleeping
  and is not the proposed behavior.
- `profile_diagnostics.py`: reuse parent_observations/generator_operation and
  timeout queue snapshots. Add observation labels at the actual new/replay/cancel
  transaction sites for this opt-in profile so aliases cannot erase attribution.
  Preserve original exceptions, scope restoration and default paths.
- `profile_pool_timing.py`: reuse opt-in monotonic TransactionTrace and SQL hashes;
  `profile_runtime_observation.py`: reuse the bounded parent loop/CPU phase recorder.
  Only the parent needs new loop/CPU observation; workers retain their existing
  behavior and trace instrumentation. Record gate attempts/acquired/cancelled/error,
  current/peak permits and wait durations, including failed/cancelled attempts.
- `profile_resources.py`: reuse actual pool inventory/headroom/cleanup evidence.
  `test_profile_diagnostics.py`, `test_runtime_observation.py` and existing workload
  safety tests remain the starting point; add focused gate cases.
- Existing Money/Quantity fixtures, deterministic identities, financial oracle,
  final-tail drain, scheduler/claim budget/heartbeat and DB migration0065 unchanged.
  No production, migration, infrastructure, new dependencies or Live orders.

The gate transfers some waiting from the pool to a semaphore. Therefore report
**gate + pool + transaction/end-to-end times**, not a smaller pool-wait number as
an improvement by itself. Permit wait is included in command and cycle latency.
Observation buffers are bounded100000 rows per process; fail on truncation.

## Validation before launch

- Default None: identical calls, timing/checks and no permits/extra business SQL.
  Invalid values or non-SMOKE profiles rejected before side effects.
- With more than4 concurrent readers, at most4 permits/owner sessions; a submission
  can reach its existing transaction while readers queue outside the pool. This
  tests the mechanism, not a universal scheduling-fairness guarantee.
- Hold permits to exercise deadline expiry/cancellation before session acquisition;
  inject query/session cleanup failure and cancellation while holding a permit.
  Every path releases resources and retains primary errors; no detached read task,
  connection leak, permit leak or new command retry.
- Release permit before sleep. Keep PENDING/missing command, failed command,
  command success with projection still pending, expected status and missing order
  behavior unchanged. No completed counter increment before both required checks.
- Preserve deterministic replay/new/cancel identities and existing admissions,
  per-owner order, due-time schedule and cycle budget. Tests prove gate wait is not
  removed from reported end-to-end latency or the cycle deadline.
- With real PostgreSQL, verify owner/RLS isolation and command/status observation
  against existing fixture helpers; record actual pool configuration and safe
  submission/read coexistence. Do not use mocked transactions as the sole proof.
- Opt-in trace phases identify submit/replay/cancel vs command/status polls; gate
  and pool timings are separate. Parent runtime phases/clock boundaries restore
  correctly on failure. Preserve aggregate outcomes and cross-boundary rows.
- Run relevant targeted safety/regression tests and scoped Ruff/format/mypy.
  Confirm each exit0 and candidate hashes **before** launch, sequentially. Reuse
  valid prior evidence; no full regression/CI ritual. Production/lock hashes pinned.

## Exactly one diagnostic after safety passes

Reuse the previously approved heartbeat/final-tail **SMOKE** workload, with this
one explicit parent gate. Fresh isolated0065 DB;100 owners ×20 baseline orders,
20 standalone workers, R8 one successful claim per phase,10 offered commands/s,
6 positive five-command cycles per owner. Measured work:600 cycles /3000 commands;
2000 baseline orders are preparation and reported separately. Reuse the current
financial/global invariant oracle and final-tail gates for all100 owners.

Nominal measured schedule is300s; allow about**10–15minutes including preparation
and verification**, with a **20-minute total campaign cap**. Retain60s cycle/drain
bounds. No full W1, new long-load profile, fault schedule or second comparison arm.
No reuse of dirty failed DBs, pool-size change, resource intervention or pruning.
Record available disk/DB health before starting; stop on resource unavailability.
The previous frozen-lock test venv may be reused if hashes remain valid.

Enable diagnostic tracing for the entire measured work including drain/timeouts:
opt-in900s trace window published at measurement start using the existing atomic
control helper (default180s retained elsewhere). No trace activation during the
long baseline preparation; report baseline timing/counters separately. Parent loop
and gate observations may be phase-labeled from setup and remain bounded. Failure
or truncation stops rather than suppressing data. No new external admin observer
is required for this proposal; do not expand DB grants.

Report offered/admitted/completed/rejected commands,600-cycle denominator,
financial/global invariants, final input lag/drain outcome, worker latency and
parent submission/gate/pool/read/loop timings. Keep missing/unfinished operations
visible. Compare to history descriptively only: NC08 showed environment variability,
and this is not a contemporaneous A/B causal experiment. Unchanged SLA/lag rules
remain; diagnostic completion does not make W1/W4/integrated acceptance pass.

On timeout/error, stop/cancel/join all owned tasks/processes before post-stop reads
and disposal. Retain queue snapshots, errors, partial counters, logs and database.
Use existing shutdown bounds; total-cap failure is Incomplete. **No replacement
or additional attempt is authorized.** After one diagnostic, stop/report. If no
improvement or still ambiguous, say so rather than trying another permit count.

## Option B — retain current evidence

Do not add the gate or run another workload. Preserve NC08 observations and
unresolved original W1 cause. No performance/acceptance claim.

## Approval status and remaining gates

Owner approved A in the current conversation before implementation. NC-SET4-09
is Closed / Approved A. The opt-in harness and targeted checks are complete;
the single authorized diagnostic is **Incomplete / cycle bound Failed**.

## Execution checkpoint — 2026-11-06

- Added `profile_parent_poll.py` and focused `test_parent_poll.py`; reused workload
  polling/session helpers, diagnostics, runtime observer and existing fixtures.
  The default path and production logic remain unchanged. Gated baseline cleanup
  joins sibling tasks, and diagnostic runtime cleanup preserves the primary timeout.
- **115 targeted tests passed**, including real PostgreSQL isolation/concurrency;
  scoped Ruff, format and mypy exit0 were confirmed before launch.
- One fresh0065 DB, `tiewtrade_set4_iso_pollgate_0fb8aef4`. Total813.431s within
  the1200s cap. Baseline2000 orders completed; measured work stopped after206.781s
  when one cycle reached60.002s. Completed289/600 cycles; offered1732,
  admitted1731, completed1632, rejected0 out of3000 planned commands.
- Gate peak4, active0, untruncated. Measured command/status gate waits average
  779.6/788.7ms, while their pool waits average17.3/17.3ms. Waiting moved outside
  the pool; no end-to-end improvement is established. The timed-out cycle waits
  on command results/projections and reaches its deadline waiting for final FILLED.
- Partial measured worker transaction p95/p99=1003.8/1339.0ms (3894 wholly
  contained samples). Financial/global oracle, final-tail and final input-lag
  checks were **Not Reached**. No acceptance or full-W1 result is inferred.
- All21 pool reports finalized with0 checkouts,21 traces closed/untruncated,
 20 worker PIDs exited, gate/runtime closed and DB connections0. Checked source
  hashes unchanged. Database and partial evidence retained.

Full metrics/limitations: [Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md#nc-set4-09--incomplete-cycle-bound-failed).
This single-run scope has reached stop/report; no replacement is authorized.
Next recommendation: inspect existing worker/queue traces for the timed-out cycle
and propose a bounded next plan. Await owner direction before that next task;
no further experiment or production change is included.

Prior W1 Failed/Partial, W2/W3 Not Run, new-writerW4 Pending Revalidation, historical
old0064W4 Passed and integrated NC-SET4-01/F17 gaps remain. No production fix,
acceptance relaxation, activation, commit/push/merge or additional experiments.
