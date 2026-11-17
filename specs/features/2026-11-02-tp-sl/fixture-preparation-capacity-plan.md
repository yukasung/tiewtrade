# NC-F17-PREP20-01 — bounded preparation-capacity check

สถานะ: **Approved — owner instructed เริ่มทำ2026-11-16 after replacement proposal**
Existing F17 amendment/branch. Engineering implementation details recorded before source.

## Scope / immutable requirements

Correct the fixture preparation method,not rebuild60s or tradingrules. One campaign:
20syntheticowners,20baseline orders/owner,6original5-commandcycles/owner =600commands,
240fills/120cancels/120replays/120cycles. Existing exact Money/Quantity/cash/reservation/
held/cost/global/idempotency oracles,no owner/Live data/orders or changed admissionrules.
This is preparation throughput diagnosis,NOT D20's fixed5min/offeredrate/HTTPprocessing
acceptance,NOT96000history/fullrebuild/W3/Release. Preserve REBUILD20-01Incomplete.

One120s/7sample preflight before ownedfixture. Expected6–10min afterharness/testsready,
cap720s frompreflight inclmigration/seed/verification/ownedcleanup. One run,no automatic
replacement/fullhistory/4h/Git/CI. No guessed minimumthroughput acceptance: report actual
baseline/cycle/cleanup time and assess nextprofile budget from evidence. Everycycle's
existing60s limit/poll4 remain. Fail/stopIncomplete on error or unsafe/incompleteproof.

## Implementation / reuse

Add explicit parallel_runtime=False option to prepare_economics. Defaultsingleworker/
1Hz/fourflows unchanged. True selects existing20separate worker processes,R8limit20/
claim1/claimcoordination,20ownerfixtureflows and10Hz publicpublisher cadence. Reuse
start_worker_processes/stop_worker_processes and worker metrics/pool protocol,not a
newworker implementation. Start each owned process through sameexisting helper with
uniquegroup/metrics;remember it immediately,so partialstartup cannot orphan siblings.
Touch allownedstop paths,then join/stop all via existing boundedowned-process helper.
Never stop otherprocesses/services or FORCEdrop. Monitor earlyworkerexit and publisher
errors;sourceguards/fencing/no-retry remain unchanged.

Publisher records only actualnormalcommit as before;10Hz uses declaredschedule;
no simulatedclock,readyoverride,delay/reacquire/retry. Keep bounded500record journal.
Save partialcounters/runtime/PIDs/metrics on failure with existing partialreceipt
helper,after ownedmutatorsjoin,so Interrupted does not lose allcounts. Parentresource
sampler receives ownedchildlist and existingPIDregistry,not fabricatedRSS.

Reuse aggregatepoolvalidator rather than duplicate weakerchecks. Add trusted,strict
boolean rebuild_fixture selector for fixed5-pool parentinventory;originaldefault13
inventory and lease/fence flags unchanged. Reject mixingfixture and observerprofiles.
Use same sharedselector for observe+validate. Workerinventory always original2pools,
all20receipts/PIDs/finalborrows mandatory;no self-declared inventory or missingreport
waivers. Existing rawInterrupted poolreport remainsFailed.

## Validation and sequence

Feature: defaultpath regressions;strict options/cadence;actual20process small2owner
fixture withoracles/journal/history/fullreplay and allworkerpools;earlyexit/partialstartup/
shutdown/cancellation/partialcounters tests;default/observer poolregistry negatives.
Run smallest affected tests plus scopedRuff/format/mypy/whitespace. Keep existing
unchanged decoder/replay safety proofs. No mock replaces actualPG/process proof.

After checksPassed,pin source/config/schema/copiedrunner. Fresh ownedDB,noRedisneeded,
existinghealthyservices only. Baseline then6cycles full20owners,join allmutators,
financial/global/counter checks,workerexit+pool evidence and resourcechecks. Keep actual
source lag and require original<=20/nonnegative;no latency exclusions or tradingretry.
IndependentDBconnection/lock/cleanup proof afterdispose;retainresource on unsafecleanup.
Report result and nextscope;do not automaticallyprepare282cycles/96000history or4h.

## Development finding / engineering adjustment before implementation

Firstexpanded safety run72Passed/1Failed:worker acceptance_profile=internal20 correctly
selected TransactionalRiskPolicy and rejected RISK_SOURCE_UNAVAILABLE,because this
F15economicfixture does not claim/provision integratedrisk/HTTP runtime. Do not change
internal_worker_options or bypass its realguard. The approvedfixture already uses
existing AllowPaperPolicy;retain that only inside strictisolatedfixture context.

