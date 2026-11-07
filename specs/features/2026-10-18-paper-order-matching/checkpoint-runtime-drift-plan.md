# NC-SET4-08 — Paired polling and runtime observation

สถานะ: **Approved A — harness, targeted tests and one campaign**
วันที่: 2026-11-06
ขอบเขต: test harness / diagnostic only; no production or trading-rule change

## Why this experiment

[NC07](checkpoint-concurrency-polling-plan.md) completed its approved replacement:
576 checkpoints, all32 owner comparisons passed. Timing remained Inconclusive.
The same1writer/no-poll condition averaged44.28ms per transaction early and260.28ms
late (5.878×). This is observed temporal variability, not proof of external host load.
Polling-on/off direction reversed between forward and reverse orderings.

Read-only examination of existing `checkpoint-polling-2/arm-*/resources.jsonl`
shows composite resource collection took1.275–4.682s per sample. Start-to-start
gaps were2.583–5.697s while writer groups lasted3.595–10.336s. The current sampler
awaits DB metadata, Docker stats and vm_stat serially, then waits another1s. Its
single interval cannot locate which collection step was slow. The old evidence
also has no direct event-loop scheduling-delay or process CPU observations.
No new workload, code change or resource intervention was performed for this plan.

Question: with writer count and work held constant, does polling have a repeatable
within-pair effect, and do slow checkpoints coincide with client scheduling delay,
client CPU activity, connection acquisition or observed DB waits? This reduces
some order confounding; it cannot fully isolate a causal host effect on a shared
machine. If observations are insufficient or inconsistent, report Inconclusive.

## Option A — one bounded paired campaign (recommended)

Keep the current0065/PG_BATCH_V1 writer. Use1 active owner/writer in every measured
arm, preserving the previous twenty BTC + two ETH headers and24 operations.
Use a fresh four-owner template and a separate sequential four-owner reference
(96 operations), reusing existing preparation. In measured arms owner0 is active;
the other3 owners provide unchanged-data controls. There is never more than one
writer for an owner. No4writer test is included in this experiment.

A = no pollers; B =100 pollers (50 command /50 status, targeting owner0).
Run exactly **A B B A | B A A B** with a fresh clone for each arm:

| Pair | Arm sequence | Measured operations |
|---|---|---:|
| 1 | A then B | 48 |
| 2 | B then A | 48 |
| 3 | B then A | 48 |
| 4 | A then B | 48 |

Eight measured arms ×24 =192 operations; reference96; **288 checkpoints total**.
No extra iterations, randomized financial inputs, discarded outliers, adaptive
reordering or reruns. Compare adjacent pairs; do not pool away their ordering.
Use new database names and retain all previous DBs/results. Reuse the current
initial raw/final normalized ten-table comparisons and normalization allowlist.
All8 ×4 =32 owner comparisons must pass (8 active histories,24 inactive raw states).
Reference snapshots are scoped to this campaign's identical fixture IDs.

Keep pool defaults,100-reader readiness,10s readiness bound,0.25s interval after
each completed read, deterministic offsets,0.1s writer pacing and one60s writer-
group bound from the barrier. Preserve60s per-operation guard, read-only ENGINE
queries and no result-driven writes/retries. All24 fixture operations and their
Money/Quantity values, decision IDs, timestamps and order stay unchanged.

No wait for a preferred host load, stopping unrelated apps/containers, CPU pinning,
resource tuning, disk pruning or hidden quiet-period selection. Record actual
conditions before/throughout the campaign. If declared DB connection headroom or
required observers are unavailable, stop without changing the matrix or pools.
Free-space/headroom observations are recorded; do not start resource recovery or
remove old evidence as an implicit part of approval.

## Additional observations — explicit opt-in, identical in A and B

Use a named harness profile `paired-runtime-v1`; retain NC07 CLI/default behavior.
These are test observations, not authoritative business data or new runtime infra.

