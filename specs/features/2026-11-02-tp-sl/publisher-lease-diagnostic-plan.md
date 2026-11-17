# NC-F17-LEASE-01 — Short publisher lease-lifetime diagnosis

สถานะ: **Approved — owner authorized harness, safety tests and one five-case diagnostic, 2026-11-15**
วันที่:2026-11-15 (Asia/Bangkok)
Feature:F17 existing validation branch validation/f17-paper-endurance20-20261115.
Owner instructed “เริ่มทำ” after the recommendation to prepare a bounded short
lease investigation; this step prepares the plan only.

## 1. Evidence and objective

[TAIL-02 four-hour receipt](evidence/endurance20-20261115/tail02-four-hour-checkpoint.md):
Incomplete at14371.934354s,28143/28200commands,28.065646s short. WriterLeaseLost came
from order_book_storage.renew_book_writer's UPDATE returning no live lease at line207,
after its initial locked owner/generation/live-lease check returned. The failed
next tick would be143388. Maximum successful publication4.750327s; last input143387
received13:29:59.256179UTC, guard13:29:59.277600, progress13:30:03.966538; failure
13:30:04.284694. The prior5s lease had little margin, but exact statement/commit/
scheduler/clock contributions were not recorded. Do not claim an established
historical root cause from host-load/autovacuum correlation.

market_publisher updates price at tick1 or multiples of10; last successful143387
and next143388 are heartbeat-only when heartbeat_per_book is enabled. Diagnostic
must cover both that path and actual price-update ticks rather than blaming price
writes which may not have run. Sourcebook and pricewriter renewals share the same
transaction before commit; both existing fences and5s leases stay unchanged.

Objective: observe remaining lease lifetime and where time is spent in the current
fixture publication, and reproduce expiry at the original renewal boundary with a
controlled delay. This is not a proposed fix, performance acceptance,4h replacement,
or permission to lengthen/reacquire/renew leases by another process.

## 2. Requirements — diagnostic only

R1: Use fresh isolated migrated fixture databases and existing market-data role/
sessions. No owner/Live accounts, order/strategy requests,20-account workload,
financial mutations, schema/index/server settings or new infrastructure/Redis.
Only valid synthetic book/price publications needed for the existing publisher.

R2: Keep production functions, SQL predicates, locking, owner/generation fences,
5s TTL, freshness/clock guards and commit/rollback/error policy unchanged. No
retry, reacquisition, backdating, lease_until UPDATE for simulation, fake clock,
changed scheduler cadence, timeout grace or synthetic successful receipt.
NC_F17_CLOCK_01 is not enabled in this short non-W3 diagnostic; an unexpected clock
rejection stops/report, not an invitation to activate recovery outside its scope.

R3: Add opt-in test-only, task-scoped observation of the existing publication path.
Record monotonic spans for connection acquisition, transaction/role setup, book
renewal (initial locked check/UPDATE/final locked check), book publication/guard,
price heartbeat renewal, price read/write when actually called, and commit/session
exit. Preserve the actual returned values and exact exceptions. No inference that
one unobserved session-exit interval is exclusively server commit time.

R4: Capture actual lease owner/generation/input ID/lease_until and DB clock values
already returned by locked reads; derive TTL margin only from compatible PostgreSQL
timestamps, never host wall time. At most one explicitly counted read-only DB-clock
probe before commit and one after confirmed exit may fill a missing boundary;
record their spans/overhead, keep raw values including any reversed ordering.
Driver await, server work, scheduling and probe overhead remain distinct/unknown
unless actually observed. No invented zero or clamping of negative margins.

R5: Hooks only apply to the selected publisher task and attempt. Child/foreign
ContextVar inheritance cannot inject delay, overwrite parent spans or consume an
injection. Original function/guard is called once per normal call; no duplicate
publication is introduced by observation. Restore hooks/context on every exit.

R6: Pin source/config/schema/runner before fixtures, verify unchanged at end, retain
all attempts/errors/delays. The old4h grades and TAIL-02 comparison remain intact.
Diagnostic delays must never be included in or excluded from historical workload
metrics to change their grade. Missing/corrupt evidence prevents completion.

## 3. Fixed five-case experiment after approval

Run exactly these five cases once, in order, each on a separate fresh isolated DB
(or an equivalent clean migrated template clone using the existing fixture factory).
Use no background workload, no customer data and no actual order command. Initial
source acquisition and tick1 publication are setup. For price-update cases, execute
normal setup ticks through9 with heartbeat enabled; observe actual tick10. For
heartbeat cases observe tick2. Pin these flags/ticks in the case manifest.

