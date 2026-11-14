# Integrated Paper timing amendment — 2026-11-14

สถานะ: **Approved under owner explicit instruction 2026-11-14**: “เริ่มทำจนจบเลยได้ไหม ถ้าทำแล้วไม่ผ่านเกินสองรอบให้ปรับเกณฑ์”. Engineering timing only; no financial/safety waiver.

## Evidence / decision before implementation

Original100 uninstrumented attempts had three unsuccessful outcomes before this
instruction (p95 and cycle60 failures); original failures retained. Representative
poll1s original100 SMOKE now passed all3000commands/economic/pool/resource checks,
p95/p99170.827/236.244ms and strict0/0cleanup within1200s via documented followup.
W1 with authenticated HTTP still FailedCycleBudgetExceededError after2963completed,
553cycles; partial7700workertransactions p95/p99288.940/429.663ms. Full final oracle
NotRun. This is a real unmet timing criterion, not an accepted financial result.

Diagnostic receipt1920matches showed workerconfirmation waitp9510.528s vsfirst-read
gapp95404ms; earlier complete expired cycle comprised sequential BUY≈20s, LIMIT≈10s,
CANCEL≈10s, SELL≈20s. These overlapping measurements cannot be subtracted from elapsed
time. Ordinary positive workflow combines five commands and multiple independent
commits/observations, unlike a single engine transaction or fault recovery.

Owner's >2-round condition already satisfied; do not run another unchanged check
merely to consume attempts. Use explicit new profile PAPER_RELEASE100_TIMING_V2:
- Ordinary five-command positive-cycle whole-workflow budget90s (50% orchestration
  margin over60s; still finite). Each existing command/status deadline60s stays.
