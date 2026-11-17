# NC-F17-LEASE-02 — Publisher lease under short internal20 load

สถานะ: **Approved — owner explicitly requested implementation of this plan**
2026-11-15. Amendment within existing F17 validation branch; no new product feature.

## Requirements

R1 Use PAPER_INTERNAL20_V1 SMOKE:20owners,400baseline orders,6cycles/owner,
600commands at2/s,20workers,10Hz publisher, existing poll4/claim coordination/final
tail/resource/financial assertions. Five measured minutes, no scheduled faults.
R2 Harness-only observer opt-in/defaultoff. Reject other profiles/phases, worker-only,
controlled delays, clock recovery and other diagnostics. Original5s lease, SQL,
fences, guards, clocks, cadence, commits/errors and financial logic unchanged.
R3 Actual task/tick/price/heartbeat flags; original functions once, no injected delay,
retry/reacquire. Record checkout/setup/renew/publication/price/exit spans and actual
PG TTL, at most1extra precommit clock probe/publication. No invented server-only
commit time. Child tasks cannot consume or overwrite parent evidence.
R4 Count all outcomes. Bound detailed retention to last64 and slowest16 plus the
single terminal failed publication. No per-tick disk IO; final/error flush only.
Missing/IO-corrupt evidence makes diagnostic Incomplete, preserve primary exception.
R5 Fresh isolated DB and dedicated labelled Redis after one120s preflight; no owner/
Live commands/services touched. Pin candidate/config/migrations/runner before it.
Run once, expected10–15min/max1200s from preflight including cleanup, then stop/report.
No4h/Git/CI/production fix authorized. OldIncomplete/F17 notCompleted retained.

## Plan and reuse

Reuse profile_publisher_lease.py recorder and M1 readiness failure receipt; add a
normal-publication descriptor and in-memory sink without weakening fixed-case delay
validation. A dedicated load controller wraps the actual market_publisher to bind
its task, then records only its publish_market calls. Unrelated/child calls stay
original. Bounded retention uses existing in-memory ephemeral observation patterns;
it is not application/session/persistent business state.

Add --publisher-lease-observer to workload/campaign CLIs; validate before any fixture,
pass through campaign namespace, scope controller in run alongside existing readiness
and owned-pool observers. Record independent state/lock witness on publisher failure
before cleanup. Normal shutdown cancellation is recorded distinctly from lease loss.
Observer failure cannot leave an apparently accepted result; retain workload grade
separately, mark diagnostic failure Incomplete. Do not modify acceptance formulas.

Private coordinator reuses owned DB/bootstrap/migrate/cleanup and Redis ownership
patterns. Pin source/schema inventory/config/copied runner before preflight. Runner
copy may adapt only root, dedicated Redis name, and reuse of the already-completed
preflight receipt (verify source binding,Passed,7samples); no duplicate readiness
window and no fixture before preflight. Capture live schema before workload. Normal
owned cleanup only; prove0connections/locks or retain with reason. Deadline cannot
justify force cleanup or stopping unrelated processes.

## Validation / stop gates

Feature: option matrix/default isolation; task identity/original-once; bounded buffers
and slow/failed retention; real-PG normal/rejected/cancelled/ambiguous-commit paths;
IO failures preserve primary, reject incomplete evidence; fixed LEASE-01/readiness
regressions and scoped Ruff/format/mypy/whitespace. Reuse unchanged money/safety proof.
Batch diagnostic: onepreflight/oneSMOKE, record actual duration/600command completeness,
original financial/finaltail/resource results, stage/TTL evidence, source stability,
independent failure witness and normalcleanup. No slow sample exclusion or acceptance
claim from observer metrics. Not reproduced in5min != fixed or four-hour Passed.
Release: all prior4hIncomplete/finalfinancial/rebuild/100account/dependencies retained.
After this campaign stop/report. No automated additional experiment or fix.