1. **Clock and phase boundaries.** Record paired monotonic/wall timestamps for
   ready, common start, final checkpoint commit, readers stopped and resources
   closed. Add monotonic fields to test trace rows through an opt-in extension;
   keep the existing default trace schema/callers unchanged. Store process ID,
   owner and phase only. Distinguish readiness, measured work and shutdown.
   Never subtract wall-clock timestamps to compute latency. Cross-process
   alignment is valid only on this local host with the same monotonic clock.
2. **Process scheduling delay.** In each writer and the polling parent, one
   lightweight task sleeps0.1s and records actual wake-up delay relative to its
   scheduled deadline with monotonic time. Record missed intervals and schedule
   the next tick from the current time; no catch-up loop. Keep at most100000 rows
   per process, fail on truncation, buffer and flush outside checkpoint timing.
   This is event-loop responsiveness including possible interpreter/OS delays,
   not a direct measure of CPU saturation or of external applications.
3. **Own process CPU time.** Record cumulative `time.process_time()` at phase
   boundaries and before/after each checkpoint outside the existing timer helper.
   These deltas describe CPU consumed by that process; they exclude PostgreSQL,
   other apps and waiting. Do not equate wall-minus-CPU with DB service time.
   For the polling parent use phase samples, not per-read CPU attribution (tasks
   overlap). No process arguments, environment variables or other users' data.
4. **Independent read-only resource samples.** Preserve the NC07 admin observer's
   explicit READ ONLY query and exact new-DB filter/metadata allowlist. Separate
   its task from Docker stats and host vm_stat/load tasks. Minimum start spacing:
   DB1s, host1s, Docker3s. Each family permits at most one outstanding sample;
   skip missed ticks rather than queue/catch up. Record each family’s own start,
   finish, monotonic/wall pair, gaps and missed ticks. A sample spanning the work
   boundary is labeled accordingly, not assigned wholesale to measured time.
   Do not increase DB privileges or use the observer for business reads/writes.
5. **Bounds and termination.** Check each observer once before work. Per external
   sample deadline10s; error/timeout records missing metadata and stops the arm.
   A5s observer cleanup grace follows stop; if necessary cancel/join its owned
   subprocess and mark Incomplete. Join all tasks/processes before snapshots or
   pool disposal. This cleanup allowance never extends the60s writer budget or
   15min total campaign cap. Retain the primary error plus cleanup errors.

Reusing the same instrumentation in A and B limits one source of bias; it does
not remove observer overhead. More measurements do not guarantee clearer causality.
No synthetic CPU load, additional SQL probe transactions or per-operation snapshots
are added inside the measurement window. No scheduler/feed/heartbeat/fills/full W1.

## Implementation reuse and boundaries (after approval only)

- `backend/tests/infra/execution_market/profile_checkpoint_polling.py`: reuse
  fixtures/setup, assignments/read_target/poll, run_group barrier and joined
  cancellation, snapshots/verify_final, validate_measurements and bounded campaign.
  Add only the explicit profile, schedule and observations above. Preserve the
  previous default matrix/576 denominator and old output interpretation.
- `profile_checkpoint_isolation.py`: reuse timed_checkpoint, clone_database,
  database_name, database_environment, verify_databases/verify_writer and child.
  Do not copy its transaction/persistence loop or change financial storage.
- `profile_checkpoint_fixture.py`: unchanged prepare(btc_orders=20) and snapshots.
- `backend/tests/infra/risk_limits/profile_pool_timing.py`: reuse TransactionTrace
  and operation_scope; opt-in monotonic fields only, default behavior unchanged.
- `backend/tests/infra/risk_limits/profile_resources.py`: reuse PoolEvidence,
  connection_budget and actual-vs-declared pool verification unchanged.
- `profile_workload.py`: reuse save/progress/percentile and RESULT_POLL_SECONDS;
  preserve its defaults and all existing standalone acceptance paths.