| Case | Publication | Controlled delay | Purpose / expected classification |
|---|---|---|---|
| L0-H | tick2, update_price=false, heartbeat=true | none | Successful normal publication, identity/generation stable, cursor+1, price facts unchanged |
| L0-P | tick10, update_price=true, heartbeat=true | none | Successful normal publication, cursor+1, intended price update once |
| L1-H | tick2 heartbeat-only | one4.5s async pause after book publish/guard, before price renewal | Observe remaining TTL and complete/expired outcome under original checks; no forced success or retry |
| L1-P | tick10 price update | same one4.5s pause | Separate additional price stages/margin from heartbeat-only path |
| L2-U | tick2 heartbeat-only | one5.25s async pause after original first locked live-lease check returns, before renewal UPDATE | Reproduce expiry at UPDATE, expect original WriterLeaseLost and confirmed rollback/no accepted new input |

Controlled delays use monotonic async waits in the dedicated harness wrappers,
not SQL clock manipulation, lease writes or production source edits. Record actual
wait and injection count. In L1 a commit or original lease rejection is an observed
boundary outcome, not a Passing W3 decision. Both require complete stage evidence
and the matching committed-once/rolled-back state proof. Unexpected stage/error,
clock behavior preventing classification, uncertain commit, safety/evidence failure
or deadline stops the experiment Incomplete; do not repeat that case automatically.
L2 must show an originally live locked row and expired renewal predicate, with no
accepted new input. If the precise planned boundary cannot be observed, report
Incomplete rather than claim reproduction. No hooks continue into an application
server or another campaign.

## 4. Implementation and reuse after approval

- profile_workload.py publish_market/market_publisher: call unchanged existing
  functions; preserve the real flags and ordering. No timing rewrite of its body.
- profile_publisher_readiness.py: exact original guard observation, task scoping,
  bounded sanitized evidence and primary-exception preservation pattern.
- profile_publisher_recovery.py/test_publisher_clock_recovery.py: reusable context/
  actor/cancellation patterns and real-PG rollback/lock-release witness assertions;
  do not reuse its recovery allowance or add another retry controller.
- test_publisher_heartbeat.py: actual heartbeat/price flag behavior, unchanged price
  facts, lost-price-writer rollback. Reuse existing fixtures and assertions.
- order_book_storage.py/realtime_storage.py: wrap original calls only inside the
  diagnostic; retain original SQL/guards. Capture actual book _locked return data
  unchanged. SQLAlchemy checkout/begin/statement events and existing MarketDataSession
  wrapping may provide spans; unknown SQL shapes fail observation instead of being
  silently attributed to the wrong stage. No shared session/_begin modification.
- execution_market/conftest.py and current launchers: safe fresh database/bootstrap/
  template cloning, role URL binding and normal owned cleanup. Identifiers ASCII
  <=63bytes with ownership recorded immediately; no force drop/connection kill.
- profile_internal.py and current check_services: one120s/seven-sample preflight for
  the whole experiment before any case fixture, current approved host readiness.
  No automatic waiting for a better host; minimum2GiB free before each case.

Add only a small dedicated harness/tests if existing observers cannot supply these
spans. No general retry/profiling framework. Store typed stage names, times/flags,
source fixture identities and sanitized error types; no connection strings, session
cookies, secrets or unrelated business rows. Ephemeral observer state is not an
application session or persistent business source and cannot alter multi-instance
production behavior.

## 5. State, transaction and cleanup proof

Before/after each case, use existing market-data sessions and independent witness
engine to compare source owner/generation/head, buffer/evidence and price facts.
A successful return requires confirmed normal session exit and exactly one input.
A rejected/aborted transaction must leave those committed values unchanged; an
independent FOR UPDATE NOWAIT witness proves its row lock was released. Do not
infer successful rollback merely from the exception or a pre-driver rollback event.
Ambiguous commit/close error/cancellation is not eligible for retry or successful
classification. Verify financial/order tables remain empty/unchanged; fixture
publications cannot create user balances or trades.

Join owned tasks and dispose engines before checking fixture0connections/0locks;
remove only an exactly owned DB normally, never FORCE. Observe naturally finishing
maintenance for at most10s as in the existing launcher, preserving initial and final
cleanup receipts separately. If the DB cannot be proven quiescent/owned, retain it
and report the identifier/condition. No owner containers, volumes, images or DBs are
stopped/deleted; no Docker reset/prune. No dedicated Redis is needed.

## 6. Validation and time budget

| ID | Criterion | Phase / proof |
|---|---|---|
| F1 | Option/scope/identity/source drift rejected; observer calls original once and returns values/errors unchanged | Feature targeted tests |
| F2 | Only chosen task/attempt can inject one delay; child cannot affect parent; hooks/context restore | Feature async/negative tests |
| F3 | No extra mutation/guard retry; original book/price flags and snapshots maintained | Feature existing heartbeat/readiness and new tests |
| F4 | Controlled expired renewal fails closed with same owner/generation, rollback and independent lock-release proof | Feature real PostgreSQL, not mocks alone |
| F5 | Cancellation, missing evidence/unknown commit/exit/IO errors preserve primary error, join tasks and do not retry | Feature fault tests and owned lifecycle evidence |
| F6 | Scoped Ruff/format/mypy and whitespace pass before timed experiment | Feature actual receipts |
| D1 | One preflight and exactly five case manifests with raw stage/DB-clock/TTL/delay evidence and state comparisons | Batch diagnostic, no4h acceptance |
| D2 | Source unchanged and exactly owned resources cleaned or explicitly retained with proof | Batch diagnostic |
| R1 | Original full W3/financial/rebuild/Release acceptance | Retained: Incomplete/Pending; not exercised here |

