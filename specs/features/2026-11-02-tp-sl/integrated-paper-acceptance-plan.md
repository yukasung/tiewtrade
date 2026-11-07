# F-17 — Consolidated Paper acceptance proposal

สถานะ: **Approved A — Owner approved consolidated Paper profile 2026-11-06**; **NC-SET4-12 Approved A - separate internal checkpoint**
วันที่: 2026-11-06

## Purpose and completion boundary

The owner requested continuous work to close F-17. Review and already specified
checks can continue under that instruction. It does not supply the missing workload
size/resource budget of F-14 V-17 or the integrated profile required by F-16 V-20.
This document makes those choices concrete before implementing their harness.

The owner explicitly approved option A in the conversation. This permits the Paper campaign below, including its harness,
targeted tests, review/fixes, necessary refactoring and conditional progression
between phases. It replaces one-experiment-at-a-time checkpoints for this campaign.
It does not lower criteria, enable production/Live, authorize new trading rules,
or mark an unexecuted phase Passed. Stop for a new requirement/architecture gap,
unsafe financial result, or three unsuccessful fix/check rounds of one criterion.

Passing this campaign can close F-17 V-18. **F-17 remains Development Complete /
Pending Release Validation** until V-19 and V-20 pass after F-20/F-21/notification
and F-22–F-24 dependencies exist. Those features are currently Planned. This plan
does not remove or transfer those gates, or authorize building unspecified features.
Git publication and merge still require explicit owner instructions.

## Fixed candidate and reused components

- Start from the current `validation/paper-set-4-20261106` candidate, including
  migration0065 and the reviewed default-off NC10 selector. Record source hashes,
  Python3.12/frozen lockfile, PostgreSQL16, role/database identities and resources.
- Reuse `backend/tests/infra/execution_market/profile_workload.py` for the F-15
  fixture, five-command cycles, offered-load schedule, financial oracle and faults.
  Reuse its parent polling limit4, separate heartbeat, final-tail and bounded cleanup.
- Add a strict harness-only option forwarding `coordinate_claims=True` to the
  existing worker service. Require R8 `limit=20/claim_limit=1`; forward on initial
  launch and every restart. Record the selected protocol in each process manifest.
  Production defaults and trading/selection rules remain unchanged.
- Reuse F-16 API/intake/bridge composition and fixtures in
  `backend/tests/infra/manual_orders/` and `backend/tests/api/`. Reuse the intake/
  policy composition in `backend/tests/infra/risk_limits/profile_workload.py`;
  that harness calls intake directly, so the approved HTTP boundary must use the
  existing API fixtures rather than claiming that direct intake is HTTP coverage.
  Do not copy the shorter
  F-18 phase durations into this campaign. Use actual authentication/CSRF, owner
  sessions, intake, bridge and the existing transactional Paper risk policy.
- Reuse F-14 position replay/snapshot functions and tests in
  `backend/tests/infra/positions/`, and F-15 `profile_restore.py` financial digests.
- Reuse F-17 `backend/tests/infra/protections/` and the existing browser command
  `npm run test:e2e:protections`; add only evidence missing from these suites.

## Unchanged F-15 baseline and acceptance

All F-15 validation section6 financial, precision, rate, resource, latency and
fault criteria remain binding. A diagnostic is never a substitute for W1–W4.

| Phase | Workload | Measured duration |
|---|---|---|
| Diagnostic |100 owners ×20 baseline orders,6 cycles/owner,3000 commands,10/s,20 workers; same NC09 fixture plus NC10 coordination |5 minutes;20-minute whole-run cap |
| W1 |100 owners ×20 baseline orders,36 cycles/owner,18000 commands,10/s |30 minutes |
| W2 |Same baseline,120 cycles/owner,60000 commands,100/s; separate existing overflow/slow-consumer phase |10 minutes plus fault phase |
| W3 |100 owners ×20 baseline orders,10/s outside the existing pinned fault windows; predeclared per-owner cycle counts |4 continuous hours |
| W4 |Existing real capital/fill/partial/cancel/correction/reset/evidence fixture and separate backup/restore DB |Completion of all restore oracles |

