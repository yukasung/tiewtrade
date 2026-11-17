# Paper internal20 — standalone four-hour endurance execution

สถานะ: Approved execution scope — owner requested four-hour testing before opening and explicitly selected “20 บัญชีจำลอง — ตรวจความเสถียร 4 ชั่วโมงก่อนเปิดภายใน” on2026-11-15.

## Approved requirements and existing implementation

Use the already approved NC12 internal-paper-acceptance-amendment.md §3 W3-20
and §16 processing thresholds, current preflight and owned-pool contract. This is
execution of the existing PAPER_INTERNAL20_V1 W3, not a new profile/strategy or an
amendment to financial rules. Owner expressly prioritizes this standalone evidence
before opening. Preserve all previous Failed/Passed/Incomplete results; do not infer
that old20W2 or100W1 passed, or use standalone execution to waive release sequencing.

Candidate: merged main b0d5580364268be7619f5369dc8488d440f12160 (PR75).
Required pre/postmerge CI and Security passed. Reuse relevant financial safety,
real-PG, profile/observer and cancellation tests on identical source; no source edits.

-20 owners,20 baseline active LIMIT orders each,20 workers; deterministic fixture
  feed,10Hz book inputs, authenticated fixture HTTP commands.
-282 cycles/owner,5640 cycles,28200 commands,11280 fills,5640 cancels and5640 replays.
-14400 measured seconds,2commands/s outside the unchanged seven fault windows in
  backend/tests/infra/execution_market/w3_fault_schedule.json. Pin schedule hash.
-Existing processing ceiling p95<=500ms/p99<=2s; original250ms/1s target reported.
  Snapshot p95<=250ms/p99<=1s, rebuild<=60s/owner; cycle/recovery and final tail bounds
  remain60s. Exact financial/global invariants, RSS/growth and owned-pool rules unchanged.

## Execution and isolation

One fresh isolated database; all fixture role URLs point to it. Dedicated Redis on a
localhost port with exact task ownership label, image reused from existing Redis.
Never pause/stop owner Redis/PostgreSQL or any unrelated service. Only the dedicated
fixture Redis and campaign-owned workers/connections may receive scheduled faults.
Copy the existing campaign runner outside tracked source with only root binding and
fixture Redis target adaptation; prove reversible substitutions and pin all hashes.
Existing campaign performs one120s/7sample preflight before fixtures/workers. No
repeated preflight waiting for better conditions. Missing/invalid readiness is Incomplete.
Use empty output root, pin source/config/schema/runner, retain all samples and actual
fault timings, then final financial/snapshot/rebuild/pool verification and cleanup.
Expected total4h15–30min including setup/preflight/final verification;4h is measured
endurance, not total wall time. Existing engine/runtime bounds remain authoritative.

## Result and stopping rules

Run once; Failed/Incomplete stops/report without automatic retry, source edits or
threshold changes. Remove only proven owned DB/container after normal cleanup and
zero connection/lock checks; retain unresolved resources if ownership/cleanliness
cannot be proven. No reset/prune/images/volumes or owner account/Live operation.

Success proves only the declared20-account four-hour workload and existing fault/end
reconciliation assertions. Do not manufacture all-owner per-fault recovery guarantees
beyond the harness's actual evidence. It does not satisfy100-account Release, opening
or bot/notification/Live dependencies; F17 remains notCompleted. After execution report
result, actual duration/metrics, faults, exact financial proof, cleanup and remaining
gates. Documents/evidence only; no automatic publication beyond this execution request.

## Execution result

[Attempt checkpoint](evidence/endurance20-20261115/checkpoint.md): Incomplete after
2411.131889 measured seconds (40min11.132s),4753/28200commands completed before the
publisher rejected input24197. Both PostgreSQL timestamps were read in sequence,
but the guard's later read was230microseconds before received_at/verified_at. Exact
underlying clock mechanism unconfirmed. No financial final oracle/rebuild/full4h
acceptance claim. Cleanup0connections/0locks; owned DB/Redis removed. Stop/report
without retry or criterion change; recommend bounded read-only clock investigation.

## Owner-started read-only clock diagnosis — 2026-11-15

