# NC-SET4-11 — Nonblocking claim coordination proposal

สถานะ: **Approved A — Owner approved 2026-11-06**
วันที่: 2026-11-06

## Decision and evidence

The approved consolidated Paper campaign reached its diagnostic gate and failed.
The second run completed baseline2000, then188/600 cycles and1091/3000 commands
before a60.001s cycle timeout. Eighteen of20 worker processes exited after the5s
selection deadline:14 while acquiring the coordinator,1 scanning and3 entering
owner transaction setup. The exits occurred142–146s into measurement; processing
p95 was already311.9ms during the first60s, above250ms. Eliminating worker exits
alone is therefore **not a demonstrated fix for latency or the full workload**.

The observed claim-skip ratio was21/3470 (0.605%), but serialization and accumulated
waits remained. The largest measured coordinator-held interval was2.946s, including
commit acknowledgement/cleanup. It does not identify an exact server lock release.
Raw evidence, partial denominators and limitations are in the
[Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md).

The proposed change conflicts with NC10's explicit requirement to use blocking
acquisition rather than a try-lock. NC10 also requires selection failures to
propagate. The consolidated approval permits fixes within the approved protocol,
but stops for a new architecture/protocol decision. Owner explicitly approved A in the conversation on2026-11-06 before implementation.
This approval replaces only the V1 acquisition policy specified below.

## Option A — replace only the opt-in acquisition policy

Revise the default-off coordinator to `SERIALIZED_CLAIM_V2`:

1. Keep the existing PostgreSQL transaction advisory key, ENGINE_SCAN role,
   READ COMMITTED requirement,5s operation deadline and2s connection cleanup bound.
   Replace blocking acquisition with one `pg_try_advisory_xact_lock` call per round.
   The same key preserves exclusion with V1 workers. No process-local ownership,
   Redis, new table, grants, migration or persistent membership.
2. A returned **false** means busy, not an exception or a successful claim. Run no
   due-order query or owner claim in that round. Release the scan transaction and
   connection before a fixed250ms cooperative backoff. Keep this busy outcome
   distinct from skipped commands, rejected orders and processing success. Preserve
   existing maintenance calls and the ordinary worker-loop sleep; do not add an
   inner retry loop. Backoff time remains inside end-to-end acceptance time.
3. A returned **true** uses the unchanged due-order query and existing owner claim
   sequence, one successful claim maximum, same lease/CAS/fencing, same hold through
   owner commit/cleanup, release before processing. No reordering or priority change.
4. A timeout, cancellation, SQL/connection failure or ambiguous commit still
   propagates. **Do not catch TimeoutError and assume no claim happened.** Never
   retry a claim after an uncertain result. Existing lease recovery remains the
   authority. Only the explicit false result permits the normal next worker round.
5. Keep `coordinate_claims=False` by default. Update only opt-in harness metadata
   and observations to name V2 and count busy outcomes separately. Preserve V1
   source/evidence before changing it. Do not enable production or Live execution.

250ms is a proposed scheduler parameter, not a relaxed acceptance threshold.
Nonblocking acquisition may increase SQL attempts or reduce fairness; it does not
promise throughput. Do not tune that parameter silently after observing a failure.
Keep workload sizes,60s progress/drain,p95<=250ms,p99<=1s and every financial rule.

## Reuse and scoped files

- `backend/src/tiewtrade/infra/paper_orders/dispatch.py`: adapt the existing gate
  helper; reuse its session/isolation checks and advisory namespace. No claim SQL
  or financial storage changes.
- `backend/src/tiewtrade/services/engine/paper_order.py`: reuse the current selector
  and single processing path; handle the explicit busy outcome after DB cleanup.
  Preserve default callers and maintenance behavior. No second worker framework.
- `backend/tests/infra/execution_market/profile_workload.py`, `profile_diagnostics.py`
  and `backend/tests/infra/risk_limits/profile_dispatch_timing.py`: reuse flag,
  restart propagation and recorder paths. Gate hold begins only after true; false
  acquisition has a busy count and no hold interval. Ensure failure summaries
  retain actual child exits instead of relying on the success-only list.
