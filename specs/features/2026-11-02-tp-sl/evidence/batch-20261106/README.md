> **Recovery notice — 2026-11-06:** the original `/tmp/tiewtrade-paper-set4-20261106`
> worktree disappeared before the next approved diagnostic. Source and this historical
> narrative were reconstructed from recorded file edits on base `98ff2f8` in the durable
> sibling `TiewTrade-paper-set4-recovery`. Original raw JSON/XML/log artifacts referenced
> below are unavailable; they have not been regenerated or represented as verified files.
> Retained PostgreSQL scratch databases still exist. New verification is recorded separately.
> Current approval remains valid; F-17 remains Pending Batch & Release Validation.

# Paper Trading Set-4 validation — 2026-11-06

Status: Partial / Failed — Pending Full Validation. Latest consolidated checkpoint
and the remaining completion blockers are recorded at the end of this ledger.

Candidate: `98ff2f840fe08dc46ab5eb9976f17bdf32b062b1`, merged F-17.
Isolated worktree/branch: `/tmp/tiewtrade-paper-set4-20261106`,
`validation/paper-set-4-20261106`. The initial checkpoint had no runtime/harness
modifications; subsequent approved changes and candidate hashes are recorded below.

## Existing evidence reused

- [Post-merge CI](https://github.com/yukasung/tiewtrade/actions/runs/42063166018):
  all six jobs passed on the exact candidate tree; backend4335 tests, frontend
  lint/types/tests, API contract, containers and cross-feature browser E2E.
- This closes the previously pending required-CI checkpoint of F-17 V-17;
  it does not close workload acceptance or pending Release dependencies.
- Existing Feature protection tests prove protection scenarios; they do not
  establish a protection workload rate or substitute for F-15 volume/SLA.

## Scope and schedule

Use `backend/tests/infra/execution_market/profile_workload.py` unchanged,
F-15 validation section6, profile `F15_W1_W2_W3_V2`:
- W1: 100 owners ×20 baseline orders, 36 cycles/owner, 10 commands/s,
  30-minute measured interval; 20 worker processes as in prior nominal evidence.
- W2: same baseline, 120 cycles/owner, 100 commands/s, 10 minutes;
  overflow/slow-consumer fault phase remains separate.
- W3: separate continuous4-hour phase using the existing pinned fault schedule;
  retain all rates/oracles/resource bounds. Do not shorten to fit the normal window.
- W4: existing `profile_restore_fixture.py` / `profile_restore.py`, fresh source
  and separate restore databases. F-15 coverage only; no F-17 history claim from
  a restore verifier whose table manifest predates F-17.

Initial W1/W2/W4 estimate: 1–2 hours including setup/analysis. W3 is a separate
4-hour phase. Failures require diagnosis before retries or subsequent phases.

## Preflight

Fresh database: `tiewtrade_batch4_w1_20261106` on the existing development
PostgreSQL16 container; existing Redis only. Database roles are set explicitly.
See `preflight.json`, `source-hashes.json` and `migration.log` for resource limits,
background containers, source identity and successful migration evidence.
No Live orders, exchange credentials or production activation.

## Open profile dependency

**Needs Clarification NC-SET4-01** is recorded in mission section9.
F-16 V-20 explicitly requires an approved integrated release profile, and F-14
V-17 does not specify its workload size/budget. No approved protection workload
composition was found. Stop these affected acceptance paths; do not invent
trade mix, workload rates, duration or acceptance thresholds. The owner explicitly
selected A on2026-11-06: run the existing standalone F-15 W1–W4 first, then prepare
the missing integrated F-14/F-16/F-17 profile for approval. F-17 V-18 remains
Pending Full Validation until that separate profile and acceptance are complete.

Release F-17 V-19/V-20 remain Pending Dependency / Full Validation.
No commit/push/merge is performed for this new validation checkpoint.

## Results

| Criterion | Result | Evidence / limitation |
|---|---|---|
| Full regression/cross-feature E2E | Passed on exact candidate | Reused post-merge CI above; no affected source/dependency/contract/harness changes |
| F-15 W1 | Failed / Partial | Baseline100x20 complete; positive cycle exceeded60s during final MARKET SELL status polling; only17 cycles completed before failure |
| F-15 W2 / overflow | Not Run | Hold higher-load phases pending W1 diagnosis; no acceptance claim |
| F-15 W3 | Not Run | Hold4-hour endurance pending W1 diagnosis; duration/criteria unchanged |
| F-15 W4 | Passed on schema0064 | Existing F-15 restore fixture/verifier; no F-17 history coverage claim |
| F-14 V-17 / F-16 V-20 / full F-17 V-18 | Pending Full Validation | NC-SET4-01 profile dependency plus failed W1; no integrated acceptance claim |

### W1 failure and read-only inspection

- Whole process651.694s including baseline setup; see `w1-process-result.json`.
- `f15-w1/failure.json`: offered329, admitted327, completed229, rejected0,
  fills98, cancels31, replays50, cycles17. These are failure-time counters,
  not completed30-minute totals or a successful final financial oracle.
- Trace ends at `profile_workload.py:1309` final MARKET SELL → `wait_status`
  → user-session checkout → pool wait, canceled by the enclosing60s cycle bound.
  Pool wait at failure is proven; the complete cause of the delay is not proven.
- Publisher remained active and no worker failure was recorded.13 resource samples
  observed connections<=65 with max_connections100, no sampled lock waits, and
  peak aggregate RSS739606528bytes. Sampling does not exclude short contention
  intervals or prove the parent pool was healthy at the failed checkout.
- The transaction percentile samples in `w1-post-stop.json` span setup plus the
  short measured window, using the existing F-15 percentile function. They are
  diagnostic observations, not a complete warm30-minute SLA acceptance result.
- `w1-post-stop.json`: PENDING2110/TERMINAL167 dispatch rows. Post-stop checks found
  zero negative reservations/positions, unlinked fills, duplicate fill effects and
  non-Paper activity. DB111FILLED differs from failure-time counter98: the snapshots
  have different cutoffs and workers were stopped after the failure. No successful
  final cycle/PnL oracle is claimed. No workload worker process remained after cleanup.
- Retain this database and raw logs. Do not increase pool limits, alter progress
  bounds, rates, quantities, financial rules or assertions to make the test pass.
- Next diagnostic can reuse the existing `PoolEvidence` from the risk workload
  harness to distinguish parent checkout waits, owner-lock/transaction time and
  worker/dispatch progress. This is a recommendation, not implemented or rerun.

### W4 current-schema evidence

- Fixture and restore process7.418s combined, both exit0; see `w4-process-result.json`.
- `f15-w4-restore/result.json`: PASSED; coverage capital4/fills3/partial1/cancel1/
  correction1/reset1/evidence22/expired-claim1. Source database:
  `tiewtrade_f15_w4_source_20261106`; restored database:
  `tiewtrade_f15_w4_restored_20261106`.
- Canonical digest and RLS/grants match;4owners/3checkpoints/2positions replayed.
  Expired claim recovered1→0 in2 rounds; recovery economic effects unchanged.
- Backup1701583bytes retained. F-17 tables are not populated by this F-15 fixture;
  the old verifier's explicit digest list is not evidence for protection history.

Checkpoint remains Failed/Partial, not Completed. W2/W3 were not retried or started;
runtime and test/harness source are unchanged. Next work is diagnosing W1 before
another workload attempt; integrated-profile preparation remains pending.

Final source verification:275 captured source/harness/lock/config file hashes match
preflight exactly. Documentation diff whitespace check passed. No new lint/type/test
run is needed for these documentation-only updates; the workload evidence is above.

## Owner-approved harness diagnostic — 2026-11-06

Owner selected A after the W1 failure: add test-only observations of pool wait,
transaction/lock and worker progress before another W1 attempt. The original W1
and W4 evidence above is retained unchanged; this is a new checkpoint.

Implementation:
- Opt-in `--diagnostics` in the existing F15 parent/worker launcher; disabled by
  default and limited to W1 for the parent. No production source changes.
- Reuse existing `TransactionTrace`, `operation_scope`, `worker_pool_evidence`
  and `traced_worker`. Parent records generator phase/owner/order UUIDs; workers
  record scan/claim/process timings and actual pool inventory.
- Trace activation follows baseline setup, at measured workload start.180s trace
  window; W1 still targets1800s,100owners,20baseline orders,36cycles/owner,10commands/s,
 20workers and the original60s cycle bound. All assertions/oracles remain intact.
- Existing `sample_database` samples PostgreSQL activity read-only every2s through
  the existing migrator engine for at most180s. Missing cross-role metadata stays
  unknown. TaskGroup cancellation joins both resource observers.
- Instrumented output is explicitly `acceptance_result:false`, even if the profile
  completes. No pool enlargement, business/financial SQL change or Live execution.

Verification:
- `diagnostic-validation.xml`: initial26 tests passed12.16s.
- `diagnostic-final-validation.xml`: final27 tests passed11.99s, including real
  worker CLI, disabled path, pool-wait cancellation, observer cancellation/join,
  error/SQL-parameter redaction, factory/listener restoration and untouched old output.
- Ruff/format passed; scoped strict mypy passed for all3 affected Python files.
  Initial type errors in the added tests were corrected before this final check.

### New diagnostic attempt blocked before execution

The shell could not create its here-document temporary file: `no space left on
device`. Python/bootstrap/workload execution did not begin. The reserved new
database name is `tiewtrade_batch4_w1_diag1_20261106`; no diagnostic workload result
exists. Do not count this as another W1 failure or as completed diagnostic evidence.

Read-only environment checks:
- Initial host free space approximately117MiB on a228GiB APFS volume at100% usage.
  Later free space approximately2.3GiB, without deleting data in this task.
- Docker VM files occupy approximately110GiB; this does not identify disposable data.
- Docker inventory requests failed with timeout/HTTP500. A bounded health check
  returned `Docker Desktop is unable to start`; see `diagnostic-environment.json`.
- Original failed W1 did not record disk headroom. The later disk/Docker failure
  does not prove the cause of that earlier workload timeout.

The instrumentation is verified, but the new diagnostic run is Not Run / Environment
Blocked. Preserve databases, volumes and raw evidence; do not prune them. Recover
Docker/host capacity before retrying the unchanged diagnostic command. W1 remains
Failed/Partial; W2/W3 Not Run; W4 Passed. No commit/push/merge performed.

Recovery attempt: `docker desktop start --timeout 20` reported already running;
`docker desktop restart --timeout 30` failed to stop backend processes4051/4052/4053
before its deadline. A subsequent Docker health check reported a missing socket.
No reset/prune, volume removal or force kill was performed. Further force quit
would affect Docker outside this test and requires an explicit owner choice.

`diagnostic-code-identity.json` verifies48 existing F15 function/class definitions
unchanged, plus hashes of changed/reused instrumentation; production source diff
is empty. The old275-hash verification above belongs to the pre-instrumentation
checkpoint, not this new test-harness diff.

### Owner-authorized Docker recovery and diagnostic launch

Owner explicitly selected A: force quit Docker backend, restart, verify health and
disk capacity, then run W1 without reset/prune/volume deletion. Revalidated backend
identities before terminating4051/4052/4053 and reopening Docker normally. Docker
API recovered; PostgreSQL accepts connections and Redis responds PONG. The original
W1 dispatch counts and W4 restored database remain; the diagnostic database had
zero public tables before bootstrap. See `diagnostic-environment-recovered.json`.

Docker VM reports104GiB available; host headroom is only around1.9GiB and is monitored.
No images, build cache, containers, databases or volumes were removed. Original failed
W1 and passed W4 artifacts remain untouched.

The first actual diagnostic W1 has now started on fresh migrated database
`tiewtrade_batch4_w1_diag1_20261106`, output `f15-w1-diagnostic-1/`.
`diagnostic-1-command.json` and `diagnostic-1-source-hashes.json` freeze argv/role
database bindings/source hashes and48 unchanged financial/workload definitions.
The earlier shell/Docker block was not a workload attempt. This instrumented run
is non-acceptance evidence; its result is pending until the process ends.

### Diagnostic W1 result and findings

`diagnostic-1-process-result.json`: exit1,578.519s including full100x20baseline;
failure approximately175.167s after the measured control file was written.
`f15-w1-diagnostic-1/failure.json`: TimeoutError at the unchanged60s whole-cycle
bound, this time while sleeping between final MARKET SELL status polls. Counters:
1438offered/1435admitted/1338completed,0rejected,532fills,260cancels,273replays,
235completed cycles. This is a diagnostic failure, not30-minute acceptance.

Evidence analysis (read-only; no subsequent workload):
- `diagnostic-1-trace-analysis.json`: parent and all20worker transaction streams
  closed without truncation. `diagnostic-1-summary.json`: all pools finalized with
  zero checked-out connections; no workload worker process remained.
- Parent performed27311 wait-command/status transactions. Their aggregate pool-wait
  time was78.9% of aggregate transaction duration (overlapping tasks, not wall-time
  utilization). ENGINE pool reached its existing15connections. Individual parent
  pool waits peaked around1.666s, not60s; final timeout is not evidence of a single
  minute-long checkout. The cycle spans several serial command/admission/fill waits.
- Worker claim calls48475:3734claimed and44741skipped (92.30%). Successful-claim
  phases included2637ACTIVE,838PENDING and260CANCEL process calls. Counters have
  slightly different completion cutoffs. Claims returningNone can reflect busy/
  stale/CAS conditions; exact split is not proven. Do not remove these safety checks.
- `diagnostic-1-findings.json`:84 PostgreSQL activity samples, maximum65connections
  excluding observer; at most1blocked session observed. Cross-role state/wait details
  are mostly unknown/null, so this does not exclude lock contention.
- `diagnostic-1-post-stop.json`:2000baseline LIMIT BUYs retained; pending13CANCEL,
  51NEW/PENDING and other active work;8MARKET SELLs remain ACCEPTED. Maximum owner
  input lag74. Zero duplicate fill effects, unlinked fills, negative reservations/
  positions or non-Paper activity in this post-stop snapshot. No completed-run
  financial/PnL oracle is claimed.
- `diagnostic-1-pending-cycle-timelines.json` correlates the8SELLs to cycle2 and
  their prior BUY/LIMIT/CANCEL/SELL command timestamps. Final SELL polling spans
  were only0.13–8.56s; earlier serial stages consumed the rest of their cycle time.
  General per-order poll spans in trace-analysis can combine ACCEPTED and CANCELED
  waits for a LIMIT order; they are not single-call wait durations.

Interpretation: parent polling/pool pressure and many non-claiming worker transactions
are demonstrated contributors worth investigating, not proof of one complete root
cause or proof that increasing pools/changing scheduling fixes W1. Worker budgets
in the approved standalone profile remain unchanged. F15 plan explicitly keeps
standalone20/no claim budget, so adopting F18 scheduling would require approval first.

Environment limitation: host free space fell from about1.9GiB to699MB during the
run, later recovered partly without task deletions. Docker VM still has substantial
logical free space; host thin-disk headroom is the concern. The130MiB diagnostic
trace and Docker/data growth occurred under this pressure. Its effect on latency
has not been isolated, so no further performance run is started in this environment.

`docker-build-cache-inventory.json` records only safe cache metadata, not command
descriptions. Docker reports roughly12GB reclaimable build cache; containers/images/
volumes were not removed. Owner's no-prune constraint remains in effect until an
explicit new decision. Next: recover host capacity before any additional diagnostic;
then choose a narrowly approved harness/scheduler investigation from this evidence.

Original W1 remains Failed/Partial; diagnostic W1 also failed; W2/W3 Not Run and W4
Passed. Runtime source, rates/quantities/progress bounds and assertions are unchanged.
No commit/push/merge; F17 integrated-profile dependency remains open.

### Owner-approved build-cache cleanup and controlled repeat

Owner explicitly allowed removal of unused Docker build cache only, overriding
the earlier no-prune constraint for that cache. Ran `docker buildx prune --force`
without `--all`, system/image/container/volume prune, database deletion or reset.
Docker reported11.95GB reclaimed; host free space increased from about604MiB to
about12GiB. See `docker-cache-cleanup-before.json`, `docker-cache-prune-process.json`,
`docker-cache-prune.log`, and `docker-cache-cleanup-after.json`.

Before/after inventories:94distinct image IDs,62container IDs,139volumes and
27databases retained; no removed IDs/names. PostgreSQL accepts connections and
Redis returns PONG. This cleanup is complete; it is not a workload pass.

One controlled repeat of the unchanged diagnostic W1 is planned on a new database
to separate the observed low-host-space condition from the persistent polling/claim
pressure. Preserve diag1; same source/profile/pools/workers/assertions and180s trace
window, no code changes. Record new host headroom, outputs and limits. Do not keep
retrying if this repeat fails; report a checkpoint before any further experiment.

### Controlled repeat after cleanup — failed checkpoint

`diagnostic-2-command.json`: same344source hashes, fresh schema0064 database
`tiewtrade_batch4_w1_diag2_20261106`, identical W1 argv except output path/database;
no production/harness code or profile/pool/claim-budget changes.

`diagnostic-2-process-result.json`: exit1,1194.489s including full100x20baseline.
The unchanged60s whole-cycle bound expired during final MARKET SELL status polling
at approximately783.956s measured. Failure counters:7516offered/7511admitted/
7416completed,0rejected,2963fills,1469cancels,1491replays and1450cycles. The18000
commands/3600cycles/30-minute criterion did not complete. Diagnostic is non-accepting.

Environment and evidence:
- Host free space was12.48GB before and12.99GB after; all recorded headroom samples
  stayed above12GB. Timeout recurred despite restored capacity. Low space therefore
  does not fully explain W1; differences in progress are not proof of a specific fix.
- `diagnostic-2-analysis.json`:21transaction streams closed untruncated; all tracked
  pools finalized with zero checked-out connections.152resource samples observed
  peak66connections and aggregate RSS801472512bytes. No workload worker remained.
- Early-window worker calls:56292claim attempts,4342claimed/51950skipped. These are
  first180s observations, not proof of the phase that caused the later timeout.
- Detailed transaction trace ended03:34:06UTC; failure occurred03:44:10UTC. The last
  roughly10minutes are outside the opted-in trace window. Full-cycle timing and
  failed owner/order identity are not available from the final traceback alone.
- Post-stop read-only snapshot:2000baseline LIMIT BUYs retained;4MARKET SELLs remain
  ACCEPTED, other queued work remains. Zero duplicate fill effects, unlinked fills,
  negative reservation/position values and non-Paper activity. No completed-run
  PnL/balance oracle is claimed.344source hashes still match the pre-run snapshot.

This is the third failed check of the same W1 progress criterion (initial run,
diag1, controlled diag2). Stop under AGENTS.md before another experiment. Preserve
all Failed/Partial results; W2/W3 remain Not Run, W4 Passed0064, and F17 integrated
profile remains pending. Cleanup is complete; Batch validation is not complete.

### Proposed next options — awaiting owner choice

A (recommended): add failure-only per-cycle phase timing/owner/order identity to
the existing test observer, then correlate it with a bounded read-only queue snapshot
after workers stop. Keep at most one active cycle record per owner and use existing
operation contexts/observers. No full-run SQL trace, new infrastructure, pool increase,
new role/grant, scheduler/business change, rate/quantity/deadline relaxation or NEW
retry. Test preservation of original cancellation/TimeoutError, cleanup and redaction
before one further explicitly authorized diagnostic. This targets the identified
missing failure-window evidence rather than repeating the same observation blindly.

B: pause further standalone workload experiments and prepare the missing integrated
F14/F16/F17 validation profile for owner approval. Keep existing W1 failures and all
pending W2/W3/integration criteria; do not claim the new profile closes the old one.

No option is implemented or run without the required owner decision after3failures.
No commit/push/merge was performed. Cache cleanup removed no protected data.

### Failure-only timeline — owner approved and verified

Owner selected A after the3-check stop: capture phase timings and owner/order for
the actual expired cycle, then take a post-stop queue snapshot. This authorizes
one new diagnostic with original profile/pool/scheduler, not a trading-rule change.

Implementation remains test-only:
- Reuse `run_scheduled_cycles`' existing `cycle_scope` hook with the identical
  `asyncio.timeout(60)` budget. Standard scheduler/body definitions are unchanged.
  An expired budget is distinguished from sibling cancellation or an inner error.
- Existing operation contexts collect up to32nested phase entries per active cycle,
  with UUID identities/status labels/timestamps only. Successful cycles are discarded;
  only genuinely expired cycles write `cycle-timeouts.json`. No per-step file writes
  or raw payload/error-detail logging. Observation-write errors do not replace timeout.
- After `_run` has stopped workers and disposed its engines, reuse ENGINE_SCAN and
  `read_scheduler_diagnostics` for bounded owner/queue and selected-command snapshots.
  The new selection is limited32IDs, owner-filtered and read-only; default diagnostic
  output remains unchanged. No new roles, grants, infrastructure or runtime pool changes.
- SQL transaction tracing still covers only the first180s. New failure-only timelines
  fill the later-window gap without full-run transaction tracing.

`failure-timeline-validation.xml`:38 targeted tests passed13.05s. Includes actual
scanner-role selected/default read-only checks, original timeout/error propagation,
sibling cancellation, completed-cycle discard, bounded retention, redaction, observer
restoration, snapshot ordering after cleanup and reader/write failures. Ruff/format
and scoped strict mypy (five affected/caller files) passed. No new production source.

Next is one fresh diagnostic W1 using the unchanged100x20/36cycles/10commands/s/
20workers/30-minute profile and60s progress bound. Preserve all prior failed runs.

The authorized follow-up is now running as `f15-w1-diagnostic-3/` on fresh schema0064
database `tiewtrade_batch4_w1_diag3_20261106`. `diagnostic-3-command.json` records
unchanged argv/profile and the four approved observer/helper/test file changes;
`diagnostic-3-source-hashes.json` freezes the344files.48 existing F15 financial/
workload function/class definitions still match the base. No production source diff.
The instrumented run remains explicitly non-accepting; final result follows.

### Failure-only timeline result — captured, W1 still Failed

`diagnostic-3-process-result.json`: exit1,574.266s including setup. All100x20
baseline orders were prepared. Failure counters:1388offered/1388admitted/
1288completed,0rejected,500fills,252cancels,268replays and215completed cycles.
This does not complete the18000commands/3600cycles/30-minute criterion.
Host free space after the run was14816460800bytes. No further workload was run.

The new observer captured exactly one expired cycle (cycle2 for owner
`d44168cb-3554-4881-85c4-c2852f9d0559`), with17untruncated phase entries:
- MARKET BUY23.992s, LIMIT SELL9.241s, replay/cancel about7.4s, final MARKET
  SELL19.369s before the unchanged60s whole-cycle deadline expired.
- Across sequential waits, command-result waits total36.757s and order-status
  waits21.548s. Nested phase timings overlap and must not all be added together.
- The four command processing transactions began about13.127s/8.558s/6.674s/
  5.862s after their DB request timestamps. Parent command-result observation
  followed worker commits by about0.11–0.28s. Admission delay therefore occurs
  mainly before worker execution in these commands, rather than after commit.
- Final SELL fill event/input timestamps precede the deadline, but its financial
  transaction committed about0.187s after it. Event time is not commit visibility;
  graceful shutdown subsequently completed the in-flight work.

Evidence: `f15-w1-diagnostic-3/cycle-timeouts.json`,
`diagnostic-3-failed-owner-analysis.json` and `diagnostic-3-db-timeline.json`.
The post-stop `timeout-queue-snapshot.json` succeeded using the existing scanner
role; all four selected commands were TERMINAL after workers stopped. Source
readiness in this snapshot does not prove readiness throughout the failed cycle.

`diagnostic-3-claim-branch-summary.json` matches the actual compiled SQL hash:
45745committed claim transactions comprise30481owner try-lock misses,
11697UPDATE paths returning no claim, and3567successful claims. The exact split
among due/stale/lease/busy/CAS guards in the second group remains unknown. This
shows contention/redundant attempts; it does not justify removing any safety guard
or prove a particular scheduling adjustment will meet the workload criteria.

`diagnostic-3-cleanup-analysis.json`: all21transaction streams closed untruncated;
all21pool reports finalized with zero checked-out connections. No workload worker
remained. Post-stop financial checks observed zero duplicate fill effects, unlinked
fills and negative reservations/positions. This is not the completed-run balance/PnL
oracle. All344source hashes still match; production source diff is empty.

The authorized diagnostic subtask is complete:38targeted tests, Ruff/format and
scoped mypy passed before this run. W1 remains Failed/Partial, W2/W3 Not Run and
W4 Passed0064. F17 integrated profile remains blocked by NC-SET4-01. No commit,
push, merge, trading-rule change or Live order occurred.

Next decision: [proposed standalone worker budget amendment](../../../2026-10-18-paper-order-matching/standalone-worker-budget-amendment.md).
Option A reuses the existing R8 successful-claim budget in an explicitly different
opt-in runtime and requires approval of that acceptance mapping. It does not cap
claim-None attempts. Option B retains the original20/no-budget runtime as mandatory
and prepares another plan. NC-SET4-02 blocks either runtime change or another
workload using the proposed runtime until the owner decides. No proposal is implemented.

### Standalone R8 opt-in — owner approved and started

Owner selected A on2026-11-06, including the explicitly different candidate runtime
for remaining F15 V19 W1–W4. The amendment/plan/validation and NC-SET4-02 were updated
before implementation. Prior20/no-budget failures remain Failed. NC-SET4-01 for
integrated F14/F16/F17 coverage remains open and does not block this standalone check.

Only test harness configuration changed: `--r8-claim-budget` forwards `claim_limit=1`
to the existing worker through initial/overflow recovery/restart paths, including
optional observers. Default staysNone. A non-None claim consumes the budget before
commit even after later failure/defer; claimNone skips do not. Manifest records
`F15_STANDALONE_R8_OPTIN_V1`, scan20/claim1/tick20ms separately from the unchanged
`F15_W1_W2_W3_V2` fixture/capability digest. No new financial/scheduling algorithm,
production default, pool/process increase, retry or infrastructure was introduced.

`r8-safety-validation.xml`:84passed/2failed of86tests in16.106s pytest time
(16.813s whole command). Both failures were new CLI test annotation evaluation,
not runtime/DB safety failures. Postponing annotations fixes that Python3.12 runtime
issue. `r8-cli-validation-final.xml`: all10tests in that affected module passed
1.222s; unaffected84results remain valid. Ruff/format and scoped mypy passed.
`r8-checks-summary.json` maps the safety/config coverage and scoped review. No
production source diff;48existing financial/workload definitions still matchHEAD.

W1 was announced as30minutes measured plus setup, approximately40–50minutes total.
`r8-w1-preflight.json` verified all8role URLs connect to the same fresh schema0064
database `tiewtrade_batch4_w1_r8_20261106`, with zero users/orders/commands before
setup;100max connections and host headroom retained. `r8-w1-source-hashes.json`
freezes345source files. `r8-w1-command.json` records the exact unchanged100×20,
36cycles/owner,10commands/s,20workers parameters plus the approved opt-in flag.
No `--diagnostics`: this is a full acceptance attempt with original financial,
progress/processing SLA/resource assertions, not a diagnostic-only pass.

Run `f15-w1-r8-1/` finished Failed; see the result below. No commit/push/merge or Live order.

### Approved R8 W1 result — Failed, publisher lease lost

`r8-w1-process-result.json`: exit1,1378.654s (22m58.654s) including baseline setup.
The full2000order baseline completed; measured load started about04:42:08UTC.
At04:59:46.760UTC the publisher raised `WriterLeaseLost` during `renew_writer`.
`with_publisher` propagated that original failure and canceled/joined the cycle
producer. This is not a60s-cycle timeout result. The30-minute/18000command/
3600cycle criterion did not finish; W1 stays Failed/Partial, not Passed.

Failure-time counters:10348offered/10343admitted/10253completed,0rejected,
4095fills/2042cancels/2058replays/2021cycles. In-flight workers completed some
additional work during cleanup; post-stop DB totals must not replace those counters.
`r8-w1-progress.jsonl` contains sparse read-only status counts, not acceptance oracles.

Read-only analysis (`r8-w1-post-stop.json`, `r8-w1-failure-analysis.json`):
- Last persisted BTC price is trade10890 at04:59:40.393791UTC; price feed lease
  ends04:59:45.530089UTC. Error host timestamp is1.230156s after that deadline.
  Book input10899 committed and book lease ends04:59:51.397996UTC.
- Existing `publish_market` renews the book each tick but renews the price writer
  only in its `update_price` branch (one in10ticks under this measured profile).
  Elapsed time between price updates can exceed the nominal1s under pressure.
  The persisted expiry is consistent with late renewal; exact `_locked` guard,
  pool/query/lock timing and DB time at the failed call were not captured. Do not
  claim a proven scheduler cause, silently extend the5s lease or reacquire/retry.
- Existing worker measurements contain46015completed processing transactions:
  p95=0.571253s, p99=0.966796s, max6.622690s. Observed p95 exceeds the unchanged
  0.250s criterion; these incomplete-run samples cannot close full SLA acceptance.
  `r8-w1-observed-summary.json` uses the unchanged percentile/resource functions.
-204resource samples observe peak65connections, zero sampled lock waits,
  peak single-process RSS60817408bytes and buffer4096rows. Sparse zero lock-wait
  samples do not prove absence of waits. Host sampled free space stayed above12GB.
- Post-stop safety counts: zero duplicate fill effects/unlinked fills/negative
  reservations/negative positions/non-Paper activity. Pending dispatch2108,
  including baseline and interrupted work, is preserved. No final balance/PnL
  oracle or recovery-completeness pass is claimed.
- All20worker metric files finalized, no workload worker PID remains, and only
  the read-only observer connection remains in this DB. Cancellation cleanup logged
  connection-termination `CancelledError` and an unhandled `connection_lost` future;
  retain these warnings. They follow the publisher failure and are not erased or
  promoted to the primary cause. All345source hashes match; production diff is empty.

The authorized implementation/safety checks/one W1 trial are complete. Do not run
another workload or W2/W3 after this failure. W4 Passed0064 remains reusable because
schema/fixture/restore paths and default worker mode are unchanged; F17 protection
history and integrated profile remain unproved. Next work needs a reviewed plan
addressing publisher renewal liveness and processing latency before another W1;
any runtime/profile amendment requires owner approval. No new fix or rerun is
authorized by this failure report, and no Git publication occurred.

### Next plan prepared — awaiting owner approval

Owner asked to continue. This step prepares the next concrete amendment only;
no runtime/test source or new workload changed. Offline analysis reuses all20R8
worker metric files: every worker has observed p95 above250ms, range546.463–603.312ms.
`r8-w1-worker-latency-analysis.json` retains input hashes, per-worker counts and
the incomplete-run/recording-scope limitation. No new performance run was used.

[Proposed heartbeat and bounded diagnosis](../../../2026-10-18-paper-order-matching/publisher-heartbeat-diagnostic-amendment.md)
specifies option A (explicit default-off per-book price-writer renewal, no price
freshness mutation, then targeted fencing/supervision tests and one300s diagnostic)
and option B (same diagnostic with original publisher). Both retain100owners,
20baseline orders,10commands/s,20workers/R8, and reuse the existing SMOKE/oracle/
180s trace observers. Six cycles/owner is a proposed diagnostic envelope only,
not shortened W1 acceptance. SQL overhead/observation effects and inability to
prove resolution of a17-minute failure are explicit risks. No production tuning,
full W1 retry, W2/W3 or Git publication is included.

NC-SET4-03 blocks implementation and that new diagnostic envelope until approval.
Next step is the owner's A/B decision; after approval work can continue through
the scoped tests and exactly one diagnostic, then stop with evidence again.
W1Failed/Partial, W2/W3NotRun, W4Passed0064 and integrated NC-SET4-01 are unchanged.

### NC-SET4-03 A — approved, safety checked, diagnostic started

Owner selected A before implementation. The amendment/plan/validation and mission
were marked Approved/closed before changing test code. No production source changed.
`--publisher-heartbeat-per-book` defaults off and requires explicit standalone R8.
Enabled mode renews the existing price writer once after book publication in the
same transaction, even on a book-only tick; the existing price-update branch and
cadence remain unchanged. No TTL/freshness/generation/fence change or reacquisition.
Manifest names `F15_STANDALONE_R8_HEARTBEAT_V1` and records the heartbeat option;
F18/restore defaults remain unchanged. Existing observers now allow SMOKE and label
publisher transactions, retaining180s/row/query bounds and non-acceptance output.

`heartbeat-safety-validation.xml`:89tests passed13.963s pytest/14.527s whole command.
Real PostgreSQL verifies one renewal per tick, unchanged price facts on heartbeat,
expired/stolen generation rollback including book buffer, and expiry during SQL
row/table-lock waits. CLI/default/manifest/R8 requirement, phase forwarding,
supervision/observer cleanup/redaction/non-acceptance and shared claim-budget checks
passed. Ruff/format and scoped mypy7files, including F18 publisher/restore callers,
passed. Scoped review found no issues. See `heartbeat-checks-summary.json`.

Announced diagnostic envelope:100owners×20baseline orders,6cycles/owner,
10commands/s,20workers, nominal300s measured; approximately10–15minutes including
setup/drain. Exact argv in `heartbeat-diagnostic-1-command.json` uses SMOKE,
explicit R8/heartbeat/diagnostic flags. All8role URLs connect to the new empty
schema0064 database `tiewtrade_batch4_hb_diag1_20261106`; preflight records zero
users/orders/commands,100max connections and11.15GB host headroom.346source hashes
are frozen. `f15-heartbeat-diagnostic-1/` is now running; result pending.

Stop after this one diagnostic to analyze/report. No full W1, further diagnostic,
performance optimization, W2/W3 or Git publication follows automatically. All
historical failures and NC-SET4-01 remain; this run cannot close W1 acceptance.

### Heartbeat diagnostic1 — Incomplete, observer control-publication race

`heartbeat-diagnostic-1-process-result.json`: the one authorized run ended after
440.559s (7m20.559s), SIGINT exit-2. Full2000baseline orders prepared; SMOKE load
started, but worker `Recorder.activate` read `dispatch-trace-control.json` before
its JSON was fully published. Three JSONDecodeErrors surfaced in claim handling
for the same command. The final control file is valid JSON; the old writer used
direct `Path.write_text`, exposing the create-before-write interval. Observation
changed the workload, so do not use its timing as a reliable performance baseline.

The exact parent was canceled (`heartbeat-diagnostic-1-stop-request.json`) to run
the existing cancellation/join/disposal path. No further workload started. Original
logs/DB/worker metrics/control/source hashes are retained. `diagnostic-only.json`
records `acceptance_result=false`, CancelledError and zero captured cycle timeouts.
Cancellation bypasses the original `_run` Exception result writer: no final
counters/resources/full financial oracle is available. This is Incomplete, not a
completed smoke, W1 failure due to heartbeat, or proof of the old lease fault's fix.

`heartbeat-diagnostic-1-trace-analysis.json` contains the incomplete100.142s captured
span, grouped transactions/pools/query hashes and limitations. Selected aggregates
are descriptive, overlap across processes and cannot be interpreted as wall time:

| Phase | Transactions | Summed duration | Pool wait | Client SQL | Unattributed remainder |
|---|---:|---:|---:|---:|---:|
| Worker order processing | 3318 | 937.901s | 25.965s | 770.653s | 141.284s |
| Worker claims | 25865 | 788.274s | 206.114s | 454.056s | 128.104s |
| Parent command polling | 6911 | 1095.723s | 790.681s | 236.484s | 68.558s |
| Publisher | 826 | 94.817s | 12.404s | 67.621s | 14.793s |

Client SQL duration includes unseparated server/network/lock waits; remainder is
not identified as commit time. Missing cross-role wait metadata stays unknown.
Do not select a production optimization or report a causal R8/heartbeat speedup
from these perturbed partial observations.

`heartbeat-diagnostic-1-cleanup-analysis.json`: all21trace streams closed untruncated,
all21pool reports finalized empty; all20worker metric files present. No workload
worker PID remains; only the read-only observer DB session remains. Post-stop
zero duplicate fill effects/unlinked fills/negative reservations/positions/non-Paper
activity; dispatch2082PENDING/634TERMINAL, orders324FILLED/161CANCELED/2034ACCEPTED.
Incomplete pending work and cancellation warnings are preserved. All346source
hashes matched before repair; no production source diff. These snapshots do not
replace complete balance/PnL/latency/resource assertions.

### Scoped observer repair — checked, no replacement run started

This is an implementation defect in the authorized observer, not a new trading or
performance rule. `publish_trace_control` now writes the same JSON through existing
`save` into a same-directory temporary file, then `Path.replace`s the final path,
reusing `publish_runtime_pid`'s pattern. Readers remain strict; no parse-error
suppression, skipped records, bounds increase or business retry is introduced.
An interrupted write propagates while the final path stays absent/unchanged.

`heartbeat-control-publication-validation.xml`:2deterministic cases force actual
Recorder/TransactionTrace reads during an empty pending write and verify successful
or failed publication. `heartbeat-control-integration-validation.xml`:8affected
regression/integration cases passed (2.497s whole command), including actual parent
SMOKE control publication and observer success/failure. Relevant Ruff/format/mypy
passed. Prior unaffected89-test heartbeat/financial/fencing evidence remains valid;
only3harness/test files differ from the failed run, recorded in
`heartbeat-control-final-source-hashes.json`. No runtime performance change.

Next: [replacement proposal](../../../2026-10-18-paper-order-matching/publisher-heartbeat-diagnostic-amendment.md#replacement-diagnostic--approved-a-2026-11-06)
under NC-SET4-04. One fresh replacement uses exactly the approved100×20/6cycles/
10commands/s/20workers/R8/heartbeat/180s trace envelope, then stops/report again;
alternatively stop experiments. The original one-trial permission is consumed.
No second diagnostic/full W1/W2/W3 or Git publication is authorized yet. W1 stays
Failed/Partial, W2/W3NotRun, W4Passed0064 and integrated NC-SET4-01 open.

### NC-SET4-04 — latest A authorizes one replacement

Owner initially chose B, then explicitly selected A before any replacement started.
Latest A supersedes the earlier stop choice. No workload ran between those choices.
Amendment/mission/plan now record approval for exactly one fresh replacement, then
stop/report. This does not authorize a production optimization, full W1 or Git work.

No worker/parent from the prior trial remained. All346source hashes matched the
checked metadata repair, so89heartbeat safety checks and8affected publication/
observer checks plus static results are reused without ritual repetition. Preflight
verified8actual role databases, empty users/orders/commands and schema0064 on new
`tiewtrade_batch4_hb_diag2_20261106`,100max connections and11.12GB host headroom.

`heartbeat-diagnostic-2-command.json` records unchanged100×20/6cycles/10commands/s/
20workers/R8/heartbeat/SMOKE and180s trace settings, with the repaired atomic control
writer. Nominal300s measured; approximately10–15minutes including setup/cleanup was
announced. `f15-heartbeat-diagnostic-2/` is now running; result pending. First trial
remains Incomplete and its partially traded DB is not reused. No runtime change
was made for the replacement. It finished with the result below; no further run follows.

### Replacement diagnostic2 result — observation complete, criteria Failed

`heartbeat-diagnostic-2-process-result.json`: exit1,715.169s (11m55.169s) including
full2000baseline setup and cleanup. SMOKE measured319.447s versus nominal300s;
drain3.433s. Exact workload completed:3000offered/admitted/completed,0rejected,
600cycles,1200fills,600cancels and600replays. Published3018measured book inputs
against3000required. No cycle timeout, writer-lease failure, control JSON error or
worker failure was reported. `diagnostic-only.json` remains acceptance_result=false.

`f15-heartbeat-diagnostic-2/result.json` records Failed, with two unmet predicates:
- Engine processing p95=0.469526s exceeds0.250s; p99=0.895255s is within1s.
  The original worker timer covers25078samples; do not replace its recording scope
  or result with a selected diagnostic subset to turn this into a pass.
- `global_invariants.input_lag`=22 exceeds the resource predicate's20. This makes
  resource_assertions_passed=false even though peak RSS/connections/lock samples
  meet their recorded bounds. Preserve the threshold and failure.

Every owner financial oracle passed:100owners each balance9992.812594USDT,
20accepted baseline orders,12fills/6cancels, reserved quote20, reserved base0,
held quantity/cost0. Global invariants passed with3800orders/1200fills/600cancels,
2000baseline dispatches pending, and zero duplicate fill effects/unlinked fills/
negative reservations/positions/wrong mode. This proves only the declared6-cycle
diagnostic economics, not full W1/F17 integrated acceptance.

Timing evidence (`heartbeat-diagnostic-2-trace-analysis.json`) has all21streams
closed untruncated and all21pool reports finalized with zero checked-out connections.
The first180measured seconds are instrumented; aggregates overlap across workers
and must not be summed as elapsed wall time:

| Phase | Transactions | Summed duration | Acquisition/pool wait | Client SQL | Unattributed remainder |
|---|---:|---:|---:|---:|---:|
| Worker order processing | 6839 | 1697.278s | 46.459s | 1382.940s | 267.880s |
| Worker claims | 52612 | 1398.248s | 368.721s | 800.389s | 229.138s |
| Parent command polling | 11801 | 1819.285s | 1286.799s | 417.487s | 114.998s |
| Publisher | 1616 | 172.997s | 23.621s | 124.561s | 24.815s |

In processing, observed client SQL accounts for about81.5% of summed duration,
acquisition about2.7%; parent polling has a separate large acquisition component.
Client SQL includes unknown network/server/lock/event-loop delays; neither it nor
the residual is a direct server-CPU or commit-time measurement. Increasing pools
is not justified as a processing-p95 fix by these observations alone.

`heartbeat-diagnostic-2-query-source-map.json` matches exact compiled static-SQL
SHA256 to source locations using the installed asyncpg dialect, with unmatched
hashes explicit and repeated statements mapped to multiple possible call sites.
Examples in order-processing transactions: owner-lock SQL44384calls/118.433s,
DB-clock SELECT37331calls/92.394s, episode SELECT28705calls/73.042s, checkpoint
update7524calls/72.752s, book-input reads19005calls/71.725s. No single query dominates
the processing total; counts do not prove that any guard/read can be removed.
Canonical refreshes, lock/claim/owner proofs and financial fences must remain.

Lag evidence: post-stop100owner cursors have lag0..22;2owners at21and6at22.
The existing drain waits for a captured recovery watermark while publishing keeps
advancing, then the final invariant uses the stopped feed's last input. That code
path can leave a tail, but this run did not record the captured watermark or exact
stop/worker ordering per owner. Do not declare the failure merely a measurement
artifact or alter the lag bound; review that contract before proposing a change.

`heartbeat-diagnostic-2-summary.json` / `heartbeat-diagnostic-2-post-stop.json`:
all346source hashes still match checked code, production diff empty; no workload
processes remain, only the read-only observer DB session.63resource samples show
peak66connections, start/end55, sampled lock waits0, peak process RSS61603840bytes,
buffer peak3778. Host free space sampled at least7469047808bytes; config/pools/
workers were unchanged. Post-stop safety counts zero. Sparse samples do not prove
absence of waits. No source code, further run or Git publication followed.

The authorized replacement diagnostic checkpoint is complete. W1 remains
Failed/Partial; W2/W3NotRun, W4Passed0064 and integrated NC-SET4-01 open. It does
not establish an uninstrumented speedup or resolve the historical17-minute lease
failure. Next: prepare a scoped latency/drain plan from the mapped DB round trips
and watermark contract, retaining every safety check; the evidence does not yet
justify a specific production optimization. Any runtime fix or new workload needs
the owner's approved plan. Stop here as required; no additional experiment.

### Next latency/drain plan prepared — awaiting owner A/B decision

Read-only caller review confirms repeated locks/canonical refreshes and per-input
clock checks have safety roles; none was removed. `persist_checkpoint`'s current
consecutive persistence block is a candidate for fewer client round trips while
preserving lock/read ordering, Python canonical decisions and validated audit.
No unsafe CTE rewrite, in-memory lock proof/cache or clock reuse was implemented.

[Proposed checkpoint batch/tail plan](../../../2026-10-18-paper-order-matching/checkpoint-batch-tail-drain-amendment.md)
under NC-SET4-05 defines A: production persistence batch via one narrow SECURITY
INVOKER/VOLATILE function with additive migration, then strict opt-in final-tail
drain. Expected checkpoint client calls about11→6, subject to measured proof;
no claim of meeting250ms. B applies tail handling only and leaves p95 unresolved.

Tail proposal preserves initial live-source watermark recovery, then records the
actual stopped head H and keeps workers through a final cursor>=max(W0,H-20)
gate inside the same total60s. No stale-source bypass or fresh-input fabrication.
Equivalence/RLS/trigger/rollback/reset/race/migration tests precede any later
100×20/6-cycle diagnostic; no full W1 is included. A's changed writer would require
rechecking affected W4 evidence before reliance for that candidate.

Preparation changed documentation only; all346runtime/test source hashes still
match diagnostic2. No tests/workload/Git publication were repeated. Next step is
the owner's A/B approval before implementation; current failures/statuses remain.

### NC-SET4-05 Approved A — implementation and diagnostic checkpoint

Owner approved A before production edits. Added0065 invoker-rights/VOLATILE narrow
checkpoint function and retained Python canonical state/audit/transaction boundaries.
The final-tail option is default-off, heartbeat/R8/SMOKE-only; normal source stop,
actual H validation and all100READY cursors share the original60s budget and20lag.
No scheduler/financial/freshness rule or shared pool/session policy changed.

`checkpoint-equivalence-result.json`: six pinned real-DB checkpoint snapshots equal,
client SQL11→6; exact generated recording metadata normalization is explicit and
raw snapshots retained. `checkpoint-migration-roundtrip-result.json`: up/down/up,
old writer/new schema and missing-function fail-closed/data preservation passed.
`checkpoint-batch-checks-summary.json` records targeted results and original failures:
- Initial safety111cases:109passed; two fixture issues corrected,7affected passed.
- Financial50cases:41passed;9old client-SQL fault hooks no longer intercept server
  internals. All16affected matrix cases pass after batch-boundary hook adaptation;
  real-DB triggers separately prove rollback after each internal write/outer audit.
- TP/SL and risk26passed. Final tail21passed including joined concurrent readers,
  stale/unavailable/slow source/owner, shared budget and cancellation cases.
- Ruff/format7files and strict scoped mypy8affected/caller files passed.
Scoped review has no unresolved correctness finding. These checks do not replace
required CI or full W1/W4 acceptance for the new writer.

Single diagnostic started2026-11-06T07:30:55Z on fresh
`tiewtrade_batch4_batch_diag1_20261106`,schema0065. Preflight verified all8roles,
empty users/orders/commands, function source/authority and350source hashes.
Manifest/command/raw log/headroom evidence uses `checkpoint-diagnostic-1-*`;
output `f15-checkpoint-diagnostic-1`. Same100×20/6cycles/10commands/s/20workers,
R8+heartbeat+tail, nominal300s and180s trace; acceptance_result=false.
Status: Running. Stop/report after this run even if criteria fail; no full W1,
new experiment, production activation or Git publication.

W4Passed0064 remains historical old-writer evidence. Affected0065 checkpoint
fixture/replay acceptance is Pending Revalidation. W1Failed/Partial, W2/W3NotRun,
V18/V19PendingFullValidation and integrated NC-SET4-01 are unchanged.


### Offline latency comparison and proposed next step — NC-SET4-06

Owner asked to start the next analysis/plan. `checkpoint-offline-comparison.json`
compares existing first180s traces with input hashes;350candidate source hashes
still match. No runtime/DB changes, tests or workload were executed for this step.
Processing mean client queries per transaction61.13→57.56, mean client query
3.31→5.10ms, mean transaction248.18→351.99ms; transaction mix/environment differ,
so these are descriptive comparisons rather than a causal A/B result. Claim mean
26.58→39.57ms and publisher107.05→142.47ms also increase. Command/status polling
transactions18163→25046; current polling acquisition accounts for about74–75% of
its durations versus2.9% for processing. Slow work and polling load can reinforce
each other; the trace does not establish which started that feedback.

Current database samples contain5381connection observations:5294state and5295wait
metadata values unavailable;2observations include blockers. Retain Unknown rather
than treating nulls as CPU/no-wait proof. No evidence justifies a guard removal,
pool increase or another unbounded100-owner optimization trial.

[Proposed bounded paired experiment](../../../2026-10-18-paper-order-matching/checkpoint-latency-isolation-plan.md):
compare pinned direct and batch writers on identical0065cloned fixtures, sizes
2BTC+2ETH and20BTC+2ETH. Three ABBA blocks each,24arms/360checkpoint operations,
full snapshot equality, timing boundaries separated from validation reads,
5–10minutes expected/15-minute cap, then stop. No production patch/full W1 included.
The purpose is to determine whether an isolated writer penalty reproduces before
choosing a production fix. Option B stops experiments with evidence retained.

Plan and validation scope are ready for owner A/B approval under NC-SET4-06.
No experiment has started. Prior Failed/Incomplete and all acceptance gaps remain.


### Next concurrency/polling plan prepared — NC-SET4-07 awaiting approval

Owner requested this next planning step. Source inspection confirms result polling
sleeps0.25s after each read, distinct from0.02s worker tick. Existing paired results
and the100-owner traces do not establish whether polling pressure, concurrency,
host load or their interaction caused the timeout. No new data was manufactured.

[Proposed controlled campaign](../../../2026-10-18-paper-order-matching/checkpoint-concurrency-polling-plan.md)
uses the same0065batch writer in all arms:1/4independent owner writers crossed with
0/100read-only polling tasks, four conditions in forward then reverse order.
Eight measured arms480checkpoints plus one sequential4-owner reference96 gives
576total. Same20BTC+2ETHfixture per owner; source/role/clone identity guards reused.
Polling observes state without controlling writer progress. Final ten-table/history
checks run after writers/readers join to avoid verification load contaminating the
concurrent timing window; intermediate projection assertions are explicitly absent
there, with preceding equivalence/safety evidence retained. Bounded client tracing
and local test-only READ ONLY admin metadata sampling improve wait visibility.

Plan declares focused tests,2–5minutes expected/15-minute cap, startup/group limits,
error preservation and immediate stop after the single campaign. Option B retains
current evidence and stops experiments. A awaits approval before harness edits or
execution. This step changed documentation only; no tests/new SQL/workload were run.
No acceptance status or financial rule changed; no Git publication.


## NC-SET4-08 planning — Awaiting Approval / Not Run

Read-only review of NC07 files found composite sampler durations1.275–4.682s and
start gaps2.583–5.697s, against writer windows3.595–10.336s. Identical1writer/no-poll
mean transaction timing changed5.878× across the run. These support a measurement
gap and temporal variability; they do not prove external host load as the cause.

The [proposed plan](../../../2026-10-18-paper-order-matching/checkpoint-runtime-drift-plan.md)
fixes measured writer count at1, interleaves adjacent polling pairs ABBA/BAAB,
uses288 total checkpoints, and adds bounded opt-in loop/CPU/phase observations
and independently timestamped read-only samplers. No new production/harness code,
DB workload or benchmark was run for planning. Await owner A/B choice before
implementation/execution. Existing failures and NC07 Inconclusive remain.


## NC-SET4-09 planning — Awaiting Approval / Not Run

Read-only inspection confirms workload parent submissions and command/status
polls use the same ENGINE pool, without a poll-specific concurrency gate. Historical
180s traces show70–75% reader transaction time at pool acquisition; submissions
21–23%. These are overlapping sums, not proof of starvation or full-run totals.
The proposal preserves all success/failure/status checks and deadlines while
placing an explicit4-reader semaphore before owner-session acquisition; one pool,
no new connections, permit released before sleep. Gate wait stays in latency.

[NC09 plan](../../../2026-10-18-paper-order-matching/parent-poll-budget-plan.md):
targeted safety/static checks, then one fresh100-owner/20-baseline/6-cycle SMOKE
with R8/heartbeat/final-tail,10–15min expected/20min cap. No full W1 or automatic
retry. Historical comparisons are descriptive; root cause remains unproved.
No source, DB or workload changes made during planning. Await owner A/B approval.

## NC-SET4-09 — Incomplete; cycle bound Failed

Owner approved A before implementation: opt-in4-reader gate, targeted tests and
exactly one existing100-owner diagnostic, then stop/report. Planning above is
historical. No production, migration, lock, pool sizing or financial logic changes.

Implementation: `profile_parent_poll.py` owns a bounded, per-run semaphore and
attempt observations. `profile_workload.py` reuses one polling-session helper,
acquires the permit before an owner DB session, releases after session cleanup
and before0.25s sleep. Gate waiting remains inside existing command/cycle60s
deadlines. Submission/replay/cancel writes do not acquire this permit. Defaults
remain opt-out; invalid profiles fail before side effects. Gated baseline failure
joins siblings; `profile_diagnostics.py` retains the primary timeout across runtime
observer cleanup. This local semaphore is test admission control, not persistent
business state or a production multi-instance/session mechanism.

Validation before launch: **115 tests passed**, including real PostgreSQL owner
isolation and submission/read coexistence, cancellation/deadlines, projection
readiness, deterministic identities, default regression and existing heartbeat/
final-tail/runtime supervision. Ruff check/format/mypy all exit0; candidate hashes
confirmed before launch. Reused the NC08 frozen-lock Python3.12 venv. Evidence:
`poll-gate-checks.xml`, `poll-gate-checks-results.json`, `poll-gate-checks-*.log`,
`poll-gate-checked-source.json`, `poll-gate-preflight.json`. Earlier setup-only
missing-DB-env failures and test typing issues were resolved before this final
check set; no assertion, deadline or financial criterion was relaxed.

One fresh0065 database retained: `tiewtrade_set4_iso_pollgate_0fb8aef4`.
All8 DB role checks passed.100 owners ×20 baseline orders,20 standalone workers,
R8 claim budget, separate heartbeat, final-tail enabled,10 offered commands/sec,
6 cycles/owner (600 cycles/3000 measured commands). Total **813.431s** within
1200s cap, including preparation/cleanup. All2000 baseline orders completed;
baseline runtime phase594.967s. The measured window ended at206.781s when one
cycle hit60.002s. Campaign process result **Incomplete**, cycle-bound criterion
**Failed**, original TimeoutError preserved; no worker-failure array entries.

| Partial counter | Observed | Planned |
|---|---:|---:|
| Cycles completed | 289 | 600 |
| Commands offered | 1732 | 3000 |
| Commands admitted | 1731 | 3000 |
| Commands completed | 1632 | 3000 |
| Commands rejected | 0 | — |
| Fill / cancel / replay counters | 638 / 326 / 334 | — |

The offered/admitted/completed gaps remain unresolved at stop; zero rejected is
not proof of eventual success. These are harness counters, not a post-stop order
or ledger reconciliation. Full financial/global invariant oracle, final-tail drain
and final input lag were **Not Reached**. No full workload result.json was produced.

Gate peak4, active0, buffer untruncated. Measurement attempts:11484 command reads
(11438 acquired,11436 returned,48 cancelled including46 while queued);5579 status
reads (5559 acquired,5557 returned,22 cancelled including20 queued). Cancellation
rows are retained. A returned read attempt can still observe a pending state.

| Partial measured read | Gate wait mean / p95 ms | Pool wait mean / p95 ms | Transaction mean / p95 ms | Gate + attempt mean / p95 ms |
|---|---:|---:|---:|---:|
| Command result | 779.6 / 1425.9 | 17.3 / 45.5 | 46.7 / 105.0 | 826.4 / 1502.0 |
| Order status | 788.7 / 1433.7 | 17.3 / 46.2 | 46.6 / 105.4 | 835.3 / 1498.5 |

Transaction intervals already include pool acquisition; do not add them again.
Gate attempt totals include queued/cancelled attempts, whereas transaction metrics
only include acquired sessions. These overlapping task durations are not elapsed
wall time or whole command completion latency. Gate/pool rows retain their exact
boundaries, including stop-time cancellation. Compared descriptively with the old
70–75% pool shares, this run transfers substantial waiting to the gate; it does
**not** establish an end-to-end performance improvement or causal root cause.

Parent submission transaction means/p95: new168.4/377.7ms (1063 rows,1 cancelled),
replay64.0/140.7ms (334 rows), cancel141.4/307.4ms (334 rows). Corresponding pool
means19.1/18.7/17.1ms. Raw trace/client-SQL timing and all outcomes retained.
Timed-out cycle2 of owner `9f2f943a-6c73-4230-b19c-e5e547af0c43` spent23.112s
on its first new order including command/projection waits,10.530s on the resting
order,8.574s awaiting cancel command and1.255s awaiting cancelled projection;
the final new-order command returned after8.348s, then its FILLED projection wait
was cancelled after7.929s when the enclosing60s budget expired. These phases
overlap nested spans; do not sum parent and child spans. The timeout queue snapshot
was captured only after workers stopped and is not a live ordering/race proof.

Worker transaction latency wholly inside the partial measured window:3894 samples,
mean509.5ms, p50=460.2ms, **p95=1003.8ms**, p99=1339.0ms, max2245.5ms.
All15878 samples including baseline: p95=1139.9ms, p99=2608.3ms, max8223.8ms.
18 samples cross measurement/timeout boundaries and remain in raw evidence.
No full-workload SLA claim is made from either partial series. Parent loop ticks
wholly inside the partial window:2033, p95=4.323ms, max294.510ms; all7891 ticks
including preparation/cleanup: p95=3.487ms, max555.370ms. No cycle-complete marker
exists, so this is explicitly a partial interval, not completed measurement.

Cleanup verified:21 finalized pool reports with0 checkouts,21 closed/untruncated
transaction traces,20 recorded worker PIDs exited, gate active0, runtime closed,
scratch DB connections0. Source/harness/migration hashes match the checked
candidate; uv.lock unchanged. Free space after run4.250GB. All databases and
previous evidence retained; no resource pruning, production change or Git action.

Evidence: `f15-parent-poll-diagnostic-1/`, `poll-gate-campaign-summary.json`,
`poll-gate-campaign-command.json`, `poll-gate-campaign-process-result.json`,
`poll-gate-campaign-run.log`, `poll-gate-database-identity.json`, and
`poll-gate-artifact-hashes.json`. Summaries distinguish missing final checks from
failed cycle timing; hashes cover this run and prelaunch check artifacts.

Original W1 Failed/Partial, W2/W3 Not Run,0065-writerW4 Pending Revalidation,
historical0064W4 Passed and integrated NC-SET4-01 gaps remain. **Pending Full
Validation**; no feature completion or acceptance promotion.

The authorized one-run scope ends here. Next recommendation: inspect the existing
worker/queue traces along the timed-out cycle and propose a bounded next plan,
without another experiment. Await owner direction before that next task. The
[approved plan](../../../2026-10-18-paper-order-matching/parent-poll-budget-plan.md)
explicitly says “After one diagnostic, stop/report” and authorizes no replacement.

## NC09 follow-up — separate processing from observation delay

Owner requested read-only analysis before deciding whether criteria should change.
No workload was run and no production/harness/criterion was changed. Existing
traces were correlated with a READ ONLY query of the retained NC09 database for
the timed-out owner's four command identities, projections and event history.
Artifacts: `poll-gate-followup-analysis.json`, `poll-gate-followup-db-snapshot.json`.
The analysis includes input hashes; the original campaign artifacts remain intact.

The60s bound in F15 validation §5 is explicitly a **harness progress bound**, not
a production order timeout. It includes result/projection observation. It is
separate from the250ms processing p95/1s p99 rules. The current failure remains
valid under that definition; the analysis does not retroactively pass it.

For each distinct command, submission-return → first handling transaction →
transaction completion → parent result observation was matched by command ID:

| Command in the timed-out cycle | Before processing starts (s) | Handling transaction (s) | Handling ends → parent observes result (s) |
|---|---:|---:|---:|
| First MARKET BUY | 10.417 | 0.791 | 0.931 |
| Resting LIMIT BUY | 7.640 | 0.801 | 0.983 |
| Cancel resting order | 7.850 | 0.285 | 0.454 |
| Final MARKET SELL | 6.647 | 0.708 | 0.999 |
| Sum across these four command-result stages | **32.554** | **2.585** | **3.367** |

These stages do not cover the entire60s cycle: later matching/projection waits,
submissions and replay also consume time. In particular an accepted command does
not imply a filled order. “Before processing” includes queue/dispatch/claim delay,
not pure DB execution; exact internal attribution remains unresolved. Processing
includes locks, client SQL, pool and cleanup, not pure compute. The four handling
transactions together spent only0.097s in connection acquisition. This localizes
the large command-result delay before handling rather than to their own pool waits.

Worker aggregate observations in the measured dispatch window:29370 claim calls,
3913 claimed and25457 skipped (**86.68%**). Claim transactions consumed1652.012
summed worker-seconds; PENDING/ACTIVE/CANCEL processing transactions consumed
707.190/1190.543/103.399 summed seconds. Calls/transactions crossing measurement
activation or shutdown can have different counts; these are overlapping process
durations, not elapsed wall time. Repeated attempts at the same candidate are
visible across workers. They are **not duplicate orders or duplicate fills**:
the unsuccessful claims are excluded by the existing fencing/owner checks.
`run_paper_order_round` scans hints before individual claims; with claim_limit1,
unsuccessful attempts can continue through the same candidate list. This is a
concrete performance investigation target, not proof that changing fairness or
claim budgets would improve this workload.

Final projection boundary, relative to cycle start:

- Last completed parent status read ends at **59.186s** without FILLED.
- Next read attempt starts at **59.436s**, waits outside the DB for a polling
  permit, and is cancelled at **60.002s** without acquiring a session.
- The only owner processing transaction after the final status wait begins is
  worker17's ACTIVE transaction at **59.318–59.723s**, outcome COMMIT. It handles
  a different existing command; matching checkpoints operate on the owner/pair
  state, so a command-ID-only search would miss related projection progress.
- Retained DB after stop shows the final SELL **FILLED**, with its fill input
  recorded near59.526s. No later owner processing transaction appears in the
  captured worker traces. Together these observations strongly suggest the final
  fill became visible near59.723s, shortly before the deadline, but the precise
  projection commit timestamp is not logged. Event `occurred_at`, command
  `completed_at` and input timestamps must not be substituted for commit time.

Thus the precise statement is: **the harness did not observe completion by60s**.
The older report's “waiting for FILLED” describes the parent waiter, not proof
the underlying order was unfilled at the deadline. This run contains substantial
queue delay and a final observation gap. We cannot assign the entire failure to
either production processing or polling alone. Gate waiting overlaps worker
progress; subtracting all gate-wait seconds would incorrectly double-count time
and is not a valid prediction for an ungated rerun.

Recommendation: **retain current correctness and timing criteria for now**.
Raising60s would hide this progress failure and would not address the separate
partial worker p95=1003.8ms. Do not mark the final financial/global checks passed
from these three projections; their full oracle was never reached.

Next step: prepare a bounded plan to reduce redundant worker claim attempts while
preserving DB fencing, owner fairness, retries and financial/idempotency behavior,
with explicit separation of processing and observation evidence in validation.
The existing evidence is enough to choose that investigation target; no additional
diagnostic is authorized or necessary merely to repeat the current observation.
Await owner direction for the next plan; implementation or criteria amendments
still require approval. This read-only analysis scope is complete.

## NC-SET4-10 planning — Awaiting Approval / Not Run

Owner requested the next plan. Inspected existing `due_orders`/`claim_order`,
R8 shared orchestration, session cleanup, dispatch/worker fixtures and architecture/
DB safety boundaries. No existing cross-worker scan-to-claim coordinator was found
in the inspected paths; existing per-owner locks and stale-hint fences remain the
authority for correctness.

[Proposed plan](../../../2026-10-18-paper-order-matching/worker-claim-coordination-plan.md)
A adds default-off PostgreSQL coordination only around selection and claim commit,
with a bounded session cleanup option and existing parallel processing afterward.
This explicitly requires shared source changes, rather than another harness-only
tuning attempt. Proposed scope ends after targeted real-DB/multi-process safety
tests and static checks; no timed diagnostic, W1, activation or Git publication.
Potential serialized-selector bottleneck is disclosed; performance is unproved.

No new test/workload result is claimed from planning. Original criteria and failed/
incomplete evidence retained. NC-SET4-10 awaits owner approval before source work.

## NC-SET4-10 — Opt-in implementation and targeted safety passed

Owner subsequently approved A before source changes. Added `coordinate_claims`
at the shared Python round boundary, default false, valid only with legacy R8
limit20/claim_limit1. The named PostgreSQL transaction advisory coordinator covers
scan and owner claim commit/cleanup, then releases before processing. Existing
owner RLS, nonblocking owner lock, due-version CAS, lease and claim token checks
remain unchanged. Claiming/processing errors keep the existing safety semantics;
selection failures propagate without fallback or a second uncertain claim.

Changed existing source: `infra/db/session.py`, `infra/paper_orders/dispatch.py`,
`services/engine/paper_order.py`. Reused `_begin`/`_bounded_cleanup` via optional
validated cleanup forwarding; reused one per-candidate claim context and one
processing/error/reconciliation path. No duplicate worker implementation. Added
`test_claim_coordination.py` and a separate adapter invoking existing financial
oracles in `test_claim_coordination_financial.py` without changing their assertions.

No global in-memory authority, new grants, schema, infrastructure or persistent
membership. The efficiency gate is shared through PostgreSQL and is not the
financial safety authority. Default callers, production main/configuration,
matching/storage, routing predicates, migration0065 and workload CLI unchanged.
No activation, timed campaign, diagnostic, W1, commit/push/merge or Live orders.

**94 unique targeted cases passed:**85 in the combined94-case invocation, plus
the9 fixture-setup cases rerun successfully. The original combined command returned
nonzero, retained in `claim-coordination-checks.xml`/`claim-coordination-final-tests.log`;
it is not relabeled as a clean run. Successful9-case rerun is recorded in
`claim-coordination-remaining-regressions.xml`/`.log`. Per-case latest evidence is
mapped in `claim-coordination-checks-summary.json`.

Combined invocation revisited execution_market after other test directories and
reported missing owner/wallet fixtures for those last9 cases. Grouping selections
from the same package contiguously makes `--setup-plan` succeed; evidence in
`claim-coordination-grouped-collection.log`. This is setup validation only, not an
extra test pass. Helper imports are deferred to execution as in existing tests.
No production code change or relaxed assertion was needed for this setup issue.

Earlier initial tests exposed test cleanup leaving worker/claim fields set and a
plaintext commit proxy incorrectly allowing SSL negotiation. Both were corrected
using existing cleanup/proxy patterns; the hung initial test invocation was stopped.
One financial adapter case called a direct admission/reset test that never enters
round orchestration; its assertions passed but the adapter's calls>0 check failed.
It is now run as the separate unchanged regression instead of claiming opt-in
coverage. All initial logs and the initial scratch DB are retained.

Coverage includes:

- Default runtime and R8 budget regression; unsupported opt-in combinations before
  side effects, READ COMMITTED/prewarmed sessions and isolation-drift rejection.
- Deterministically synchronized legacy/gated collision: two distinct owner heads
  required3 claim attempts in the forced legacy stale-hint case and2 in the gated
  case. Both owners processed concurrently after claim selection. This demonstrates
  only that controlled collision reduction, not real workload throughput.
- Same-owner fencing/FIFO/expiry recovery, busy-owner fallback, mixed legacy/gated
  workers, separate child processes, termination before/after claim commit and
  processing cancellation. Gate/checkout/holding deadlines include queued time.
- Real connection termination and dropped COMMIT acknowledgement: no extra claim,
  no processing on unknown commit, retained valid lease, old token fenced after
  recovery; no fallback to an uncoordinated selection path.
- Existing financial oracles through the option: fill/restart/replay/cancel,
  projection failure, lost reply/disconnect, reset-vs-fill, durable position conflict,
  duplicate identity, and BUY/SELL balance/reservation races. Direct admission/reset
  remains an unchanged regression. Full workload financial acceptance is still
  not established by these targeted fixture cases.
- User/scan cleanup forwarding, invalid bounds before checkout, primary-error
  preservation and existing real-DB stalled-cleanup/abort/reuse tests. Session and
  scanner role checks retained.

Scoped Ruff check/format and mypy passed for5 affected Python files; final test
import changes rechecked. Import-linter:7 contracts kept,0 broken. Evidence:
`claim-coordination-static.json`. Changes from the previous checked833-file source
snapshot are exactly the3 approved existing source files; the two test files are
new. Candidate hashes are in the checks summary. Formatting/diff check passed.

Scratch DBs retained: `tiewtrade_set4_iso_claim_7bd0111c` (initial) and
`tiewtrade_set4_iso_claim_5f90c2fc` (corrected checks). Post-stop checks show0
connections and0 advisory locks on both; no child test processes remain. No caches,
database contents or old workload evidence pruned.

**Implementation/targeted safety checkpoint reached; Performance Not Run.** There
is still a risk that serialized selection becomes a bottleneck. No new p95, cycle
completion, full financial or W1 acceptance result is claimed. Historical gaps
and Pending Full Validation remain. Next recommendation: owner-requested code
review scoped to NC10, then a separately approved comparison plan if appropriate.
Stop/report here; no automatic refactor, runtime activation or additional experiment.

## Consolidated closure review and validation — 2026-11-06

Owner requested continuous work to close F-17. Completed the outstanding NC10
review and already specified affected checks rather than requesting another review
or restore permission. This checkpoint is not a claim that F-17 is Completed.

### Review and the one resolved coverage finding

Reviewed NC10's three runtime files (`infra/db/session.py`,
`infra/paper_orders/dispatch.py`, `services/engine/paper_order.py`), its two test
files and surrounding selection, claims/fencing, cleanup, financial processing and
default callers. Checked the approved protocol and prior real-DB/process evidence.
Also checked the0065 checkpoint writer and restore boundary for affected validation.
This is not a new full review of every earlier diagnostic harness or the entire repo.

| Severity | File/location | Problem and impact | Fix / evidence |
|---|---|---|---|
| Medium — resolved | `backend/tests/infra/execution_market/test_claim_coordination.py`, `test_lost_claim_commit_reply_stops_and_existing_lease_recovers` | Existing lost-COMMIT proof targeted the owner connection; scanner disconnect proof occurred before claiming. The important committed-claim/coordinator-reply-loss boundary lacked direct evidence, so it could miss processing/retry mistakes after the claim was already durable. No production defect was demonstrated. | Parameterized the existing oracle for owner and scan COMMIT reply loss. Both real-DB cases pass: exactly one claim, no processing, no checked-out connections, coordinator reacquisition and recovery with a new fencing token; old claim rejected. No duplicate oracle or production-code change. |

No Critical/High runtime finding was established in this scope. The shared PG gate
is an efficiency mechanism, while the existing owner locks and claim fences remain
the safety authority. Owner RLS/scan read authority, READ COMMITTED checks, default
call contracts, cancellation and ambiguous-commit behavior remain intact. Money/
Quantity and business state continue to use existing domain/storage logic; no local
session/business-state authority or financial formula was introduced. A lower
controlled stale-attempt count is still not proof of production throughput.

### New verification results

| Check | Result | Evidence |
|---|---|---|
| Owner/scanner lost COMMIT reply + fenced recovery |2 passed,0 failures/errors/skips;1.138s pytest |`closure-safety.xml`, `closure-safety-tests.log` |
| Changed-test Ruff / format / mypy |All exit0 |`closure-safety-{static,format,types}.log` |
| F-17 protection integration on fresh0065 |48 passed,0 failures/errors/skips;57.003s pytest |`closure-protections.xml`, `closure-protections-tests.log` |
| F-15 W4 actual0065 writer fixture + backup/restore |Passed;10.033s fixture/verifier subprocesses, excluding migration |`closure-w4-fixture/`, `closure-w4-restore/result.json` |
| Restored0065 function source/authority |Body, invoker status, search_path, owner and execute ACL identical |`closure-restore-function.json` |
| Cleanup and candidate identity |Four retained DBs,0 connections/0 advisory locks;835 Python source hashes unchanged during checks |`closure-cleanup.json`, `closure-*-source-hashes.json` |

The existing94 NC10 case results remain valid for unchanged code. The scan-COMMIT
case is one additional scenario; the owner-COMMIT case was rerun. Do not describe
this cumulative evidence as a new95-case combined successful pytest run. Existing
48-case F-17 suite also produced its two known JUnit `record_property` warnings;
neither case failed and the warning is retained in the log.

W4 source `tiewtrade_set4_iso_close_restore_2ad923c6`, restored target
`tiewtrade_f15_w4_close_1a62b393`: capital4/fills3/partial1/cancel1/correction1/
reset1/evidence23/expired-claim1. Canonical digests and RLS/grants match;
4episodes/3checkpoints/2positions replayed. Expired claim1→0 in2 rounds, with no
additional economic effects. Backup1706204bytes retained. This revalidates F-15
restore on0065; the fixture's explicit digest does not prove F-17 history restore.

Commands, process exit codes and durations are in `closure-checks.json`; role/schema
verification is in each `closure-*-preflight.json`. Python3.12.15 frozen-lock venv
`/tmp/tiewtrade-nc08-venv.3NHM82`, local PostgreSQL16.15. Host free space5.3GiB
before checks. Other containers remained untouched, including pre-existing
restarting UI-check workers. This is not a controlled performance environment claim.
Source/test preparation and review were not separately timed; no duration invented.

### What still prevents F-17 completion

| Gate | Current result | Required next work |
|---|---|---|
| NC10 performance |Not Run |Harness runtime composition and the defined comparison/acceptance profile; safety does not prove speed |
| F-15 W1 / W2 / W3 |Failed/Partial / Not Run / Not Run |Demonstrate existing volume, duration,60s progress, p95/p99 and complete financial/resource oracles |
| F-15 W4 |Passed on0065 |Reuse while its source/schema/fixture remains valid; integrated history extension is separate |
| F-17 V-18 |Partial/Failed; NC-SET4-01 Needs Clarification |Approve and execute the integrated F-14/F-16/F-17 composition, then final combined regression/E2E |
| F-17 V-19 |Not Run / Pending Dependency |F-20/F-21 and notification features, then bot failure→close→stop and enabled-channel tests |
| F-17 V-20 |Not Run / Pending Dependency |F-22–F-24, then Live mapping/reconciliation/isolation/recovery validation using fixtures/FakeVenue |
| Current Set-4 candidate publication |Uncommitted; final required CI Pending |Explicit Git instruction and required CI on final candidate; old98ff2f8 CI does not certify these changes |

Prepared the [consolidated Paper proposal](../../integrated-paper-acceptance-plan.md)
for the genuinely missing NC-SET4-01 parameters, with continuous conditional
progression instead of another sequence of routine approval checkpoints. It is
**Draft**, not an approved spec. The owner must decide those new profile/budget
parameters under AGENTS.md's prohibition on inventing requirements. Even a passing
Paper campaign does not satisfy the unbuilt bot/notification/Live dependencies.
No new timed campaign, production activation or Git publication occurred here.
Next step: owner decision on that proposal; do not claim completion or relax gates.

## Consolidated profile approved and coordinator diagnostic started

Owner selected A for the consolidated plan. NC-SET4-01 is now Closed / Approved;
its newly defined integrated acceptance remains unexecuted. Under the approved
continuous implementation/fix/check scope, connected the NC10 option to the
existing first diagnostic fixture before the later integrated acceptance phases.

The harness-only `--coordinate-claims` option requires explicit R8 and preserves
limit20/claim_limit1 on normal, recovery and restart launch paths. Parent and child
metadata name `SERIALIZED_CLAIM_V1`. Existing dispatch recording observes selection
and gate setup/acquisition without additional worker SQL. Default callers remain
unchanged and production coordinator activation is still off. No financial source
changed.133 targeted tests passed, with scoped Ruff/format/mypy confirmed before
launch. Initial type errors in optional kwargs/module-export test access were fixed;
the failing log is retained and no campaign ran before all final checks passed.

Preflight initially stopped before DB creation/worker launch: the temporary host
runner assumed unavailable psutil, corrected to the existing macOS `sysctl` query;
then host space was1.7GiB. It recovered to2.7GiB without agent cleanup. Kept the
existing2GiB launch guard and added a bounded host-space watchdog to stop the run
if less than1GiB remains. No images, containers, databases, volumes or caches were
deleted. These preflight stops produced no workload result or consumed measurements.

### Coordinated diagnostic1 — Incomplete / setup Failed

Fresh DB `tiewtrade_set4_iso_close_coordinated_41372e13`, all8 actual roles verified,
schema0065/function body/authority verified and empty users/orders/commands before
launch. Exact approved fixture:100×20 baseline,6 cycles/owner,3000 commands at10/s,
20 workers, heartbeat/tail/poll4,20-minute campaign cap. Process exited1 after
302.271s; neither time cap nor disk watchdog fired (minimum free2.570GiB).

Only18 full baseline batches were observed complete.1900 setup commands were
submitted and1883 orders were ACCEPTED/SUCCEEDED after stop, short of2000 required.
Measured offered/admitted/completed/cycles were all0: the measured phase never
started, so no full financial oracle, final-tail, lag or SLA result is available.

Twenty selector deadline exception stacks occur:12 at coordinator advisory-lock
acquisition,5 at `due_orders` and3 in owner transaction timeout setup. These locate
where the overall5s selection deadline expired; they do not establish that each
individual SQL statement ran5s. Twenty worker metrics files name the coordinator
protocol. Parent `worker_failures=[]` is not proof of healthy workers: that summary
is populated after the successful workload path, while this run failed in setup.

Setup-only processing11060 samples had p95=0.209113s/p99=0.367470s/max=1.897855s;
these are not measured-workload acceptance values. No setup dispatch summary or
detailed trace rows survived: the existing recorder only emitted setup totals when
the measured-phase control file activated. Thus actual loaded gate hold/wait and
claim-attempt totals cannot be reconstructed from this run. A separate post-stop
single-scanner EXPLAIN took16.556ms execution/5.640ms planning and gate setup/
acquisition0.004505s; that unloaded observation does not prove the loaded cause.

All21 pool reports finalized with0 checkouts;20 dispatch and21 transaction streams
closed; DB connections/advisory locks0. Post-stop negative reservations, invalid
positions, duplicate effects, unlinked fills and wrong-mode counts were0. These
limited setup checks do not substitute for a completed3000-command financial oracle.
All837 captured Python/lock/config hashes matched before the subsequent harness fix.
Raw files and analysis are retained in `coordinated-diagnostic-1*`; their artifact
manifest protects the original evidence.

### Targeted evidence repair and changed-candidate check

Fixed the identified setup evidence gap in the recorder: final flush now retains
SETUP_SUMMARY even when measurement never starts. Added a separate coordinator-held
interval from successful acquisition return to scan transaction cleanup return.
It includes COMMIT acknowledgement/cleanup and is not an exact server release time
or an independent wait to add to selection time. Existing transaction context and
recording logic are reused; no SQL, deadline, eligibility, financial rule or worker
retry/fallback changed. Regression proof covers normal/failing operations before/
after activation and a real PostgreSQL rollback/reacquisition case.

The initial setup-emission repair passed44 targeted cases/static checks; the final
hold-interval repair passed45 with Ruff/format/mypy. Old logs/results are retained.
Continued the approved fix/check cycle on a changed harness candidate with the same
defined diagnostic profile; this is not an automatic same-candidate retry or a W1
attempt. Diagnostic2 uses a new empty DB and retains diagnostic1 as Failed/Incomplete.
Later HTTP/snapshot/rebuild/extended restore implementation and acceptance remain
conditional on the diagnostic gate; no passing result is claimed in advance.


### Coordinated diagnostic2 — Incomplete / cycle Failed

Same approved fixture and runtime, fresh empty DB
`tiewtrade_set4_iso_close_coordinated2_8683546b`, schema0065/all8 roles verified.
Only the tested observation repair changed from diagnostic1. Workload process
exited1 after405.488s; neither20-minute cap nor disk watchdog fired. Minimum free
space2.315GiB. The outer orchestration script returned normally after recording
that failure; its exit0 is not the workload result. No third workload was launched.

Baseline2000 finished in about249.36s. Measurement then reached188/600 cycles,
1191 offered/admitted,1091 completed,0 rejected of3000 planned before a60.001318s
cycle timeout.428 fills/211 cancels/226 replays are partial counters. The failed
owner's last FILLED observation waited27.268s; its order remained ACTIVE/PENDING
in the post-stop snapshot. Earlier waits had already consumed the same60s budget.
Post-stop state is not an on-time acceptance result.

| Observation | Result and limitation |
|---|---|
| Measured claims |3470 attempts:3449 claimed,21 skipped (0.605%). This does not prove throughput or exactly-once effects. |
| Coordinator acquisition/setup |3455 calls, mean0.548s/max7.306s, including setup SQL and cancellation/cleanup. Not pure server lock-wait time. |
| Coordinator-held interval |3452 intervals, mean0.0418s/max2.946s; includes owner commit and scan acknowledgement/cleanup, not exact server release. |
| Partial processing, measured start to stop |3450 samples,p95=441.610ms,p99=789.372ms,max7.244s. Full workload was not completed. |
| First60s processing |1959 samples,p95=311.908ms,p99=437.530ms. Already above250ms before worker exits. |
| Existing harness population, setup plus measured |15232 recorded samples,p95=281.312ms,p99=478.754ms. Retain this population separately; neither population certifies a completed run. |
| Worker failure |18 selector-timeout stacks:14 acquiring coordinator,1 due scan,3 owner transaction setup.18 distinct cancelled selector traces finish142.167–146.034s after measurement start. Resource sampling then shows2 workers remaining. |
| Partial resources |30 samples; peak observed process RSS58,736,640 bytes. This is not endurance/resource acceptance. Parent-loop lag p99 is recorded in analysis; routine DB wait fields lack visibility. |

The largest scan transaction lasted7.489s including cleanup: its gate SQL consumed
4.410s before a0.272s due query and cancellation during owner setup. This supports
a nearly exhausted selection budget followed by cleanup/queued timeouts; it does
not establish one SQL/host bottleneck as the sole cause. The operation5s limit
explicitly excludes bounded cleanup, so7.489s wall is not by itself a deadline bug.
Three privileged read-only snapshots showed12–14 advisory waiters before failure;
all other data collection used existing instrumentation. Their timing does not
prove what held the gate at failure. Do not sum overlapping intervals.

Known mechanism: accumulated gate wait can consume the selection budget and, under
the approved fail-fast protocol, terminate worker processes. That late capacity
loss compounds the failure. Separate limitation: processing latency was already
above criteria before exits, so preventing exits alone may still fail acceptance.
The empty parent `worker_failures` list is a success-path reporting gap, not proof
of healthy children; raw exceptions/traces/resource samples are authoritative.

All21 pool reports finalized with0 checkouts;20 dispatch and21 transaction streams
closed; parent plus20 worker PIDs no longer existed at cleanup verification. DB
connections/advisory locks0. Post-stop negative reservations, invalid positions,
duplicate fill effects, unlinked fills and wrong-mode counts0. These are limited
invariants, not the unexecuted complete financial oracle. Full final-tail/input-lag,
HTTP, rebuild/snapshot and extended restore acceptance were not reached.
All837 captured source/lock/config hashes matched throughout the run.

Artifacts: `coordinated-diagnostic-2/`, process/preflight/source records, raw log,
`coordinated-diagnostic-2-analysis.json`, analysis/runner snapshots and artifact
hash manifest. Previous diagnostic1 and initial failing static/preflight results
remain preserved. Evidence/script preparation and offline analysis were not
separately timed; no duration is invented.

### Checkpoint and next decision

The integrated profile is Approved A, not missing. The failed diagnostic blocks
conditional W1–W3 and integrated HTTP/F-14/restore progression. Standalone0065 W4
and the48 protection cases remain valid for their narrower scopes. F-17 remains
Development Complete / Pending Batch & Release Validation; V19/V20 still require
planned bot/notification/Live dependencies and current changes need final CI.

Prepared [NC-SET4-11](../../../2026-10-18-paper-order-matching/worker-claim-contention-amendment.md)
for a specific acquisition-policy change: explicit nonblocking busy result,
250ms backoff after cleanup, actual errors still propagate. It is Draft/Needs
Approval because NC10 explicitly requires blocking acquisition. No V2 source,
third diagnostic, Git publication, production activation or SLA change occurred.
Next step: owner decision on that amendment; later phases remain conditional on
all unchanged criteria, not merely survival of workers.

Final evidence verification:140 diagnostic1 artifact hashes unchanged,146 diagnostic2
artifacts hashed,837 candidate source/lock/config hashes unchanged. JUnit results
confirmed2 commit-loss,48 protection,133 initial harness and45 affected observation
tests passed in their separate runs; final scoped static results were exit0.
Document links checked; a trailing blank line in the current plan was removed.


## NC-SET4-11 — Approved A, V2 implementation and safety

Owner approved the precise nonblocking/250ms amendment before source edits.
Archived nine V1 files plus hashes in `nc11-v1-source/`; previous diagnostics and
criteria are retained. Two runtime files changed: try-lock result in dispatch and
after-cleanup busy backoff in the existing selector. The same advisory key excludes
V1/V2 workers. Existing owner transactions/fences remain safety authorities.
Default activation is false; no production/Live activation, SQL privilege changes,
financial formula changes, migration or new infrastructure.

Reused the existing recorder for acquired/busy/held distinctions and per-process
V2 manifests. Parent exceptional-path evidence now retains actual child exits
after bounded shutdown; evidence cleanup preserves a primary error. Tests cover
real PostgreSQL, independent processes, busy cancellation, scan commit reply loss
while busy, owner/coordinator uncertain commits, financial consistency and defaults.

`nc11-tests.xml`:135 passed,0failed/errors/skipped,23.715s JUnit duration. Scoped
Ruff/format/mypy passed for seven changed Python files; import-linter7/7 kept.
The initial import-order/type-access issues were fixed before testing/campaign;
the initial mypy failure log remains. Test DB `tiewtrade_set4_iso_close_nc11_ffd3bb99`
is retained with0 connections/advisory locks. Scoped diff review complete, no
remaining demonstrated runtime finding; no unrelated refactor.

Started exactly the approved V2 diagnostic after confirming all final check exits,
with fresh database, unchanged100×20/600cycles/3000commands/10per-second/20workers,
heartbeat/final-tail/poll4 and20-minute whole-run cap. Source snapshot freezes the
candidate during measurement. Current status: running, not acceptance Passed.


### NC11 diagnostic1 — Incomplete / setup Failed

The one approved V2 run used empty DB
`tiewtrade_set4_iso_close_nc11diagnostic_f03b4030`, all8 roles verified and schema0065.
It exited1 after165.058s, before either the20-minute cap or disk watchdog fired;
minimum free2.183GiB. Three full100-order baseline batches were observed.400 setup
commands were submitted,394 orders/results succeeded of2000 required. The measured
phase never started:0 offered/admitted/completed/cycles; there is no measured SLA,
full financial oracle, final-tail/input-lag or resource acceptance result.

Parent primary error: book `WriterLeaseLost` in the first `_locked` call of
`renew_book_writer`. The persisted source still has the expected owner/generation1
and last input279. Lease expiry13:27:35.058295Z precedes the publisher failure log
13:27:35.415848Z. These DB/host timestamps are different clock domains, not an exact
server execution trace; the matching identity and guard support expiry rather than
an observed takeover. Maximum successful publish duration was5.054753s but the
summary does not identify its tick. No TTL/freshness change is justified by this.

| Setup observation | Result |
|---|---|
| Gate calls |7297:2092 acquired,5205 explicitly busy; no gate acquisition timeout stack observed |
| Claims |2084 attempts:2082 returned a claim,1 skipped,1 raised; failed attempt kept in denominator |
| Gate-held interval |2092 samples,max9.388s including transaction/cleanup; not exact server release time |
| Processing |2082 samples,p95=684.110ms,p99=1487.134ms,max13.990s; setup only |
| Child exits |worker5 exit1 after selection deadline in claim SQL; worker10 exit-15 during bounded parent shutdown |
| Parent loop |1589 samples,p99lag61.242ms,max783.613ms; does not identify child/DB latency |

The repaired parent failure record reports both child exits instead of a false
empty list. SQLAlchemy logged cancellation while terminating connections. All21
pool reports nevertheless finalized with0 checkouts;20 dispatch/21 transaction
streams closed, all21 process PIDs were absent and DB connections/advisory locks0
at verification. No cleanup success is inferred merely from an empty error list.

The parent trace contains0 detailed transactions and9083 setup counters; worker
traces likewise do not retain baseline query details. Setup dispatch aggregates
survive, but cannot identify slow query versus row lock, commit acknowledgement,
process scheduling or I/O. A filtered existing PostgreSQL log window contains one
checkpoint-start entry after the publisher failure and no recorded space/OOM/FATAL
entry; that absence does not prove the host/database environment was healthy.
No additional SQL probes ran during the campaign. Offline hashes of older evidence
were read during setup; that observer I/O is a possible unquantified contributor,
not an established cause or grounds to erase this failed run.

Limited post-stop invariants (negative reservations/positions, duplicate fill
effects, unlinked fills, wrong mode) were0. They do not replace the missing full
financial oracle.837 Python/lock/config hashes matched start/end; no source change
occurred during measurement/setup. Previous140/146-artifact V1 manifests and nine
archived V1 files were verified intact. No images/containers/DBs/volumes were deleted.

Artifacts: `nc11-diagnostic-1/`, raw log/preflight/source snapshots, final process
result, `nc11-diagnostic-1-source-and-baseline.json`, analysis JSON and filtered
PostgreSQL environment log. Runner/check scripts are retained. Source edits and
offline analysis were not separately timed. The135-test JUnit time is23.715s;
command durations remain in `closure-checks.json` rather than being conflated.

The approved one-run stop/report checkpoint is reached. **Do not repeat or run W1.**
NC11 approval itself is closed; the remaining blocker is the unlocalized publisher/
DB delay and unpassed workload. Next recommended task is a bounded baseline
publisher trace plan, reusing the existing tracing code and covering query/pool/
commit/cleanup times from setup start; no new timed execution is authorized here.
Keep all lease/freshness/financial/SLA rules. V2 affects the final shared-worker
candidate, so old protection/restore results retain provenance and cannot certify
its final integrated gates. F-17 V18 Partial/Failed, V19/V20 Pending Dependency;
final CI/Git permissions remain pending. No production/Live activation or Completed
claim, and no fourth diagnostic, followed this run.