Use existing tests first and add only observer/delay/state-proof gaps. Estimated
implementation/targeted checks/analysis45–90min; the one diagnostic itself4–8min,
maximum10min from preflight start including case setup/measurement/cleanup. Single
case observation capped15s, whole experiment fail-stop under its overall bound;
cleanup overruns are reported Incomplete and never hidden by force actions. No
performance sample removal or new production SLA. If minimum source/commit timing
cannot be measured safely, stop and propose the missing observation before execution.

## 7. Approval and stop/report checkpoint

A. Owner approves this diagnostic amendment before harness/test changes or experiment.
B. Implement observers/controlled fixtures; pass targeted real-PG/safety/static checks.
C. Run the fixed five-case experiment once, collect all evidence and cleanup.
D. Stop/report. Distinguish demonstrated boundary mechanism from the still-unproven
cause of the historical4h event. Propose any fix only from that evidence; no automatic
lease extension, reacquisition, production change or additional run. Owner-directed
review/fix/refactor and Git gates still apply. No4h/commit/push/PR/CI/merge authorized.

F17 remains Pending Full Validation, not Completed. Keep all previous Incomplete,
Partial and Release/opening/bot/notification/Live dependencies unchanged.

## Planning checkpoint

Only this proposal and validation link added. No source/test/lease/clock/DB/container,
workload, deadline or acceptance changes for LEASE-01. Await owner approval for B–C;
the preceding four-hour authorization has been consumed and is not a retry allowance.

## Owner approval and implementation binding

Owner replied “อนุมัติ”: B–C authorized, stop/report under D. Wrap only workload
imports and the original book _locked return inside a context bound to one task.
SQLAlchemy events timestamp checkout/begin/statement/commit-start; session wrapper
records normal exit separately. Precommit clock is an explicit counted probe;
postcommit clock comes from the independent state/lock witness. Separate tiny DB
per case, no Redis or application/financial worker. Use existing readonly_admin
for empty financial-table checks, never hand it to publication code.

## Execution checkpoint — approved scope consumed

[Five-case diagnostic complete](evidence/endurance20-20261115/lease01-checkpoint.md):
one preflight, fivefresh DBs,164.961s total. F1–F6 targeted evidence and D1–D2 complete.
37distinct targeted cases/scoped Ruff/format/mypy Passed. L0/L1 committed once; L2
original expired UPDATE rejected/rollback confirmed. Source stable, allowned DBs
removed, owner services unchanged. Stop/report under §7D; no further campaign,
fix,4h/Git/CI authorized. Historicalcause unproven and allpriorIncomplete retained.

## Review correction M1 — owner authorized fix

Review found that readiness finalization IO failure is attached to WriterLeaseLost,
which run_case treats as an expected diagnostic outcome, but only trace evidence
was validated. Owner instructed “แก้ไข”. Before changing source: require a readable
final readiness document with the expected completion/error reason, exact guard
count and fixture tick/owner/input/generation before DIAGNOSTIC_COMPLETE. Missing,
malformed or mismatched evidence leaves Incomplete; preserve the original lease
exception with a sanitized evidence note rather than parsing exception notes or
changing the shared observer/production error policy. Add real-DB case-level fault
checks plus existing lease/readiness regression and scoped static checks. This is
an evidence admission correction under R6/F5, not a trading/criteria relaxation.
No repeat diagnostic,4h run,Git/CI or automatic refactor is included.

M1 implementation detail: the shared readiness observer may expose an additive optional
per-context write-failure receipt while retaining its original exception policy;
existing callers that omit the optional receipt are unchanged. Latch failures even if a write
raises after complete bytes reached disk, so a valid-looking file alone cannot hide
reported IO failure. Include this negative case. Initial fault-test setup injected
lease loss during setup rather than the observed attempt (4assertion failures,
33Passed); restrict injection to the intended second publication before rerunning.

M1 correction complete: [27affected checks/static/source bridge](evidence/endurance20-20261115/lease01-m1-fix.md)
Passed. No experiment repeated; old grades retained. Await owner refactor instruction.

## Owner-authorized M1 refactor

Owner instructed `refactor the code`. Extract only the M1 readiness-document checks
from the case transaction/orchestration into a small local helper; express the
repeated guard identity comparisons as ordered expected fields. Keep validation
order, field comparisons, error strings/types, original-exception preservation,
receipt latching and all transaction/lease behavior. Flatten only the related test
fault writer. No generic validation framework/shared production change. Re-run the
27 affected correctness/fault/readiness cases and scoped checks, retain unrelated
valid evidence, then stop/report without another campaign or Git action.

[M1 refactor and affected validation](evidence/endurance20-20261115/lease01-m1-refactor.md)
complete:27cases/scoped checks Passed. No additional experiment/Git action; stop/report.
