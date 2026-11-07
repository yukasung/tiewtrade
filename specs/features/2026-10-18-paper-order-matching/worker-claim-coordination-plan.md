# NC-SET4-10 — Coordinate selection and claim before parallel processing

สถานะ: **Approved A — opt-in implementation and targeted safety tests**
วันที่: 2026-11-06
ขอบเขต: opt-in Paper worker code and targeted safety validation only

## Decision requested

**A (recommended):** implement the bounded PostgreSQL coordination option below,
disabled by default, and run targeted correctness/concurrency/static checks. Then
stop/report. This authorizes changes in shared worker/session source, unlike the
NC09 harness-only change; it does not enable the option in deployed workers.

**B:** revise this proposal before implementation; retain current evidence/code.

No timed campaign,100-owner diagnostic, W1, deployment, production activation,
commit/push/merge or automatic follow-on experiment is included in either choice.
Passing safety tests will not establish a performance improvement. A later workload
needs its own concrete profile and approval after reviewing the implementation.

## Evidence and purpose

[NC09 follow-up](../2026-11-02-tp-sl/evidence/batch-20261106/README.md#nc09-follow-up--separate-processing-from-observation-delay)
found29370 measured claim calls,25457 skipped (86.68%). The timed-out cycle's four
command-result stages spent32.554s before handling,2.585s handling and3.367s from
handling completion to observed result. These are partial stages, not all cycle time.
The final read ended59.186s; a subsequent read queued until60.002s. Post-stop FILLED
and the last owner transaction ending59.723s suggest a final observation gap, but
do not provide an exact projection commit timestamp.

Current `run_paper_order_round` releases its scan transaction before attempting
owner-scoped claims. Multiple workers can therefore obtain overlapping candidate
lists. `claim_order` correctly rejects stale/busy candidates; R8's successful-claim
budget does not limit unsuccessful attempts. These are repeated attempts to claim
work, not evidence of duplicate orders/economic effects. Reducing this overhead is
a hypothesis worth testing, not an established fix for W1 or processing p95.

## Requirements and architecture boundary

F15 requirements remain Approved. No change to quantities, matching, FIFO within
an owner, fees, PnL, risk, liquidity, source freshness, money types or idempotency.
Owner explicitly approved A in the current conversation before implementation.
NC-SET4-10 is Closed / Approved A for this protocol and targeted safety stage only.
Prior R8/NC09 approvals alone did not authorize this change.

PostgreSQL remains the only authority for claims/business state. Use transaction
advisory coordination shared across processes, not an in-memory semaphore, static
owner partition, local cache, Redis or persistent worker membership. ENGINE_SCAN
continues to read hints only; all user mutations use ENGINE under owner RLS.
No migration, new grant, definer function or infrastructure is planned. If current
role/session contracts cannot support this protocol, stop and amend the proposal
rather than widening privileges. Record the approved coordination decision here.

## Approved protocol: SERIALIZED_CLAIM_V1

Add a strictly validated boolean option to `run_paper_order_round`, default false.
For this candidate, true requires `claim_limit=1`, `limit=20` and legacy R8 selection
(same-pair/admission-first/source-resumption options all false). Reject unsupported
combinations before opening a DB session. Existing callers remain unchanged.

1. Start a5s selection deadline **before** acquiring the scan connection. Open the
   existing ENGINE_SCAN session. Acquire a transaction advisory lock using one
   fixed namespaced key, `paper-order-selection:v1`, on that database. Use bounded
   blocking acquisition, not a try-lock/retry spin. Apply local5s statement/lock
   timeouts; the outer5s deadline covers the entire selection/claim section, not
   a fresh5s for each candidate. The new5s bound applies only to this opt-in path;
   it does not replace the existing60s cycle/drain or any trading timeout.
2. After obtaining the coordinator lock, run the unchanged `due_orders(limit=20)`
   legacy query. Keep the scan transaction open while trying those candidates in
   the returned order through existing, separate owner-scoped ENGINE transactions.
   Reuse the existing statement/lock guards and `claim_order`; do not copy/rewrite
   its owner try-lock, due-version CAS, SKIP LOCKED, lease or claim-token checks.
3. A None claim advances to the next returned candidate within the same deadline.
   A non-None claim consumes the one-success budget **before commit**, as today.
   Retain the coordinator until the owner transaction's commit/cleanup finishes.
   Never try another candidate after an ambiguous commit/error. A failed gate
   acquisition is not a skipped command and must not inflate the skipped counter.
4. Exit the scan transaction/release the coordinator **before** processing,
   deferral, reconciliation or sleep. Then use the existing processing/error paths
   exactly once for the claimed command. Other workers may select another owner
   while this one's processing runs; processing is not globally serialized.
5. Gate/selection timeout or infrastructure failure propagates to the diagnostic
   supervisor; no silent fallback to the legacy selector, extra command submission,
   or immediate retry loop. Preserve primary errors on cleanup. If a claim committed
   but processing never started, retain the existing DB lease/fencing recovery;
   do not erase a claim or invent a success result.

The gate is an efficiency aid, not a safety lock: existing owner/claim fences must
remain sufficient if a scan connection drops, a worker crashes or a legacy worker
ignores the new gate. Lost coordinator connection can allow another scanner in;
it must never permit two valid writers for an owner. Mixed versions may still do
redundant work. No exactly-once claim-acquisition or worker-lock fairness promise.

No candidate reordering, earlier due timestamp, admission-priority activation,
global lease extension or new owner starvation rule. Existing owner fairness tests
must pass. The coordinator may reduce throughput or accumulate waiters; no claim
that it can sustain10 commands/sec is made before later workload validation.

## Reuse and file scope

| Existing path | Planned use/change |
|---|---|
| `backend/src/tiewtrade/infra/paper_orders/dispatch.py` | Reuse `due_orders`, `claim_order`; add a small ScanSession-only helper for coordinator SQL. No alteration of claim predicates or financial functions. |
| `backend/src/tiewtrade/services/engine/paper_order.py` | Add default-off selection option and share the existing per-candidate claim routine where needed. Keep a single processing/error/reconciliation path; avoid copying the whole worker loop. |
| `backend/src/tiewtrade/infra/db/session.py` | Forward an optional bounded-cleanup argument through existing user/scan session wrappers to `_begin`; default behavior unchanged. Opt-in selector uses existing2s `_bounded_cleanup` machinery, not a second connection-abort implementation. Validate the optional bound before checkout. |
| `backend/tests/infra/execution_market/test_dispatch.py` | Reuse intent/submit helpers and real-DB stale-hint, owner isolation, lease/fence and FIFO tests. |
| `backend/tests/infra/execution_market/test_worker.py`, `commit_proxy.py` | Reuse real processing/financial/reset/replay tests and `drop_commit_reply` fault injection. |
| `backend/tests/infra/risk_limits/test_worker_rounds.py` | Preserve default production/F18 call contracts and successful-claim budget behavior. |
| `backend/tests/infra/execution_market/test_claim_coordination.py` (new) | Only new protocol risks not already covered, including independent connections/processes. Reuse fixtures; no parallel implementation of claiming. |
| `backend/tests/infra/execution_market/test_claim_coordination_financial.py` (new) | Invoke existing financial oracles unchanged through the opt-in service boundary; keep this adapter separate from selector/barrier tests. |
| Existing DB session cleanup tests | Default contract plus opt-in cancellation, primary-error preservation and connection quarantine. Locate/reuse matching cases before adding tests. |

Expose the option initially only at the shared Python service boundary for tests.
Do not add environment toggles, production-main settings, parent/worker CLI plumbing,
or alter NC09 polling. Runtime activation and manifest integration are a later plan.
No change to matching_storage, migration0065, routing SQL or user-facing UI.

The5s operation deadline excludes necessary cleanup: each nested connection uses
the existing2s cleanup bound and quarantine/abort behavior. Report operation timeout
and cleanup separately; do not claim a hard5s wall duration. No detached task or
unchecked still-held coordinator may remain when a test/report finishes.

## Targeted validation — Feature safety before any performance experiment

All cases below are **Feature** checks; current Batch/Release acceptance stays
Pending Full Validation. Use fresh isolated PostgreSQL and the existing role
bootstrap. Never reuse a dirty workload DB for correctness assertions.

1. Default false is behaviorally identical: current scan/claim/processing call
   order, R8 budget, F18/production flags, error handling and maintenance. Invalid
   combinations fail before DB work. No new SQL or gate in default mode.
2. Real concurrent selector calls with a controlled barrier: at most one gated
   scan/claim section at a time; each successful claim consumes its budget before
   commit. Next scanner sees the committed busy owner, not a pre-gate snapshot.
   Check READ COMMITTED behavior explicitly, including prewarmed pooled sessions.
3. Deterministic collision regression using the same fixture: two workers and
   two eligible owners. The controlled legacy case can share stale hints; the gated
   case must avoid that specific stale duplicate attempt. Keep default behavior
   valid; do not turn a timing race into a flaky probability-based assertion.
4. Multiple owners and two queued commands/owner: preserve existing due/FIFO
   selection and fairness; an unclaimable owner must not prevent later candidates
   within the existing20 bound. Hold processing with a barrier to prove another
   owner starts processing concurrently after the coordinator is released.
5. Two independent worker processes, not just asyncio tasks, share the PG gate.
   Gate-acquisition cancellation, processing cancellation and termination before/
   after claim commit release/quarantine their connections. DB advisory locks,
   checkouts and child tasks/processes return to zero after cleanup.
6. Lost commit reply, scan-connection failure, owner-connection failure, deadline
   expiry while queued/holding the gate and cleanup failures: no second claim in
   the uncertain round, no fabricated completion, primary error retained. Existing
   lease expiry and fencing recover with one valid writer. Include a gated plus
   legacy-worker race to prove financial correctness does not depend on the gate.
7. Real processing under the new option: reuse acceptance/fill/cancel/replay,
   two-orders/one-balance, reset/correction and conflict cases affected by the shared
   orchestration. Money/Quantity, reservation/cash/position consistency and duplicate
   economic effects assertions unchanged. Scanner still cannot write owner data.
8. Scoped Ruff/format/mypy, architecture/import checks for touched layers and DB
   session regressions. Confirm all result exits before claiming this stage passed.
   No full regression unless the resulting diff exposes broader unresolved risk.

Use normal bounded test timeouts and deterministic synchronization. These tests
prove protocol safety and a specific collision reduction, **not production speed**.
Do not add a timed benchmark, throughput target or full-diagnostic run to this scope.

## Keep processing and observation evidence distinct

Future workload reporting must separately identify submission return, processing
transaction interval and parent observation using stable command/owner IDs. Include
final projection waits, gate waits and cancelled attempts. Transaction return is
not the exact DB commit instant; event/source timestamps are not commit timestamps.
Where a fixture does not capture a transition's commit visibility, report unknown
instead of attributing it to worker or polling. Do not subtract overlapping waits,
extend cycle budgets or promote post-stop FILLED to on-time acceptance.

Retain60s progress/drain,250ms p95/1s p99, offered/completed denominators and every
financial criterion. This plan adds no metrics migration or production audit schema.

## Checkpoint and remaining risks

After implementation and the targeted checks above, record diff, outcomes, failures,
cleanup and any unproven case, then stop/report. Do not run W1 or another diagnostic.
This is a subtask, not whole-feature Ready for Code Review or completion.

Main risks: serialized selector bottleneck, longer-lived scan connection, lock wait
under load, ambiguous cross-connection failures, interaction with mixed workers and
fairness. Safety tests cannot settle throughput; a subsequent small comparison plan
must measure gate wait + successful claims + failed attempts + end-to-end progress,
not merely a lower skipped percentage. If implementation requires different scope,
privileges, selection semantics or cleanup architecture, stop for an amendment.

Prior NC09 Incomplete/cycle Failed, W1 Failed/Partial, W2/W3 Not Run,0065 W4 Pending
Revalidation and integrated NC-SET4-01 remain. No earlier result is overwritten.

## Execution checkpoint — targeted safety passed

Implemented `coordinate_claims=False` at the Python service boundary. Three existing
source files changed: dispatch's ScanSession-only coordinator, shared worker
selection/common claim routine, and optional cleanup forwarding in user/scan sessions.
Claim predicates, matching/storage, migration0065, production main and harness
runtime flags are unchanged. The new option is not enabled anywhere by default.

**94 distinct targeted tests passed**, using85 successful cases from the combined
run and9 previously setup-blocked regressions rerun successfully. The combined
command revisited one package after unrelated paths and lost fixture discovery;
contiguous same-package ordering passes `--setup-plan`. That setup check is not
counted as test execution. Initial test-only cleanup/proxy configuration and adapter
coverage issues were corrected; old logs retained. No correctness assertion lowered.

Ruff/format/mypy passed for all5 affected Python files; final test import changes
rechecked. All7 import-linter contracts kept. Real PostgreSQL and two child processes
cover coordination, simultaneous processing, mixed legacy workers, cancellation,
connection loss and ambiguous commit recovery. Existing financial oracles cover
fill/restart/replay/cancel, projection/commit failures, reset, conflict and balances.
The direct admission/reset oracle is a separate unchanged regression because it
does not call the round orchestration. Existing bounded-cleanup tests reused.

Two scratch DBs retained with0 connections and0 advisory locks; no child processes
remain. Checked pre-existing source changes are exactly the3 approved files.
See [Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md#nc-set4-10--opt-in-implementation-and-targeted-safety-passed)
and `claim-coordination-checks-summary.json` for candidate hashes and per-case evidence.

Implementation/safety checkpoint reached; stop/report. Performance and production
activation are **Not Run**. Next recommended step is code review scoped to NC10
before planning a comparison; await owner review command. No additional runtime
validation, refactor, diagnostic, W1 or Git publication is implied by this checkpoint.

## Follow-up review under the owner's consolidated completion request

NC10 scoped review is complete. One Medium coverage gap was found: scan connection
loss was tested before claiming, but not a lost coordinator COMMIT reply after the
owner claim had committed. Parameterized the existing commit-loss/recovery test for
both owner and scan connections, without duplicating its oracle. Both pass on real
PostgreSQL: one claim, no processing, released coordinator/pools and fenced recovery.
No production defect was established and no production code changed in this follow-up.

Changed-test Ruff/format/mypy passed;48 existing F-17 integration cases passed on
fresh0065. Prior94-case evidence is retained, plus the new coordinator-commit case;
this is cumulative coverage, not a new all-green95-case combined command.
The broad request authorizes this review/fix and already defined validation work;
it does not define the missing NC-SET4-01 acceptance parameters. See the
[consolidated Paper proposal](../2026-11-02-tp-sl/integrated-paper-acceptance-plan.md).
Performance remains unproved and activation remains off.


## Superseding acquisition policy — NC-SET4-11 Approved A

After the two failed V1 diagnostics, the owner explicitly approved
[NC-SET4-11](worker-claim-contention-amendment.md) on2026-11-06. Its V2 policy
replaces only the blocking acquisition/busy behavior for the default-off option.
The V1 protocol and failures above remain historical evidence. Actual exceptions,
owner claims, lease/fencing, selection order and all financial rules are unchanged.
