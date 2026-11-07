# Checkpoint concurrency and polling isolation

สถานะ: **Approved A — owner approved harness, targeted tests and one campaign (NC-SET4-07)**
วันที่: 2026-11-06

## Question and evidence

The previous paired campaign completed24arms/360checkpoints, with330snapshot
comparisons equal and11→6client calls confirmed. Timing was mixed; the100-owner
cause remains Inconclusive. See the [Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md)
and `isolation-campaign-summary.json`. No further experiment was authorized there.
Owner now requested this concrete next plan; only documentation/read-only analysis
has been performed for NC-SET4-07.

Existing workload traces show parent command/status polling consumed about74–75%
of its transaction time acquiring connections; processing acquisition was about2.9%.
Slow processing can cause additional polls, and polls can add DB/client load. The
experiment below tests that interaction at the checkpoint layer, without assuming
which direction caused the original timeout. Current `RESULT_POLL_SECONDS` is0.25s;
this is distinct from the worker's0.02s tick and must not be confused with it.

## Option A — one bounded two-factor campaign (recommended)

Freeze the current0065/PG_BATCH_V1 writer for every condition. No comparison with
legacy writer, production patch, new migration, pool tuning or cadence optimization.
Test two factors: independent concurrent writers (1or4), and additional read-only
poll tasks (0or100). Each writer owns a different Paper owner; never two writers
for one owner. This does not run the scheduler, price feed, fills or full W1.

| Condition | Writer processes / active owners | Poll tasks | Checkpoints |
|---|---:|---:|---:|
| 1writer, no polling | 1 | 0 | 24 |
| 1writer, polling | 1 | 100 | 24 |
| 4writers, no polling | 4 | 0 | 96 |
| 4writers, polling | 4 | 100 | 96 |

Run this order once, then its reverse once:8measured arms and480checkpoints.
Before those arms, prepare one untimed sequential reference arm for all4owners
(96checkpoints). Total9arms/576checkpoints in one campaign. No automatic retries,
extra repetitions, discarded outliers or adaptive selection of conditions.

### Data and startup

Prepare one fresh0065template with4owners, each using the existing20BTC+2ETH
fixture and24canonical operations. Call existing fixture preparation per owner;
keep its prices, Money/Quantity, decision IDs, timestamps and operation order.
Clone the unchanged prepared template before the reference and each measured arm.
Freeze all four fixture documents, initial raw snapshots, source/function/schema,
role URLs/actual DB, dependencies and harness hashes. Retain old failed databases.

Verify available connection headroom against declared process/pool configuration
using existing resource-budget patterns before measurement. Insufficient headroom
or identity mismatch stops the campaign; do not reduce the matrix or change pools.
One ENGINE pool per writer process; poll tasks use one separate shared ENGINE pool,
as in the existing parent/worker separation. Keep all pool settings at their current
values. This deliberately does not model generator command submissions competing
with polls in the original parent pool; record that limitation.

Each writer completes the same owner-session warm-up and signals ready before a
common start barrier. With polling enabled, all100readers must complete one initial
read within a10s readiness limit before the writer barrier opens. Initial absence
of a projection is a recorded observation, not a reason to fabricate a status.
Distribute initial poll offsets deterministically across one0.25s interval to avoid
an artificial single startup burst. Startup/readiness durations are reported
separately from transaction timing and still count against the campaign cap.

### Writer and polling behavior

Each active writer performs its24fixture operations in order, one owner transaction
per operation. Wait0.1s after each committed checkpoint before the next operation,
outside timing. Use identical pacing for every condition and the reference; report
actual start times/throughput. This is a controlled closed-loop probe, not a promise
of fixed offered throughput or a new W1 load profile.

Pollers alternate query families by task assignment:50command readers and50status
readers total. With one writer, all target its owner. With four, allocate26/26/24/24
tasks by owner, equally split within each owner between command and status reads.
Bind each target to that owner's first BTC header/command during setup. Reuse
`get_order_command` and the existing status SELECT under `user_session(...ENGINE)`.
Do not give pollers elevated roles or change grants. After each completed read,
sleep the unchanged0.25s. No catch-up flood or read-driven financial action.

Reader results are observations only: they do not schedule writes, complete a
command, choose a retry or determine financial success. This breaks the original
closed-loop polling feedback sufficiently to test the pressure from reads. All
fixture writes proceed independently of reader results. No order submissions,
market inputs, heartbeat/freshness updates or business-state caches are introduced.

### Timing, correctness and observation boundaries

Reuse checkpoint and full owner-transaction monotonic boundaries from the previous
harness. Store every operation's owner/index/kind/cardinality, statement count,
start/end, outcome and source identity. The transaction boundary includes context
exit; it must not be labeled pure server commit time.