Add a thin fixture-only CLI wrapper in profile_rebuild20 that validates local matching
ENGINE/ENGINE_SCAN internal20 DB URLs and fixedR8/coordination flags,then calls original
run_worker_process with existing F15fixturepolicy and workerpool tracking. Add strict
rebuild_fixture=False selector to reusedlauncher for this wrapper only;reject mixing
with acceptance/diagnosticprofiles. Ordinaryworker/profile policy/defaults unchanged.
This is not a newworkerimplementation/service or risk/admission acceptance result.
Retain failedsafetyreceipt;retest actual20processfixture before timedcampaign.

## Safety readiness before the single timedcampaign

82affectedtestsPassed in32.865s inclfreshDBsetup/cleanup:actual20process standalone
fixture withfinancial/RLS/source/fullsmallreplay and21poolreports;defaultpath,
partialstartup/unknowncommit/journal/IO/repeatedcancel,worker role/entry isolation,
launcherflags and existing/default/observer poolregistry regressions. Failedfirst
safetyreceipt72Passed/1RiskSourceUnavailable retained;no guardwasweakened. Five-file
Ruff/format/mypy/whitespacePassed. Specializedwrapper calls originalF15workerloop,
ordinary internal_worker_options and productionriskpolicy unchanged. Finalteststyle
context consolidation leaves assertions/behavior unchanged;staticverified.
Onepreflight/freshDB/600command capacityrun nowauthorized;no fullhistory/4h follow-on.


## NC-F17-PREP20-01 execution checkpoint — 2026-11-16

[Scoped preparation check Passed](evidence/endurance20-20261115/prep20-checkpoint.md):
600/600 commands, 400 baseline orders, 20 financial oracles and 21 pool reports passed.
182.374s total including preflight/cleanup; preparation 54.254s. Source unchanged;
normal owned cleanup independently confirmed, no workers/connections/locks remain.
82 affected safety tests and scoped Ruff/format/mypy passed; earlier failed safety
receipt retained. This uses fixture-only policy and 10Hz book+price publication, not
integrated W3 admission or one-Hz price cadence. Not D20/full-history/full-rebuild/W3
acceptance; no linear duration extrapolation. Prior Incomplete grades and F17 status
unchanged. One approved campaign ended; next owner code review, no automatic full-history/
four-hour run or Git/CI.


## Review fixes M1/M2 — authorized engineering amendment, 2026-11-16

Owner instructed แก้ไข after review. Before source edits: M1 found unbounded waits
following child termination, including the reused helper. Keep ordinary worker behavior
unchanged; bound the fixture call to that helper, then independently terminate/join only
remembered children within a second bounded window. Continue through per-child signal
errors, retain the primary exception, and report remaining PIDs as Incomplete; no force
DB drop or other-service action. Add stuck-child/signal-error/primary-retention tests.
M2 found executable external launcher helpers outside the pinned inventory. For future
runs, require an explicit expected SHA-256, copy exact verified bytes into the campaign
root exclusively, and execute selected functions only from that pinned copy. Record the
helper digest before execution. Negative tests must reject mismatch before execution.
Preserve the original runner and historical Passed capacity result with this provenance
limitation; do not retroactively claim the dependency was pinned. Prepare a revised
runner separately without running it. No workload/4h/Git/CI in this fix scope. Use scoped
Ruff/format/mypy and targeted lifecycle tests; unchanged real-DB financial proofs retained.


2026-11-16 [PREP20 review fixes M1/M2](evidence/endurance20-20261115/prep20-review-fixes.md):
bounded fixture-only worker shutdown including startup failures; independent per-child
termination and retained remaining-PID/primary-error evidence. Verified external helper
copy/hash before execution in a separate future runner, original runner unchanged.
32 targeted tests/scoped three-file Ruff/format/mypy Passed; retained prior real-DB
proof within original scope. Historical capacity result has external-helper provenance
limitation, not retroactively repaired. No workload/fullrebuild/4h/Git/CI. F17 status and
prior Incomplete unchanged. Await owner refactor decision before that next step.


## Owner-authorized review-fix refactor — 2026-11-16

Owner instructed refactor the code. Scope only M1/M2 additions: flatten the shutdown
loop's exited-child branch without changing signal/error ordering; reuse one blocking
coroutine in shutdown fault tests and consolidate hashlib imports. No new abstraction,
timeout/policy/exception/evidence behavior change. Run the existing 32 affected tests
and scoped Ruff/format/mypy/whitespace; retain unaffected real-DB and historical campaign
proofs with their stated limits. Validation follows automatically; no timed campaign,
full rebuild, four-hour run or Git/CI under this amendment's stop/report scope.


2026-11-16 PREP20 owner-authorized M1/M2 refactor complete: flattened shutdown loop,
reused blocking test coroutine, consolidated imports; behavior/assertions unchanged.
32 affected tests/scoped Ruff/format/mypy/whitespace Passed. Impacted validation complete;
no timed campaign/fullrebuild/4h/Git/CI. See evidence/endurance20-20261115/prep20-review-fixes.md.
Next bounded representative full-history/rebuild scope requires explicit start; F17
not Completed and historical Incomplete/provenance limitations unchanged.