Owner instructed “เริ่มทำ” after the recommendation to diagnose clock ordering.
Scope: inspect retained failure/source and Docker/host/PostgreSQL logs around
2026-11-15 06:43:51 Bangkok, then one bounded300s read-only clock probe. One PostgreSQL
connection to the existing postgres maintenance DB, explicit READ ONLY transaction,
local2s statement timeout/200ms lock timeout, no tables/fixtures/orders/DDL/clock
settings or server-wide config touched. At most300batches of10000 ordered samples,
one batch/second; record only times/backend identity, reversed counts and bounded
examples, not all3million timestamps. Expected5–8min including analysis/cleanup.
No retry if incomplete; absence of reversal cannot disprove the earlier event.
Compare earlier/next readings on same connection; record backend clocksource and
service start/restarts without changing them. Historical SYNC/clock messages are
correlation only unless they establish exact cause. No production fix, guard change,
backdating/tolerance, workload replacement or opening in this diagnostic scope.

Read-only diagnosis completed: [receipt/limits](evidence/endurance20-20261115/clock-diagnosis.md).
One300s/3million-sample readonly probe did not reproduce reversed clock ordering;
dense sample spans only0.754434s, so no stability/repair claim. Exact OS/VM mechanism
unconfirmed from retained logs. Connection closed and backend absent. No source,
clock, criteria, order changes or workload retry. Next requires a reviewable clock
runtime or safe fixture-publisher recovery plan; original run remains Incomplete.

Owner requested preparing the next plan. [NC-F17-CLOCK-01 proposal](publisher-clock-recovery-plan.md)
is ready for review: harness-only opt-in, confirmed explicit rollback, one campaign
recovery/one retry/1s bound, no guard waiver or financial retry, real-PG validation.
Proposed only; no source edits or replacement authorization. Existing outcomes unchanged.

## NC_F17_CLOCK_01 replacement execution result — 2026-11-15

[StepD receipt](evidence/endurance20-20261115/clock01-four-hour-checkpoint.md):
Incomplete. Measured14400.002106s and completed28200commands;7fault observations
RECOVERED, no clock recovery used. Final-tail cursor collection exceeded the60s
shared budget; finalfinancial/rebuild/global acceptance NotRun. Cleanup independently
verified, old results retained. Stop/report before any replacement or source change.
NoGit action; F17 notCompleted. Next needs a bounded final-tail investigation plan.

## TAIL-02-refactor confirmation outcome

[Execution receipt](evidence/endurance20-20261115/tail02-four-hour-checkpoint.md):
Incomplete at14371.934s/28143commands due WriterLeaseLost before final-tail. Approved
clock recovery succeeded once in125.802ms; overall4h/financial/rebuild acceptance
not reached. Campaign cleanup initially false for autovacuum; final owned cleanup
independently0/0 and resources absent. Stop/report, no new retry/source/TTL/Git action.

### CUT-01 four-hour result — 2026-11-17, stop/report

[Evidence](evidence/endurance20-20261115/cut01-four-hour-result.md): full14400s/28200
commands,7faultsRecovered,4820snapshotreadsReturned,finaltail49.641s. Incomplete:
first-owner replay read_execution_inputs exceeded60s; remaining19/finalfinancialoracle
NotRun. Allborrows0beforedispose,80workerpoolsPassed; parentFailed from replay timeout
cancellation, not waived. Cleanup independentlyPassed. F17notCompleted; noautorerun/Git.
Next proposed short replay-read diagnosis with existing observer/representative fixture.

### REPLAY05 four-hour replacement execution — 2026-11-17