- Reuse `test_claim_coordination.py`, `test_claim_coordination_financial.py`,
  `test_standalone_runtime.py` and `test_profile_diagnostics.py`. No copied financial
  oracle or unrelated refactor.

## Validation before any campaign

1. Real DB/process contention: one holder, another returns busy with no due scan,
   owner claim or economic effect; connection/gate released before backoff. After
   holder release a normal later round can claim. Include same-key V1/V2 exclusion.
2. Preserve one-success budget, FIFO/owner isolation, concurrent processing,
   mixed legacy workers, RLS and deterministic existing financial tests.
3. Preserve cancellation/deadline, lost connection, owner and scan COMMIT reply
   loss, no second claim and lease/fencing recovery. Busy is never inferred from
   an exception, including failure while closing an otherwise busy transaction.
4. Cancel during backoff: no active DB connection or detached task. Default false
   makes no gate/backoff calls. Invalid options and every restart preserve flags.
5. Observer tests distinguish busy/held/failed attempts; setup failure evidence
   survives. Record child failures on exceptional parent exits. Run scoped static
   checks and affected safety tests, and review the final diff before timing.

## Conditional continuation and checkpoint

Under approved A, implement/test/review/fix the scoped change continuously, then
run the same one diagnostic on a new empty DB:100 owners×20 baseline,6 cycles/owner,
3000 commands at10/s,20 workers,5-minute measurement,20-minute whole-run cap.
Allow approximately10–15 minutes including preparation, after development/tests.

Only complete passing financial, latency, progress, resource and final-tail
evidence permits the already approved integrated plan to advance to W1, W2, W3
and extended W4. Those later phases still require their HTTP/snapshot/restore
harness and tests. No routine subtask approval is needed within the approved scope.
On diagnostic failure, analyze and report; no automatic same-candidate repetition.
Stop for new protocol/business decisions or the existing three-round rule.

This addresses a demonstrated contention failure mode. The earlier processing
latency remains a separate acceptance risk and may still block progression.
Preserve both failed coordinated runs. F-17 V19/V20 dependencies, final candidate
CI and explicit Git permissions remain unchanged; no Completed claim is authorized.

**A (selected/approved):** this narrow protocol amendment and conditional work.

**B:** retain V1 and stop timed work; revise the next approach before source changes.


## Implementation and safety checkpoint

Owner A recorded before changes; nine V1 source/test files archived with SHA256
under the Batch ledger's `nc11-v1-source/`. V2 changes two production files only:
`dispatch.py` returns the PostgreSQL try-lock result; `paper_order.py` backs off
250ms only after an explicit false and successful transaction/connection cleanup.
Busy rounds preserve maintenance and the ordinary worker tick. No exception is
converted to busy. Gate key/roles, financial predicates and defaults are unchanged.

Harness metadata identifies V2, records acquired/busy separately and holds only
on true. Parent failure evidence now includes child exits after cleanup, including
exceptional parent paths. Final evidence-write errors retain the primary exception
and occur after engine disposal. Reused the existing recorder and worker lifecycle.

135 targeted tests passed in23.715s JUnit time on a new isolated0065 PostgreSQL DB,
including independent V1-holder/V2-worker processes, busy cancellation/cleanup,
scan COMMIT loss while busy, owner/coordinator ambiguous commits, unchanged
financial oracles, default caller regression and observations. Initial lint import
ordering and test-only mypy module-export access were corrected; final Ruff/format/
mypy passed for seven affected files and all seven import contracts passed.
Scoped final review found no remaining correctness/security/architecture issue in
this diff. PostgreSQL remains the shared authority; transient local observations
are not business state. No extra refactor was needed after the scoped cleanup.

The one approved diagnostic has started. Safety evidence does not establish
performance or completion. Later integrated phases remain conditional on its full
financial, latency, progress, resource and final-tail checks.


## Diagnostic result and stop/report checkpoint