Retain60s positive cycle/recovery drain, processing p95<=250ms/p99<=1s, zero
duplicate economic effects or balance/position/reservation violations, no false
READY, no owner/mode/episode crossing, process RSS<=1GiB and W3 growth<=20%.
Do not subtract overlapping coordinator, pool or observation waits from deadlines.
Record partial denominators and preserve all old Failed/Incomplete evidence.

## Approved integrated composition

These are owner-approved validation parameters, not product limits.

1. **F-16 intake:** every measured NEW/CANCEL/replay command in W1–W3 goes through
   the authenticated F-16 HTTP endpoint, durable inbox, bridge and real worker.
   Keep all100 core owners, the same five-command cycle, counts, amounts and
   idempotency identities. Setup commands stay outside measured denominators.
   Record HTTP acknowledgement, durable command result, processing and observed
   projection separately. Exact retry must add zero orders/economic effects.
   Existing browser complete-flow and receipt-loss tests run on the same candidate;
   they do not substitute for the sustained HTTP/queue workload.
2. **F-14 workload size:** retain the complete history of all100 core episodes.
   At the end of each successful W1–W3 phase, stop mutations, then replay every
   episode and compare exact cash, position, cost/PnL, reservations and source
   revisions against the independent cycle oracle. Read all100 current snapshots
   with at most4 concurrent clients. No sampling of only successful owners.
3. **F-14 budgets:** record elapsed time and query/row counts per owner;
   each final rebuild must finish within60s. For the bounded snapshot pass require
   p95<=250ms/p99<=1s and RSS<=1GiB per process. During W3 read all100 snapshots
   once/minute,4 concurrent readers, with process memory growth<=20% from the first
   stable hour to the last. A failed read remains a failure/sample, not omitted.
   Existing real-DB concurrency tests must prove another owner can progress while
   one owner rebuilds; the campaign cannot replace that deterministic safety proof.
   Rebuild work may grow with retained history; unexplained superlinear query or
   memory growth fails investigation rather than receiving an invented allowance.
4. **F-17 coverage:** use all approved Feature lifecycle/race/fault/financial cases
   on the final candidate, including the existing browser-to-worker flows. As V-18
   specifies, these add protection coverage without replacing ordinary baseline
   volume/SLA. This proposal makes no100-owner protection-trigger throughput claim.
5. **Restore integration:** keep the existing F-15 fixture and add the existing
   F-16 receipt/transfer and F-17 pending/armed/exit/retry fixtures in a separate
   extension. Extend canonical digest coverage to their durable tables; verify
   identity, history, grants/RLS and restart recovery without duplicate exit or
   fill. The standalone0065 W4 result remains valid for its narrower scope.

## Execution gates and reporting

1. Implement the harness changes and deterministic contract/safety tests. Confirm
   default behavior, option validation/restart propagation, deadlines, exact
   quantities, API idempotency and cleanup. Finish lint/types/review before timing.
2. Run the one defined diagnostic to check NC10 under the actual parent and worker
   composition. Require complete financial/final-tail/resource evidence and the
   unchanged thresholds before advancing; if it fails, diagnose and report the
   cause or remaining uncertainty. No automatic same-candidate repeat.
3. On a passing diagnostic, run W1, then W2/faults, then W3 and integrated W4.
   Each phase needs a fresh isolated DB; no reset/prune of existing databases.
   Freeze fault schedules/counts and verify role URLs before each phase.
4. On the stable candidate run required affected regression, cross-feature browser
   E2E and final review. Required remote CI must pass on the published candidate
   before merge; local evidence cannot substitute. Record any unapproved Git gate.
5. Record V-18 Passed only when every constituent criterion passes. Keep V-19/V-20
   Pending Dependency, and do not call F-17 Completed while they remain pending.