During measured arms, defer snapshot verification until all writers finish and
pollers have stopped/joined. Otherwise one owner's verification queries would add
uncontrolled load to another owner's timed transaction. The untimed reference may
retain per-operation snapshots. For measured arms compare each active owner's final
normalized ten-table snapshot against its reference, including the complete event/
audit/ledger history and sequence/revision/identity counts. Verify inactive owners
retain their initial raw snapshots. Preserve raw final snapshots and the existing
normalization allowlist; no economic field or business timestamp may be omitted.

There is no intermediate projection/reservation assertion in the concurrent timing
window; reuse the preceding per-operation equivalence/safety evidence and explicitly
retain this limitation. No full financial/PnL/W1 oracle is claimed. Any missing or
duplicate decision, cross-owner change, final-state/history mismatch or exception
fails the experiment and stops later arms.

Use existing `TransactionTrace`/`operation_scope` for bounded per-process pool/client
SQL observations, with identical instrumentation in every condition. Configure the
trace window to cover each entire measured arm, including a timeout; retain the
existing100000-row cap and fail on truncation. Report poll started/completed/
cancelled/error counts and actual read rate; never exclude failures silently.
The measured effect includes instrumentation overhead, not just uninstrumented SQL.

Sample host load/memory and container CPU/memory at most once per second, with at
most one sample operation outstanding. For DB visibility, use a separate local
`docker exec ... psql -U postgres` observer in explicitly READ ONLY transactions,
filtered to the current newly created test database. Read only connection count,
PID/role/state/transaction-start/wait type/wait event/blocker IDs; never query text,
parameters, secrets or business rows. This is a test observer, not an application
credential or grant change. Verify its availability before measurement; if unavailable,
stop/report rather than silently running without the planned visibility. Record
actual sample times, gaps and missing values; sparse samples cannot prove no waits.

### Reuse, implementation and validation

Reuse `profile_checkpoint_fixture.prepare(btc_orders=20)`, `checkpoint_snapshot`,
`profile_checkpoint_isolation` clone/name/URL/role/function/source guards and joined
child cancellation, and `profile_workload` save/progress/percentile helpers. Extract
only the small common operation-persistence/timing helper needed to avoid copying
the same loop into a third implementation; preserve existing CLI/default behavior.
Put this campaign's coordination in a test-only entry point with focused tests.
No general benchmark framework, new dependency or production infrastructure.

Before the campaign, targeted checks must prove:
- Four distinct owner identities, fresh independent clones, pinned writer and actual
  role/database/function rejection; the exact8-arm order and576total operations.
- Pollers issue only the allowed owner-scoped reads and do not govern writes;
  deterministic50/50query mix, owner distribution and0.25s interval are preserved.
- Barriers/readiness failures, writer errors, reader errors and deadlines cancel
  and join every child/task before snapshots/disposal; original errors survive cleanup.
- Verification cannot overlap measured writes; snapshots include all four owners,
  active final histories and inactive initial states, with the existing allowlist.
- Timing excludes pacing/verification; caps/truncation/incomplete denominators fail
  closed. Previous fixture and paired-harness defaults/callers remain covered.

Reuse valid production safety results. Run affected harness/real-DB isolation checks
and applicable Ruff/format/scoped mypy, not full regression or required CI as a ritual.

### Caps, interpretation and stop

Announce approximately2–5minutes including setup, with a15-minute campaign cap.
Each measured writer group has one60s budget from its start barrier (not a new60s
per owner); setup readiness is bounded as above. Keep the existing60s per-operation
bound as a further guard. Cap failure is Incomplete, not permission for a replacement.
Stopping cancels/joins pollers and writers before verification; preserve all errors,
snapshots, logs and database names. No broad cleanup/prune or alteration of unrelated
workloads/Docker resources. Remove only newly created temporary source/process files.

Report every arm separately and the polling-on/off comparison within each writer
count for both orderings. Report the concurrency effect separately, including actual
throughput and pool/SQL/resource observations. Small samples, different total work
at1versus4writers and host drift limit inference; no significance claim or250ms SLA
application. Mixed direction or inadequate visibility remains Inconclusive.

After this one campaign, stop/report. If polling consistently increases latency,
propose a narrowly scoped harness observation change for separate approval; do not
claim the production scheduler is fixed. If concurrency dominates, use observed
wait/resource evidence to propose the next bounded investigation. Do not tune pools,
remove safety checks, change production or start another experiment automatically.

## Option B — stop at the current evidence

Retain current checked code and all failed/inconclusive results. No new harness
changes or trials; concurrency/polling causality remains unresolved.

## Approval and acceptance status

Owner approved A in the current conversation before implementation/execution. This plan
changes only a test experiment. It preserves existing money/quantity/risk,
RLS/owner locks/idempotency/transaction rules and stateless production architecture.
No new persistent session/business data is held in process memory. Live remains off.
Original p95<=250ms,p99<=1s,cycle/drain60s and lag<=20 acceptance criteria remain.
W1Failed/Partial,W2/W3NotRun,new-writerW4PendingRevalidation,old0064W4Passed and
integrated NC-SET4-01/F17pending gates are unchanged. No production patch, full W1,
activation or commit/push/merge is authorized by this proposal or its experiment.