สถานะ: owner authorized start (เริ่มทำ) after REBUILD20-05 Passed.
One original W3 replacement on REPLAY05 final candidate. Reuse CUT01 launcher/helpers,
changing only run identity to replay05; preserve profile PAPER_INTERNAL20_V1,20owners,
400baseline,282cycles/owner,28200commands,2/s,14400s measurement,seven original faults,
18000s total budget including preflight/cleanup and120s cleanup reserve. Preserve all
original money/order/tail/resource/pool/60s-per-owner replay checks and observer/clock
flags; no new retries,TTL changes,waivers,prefix or scheduled diagnostic. REBUILD20-05
all20fullfinancialreplays at144364 records passed44.047–46.732s,closing the known replay
readiness gap. Existing75REPLAY05 safety cases and CUT01 cleanup proofs remain valid;
no shared runtime source edits. Verify candidate inventory against retained REBUILD20-05
and REPLAY05 bindings,compile launcher and prove identity-normalized AST equivalence
before the single120s preflight. Pin config,source,migrations,runner andfault schedule.
Use only fresh ownedDB/Redis andsynthetic accounts. Monitor through final oracles and
independent cleanup. Stop/report on failure without automatic retry; retain earlier
Incomplete/Failed. Expected4h15–30min including replay/cleanup; total bound5h unchanged.
No commit/push/CI/merge. Passing this20owner run alone does not close F17 Release.

REPLAY05 replacement [result](evidence/endurance20-20261115/w3-replay05-result.md):
Incomplete at1042.037s measurement,2079/28200completed. Host Idle Sleep569s overlapped
leaseexpiry;WriterLeaseLost at10473,committed10472. Fullreplay/finaloraclesNotRun.
Cleanup independentlyPassed. Next process-scoped sleep prevention for a separately
started replacement;no criterion change/autorerun/Git. Earlier results retained.

### AWAKE01 replacement — 2026-11-17

สถานะ: owner authorized เริ่มทำ after the sleep-related Incomplete and next-step
recommendation. Before edits: evidence links host Idle Sleep569s to lease expiry in
REPLAY05 W3. Select native macOS `/usr/bin/caffeinate -is <python> <launcher>` for the
entire launcher lifetime (preflight through cleanup). Local caffeinate manual states
utility-scoped assertions persist only while utility executes; -i prevents idle sleep,
-s prevents system sleep on AC. No permanent pmset change,no display-wake assertion,
no service stop or additional infrastructure. Prefer native utility over custom power
management code; require AC and verify owned assertion during preflight. First verify
success/failure child exit and assertion removal with short non-workload commands.
Reuse previous launcher verbatim except identity REPLAY05→AWAKE01; compare normalized
AST and retained source inventories. Candidate/workload/faultschedule/TTL/financial/
resource/60s replay bounds unchanged. One fresh120s preflight; if it passes, one original
14400s20owner W3 under18000s budget and120s cleanupreserve. Explicit sleep/lid closure
is not guaranteed prevented; retain power logs and do not count suspended execution as
continuous acceptance. Verify no sleep overlaps measurement, alongside original checks.
Monitor continuously and stop/report after this single attempt,including failure;
noautomaticrerun/Git. Existing engineering delegation covers process-scoped environment
preparation; owner start authorizes the replacement. Original Incomplete retained.

AWAKE01 [result](evidence/endurance20-20261115/w3-awake01-result.md): **Passed scoped
observed original4hW3/internal20**.14400s,28200commands,7faultsRecovered,20financial
oracles/fullreplaysPassed(51.858–56.567s),finaltail27.916s,p95/p99transactions109/194ms,
81poolsPassed. Total4h21m07s. Independentcleanup0/0/resourcesabsent;nohostSleep in
powerlogs,ownedassertionsreleased. Keep observerdiagnosticmetadata/history andF17
PendingFullValidation;not100accountRelease/Completed. Stop/report,noadditionalrun/Git.

## W4-CURRENT01 — current-candidate restore verification, 2026-11-17

สถานะ: Approved execution — owner instructed “เริ่มทำข้อ 1” after the Paper gate audit.

The audit identified changed production evidence readers and shared replay code since
old W4. Reuse the approved W4 fixture, actual pg_dump/pg_restore, canonical/security
comparison, replay and integrated recovery (original 60s bound); do not repeat W3.
Engineering delegation covers binding the previous private restore runner/support to
this worktree, a unique owned Redis and fresh source/target databases. Reuse the
AWAKE01 launcher environment/bootstrap/ownership/cleanup helpers. Preserve every
original assertion and production setting. Run one 120s seven-sample preflight before
fixture/worker creation; the inner runner consumes its passed, candidate-bound receipt
rather than repeating it. Pin current source/config/migrations and runner/support
hashes before execution. Native caffeinate -is lasts only for this process.