Estimated execution after harness/tests are ready:6–8 hours including setup and
analysis; W3 itself remains4 hours. Harness implementation time is additional and
cannot be estimated reliably until the reused intake/restore interfaces are mapped.
Failures can extend the work; this is not a promised completion time.

## Owner decision

**A — selected/approved:** approve the consolidated Paper profile and conditional
continuation above, keeping all current safety criteria and Release gates.

**B:** retain current approval boundaries and revise the proposed integrated
composition/budgets before implementing or running it.

Neither choice by itself makes F-17 Completed. To change that definition to
Paper-only would require a separate explicit requirements/validation amendment;
no such change is proposed here.

## Execution — approval and diagnostic harness

NC-SET4-01 is Closed / Approved A. The first campaign phase uses the explicitly
specified NC09 diagnostic fixture plus NC10 coordination. Integrated HTTP intake,
F-14 snapshot/rebuild and extended restore remain required before their later
acceptance phases; the diagnostic cannot certify those paths.

Implemented a harness-only `--coordinate-claims` flag, strict R8 compatibility,
initial/recovery/restart forwarding and per-process protocol metadata. Reused typed
optional-argument and dispatch-recorder patterns. Observations include whole
selection and coordinator setup/acquisition calls; the latter includes isolation/
timeout setup SQL and is not an exact server lock-wait measurement. No metrics are
subtracted from processing/progress criteria and no additional SQL observation added.

133 targeted tests passed, including default paths, flag propagation, cancellation,
observer restoration and existing poll/heartbeat/tail safety. Ruff/format/mypy passed
before campaign launch. An initial mypy failure was fixed and retained in evidence;
it did not overlap a running campaign. Prior NC10 real-DB/process/financial proofs
and the latest48-case protection result remain valid; runtime source is unchanged.


## Diagnostic gate outcome — blocked before W1

Coordinated diagnostic1 failed during baseline setup. Fixed a concrete recorder
coverage gap, passed45 affected tests/static checks and ran the same profile on a
changed harness candidate. Diagnostic2 completed baseline2000, then188/600 cycles
and1091/3000 commands before a60.001s cycle timeout. Both failures are retained.
Runtime source and all837 captured Python/lock/config files were unchanged during
each run. Full financial/final-tail/resource acceptance was not reached.

Eighteen of20 workers exited on selection deadlines,14 while acquiring the gate.
Partial measured processing p95=441.6ms; even the first60s had311.9ms, before the
exit cascade. Lower claim collisions therefore do not prove the acceptance fix.
All21 pool reports finalized, no checkouts/processes remained, and DB connections/
advisory locks were0. Raw evidence and limitations are in the Batch ledger.

NC-SET4-01 remains Closed / Approved A; the profile is no longer missing. W1–W3
and integrated HTTP/snapshot/restore phases cannot advance past this failed gate.
The [NC-SET4-11 proposal](../2026-10-18-paper-order-matching/worker-claim-contention-amendment.md)
changes the explicitly approved blocking acquisition protocol and needs owner
approval before implementation. No third diagnostic or threshold change occurred.


### NC-SET4-11 approved and executed

Owner approved V2 nonblocking acquisition/250ms backoff. Implementation,135 targeted
safety tests, scoped static checks/import contracts and diff review passed. The one
V2 diagnostic failed setup on book `WriterLeaseLost` after165.058s;394/2000 baseline
orders succeeded,0 measured commands/cycles. No gate-acquisition timeout stack,
but one claim SQL selection timeout and one shutdown termination remain. Cleanup
verified, raw evidence retained. NC11 approval is no longer pending; its one-run
stop/report checkpoint is reached. Later phases remain gated. Next timed work needs
a scoped publisher-baseline timing plan/approval, not an automatic repeat or W1.

## Internal-pilot checkpoint - NC-SET4-12 Approved A

The [20-account internal-pilot amendment](internal-paper-acceptance-amendment.md)
was approved A on2026-11-06. It authorizes a separate internal opening gate and
scoped harness/checks/conditional campaign. It does not certify this100-account
campaign, erase Failed/Incomplete results, or close F17 V-18/V-19/V-20.
