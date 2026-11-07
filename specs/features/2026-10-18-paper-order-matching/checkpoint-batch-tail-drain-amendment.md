# F15 checkpoint SQL batch and final-tail drain

สถานะ: **Approved A — owner approved checkpoint batch, tail drain, safety checks and one diagnostic on 2026-11-06**
วันที่: 2026-11-06

## Decision and evidence

Owner approved option A: implement the narrowly scoped storage batch and test-only
final-tail gate below, prove safety/equivalence, then run exactly one unchanged
100-owner/6-cycle diagnostic. Stop/report afterward. This explicitly includes a
production Paper storage change and additive DB function migration; prior approvals
for R8, heartbeat or diagnostic replacement did not authorize those changes.

Option B: implement only the opt-in test-harness final-tail gate and its tests,
then one diagnostic with the original checkpoint storage. Production stays
unchanged; processing p95 remains unresolved and may still fail. Stop/report.

Baseline: [replacement diagnostic2](../2026-11-02-tp-sl/evidence/batch-20261106/README.md#replacement-diagnostic2-result--observation-complete-criteria-failed)
completed3000commands/600cycles and all100financial oracles, but failed observed
processing p95=469.526ms against250ms and final input lag22 against20. The first180s
trace attributes about81.5% of processing duration to client SQL round trips and
2.7% to connection acquisition. These are overlapping aggregates, not server CPU
or causal speedup estimates. No single SQL statement dominates the processing total.

`matching_storage.py::persist_checkpoint` currently makes approximately11client
SQL calls including its helpers. The candidate batch removes five client round
trips from this path; it does not remove the underlying DB mutations or guarantee
that overall p95 will meet250ms. No new benchmark or source change was made while
preparing this proposal.

## A1 — preserve Python decisions, batch only checkpoint persistence

Keep `persist_checkpoint`'s public signature, return value and caller transaction.
Reuse existing `_matching_document`, `state_payload`, `order_payload`, Money/Quantity
serialization, `lock_active_episode`, `enable_financial_writer`,
`increment_wallet_revision`'s SQL semantics, and `record_event` validation.
Do not create a second financial/matching implementation in SQL.

Retain these Python-side steps in the same order:
1. Require the existing UserSession; acquire the existing owner/active-episode
   lock, including its separate post-lock canonical episode query.
2. Enable the existing F15/F17 writer markers; lock/read READY activity and obtain
   current source_sequence/revision exactly as today.
3. Build the same canonical decision payload/digest, projection/reservation rows,
   decision identity and timestamps in Python. Compute only existing metadata
   sequence/revision increments; no new fee/PnL/quantity/risk arithmetic.
4. Invoke one narrowly typed DB function for the consecutive persistence block.
5. Call existing `record_event` in Python after the batch. Its ownership and secret
   checks remain intact; return the original MatchingCheckpoint shape.

Add a versioned `paper_persist_checkpoint_v1` function through the next additive
migration after the verified migration head. Use PL/pgSQL, explicit VOLATILE,
SECURITY INVOKER, fixed safe search_path and schema-qualified objects. Revoke
PUBLIC execution and grant only ENGINE execution; add no table privileges,
roles, infrastructure, persistent caches or new business state. Do not use a
SECURITY DEFINER shortcut. Existing RLS, domains, constraints and triggers remain.

The function executes the existing statements sequentially, in their current order:
- Read the anchor order's next event sequence and INSERT the same decision event.
- Upsert this pair's projections and advance other active pairs' revisions using
  the current disjoint-row predicate; preserve historical terminal revisions.
- Upsert reservations and advance other active-pair reservation revisions using
  the current predicates, after projection changes are visible.
- Advance activity source_sequence/revision/observed_at, then wallet revision.

The current owner/episode/activity locks stay held through all of this and audit
until outer commit. Bind all arguments; do not construct SQL from payloads.
Validate owner/episode/pair/identity and expected metadata against the locked
source; mismatches fail closed and roll back, never silently skip/update another
owner. The function must not enable writer markers or acquire elevated authority
on behalf of an otherwise unauthorized caller. No commit, retry, fallback to an
unmigrated DB, new error-detail logging or new trade identity is introduced.

Retain sequential statement visibility and trigger behavior. A single large
data-modifying CTE is not substituted for these dependent writes: sibling writes
share a snapshot and do not read each other's changes through target-table reads.
The PostgreSQL16 references on [CTEs](https://www.postgresql.org/docs/16/sql-select.html),
[VOLATILE snapshots](https://www.postgresql.org/docs/16/xfunc-volatility.html) and
[invoker execution](https://www.postgresql.org/docs/16/sql-createfunction.html)
support this design; real-DB tests below must prove the actual repo's constraints
and routing/risk/protection triggers, not assume documentation alone proves it.

Migration up adds only the function/its narrow execute grant; down drops it without
rewriting financial history. Old code's direct SQL remains compatible after up.
New code requires the migration and fails closed if the function is missing;
deployment/rollback ordering must be documented. Do not bump existing writer
protocols or change table layout merely to claim a performance improvement.

## A2 / B — opt-in final-tail drain in the standalone harness

Current `_run` drains a captured watermark while publishing continues, then stops
the publisher and checks lag against its later final input. Preserve that initial
live-source recovery stage; add an explicit final-tail stage instead of relaxing20.

Add `--final-tail-drain`, default off, parent-only, requiring existing R8+heartbeat.
Approval here covers SMOKE only; no full W1 is implicitly authorized. Other harness
callers and the legacy default remain unchanged. Record the option and actual
storage/runtime/source identity in the manifest (new tail runtime identifier).

Within one original60s drain budget measured from the same drain start:
1. Capture W0 and run existing `wait_for_input_recovery` with publisher alive.
2. Request normal publisher stop; await its in-flight transaction and normal exit.
   Preserve any publisher error. Record committed final watermark H from the
   stopped publisher and verify it against the actual pair state using existing
   permitted market-data reads; an identity/generation mismatch fails closed.
3. Keep existing workers/resource sampler running. Reuse owner-scoped
   `wait_for_input_recovery` for minimum cursor `max(W0, H-20)`. Record W0/H,
   per-owner cursor/lag and stage timings. Retain the original READY predicate.
4. Only then stop workers and perform the original final financial/global/resource
   checks against the actual final head H. Final lag must still be<=20; all old
   pending-count/financial checks remain. No second60s budget, new connection pool,
   new DB grant, unbounded wait, false READY or incomplete owner denominator.

Heartbeat alone must not refresh book/price observations. Do not republish fake
fresh data after source stop or allow stale inputs to match. If remaining source
freshness or capacity cannot drain that tail under existing guards and the same
60s budget, fail and retain evidence. The gate makes shutdown verification explicit;
it does not guarantee passing or redefine the original lag criterion.

## Scope and reuse

- Production A only: `backend/src/tiewtrade/infra/paper_orders/matching_storage.py`,
  the next additive migration, existing matching-storage/checkpoint safety tests.
- A/B: `tests/infra/execution_market/profile_workload.py`, focused drain/config tests;
  reuse existing publisher/worker supervision, resource/oracle/diagnostic helpers
  and repaired atomic control publication without changing trace bounds.
- Reuse `test_bulk_checkpoint_preserves_other_pair_and_rebuilds_multiple_orders`,
  execution evidence/replay, worker/reset/correction/process-recovery and relevant
  protection/risk/writer-fence/rollback tests. Do not alter shared db sessions,
  role verification, admission/matching algorithms, clocks, locks, freshness, claim
  scheduling, exchange adapters or unrelated F18/F19 harnesses.
- Preserve Stateless/Multi-Instance architecture: DB transaction/locks remain the
  authority; add no process/global business cache, lock-proof cache or session data.

## Required validation and stop gates

1. Before production edits, capture small existing checkpoint fixtures and SQL
   statement-count evidence on the unchanged baseline. No timed workload. Pin
   source and inputs; preserve raw outputs. Do not copy the old implementation
   into a permanent second writer merely to compare it.
2. A: real PostgreSQL before/after semantic comparison covers decision identities,
   sequence/revision/payload/digest, all projection/reservation/other-pair rows,
   terminal history, wallet revision and typed audit facts. Only explicit DB-generated
   audit IDs/recording timestamps may vary; economic/event/input identities and
   business timestamps must not be normalized away. Verify fewer client calls
   (target11→6 on the representative checkpoint path), not mocked correctness.
3. A: injected failure after each internal write rolls back the whole batch and
   outer audit; test duplicate identity/commit-ack loss, retries without duplicate
   effects, reset/fill/correction races, two workers/same owner and owner isolation.
   Test row triggers/routing and F17 replacement/protection history. Missing function,
   wrong role/owner/episode, disabled writer marker and malformed values fail closed.
   Up/down/up preserves data and PUBLIC/API/MARKET_DATA/ENGINE_SCAN cannot execute it.
4. A/B drain tests force input arriving during recovery and during stop, slow owner,
   owner not READY, stale source, publisher failure, worker failure, cancellation,
   budget exhaustion and final-head mismatch. Enforce the same total60s and final20;
   verify no new NEW/retry, false success, source refresh or leaked task/connection.
5. Run affected targeted correctness/safety/static checks and scoped code review;
   expand if actual dependencies require it. No unrelated refactor. If equivalence,
   trigger order, authority or stop semantics cannot be proved, stop/report rather
   than implementing an alternative unapproved architecture.
6. Only after those gates: exactly one fresh diagnostic with100owners×20baseline,
   6cycles/owner,10commands/s,20workers, R8/heartbeat/final-tail and existing SMOKE
   plus180s trace. A uses the new migration/storage; B retains original storage.
   Verify all role URLs/actual DB/schema, freeze source/dataset/config and announce
   approximately10–15minutes plus any newly evidenced setup cost. Keep all financial,
   p95<=250ms/p99<=1s, cycle/drain60s, lag<=20 and resource predicates unchanged.
7. Stop/report afterward, including partial/failed results, observed processing
   and SQL/acquisition breakdown, gate watermark/tail evidence and cleanup. No
   further diagnostic/full W1/W2/W3, production activation, commit/push/merge is
   authorized. This instrumented run never closes full W1 acceptance.

W1 remains Failed/Partial, W2/W3NotRun, W4 and integrated coverage retain their
current statuses until dependencies justify revalidation. For A the changed
checkpoint writer invalidates affected W4 fixture/replay evidence and it must be
rechecked before relying on W4 for the new candidate; old evidence remains valid
only for the old writer. Do not mark F15/F17 Completed or assume CI approval.

## Implementation checkpoint — 2026-11-06

Implemented migration0065 (down_revision0064), PG_BATCH_V1 checkpoint storage and
opt-in F15_STANDALONE_R8_HEARTBEAT_TAIL_V1. Canonical Python decisions/audit,
owner/episode/activity locks, sequential trigger visibility and money rules remain.
Final cursor reads use bounded TaskGroup ownership and join on failure/cancellation.

Deployment ordering: apply0065 before deploying the new application. Old direct-SQL
writers remain compatible with0065. For rollback, deploy the old application first,
then optionally downgrade0065; dropping the function while the new writer runs fails
closed. The migration changes no stored financial rows and enables no Live mode.

Six pinned real-DB checkpoint snapshots match before/after, with client statements
11→6 per checkpoint. Only explicit generated recording metadata is normalized;
raw identities/business timestamps remain compared. Up/down/up, old writer on0065,
and missing-function rollback passed. Real-DB fault/authority/duplicate tests,
worker recovery/concurrency, TP/SL and risk regressions passed after scoped test-hook
repairs; initial failures and their resolutions are retained, not relabeled.
Final tail suite21passed; Ruff/format7files and scoped strict mypy8files passed.
Detailed case counts and evidence: `checkpoint-batch-checks-summary.json` in the
[Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md).

The one authorized fresh diagnostic started2026-11-06T07:30:55Z after empty0065 DB,
all8roles/function-source and350source-hash preflight. No further timed trial is
authorized. Full W1/W2/W3, affected new-writer W4, required CI and integrated profile
acceptance remain pending; old failures and old-writer W4 evidence remain intact.