Estimate 5–10 minutes, bounded at 20 minutes from preflight with 120s reserved cleanup.
Check adaptation reversibility/compilation before launch. Stop/report on failure; no
automatic replacement. On exit join owned child, require zero connections/advisory
locks and remove only databases proven by creation/manifest receipts plus labeled
owned Redis. Retain resources if ownership or safe cleanup cannot be established.
No production/shared harness edits, financial criteria changes, Live, Git or CI.
Record sanitized result and current gate mapping; retain historical failures and
Incomplete results. This run alone cannot complete F-17. Next scope is publication
inventory/affected-proof mapping after reporting this item-1 checkpoint.


### W4-CURRENT01 checkpoint — 2026-11-17

Current-candidate W4 **Incomplete** after157.256s: preflightPassed, actual backup/restore
completed, expired-claim recovery stopped withSourceUnavailableError before aggregate
result/integrated recovery. Copied market lease expired just before failure was recorded;
no verify publication occurred. Preserve historicalW4Passed and currentAWAKE01W3Passed.
Both owned DBs/Redis cleaned, independent absence confirmed,1046-file candidate unchanged.
No automatic rerun or Git. Next: targeted restored-readiness harness amendment and real-DB
proof, then replacementW4; no four-hour rerun without affected evidence.
F-17 remains Pending Full Validation. Evidence:
[W4 result](evidence/endurance20-20261115/w4-current01-result.md).

## W4-READY02 — restored market readiness, 2026-11-17

สถานะ: Approved continuation — owner instructed “เริ่มทำ” after CURRENT01 report.
Engineering delegation: fix the harness readiness gap identified by the retained dump
and SourceUnavailableError. Copied readiness expires while dump/restore/replay runs.
Reuse profile_workload.market_publisher, wait_publisher_ready and join_owned_tasks.
Start an owned publisher against the restored database (MARKET_DATA role URL retargeted
from the actual target engine database); await original readiness before legacy claim
recovery. Keep it alive through recovery, then stop/join and dispose its own engine.
Preserve primary errors/cancellation. Do not modify ambient URLs or source database.
Keep original economic digest, source-unchanged, RLS, exact-once and freshness guards.
Add focused target-binding/lifecycle tests and retain existing real-DB extension recovery
regression; actual replacement W4 proves dump/replay/legacy plus integrated recovery.
Review/refactor affected harness under the owner's continuing instruction, run relevant
Ruff/format/mypy and tests. Then one replacement W4 with the CURRENT01 launcher pattern,
new identities,120s preflight and1200s total budget. Stop/report on failure, no automatic
retry, Git or four-hour run. Earlier Incomplete remains unchanged. W3 economic/load
proof remains applicable because this change only affects the W4 recovery callback.

### READY02 safety/review checkpoint

4 targeted lifecycle/target/cancellation tests Passed; existing isolated real-DB
extension/retry recovery test Passed. Ruff and mypy (2 affected files) Passed.
Focused review: target derived from engine URL; role credentials retained, ambient env
unchanged; original recovery called once; publisher joined before own engine disposal.
Existing shared readiness and owned-task helpers reused; no additional abstraction or
refactor needed. No new feature, so this is an amendment checkpoint rather than a new
Ready for Code Review gate. Owner's continuing review/refactor authorization applies.
Proceed to one actual W4 replacement: approximately5–10min,1200s bound incl cleanup,
seven-sample preflight; original financial/exact-once assertions remain mandatory.


### W4-READY02 — current restore Passed, 2026-11-17

Replacement W4 Passed154.124s including120s preflight/cleanup. Actual dump/restore,
canonical/RLS match, replay21episodes/58evidence, expired claim1→0 with economic digest
unchanged, integrated recovery/exact retry/0duplicate exit-fill and source unchanged.
Both owned DBs/Redis independently confirmed absent. W4-only readiness harness amendment;
4 focused tests + isolated real-DB regression/Ruff/format/mypy Passed. CURRENT01 retains
Incomplete. AWAKE01 four-hour proof unaffected. Next publication inventory/affected-proof
mapping and final candidate required CI; F17 remains Pending Full Validation.
Evidence: [W4 READY02 result](evidence/endurance20-20261115/w4-ready02-result.md). No Git/CI in this execution scope.