- Engine transaction p95≤500ms: reuse approved NC12 Paper processing ceiling, with
  250ms retained as optimization target/warning. p99 remains≤1s (not NC12's2s).
- Keep all100owners,20baselineorders/owner,20workers, exact amounts and commandcounts,
  offered rates/phase durations/overall elapsed bounds, HTTP auth/CSRF/RLS and all
  original seven four-hour faults. No change to sources/worker selection/claim order.
- Fault drain/recovery, final-tail drain, replay≤60s, snapshot p95≤250ms/p99≤1s,
  freshness, TP/SL trigger/fence/STOP/idempotency/financial/precision rules unchanged.
- Resource/pool/RSS/connection/growth and zero economic inconsistencies unchanged.
  No phase can pass without complete independent economic/snapshot/replay oracles.

This admits slower Paper processing under load; it is NOT evidence of original
250ms/60s performance, Live readiness or100-owner TP/SL trigger throughput. Record
strict-original processing grades and cycle max/counts over60s alongside new grades.
No slow-sample removal, overlapping-wait subtraction, hidden retry or money waiver.
V19/V20 dependencies remain; not F17 Completed. Old profiles/defaults unchanged.

## Validation and execution

Add negative boundaries p95>500ms/p99>1s, missing values, exact90s selection, original
profiles still250ms/60s, unchanged counts/faults/resources and nested timeout/cancel
semantics. Cycle summary bounded in memory (aggregates only), preserving failures
if evidence write fails. Targeted profile/workload/fault/gate/static checks before
fresh revised SMOKE then W1→W2/overflow→W3→W4 on previous-phase pass. Reuse unaffected
source safety191cases, timing/polling/cleanup proof. No full financial rerun for a
post-stop evidence-only edit. No further engineering approval stop; reassess any
remaining timing failure from its evidence, never automatically waive safety.

## R2 — Consistent final workflow allowance; decided before grader change

Revised SMOKE completed all3000commands/600cycles,all100economic oracles/global/
resource/poolPassed,p95/p99383.937/584.397ms,cyclemax63.345s(61over60),nointerruption.
Actual measurement369.355s failed only original overall300+60=360s, despite revised
positive workflow allowing90s. Complete observations retained; rawR1Failed unchanged.

The last scheduled workflow starts just before the nominal end. A permitted90s
workflow therefore requires at most nominalduration+90s to finish; keeping+60s
would independently reject an allowed workflow. R2 changes only this final ordinary
workflow allowance from60→90s for TIMING_V2, derived directly from its declared90s
budget. Fault-window durations still added exactly once; no overlapping waits
subtracted. All phase nominaldurations/rates/counts, recovery/tail60s and economic/
security/resource assertions unchanged. Original profiles still+60s. New receipts
record R2 and both overall limits/grades; maintain prior rawR1Failed and strict grades.

Validate exact target+90/over-boundary rejection and unchanged target+60 defaults.
Reuse the completed R1SMOKE economic/performance measurements by a separate R2
regrade receipt verifying all original independent assertions and only this revised
limit, original-source hashes and exact source diff. Do not rewrite result.json or
manufacture a new execution. This post-measurement grader-only change does not
justify repeating the same financial workload. Then proceed directly to freshW1.


## R3 disposition — retained 100-account failure; finish approved internal checkpoint

R3 W1 used complete1s observation for HTTP transfer/DB command/status. Failed after
1999.601s total:12341/18000commands complete,2431/3600cycles; one positive workflow
exceeded90s while awaiting final SELL status. All100tasks canceled after the first
failure;100interrupted is not100independent timeouts. No worker-process failure or
rejection recorded, but final financial/snapshot/rebuild oracle NotRun; therefore
no whole-run monetary pass inferred. Cleanup0connections/0locks, DB normally dropped.
Raw Failed and original60s/90s grades preserved in r3-w1-summary.json.

Latest owner instruction authorizes continuous completion and engineering criteria
adjustment after repeated failures. Do not increase timeout without bound or erase
100-account performance failure. Resume the already-approved NC12 Internal Pilot
checkpoint (20accounts/400baseline, same per-account amounts): existing V1SMOKE/W1,
V2W2/overflow and V3shortW3, then W4, with current source and strict unchanged
per-command/cycle60s, pool contract and all monetary/source/recovery/protection
assertions. This uses existing approved scope/criteria; no new capacity claim,
account cap, strategy, gate activation, source runtime or production edit. Internal
p95/p99 ceilings500ms/2s are existing NC12, not100 release criteria.

Refresh20-account SMOKE because original20 proof predates production accounting
reads and HTTP correction. Reuse current controlled20 TP/SL proof and113HTTP/poll
plus191production safety cases where unaffected. Before each phase preflight,
fresh fixture and new output, candidate/runner hash, strict cleanup. Conditional
SMOKE→W1→W2→overflow→shortW3→W4, stop next phase on failure, diagnose/fix within
owner engineering delegation. Expected whole internal checkpoint about2h including
preparation. No full regression/CI publication repeated during timed workloads.

100-account W1 remainsFailed;100W2/overflow/4hW3/W4 remainNotRun/PendingFullValidation.
Internal checkpoint success cannot close original100release gates or F17V19/V20.
Report both scopes separately; do not call all Paper/release or F17Completed.


## R4 — Local burst5 and narrowly proven public-reader deadline; BEFORE source edit

Authorization: latest owner expressly requested continuous completion and criteria
adjustment after >2 unsuccessful rounds. That condition is met by retained original
100 failures, R3W1 and current W2. Engineering only; never waive pool return, money,
positions, TP/SL, source freshness, STOP, auth/RLS, unknown commits or Live controls.

Current internal W1 Passed3600/3600, all20 financial/snapshot/rebuild oracles, engine
p95/p99285.161/450.931ms, snapshot22.192/22.967ms, cleanup0/0 and normalDBdrop.
W2 completed12000/12000, all20 financial/snapshot/rebuild oracles and global invariants
Passed, no rejection/crash/duplicate effect. RawFailed retained:1645.305s measured
exceeds1260s; p95508.348ms exceeds500ms (p99756.262ms within2s); pool report has4
ConnectionResourceError instances. These are CancelledError at API public_read,
pricepool3+0, cancellation_requests1, quiescingFalse; all final borrows/disposal0,
strict DBcleanup0/0 and normaldrop. Deadline provenance was not observed and pool
was not configured read-only. This cannot be retroactively certified or regraded.

1. Preserve the existing500ms/2s engine ceiling,60s cycles/commands,20accounts and
400resting baseline. Add explicit local burst5 profile:60cycles/account,6000commands,
5commands/s over1200s;2.5x the approved2/s sustained load. Same per-command amounts,
fees, quantities and independent oracles. Original V2 ten/s and12000 benchmark stays
unchanged/Failed; retain its complete monetary facts as additional heavy-load proof.
No claim of10/s or100-account capacity. No product rate cap/user limit introduced.
2. Public price pool alone is configured PostgreSQL read-only using its existing
engine's execution options (same identity/pool3+0); keep0.5s deadline and all query/
lock limits. Bind its existing asyncio timeout to a typed local _deadline. No
financial engine/session, public API/schema/source decision changes. This tightens
write capability and exposes only an existing timer's identity for safe observation.
3. Extend existing task_provenance: inspect ONLY the known app.public_read code
location and typed asyncio.Timeout _deadline; never enumerate/serialize locals,
SQL, params, names, tokens or exception text. Classify expected read cancellation
ONLY if actual timer expired, deadline finite/past, single pending cancellation,
CancelledError with no08SQLstate, API pricepool3+0 and configured read-only. Record
separate bounded expected-read-deadline diagnostics/warnings; no financial/resource
error suppression elsewhere. Final0borrow/0disposal and strict DB0/0 still mandatory.
Unknown/external/multiple cancellations, writable/ENGINE/admin pools, real disconnect,
pool exhaustion and unreleased borrows remain failures. Old unproven4 stayFailed.

Before workload: test actual PG read-only setting and blocked public-price SELECT
hitting the unchanged deadline with0returned borrows; successful next read; negative
classification for unknown/unexpired/external/multiple/writable/wrong-role/08errors,
leaked borrow/disposal and privacy/callback cleanup. Retain existing real cancellation
negative tests unchanged. Test new profile exact counts/rate/duration, unknown/wrong
params, unchanged old profiles/4h release/fault defaults. Scoped Ruff/format/mypy,
existing public-price/lifespan/pool/HTTP tests only. No workload until checks pass.

Then fresh local burst5 (one new source/fixture, not a rerun of the old criterion),
conditional overflow→approved V3shortW3→W4. Source edits during no active workload;
reuse unaffected monetary191cases/W1 controlled20 proof with explicit hash mapping
(price-read write restriction/observer/new profile do not modify financial paths).
Refresh the private runner, preserve all old receipts. Estimated remaining75–90min
including checks and campaigns. No owner-account action, Live, public activation,
100/4h acceptance or F17Completed claim. No automatic publication from local results.


### R4 correction before replacement implementation — shared authentication pool

First new test collection failed from an incorrect presented_session import; fixed
only test import. Scoped static5filesPassed. Actual deadline/readonly/pool/profile/
HTTP tests passed, but5existing WebSocket cases failed. Inspection proves price_guard
also uses app.state.price_engine for presented_owner/session refresh; setting the
entire engine read-only wrongly prevents that existing authenticated write. Preserve
these test failures and restore original auth semantics; do not modify expectations.

Before replacement code: keep app.state.price_engine writable and create a read-only
execution-options facade over its SAME pool for public_read alone. No new physical
pool/credentials/role. SQLAlchemy resets transaction characteristics on pool return;
prove public-read transaction read-only and subsequent original-engine transaction
read-write, plus all previously failing actual WS tests. Resource classification
must read the effective failing SQLAlchemy context.engine options (the actual facade),
not the writable registered pool engine. Exact timer scope, single cancellation,
zero returned/disposal/DB counts and all other failures remain mandatory. Update
actual test probe to assert readonly inside public_read and auth pool writable; do
not weaken WS/session assertions. This is correction of our first overly broad
implementation, not a new authentication requirement or deadline increase.


R4 corrected scope checks:168Passed/2Skipped (explicit test Redis URL absent),
including actual read-only timeout, external cancellation failure, borrow-leak
failure, same-pool six-engine inventory, writable auth after read-only return and
all five WS regressions nowPassed. Set TEST_REDIS_URL to the dedicated fixture and
run the two skipped guards, not owner Redis. Static5filesPassed. No new workload yet.

Two bounded review corrections before final source: pre-ping error contexts may
have no execution engine; keep those unproven cancellations/disconnects as resource
failures, never raise from the observer while inspecting None. Add negative callback
case. Also reject full-diagnostics parent execution for RELEASE100_TIMING_V2 before
resources: its custom diagnostic cycle scope is fixed60s and cannot certify the
90s summary. This unsupported combination otherwise produces misleading failures;
normal timing and all legacy diagnostics remain unchanged. Add early-reject/legacy
unit cases, no new abstraction, then scoped static and affected small tests. These
harness guards change no financial code or retained valid runtime configuration.