- Before writing a sampler, search for an equivalent helper again. Current search
  of backend/tests/infra found no process_time/event-loop-lag helper. Use a small
  test-local helper; no general telemetry framework or new dependencies.

No production module, migration, infrastructure, live exchange or business/session
storage changes. PostgreSQL remains authoritative; observation buffers are ephemeral
and never drive trading actions. No UI changes, commit/push/merge or release.

## Validation and launch gate

Before launching, use targeted tests/static checks covering only affected paths:

- Explicit profile has exact ABBA/BAAB order, eight fresh measured clones,
  four-owner reference and288 checkpoints; default NC07 remains576 unchanged.
- Both profiles retain owner isolation, immutable fixtures, actual role/schema/
  function/source checks, pool headroom and all-four-owner post-join comparisons.
  Reuse prior valid real-PostgreSQL safety evidence; rerun impacted owner/transaction
  checks when helper changes affect their behavior. No mock-only proof of RLS.
- Fake monotonic/CPU clocks verify units and timing boundaries; timestamp fields
  do not affect money math or default trace output. Event-loop sampler stays
  bounded, skips missed ticks, cannot schedule writes or mask an original error.
- A delayed Docker sample cannot block the DB/host families. Each family stays
  within its cadence, avoids overlap and retains gaps/timeout/partial observations.
- Readiness/reader/writer/observer/deadline/cancellation faults join children and
  tasks before snapshots/disposal. Verify the existing stop/cancel/closed evidence
  remains intact and no incomplete denominator can be marked complete.
- Trace/observation caps fail closed. Measurement-only reader pool totals exclude
  readiness/shutdown; cross-boundary transactions are reported separately with
  full counts preserved, never silently discarded or assigned partial SQL costs.
- Test old/default callers plus focused Ruff/format/scoped mypy. Inspect **every
  exit code before launch**, save commands/results and candidate source hashes;
  no concurrent check-and-launch command. No full regression or required CI ritual.

Documentation is the only change before approval; validate links, arithmetic and
consistency now. Do not run a campaign or add code merely to prepare this proposal.

## Reporting, interpretation and stop

Expected **2–5minutes including setup**, capped at15minutes for one campaign.
Preserve all partial results/errors if any cap fails; no automatic replacement.
Report each arm's checkpoint/full-transaction mean,p50,p95 and all operation rows,
actual throughput, poll counts/rate/cancellations/errors, reader/writer pool and
SQL intervals, CPU deltas, scheduling delay and resource timestamps/gaps.

Compute polling-on/off ratios within each of the four adjacent pairs. A consistent
observed direction requires both checkpoint and full-transaction means to agree
across all four pairs; otherwise label Mixed/Inconclusive. Report p50/p95 even if
they disagree with means; this is descriptive, not a significance test or SLA.
Retain order-dependent baseline drift and matched operation index/cardinality.
Align slow-operation intervals with loop/CPU/wait observations without asserting
that correlation proves a cause. Sparse DB samples cannot prove absence of waits.

A repeatable effect can justify a separately proposed targeted investigation, not
pool tuning or production changes. Continued variation/ambiguous visibility means
stop/report Inconclusive, not another iteration. This tests1writer only and does
not settle four-/twenty-writer or100-owner scheduler behavior.

After this single campaign, stop and report evidence, limitations and recommended
next step. Original W1 Failed/Partial, W2/W3 Not Run, new-writerW4 Pending Revalidation,
old0064W4 Passed historical, F17/integrated NC-SET4-01 pending remain unchanged.
No250ms SLA, final-tail, full financial/PnL oracle or Completed claim from this probe.

## Option B — stop experiments

Keep the current44-test/static-check evidence and NC07 Inconclusive result. No new
harness or campaign; performance attribution remains unresolved.

## Approval recorded

Owner approved A in the current conversation before implementation: this opt-in
harness/profile, targeted checks and exactly one288-checkpoint campaign, then stop.
No production fix, W1 or Git publication. All prior failures and results retained.