Implementation binding before execution: the independent witness uses one explicitly
owned diagnostic MARKET_DATA pool(size1,overflow0,timeout0.5s), created once per
publisher and disposed on every exit. In opt-in mode only, add exactly that pool to
the observer's expected inventory; all original workload pool identities/caps and
return/disposal assertions remain required. This accounts for diagnostic overhead
rather than hiding the observer connection or relaxing the original pool checks.

## Execution checkpoint — authorized campaign consumed

[Result Incomplete](evidence/endurance20-20261115/lease02-checkpoint.md): onepreflight,
600commands/301.051s,3087successful publisher calls, nolease loss; total469.132s.
Aggregate parent pool validator did not accept the added declared witness pool;
retain Incomplete. Allindividual pools/financial/base checks Passed, cleanupverified.
57distinct targeted tests/scopedstatic Passed; aggregate-validator test gap recorded.
Stop/report, no further source correction or experiment/Git action in this approval.

## Owner-started review and aggregate-pool correction

After the Incomplete checkpoint, owner instructed “เริ่มทำ” for the stated next step
(review observer and correct aggregate validation). Review confirms the explicit
witness pool is tracked/disposed but validate_reports still hardcodes the original
parent inventory. Before source changes: centralize the parent inventory selector
with an explicit boolean diagnostic option, defaultFalse; use the same selector
for tracker creation and aggregate validation, pass the trusted validated option
from run. Do not infer permission from a report's self-declared expected list or
accept arbitrary extra pools. Original13parent pools,worker inventories/capacity/
borrow/disposal/sample/error rules remain mandatory. Add default/opt-in positive
and negative inventory/lifecycle tests, including actual run caller wiring, and
run affected pool/load regressions/static checks. No offline change of old result,
new campaign,4h or Git/CI action. After correction/verification ask owner refactor
instruction as AGENTS requires. Historical lease cause remains unproven.

[Review correction complete](evidence/endurance20-20261115/lease02-pool-fix.md):
68affected tests/scoped checks Passed, no campaign repeated or old result regraded.
Await owner refactor instruction.

## Owner-authorized aggregate-pool refactor

Owner instructed `refactor the code`. Runtime inventory selection/caller wiring is
already small and shared, so leave it unchanged. In only the14new pool correction
tests, consolidate repeated configured-engine creation in a local typed helper and
rename parent/worker inventories and expected result for clarity. Preserve engine
creation/disposal order, contexts, all assertions and test cases. Run these14affected
cases and scoped test-file static checks immediately; retain54unchanged regressions
from68Passed. No campaign,criteria/runtime/Git change or regrading of old Incomplete.

[Pool correction refactor/validation complete](evidence/endurance20-20261115/lease02-pool-refactor.md):
14affected cases/static Passed,54unchanged retained; runtime unchanged. No new
campaign or Git action authorized/performed; old Incomplete retained.

## Replacement campaign approval — owner instructed เริ่มทำ

After reviewed aggregate-pool correction, authorized refactor and affected checks,
owner instructed “เริ่มทำ” in response to the proposed replacement short diagnostic.
Authorize exactly one replacement on this corrected candidate: same internal20 V1
SMOKE,400baseline orders/600commands/5measured minutes, one120s preflight before
fixtures, expected10–15min/max1200s including cleanup. Retain prior Incomplete.
Reuse the original private coordinator with only fresh output/ownership/Redis names;
pin its copy/hash and current source/config/schema. Reuse14affected/54unchanged tests
and scoped static evidence because runtime is unchanged since those checks. No
retry/criteria/lease/production change or4h/Git/CI. Stop/report on completion/failure;
this replacement authorization is consumed by that one run.

[Replacement checkpoint](evidence/endurance20-20261115/lease02-r2-checkpoint.md):
Incomplete on actual tick557 price lease expiry,9.848s fence-call interval; rollback
witness/head556 confirmed.243.661s total, cleanup independently verified. Replacement
authorization consumed, no subsequent source fix/experiment/Git action. Stop/report.
