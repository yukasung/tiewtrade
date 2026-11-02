# NC-F19-19 — bounded rolling monitor admission

Owner approved `approve NC-F19-19` on 2026-11-02. Base `2322d86541a5ef68ef41e86f7f3ec9e6778e0fba`;
working branch `validation/f-19-set5`. No Git/deployment authorization is implied.

## Implementation

- `services/engine/risk_limit.py`: shared internal candidate scan and owner evaluation.
  Active owners are excluded by bound UUID-array predicate before LIMIT. Original
  Paper eligibility, hint/cursor order and due priority within a selected batch remain.
- `services/engine/risk_limit_main.py`: at most four local evaluation tasks. Select
  only free slots, refill after FIRST_COMPLETED, preserve UUID cursor before due sort,
  poll 20ms when no candidate, propagate failures, cancel/join tasks before pool disposal.
- Local task map/cursor are disposable scheduling state. Database/RLS/advisory locks
  remain authoritative across instances/restarts; no business/session cache or new infrastructure.
- Legacy round API/signature/results remain. The extracted authoritative transaction
  and exception body is AST-identical to the old nested evaluator (verified against HEAD).
  No API/schema/trading calculation, pool/resource bound, retry or risk threshold changes.
- Harness manifest identifies rolling admission. Bounded scheduler counters record
  actual scan/selection/in-flight/outcomes/cleanup without per-owner retained history or extra SQL.
  Scoped NC18 observer records rolling turn/owner linkage and fails if selection is missing.

## Targeted evidence

Artifacts in `validation-artifacts/f19-set5-20261101/`:

| Run | Result | Scope |
|---|---|---|
| `nc19-targeted.xml` | 35 passed, 13.107s, zero skips | Initial scheduler, real DB exclusion/lock/rollback/cancel and observer tests |
| `nc19-regression.xml` | **95 passed, 1 failed**, 46.312s, zero skips | Monitor/snapshot/replay/matching fence, partial barrier, concurrency, boundaries |
| `nc19-safety.xml` | 26 passed, 19.797s, zero skips | Fresh-DB concurrency, pending-source intake and stop financial safety |
| `nc19-linux.xml` | 43 passed, 1.864s, zero skips among selected tests | Linux observer, CLI and scheduler tests; four fresh-global tests were **deselected**, not exercised here |
| `nc19-preflight.xml` | 4 passed, 26.591s, zero skips | Explicit fresh-global Linux real-worker overlap/partial-stop/restore matrix |
| `nc19-final-targeted.xml` | 9 passed, 0.588s, zero skips | Newly eligible work during slow peer, failure/cleanup/fairness and setting disappearing after selection |

The regression failure was
`test_stop_and_in_flight_fill_serialize_without_duplicate_money_or_cancel[True]`:
`NoResultFound` reading its own `trading_stop_results`, **before** the in-flight fill/cancel
race. The fixture invokes one globally bounded stop round (limit20) and assumes its new
request is included. Reusing the earlier targeted DB plus new breach fixtures accumulated
more than20 older requests. A subsequent round from the next parameter processed the
missing receipt: both last USER_REQUEST receipts ended APPLIED; no pending request remained.
Production stop bounds and test assertions were not changed. The entire concurrency module
then passed on a freshly migrated database, together with pending-source and financial stop
regressions (`nc19-safety.*`). This changes test state intentionally after diagnosing the branch;
it is not an unchanged workload rerun hoping for a pass. The failed result is retained.

Ruff/check and format pass on seven changed Python files. Mypy passes on the same seven,
including newly typed test callbacks. `lint-imports`: seven contracts kept, zero broken.

## Preflight selection correction

The first Linux command inherited pytest's default `not fresh_global_state` marker.
Inspection of its JUnit count revealed that the intended real-worker matrix was absent.
The initial W1 invocation (`nc19-w1-r1`) was explicitly stopped during setup (baseline3/20),
before any measured load phase. Preserve it as **ABORTED_SETUP**, acceptance false,
not a completed W1 or an SLA pass/failure. It exited137 from operator termination,
not OOM. `phases.jsonl` contains only setup; `preflight-abort.json` records why.
No runtime/threshold change was made in response.

The missing four tests passed on a separate newly migrated DB using explicit
`-m fresh_global_state` before the single measured W1 acceptance invocation (`nc19-w1-r2`).
The candidate backend source/harness tree hash is
`78057f30fd2c13b13c6584120011b7e4586edf6016fd994545ea209377f5e53a`.
`nc19-measured-candidate-files.json` inventories the frozen files. Docker VM 3,043,373,056
bytes/8 CPUs and PostgreSQL 4 CPUs/3GiB match the approved inventory.

Post-run inspection of targeted DB breach/audit identities (`nc19-analysis/targeted-audit-proof.json`)
found 27 breach events, each with exactly one matching `RISK_LIMIT_BREACHED` audit identity;
zero missing or duplicate audit matches. This complements the two-instance rollback/cancel checks.

## W1 / next gate

