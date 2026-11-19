# Chart3m E2E blocker — bounded next-step proposal

สถานะ: **Approved — owner replied “approve” 2026-11-19 before corrective work**
วันที่: 2026-11-19
PR81 head4578c20; CI run44464956048. Main remains fea1579.

## Verified evidence and limit

Attempts1/2 failed hosted Ubuntu HTTPS preflight before E2E. Attempt3 passed preflight,
then35main-suite tests passed and candlestick-chart.spec.ts:421 exceeded the existing30s
limit. Captured observer: BTC/3m, HTTP200, no abort/shape/HTTP failure, history998→999rows,
live NO_DATA→RECOVERING with1row; no READY observed and ETH not reached. This evidence
locates the blocked readiness condition; it does not establish the root cause or show
that increasing the timeout would be correct. Backend/frontend/API/container/Security pass.
No runtime/trading/session/lock changes exist in the history-reconciliation diff.

Stop further CI/test execution under AGENTS.md three-failure rule. Do not merge/delete refs,
relabel Failed as Passed, increase30s or weaken READY/financial/source assertions.

## Recommended bounded continuation (needs owner authorization)

1. Read and correlate approved chart3m/candlestick requirements, plan/validation and already
   captured observer with `frontend/e2e/candlestick-chart.spec.ts`, fixture
   `specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py`, producer
   `backend/tests/e2e_candle_runner.py` and actual chart API readiness/watermark dependencies.
   Determine whether fixture seeding, producer lifecycle or runtime readiness violates the
   existing contract; do not assume the fixture is at fault or invent readiness semantics.
2. Record causal evidence, alternatives and affected-proof mapping before any necessary
   engineering correction under existing delegation. Use existing functions/tests first.
   Changes to money/risk/Live/product/readiness correctness thresholds still need a separate
   owner decision; this proposal does not authorize them.
3. Authorize one correction checkpoint: smallest relevant local correctness/static tests,
   real-DB proof where required (owned CI services if local unavailable), review/fix, then
   one new required CI round on the corrected final candidate. Existing final/postmerge
   gates remain mandatory. If that new CI round fails, stop and report before another run.
   No automatic extra replay/endurance/capacity/Live campaign.

Scope estimate: focused investigation/correction approximately20–40minutes depending on
causal evidence, plus required CI approximately20–30minutes and postmerge20–30minutes
if candidate succeeds. These are estimates, not authority to exceed the approved round.

## Alternative

Keep PR81 open, main and original four refs untouched, and pause further investigation.
This preserves completed historical merges/approved exception in the candidate and all
failure artifacts. It does not fulfill final main merge or justify bypassing required CI.

## Approval and investigation checkpoint

Owner approved this bounded continuation with “approve”. Existing past Failed runs remain
Failed; authorize targeted local real-DB/static work and one new required CI round after
correction, then stop on any failure before another hosted attempt.

Static evidence: production read_live requires a committed prior same-timeframe candle
with end-qualified REST fetch before READY. CandleSupervisor only queues bootstrap/ended
repair demand; it deliberately does not fetch REST. E2E producer starts only that supervisor,
while browser seed is a one-time snapshot. Therefore real missing-prior/rollover states
cannot converge in this composition without the ordinary ingestion worker. This explains
a reproducible class of persistent RECOVERING, not yet the exact cause of the old CI trace.
Before implementation, reproduce missing prior on owned PostgreSQL with real supervisor,
production read_live and run_round, proving stream-only stays unrecovered and real REST
repair makes it eligible. Reuse existing reconnect-bootstrap real-DB coverage and fixture
RepairSource instead of changing runtime readiness or budgets.

## Causal proof and selected correction — before implementation

Owned PostgreSQL16/Redis7 were bootstrapped/migrated using the existing roles, on isolated
loopback ports. Actual production supervisor/read_live/run_round plus existing fixture
RepairSource reproduced BTC and ETH: three fresh stream updates cannot satisfy missing
REST predecessor; one ordinary round (two fetches/1000unique end-qualified rows per series)
makes recovered true. No READY flag/mock or direct candle insert substituted for ingestion.
[Receipt](chart3m-real-db-reproduction.json). Original CI timestamp cause remains unknown;
the missing REST component is a demonstrated nonconvergent harness state.

Reuse `RepairSource` from the existing browser fixture (fixed repo-owned import path),
production `_seed_initial_demand`/`run_round` and existing MarketDataSession. Add an opt-in
`--repair-native-3m` to the test producer and enable it only in the affected native3m browser
case; default producer behavior remains unchanged so deliberate1h gap/repair tests retain
their controls. The synthetic REST loop services BTC/ETH3m via ordinary claims/finality
semantics, parks unrelated timeframe jobs only in the already guarded disposable E2E DB,
and respects original four-fetch/round, claims, backoff and freshness policies. Monitor
and cancel/join both test tasks on failure/stop; do not turn producer failure into READY.
No production code,30s timeout, READY/data/no-order assertions, worker1s SLA or auth500ms
changes. Add real-DB composition regression for opt-in recovery and default stream-only
non-recovery, plus lifecycle cleanup; reuse existing preview/reconnect tests (includeM3).

Local diagnostic setup failures retained: initial synthetic bar changed open without
high/low/close and correctly failed OHLC validation; corrected to existing fixture prices.
The next setup parked ETH while proving BTC; isolated/reset each test target before the
ETH proof. Both final base cases Passed with original readiness assertions unchanged.

## Local composition-test measurement correction — before adjustment

Default stream-only regression Passed; opt-in composition reached recovered=true for both
bases, then a new overstrict diagnostic asserted every REST row was ended. Production
initial_window/_prepare intentionally may include the current OPEN candle. Production initial_window explicitly includes next_open, so current OPEN rows are allowed;
the post-test diagnostic query was empty after fixture cleanup and is not row-level proof. OPEN is
not the previous-slot readiness evidence. Correct the new test to require unique native3m
rows and end-qualified non-OPEN predecessors, while explicitly allowing the current
OPEN slot. Preserve the failed assertion result; original READY/30s/no-order/browser
assertions remain unchanged. This is test measurement correction under delegated authority.

## Static import boundary review

Strict targeted mypy needs local src in its search path (full CI already includes src);
the out-of-tree existing browser_fixture is a runtime-only test import. Reuse existing
importlib.import_module pattern with a typed CandleSource boundary instead of ignoring
missing-import/return-any checks or moving/duplicating fixture logic. Runtime source path
and class remain the same; recheck the actual real-DB composition after this import-only
change. Preserve default and opt-in behavior, no checker configuration relaxations.

## Edge-case review refinement

A final review avoids requiring every stored REST row to be ended: native current OPEN
or an in-flight pre-end observation is valid across a UTC rollover. Verify the exact
previous slots used by read_live are non-OPEN/end-qualified in PostgreSQL, all stored
rows have native3m spans and unique opens, and default stream-only cannot manufacture
REST rows. This strengthens the causal readiness check without imposing a new global
finality rule; original browser assertions and budgets unchanged.