The one approved diagnostic is **Incomplete / setup Failed** after165.058s.
Only3 complete baseline batches were observed;400 commands submitted and394
orders/results succeeded of2000 required. Measured offered/completed/cycles0.
Parent stopped on `WriterLeaseLost` in `renew_book_writer`'s first locked check.
Post-stop source owner/generation/input279 match the last successful publisher;
its lease expiry is consistent with that guard failure. Maximum successful
publication duration5.054753s is recorded, but not attached to a particular tick.
Do not claim that it was exactly the last transaction or identify its slow SQL.

7297 gate calls returned2092 acquired and5205 busy; no gate-acquisition timeout
stack was observed. One worker still hit the selection deadline in claim SQL;
another required SIGTERM during parent shutdown. Setup-only processing2082
samples hadp95=684.110ms/p99=1487.134ms. These are not measured-workload results.
No full financial/final-tail/input-lag/resource acceptance was reached.

All21 pool reports finalized with0 checkouts,20 dispatch/21 transaction streams
closed, all parent/worker processes stopped and DB connections/advisory locks0.
Limited post-stop invariants are zero; full financial acceptance remains unproved.
837 source/lock/config hashes unchanged during execution. Both old V1 failures
remain intact; this V2 run is separate. No threshold, lease duration, publication
rules, production activation or Git state was changed after the run.

Approved checkpoint reached: analyze and report, no repeat or W1. The remaining
cause is **which publisher/DB/commit/scheduling stage consumed the lease window**.
Existing baseline transaction files retain counters only, so that cause cannot be
reconstructed from this run. Next recommended work is a scoped baseline publisher
trace plan with bounded retained timings before another campaign. A new timed run
requires owner approval; the current one-run permission is consumed. Later integrated
phases and F-17 Release dependencies remain unchanged.


## Approved follow-up — baseline publisher timing

Owner approved the recommended next step after the NC11 report. This authorizes
harness-only timing from source acquisition and baseline publication, followed by
one unchanged diagnostic after safety passes. Reuse `TransactionTrace`,
`parent_observations`, `generator_operation` and the existing parent runtime observer;
no production source, lease, SQL, pool, workload or acceptance change.

The explicit coordinated SMOKE diagnostic captures only publisher/source acquisition
transactions before the existing measurement control starts. Retain monotonic
connection acquisition (including connection/pre-ping), query fingerprints/durations,
body and transaction-finalization duration (commit/rollback plus connection cleanup),
and publication tick/book identity. These client timings do not separate server CPU,
server lock wait, network and scheduler delay; finalization is not pure commit time.
Do not serialize SQL, bound parameters, credentials or exception text. Bound transaction
records at the existing100000 cap and per-publisher query detail at64; truncation fails.
Default observers and worker trace activation remain unchanged. Exceptions/cancellation
and cleanup must retain their existing behavior. Verify with real-DB contention,
controlled delayed finalization and default/opt-in/redaction/cancellation tests.

Run once on a fresh0065 database:100 owners ×20 baseline orders,600 measured cycles /
3000 commands,20 workers,10 commands/s, R8 claim1, V2 coordination, per-book heartbeat,
parent poll4 and final-tail drain. Approximately10–15minutes,20-minute cap; existing
60s cycle/drain and financial/p95/p99/resource gates unchanged. Stop/report if it fails;
only passing gates permit previously approved integrated continuation. No Git publication.

Recovery note: the previous temporary worktree and raw artifacts were lost. Recovered
source is revalidated before this follow-up; historical results above remain narrative
records, not newly verified evidence. See the Batch ledger recovery notice.

Follow-up checkpoint: source recovery/safety passed; the one publisher diagnostic
finished566.039s Incomplete at a60.002s measured cycle timeout (917/3000 commands,
145/600 cycles), with partial measured worker p95=470.510ms. No publisher lease loss
or worker exit reproduced; full financial/tail acceptance not reached. All resources
closed, source hashes stable. Stop/report; next runtime-fix plan requires a concrete
reviewed change. [Current evidence](../2026-11-02-tp-sl/evidence/recovery-20261106/README.md).