W1 invocation Failed during setup; environment invalid as detailed below. V-20 retains Failed / Pending Full Validation;
previous NC17 Failed evidence is not overwritten. W2/W3/W4 do not start until W1 passes.

## Final checkpoint — W1 Failed / environment invalid

`nc19-w1-r2` ran 09:25:01–09:28:55 Bangkok, exiting1 (not OOM). Setup progressed
through core100×20 baseline and the dedicated LOSS_LIMIT partial fill→stop effects
complete→RESET (attempt1 APPLIED)→opening blocked. The **later BOT resting order setup**
failed, not the earlier LOSS_LIMIT scenario. There is no load phase in `phases.jsonl`,
all measured counters are0, and no600s risk-SLA conclusion can be drawn.

The launcher created `tiewtrade_f18_release_set5_nc19_w1_r2` but all nine database URLs
still referenced `tiewtrade_f18_release_set5_nc19_preflight`. The preflight launcher had
rewritten the shared temporary Linux env file; the later launcher attempted string
replacement of its former database name, which no longer matched. It did not assert
the actual connected identities. `database-inventory-mismatch.json` records the exact
role inventory. The intended database remained empty (dump6,135bytes); the **actual**
preflight database dump is13,806,019bytes. Both dumps and SHA256 are retained.
This is an execution/configuration error in this checkpoint. **Do not attribute the
rejection to the old database as a proven cause**, or treat it as proof that rolling
admission improves/worsens acceptance latency. This run is unsuitable for acceptance.

The actual failure identity (`nc19-analysis/failed-bot-command.json`):

- Owner `ee5153af-eb1a-49be-8d39-c96409bf65f8`, order
  `7c93f05b-7329-552f-a5d3-0978cc558d31`, NEW/BOT command
  `a403d12f-c73f-437f-b473-da6d5e04b456`.
- Readiness hint02:28:52.965749UTC: READY, cursor3191, publication3233 (lag42), pendingfalse.
  This is a read-only hint, not authorization of the later transaction.
- Command requested02:28:52.989782UTC; terminal REJECTED at02:28:53.964750UTC,
  `RISK_SOURCE_UNAVAILABLE` (0.974968s). No order event was created for it.
- Monitor observation02:28:53.754329UTC records cursor3291/pendingtrue; paper observation
 02:28:54.051290UTC records3391/pendingtrue. Final durable owner/evaluation state is
  pendingtrue, reasonSOURCE_UNAVAILABLE, cursor3391 vs publication3485.
  This supports pending replay in the window, **not an exact transaction-level proof**
  of which budget/evidence branch rejected the command. No stage/TX linkage was enabled
  for this acceptance attempt; missing evidence is explicit. Do not select another
  production fix or introduce NEW retries from this correlation.

Actual scheduler inventory:11,349 scans,13,743 selected owner attempts, max selected4,
max in-flight4;13,470processed/270deferred/3cancelled/0unexpectedfailed, active0 atclose.
All13 pool files finalized with checked_out0, remaining actual-DB connections0.
Partial safety snapshot: duplicate fill identities0, negative position/reservation0,
failed BOT order events0. These are partial checks, not full financial/resource acceptance.
69 original run files are hashed in `nc19-analysis/raw-sha256.json`.

## Concrete correction and next approval

Prepared `validation-artifacts/f19-set5-20261101/nc19-analysis/runner_database_guard.py`:

1. Construct each role URL with parsed URL path replacement; never mutate the source env.
2. Require all9role URLs and the explicit database marker to match the intended disposable DB.
3. Before migration, connect through **every** role and assert `current_database()` matches;
   migrator also requires zero public tables. Abort on any mismatch/non-fresh schema.
4. Use a new output/DB/env file and store safe connected role/database identities.
   Keep credentials only in mode0600 files; do not print them.

Self-test passed: all paths rewritten, source unchanged, mixed-database config rejected.
Real read-only verification through all9roles passed against the still-empty intended DB
(`runner-guard-verification.json`), including freshness. No workload was run by these checks.
The existing scheduler candidate/runtime and acceptance criteria remain unchanged.

**Needs Clarification / stop:** NC19 acceptance failed and the approved plan says stop
on failure. Request authorization for **one replacement W1 on a verified fresh DB using
this guard**, keeping all criteria/resources and preserving both earlier attempts.
No W1 rerun/W2/W3/W4, additional production edits, commit/push or deployment has followed
this checkpoint. V-20 remains Failed / Pending Full Validation; V-21..24 Pending Dependency.

## Subsequent authorized replacement

Owner approved `approve W1 fresh DB rerun`; `nc19-w1-r3` now verifies all nine actual
connections and the empty fresh fixture before load. Setup passed; W1 **Failed** at
recorded+37.594s because the child BOOK publisher raised SourceUnavailableError.
The earlier invalid-DB issue is not reused as an explanation of this valid fresh run.
Single-recorder wall-time reversal is confirmed near the failure, but missing guard
arguments prevent an exact causal proof. No additional production changes or reruns.
See [fresh rerun report](w1-fresh-rerun-2026-11-02.md) and proposed NC-F19-20 for next scope.
