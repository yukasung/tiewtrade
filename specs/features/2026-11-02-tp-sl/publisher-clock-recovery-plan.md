# NC-F17-CLOCK-01 — Fixture publisher recovery after clock reversal

สถานะ: **Approved A — owner approved implementation and targeted safety tests, then stop for review,2026-11-15**
วันที่:2026-11-15 (Asia/Bangkok)
Feature:F17; branch validation/f17-paper-endurance20-20261115; base main b0d5580/PR75.
Owner requested preparing this plan after the read-only diagnosis. This is not
approval to implement recovery or run a replacement campaign yet.

## 1. Problem and evidence

[Four-hour attempt](evidence/endurance20-20261115/checkpoint.md) stopped Incomplete
at40min11.132s,4753/28200commands. The publisher's book timestamp was230us later
than a subsequent PostgreSQL guard timestamp. Both came from PostgreSQL; underlying
OS/VM correction mechanism remains unproven. [Read-only diagnosis](evidence/endurance20-20261115/clock-diagnosis.md)
did not reproduce the reversal; sparse samples cannot certify clock stability.

The production future-input guard correctly rejected the input. The fixture
market_publisher currently stops on every publisher exception, so a rejected
synthetic observation ends the endurance run. Do not label this a proven production
financial defect or repair the original result into Passed.

## 2. Proposed requirements amendment — harness only

Allow an explicitly selected internal20/W3 runtime to recover **one** narrowly
identified rejected synthetic publication, while every accepted input still passes
the original production guard. This changes the fixture's failure/recovery policy;
it requires owner approval even though monetary/safety rules remain unchanged.

- Opt-in only, default off, initially permitted only for PAPER_INTERNAL20_V1 W3.
  Recovery eligibility starts only for publication attempts begun inside the active
  measured W3 window; setup/baseline and attempts begun before that boundary retain
  fail-stop behavior. Legacy/original100/other phase commands keep existing behavior.
- Maximum **one recovery event in the whole campaign**, maximum **one additional
  publication attempt** for that event. A second clock incident stops Incomplete.
  This conservative cap prevents repeated platform clock faults being hidden; it
  may still stop a replacement run if the environment repeatedly reverses time.
- Maximum recovery budget **1second monotonic**, measured from first guard rejection
  through rollback/session exit/fresh transaction/confirmed publication commit.
  This is an extra upper bound, not added grace: no existing cycle/source/measurement/
  recovery deadline is extended. Cancellation or exhausted budget stops Incomplete.
- No timestamp tolerance, rounding/clamping, backdating, artificial clock, guard
  bypass, stale-input exception, source rebase or automatic lease reacquisition.
- No financial/order-command/HTTP POST retry. Only the rejected fixture market
  publication may be regenerated. Amounts, quantities, fees, balances and risk
  rules unchanged; production code/API/schema/session/Live untouched.
- Keep first failure/event, all attempt durations and waiting in the measurement;
  do not discard slow samples or exclude recovery time to pass latency criteria.
  Keep original setup/measurement boundaries and fixed14400s window; never add
  measurement time to compensate for a recovery or move setup time into that window.
- Existing no-retry Incomplete and older Passed/Failed results remain immutable.
  A future result must identify this new opt-in runtime revision; it cannot be
  presented as a passing rerun of the old no-retry runtime or100-account Release.
  Proposed prospective acceptance: all existing assertions must pass, plus the new
  cap/budget/evidence rules. If one recovery was used, report Passed only for this
  declared opt-in runtime with a visible clock-recovery warning. This prospective
  fixture-policy change is part of the requested owner decision, not a silent waiver.

## 3. Existing components to reuse

- tests/infra/execution_market/profile_workload.py: publish_market, market_publisher,
  existing cadence/counters/processing-window and parent cleanup.
- tests/infra/execution_market/profile_publisher_readiness.py: actual original-guard
  call, task-scoped ContextVar and bounded sanitized evidence. Observe the existing
  call; never call the guard a second time merely to classify an exception.
- tests/infra/execution_market/remaining_paper_campaign.py and profile_internal.py:
  explicit options, early invalid-profile rejection, fixed profiles, provenance,
  unchanged preflight/isolation/cleanup.
- tiewtrade.infra.db.session.market_data_session: keep its role assertion and shared
  transaction factory. Existing harness uses session._connection; SQLAlchemy's
  active transaction rollback may be used only on this authorized fixture connection.
  Do not edit shared _begin/error policy or construct an unauthorized session.
- Existing test_publisher_readiness.py, test_publisher_heartbeat.py,
  test_remaining_paper_campaign.py and test_internal_profile.py first; extend their
  fixtures/patterns before adding a dedicated small test module if needed.

No infrastructure, general retry framework, persistent business cache or duplicated
publisher implementation. Any extraction is limited to the existing publication
body so initial and regenerated attempts execute the same production functions.

## 4. Detailed flow proposed

1. Only with the explicit option, capture immutable actual guard arguments and
   exception identity for the current parent publisher task/attempt. Existing
   observation still calls the unchanged production guard once per attempted input.
2. Eligible only when that exact guard raised SourceUnavailableError for the current
   synthetic book: ready=True, source_at=None, received_at==verified_at==the attempt's
   PostgreSQL sample, guard_now earlier than that sample, and expected source/pair/
   writer identity. Incomplete evidence, another task, another error stage or other
   readiness/sequence/ownership failure is not eligible. Do not classify by message
   text or a later clock read, nor by parsing an evidence file.
3. Before commit is ever attempted, explicitly await rollback of the active root
   transaction on the existing authorized fixture session connection. Record success
   only after rollback returns successfully. Let the normal session context exit;
   any rollback/close failure, cancellation or changed exception stops without retry.
   Merely receiving the original error outside market_data_session is insufficient:
   shared _begin intentionally suppresses some secondary rollback errors. Do not
   change that shared behavior. Prove the explicit-rollback/context-exit approach
   with real PostgreSQL before implementing the recovery path around it; if it
   cannot provide the promised proof, stop and revise this plan rather than relax it.
4. Require eligible matching error + confirmed rollback + exited prior session +
   unused global budget + persisted rejection evidence. Never retry a commit error
   or ambiguous commit, regardless of error text/type similarity.
5. Open a fresh market_data_session and regenerate BookState/ExecutionMetadata from
   a fresh PostgreSQL clock sample. Keep original logical tick/trade ID, pair, writer
   owner/generation and next input ID; do not advance published counters for the
   rejected attempt. Run normal writer renewal, publish_input and price publication.
   Production source sequencing, digest, lease and readiness checks all run again.
   If clock is now before previously accepted source time, the original input-gap
   rule must still fail; recovery does not waive that rule.
6. Only after confirmed outer commit advance published/last_input/first-ready state
   once. A repeated guard rejection or any other second-attempt error ends the run.
7. Keep evidence for rejected/retried/committed/aborted states in a separate bounded
   artifact because the existing recent64 window can evict the first rejection.
   Include exact timestamps/delta, monotonic attempt/rollback/commit timings, tick/
   input identity, retry count and type-only errors; no cookies/tokens/URLs/secrets.
   Evidence-write failure also stops; no silent recovery without its receipt.

## 5. Validation proposed — Feature

F1 Default behavior: disabled option has original exception identity and no extra
SQL/guard call/retry. Existing heartbeat/readiness tests remain valid. Unsupported
profile/phase rejected before output/preflight; no worker forwarding or side effects.

F2 Eligibility: exact captured230us reversal, plus1us boundary; original guard rejects
the first input. Not-ready/stale/source-future/source-stale/mismatched timestamps,
input gap/replay conflict/writer lease loss/foreign or inherited-child task are not
recovered. Unknown/missing evidence is not recovered.

F3 Real-DB rollback proof: first attempt rejection rolls back source state/buffer/
price changes and releases the old transaction before retry. Use existing sessions,
real PostgreSQL and controlled test-only clock injection; never alter OS/server time
or replace the production guard. Assert one valid input/price effect on retry,
unchanged monetary/order/position/reservation tables, preserved source identity and
correct next input ID. Real rollback/connection lifecycle cannot be proven by mocks.

F4 Fail closed: rollback error/timeout, cancellation, session-exit failure, commit
error/unknown outcome, exhausted1s budget and second clock event all stop without
an additional publication. No financial POST retry or synthetic successful receipt.
Original cancellation/error retained appropriately; hooks/context reset and pools
return/dispose without remaining borrows.

F5 Measurement/evidence: rejected attempt survives ring eviction; all wait/attempt
intervals retained in unchanged window/cycle formulas. Published logical count is
once per confirmed input, separate attempted/rejected/recovered counters reconcile.
Metadata records option/revision/cap/budget/actual recovery count. No old evidence
rewritten. Failure to write or parse required new evidence prevents acceptance.

Run the smallest affected existing tests plus new correctness/real-PG regressions;
scoped Ruff/format/mypy and diff check. Reuse PR75 financial/WS/readonly evidence
unless an identified dependency is affected. No full suite, CI or workload ritual
at this implementation checkpoint.

## 6. Execution order and stop gates

A. Owner approves this amendment (including the1event/1retry/1second limits).
B. Implement harness-only option/evidence and targeted real-PG/negative tests, then
report changes/results for owner-directed code review. This is a scoped correction,
not whole-F17 completion; do not misuse Ready for Code Review for the entire feature.
C. Follow required review/fix/refactor authorization gates. No4h run before affected
safety tests and review/fix checkpoint pass. No default activation or opening.
D. A replacement campaign needs explicit execution authorization after C: same20/
400baseline/28200commands/14400s/7fault schedule and all original monetary/latency/
snapshot/rebuild/pool assertions, with the new option/revision pinned. One fresh DB/
Redis, preflight once, estimate4h15–30min, cleanup and stop/report on any failure.
Do not retry automatically or increase recovery limits to fit an unsuccessful run.
E. Commit/push/merge only through the applicable owner Git instructions and required
CI gates. This plan does not modify previous PR75 or existing results.

## 7. Current work in this planning step

Only this proposal and documentation links are added. No application/test source,
configuration, transaction or guard modification; no new experiment/workload/CI.
F17 and standalone4h20 statuses remain unchanged. Approving A authorizes B, not D.

## Owner approval and implementation choice — 2026-11-15

Owner explicitly approved A (implementation/targeted safety tests, stop for review).
This supersedes proposal/awaiting-approval wording above for steps A–B only. No4h
replacement/Git authorization. Reuse the authorized session connection's active
root transaction rollback, await its success and normal context exit, then fresh
session; no added savepoint SQL in the normal publisher path. Tests must prove
context compatibility/lock release and refuse rollback/exit/commit ambiguity.
Recovery state is ephemeral per-campaign fixture control, never session/business
state; capture original guard arguments through the existing task-scoped observer.

## Implementation checkpoint

Approved steps A–B implemented and verified; [receipt](evidence/endurance20-20261115/clock-recovery-implementation.md).
Explicit root rollback compatibility/lock release proven against PostgreSQL; no
savepoints or shared transaction-policy changes. Only the measured publisher task
may recover; global event cap and1s budget retained. Incremental safety/regression
and static checks Passed. Stop for owner-directed code review, no4h or Git action.

## Owner-directed review corrections — 2026-11-15

Owner instructed “แก้ไข” after review. Correct R1–R3 within the existing approved
harness contract: leave the session normally after confirmed root rollback and
rethrow the captured rejection only outside that session; reject changed source
identity under the renewed row lock before retry publication; ignore inherited
recovery context in foreign publisher tasks before any state mutation. Add real-PG
internal-close-failure/concurrent-input and pending-parent child regressions. Keep
all guards, caps, deadlines and production/session code unchanged. Run targeted
safety/static checks, report and ask for the required refactor instruction. This
does not authorize a replacement workload or Git publication.

Review fixes implemented and targeted real-PG/static checks Passed;
[correction receipt](evidence/endurance20-20261115/clock-recovery-review-fixes.md).
Await separate owner refactor instruction; steps D–E not executed.

## Owner-directed refactor — 2026-11-15

Owner instructed `refactor the code`. Keep the review corrections and all runtime
behavior: consolidate the repeated test buffer-ID query using the existing
authorized session type, simplify repeated first-attempt access and remove the
unreachable fallback after commit evidence validation. Reuse existing fixtures
and database sessions; do not extract a general retry framework or change timing/
transaction ordering. Run affected recovery tests and scoped static checks, retain
unchanged regression/workload evidence. Step D still requires separate execution
authorization; this instruction does not authorize Git or a four-hour run.

Owner-authorized refactor and affected Feature validation Passed;
[refactor receipt](evidence/endurance20-20261115/clock-recovery-refactor.md).
Step D execution authorization and Git instructions remain pending.

## Step D execution authorization — 2026-11-15

After the refactor checkpoint and recommendation to exercise the approved policy,
owner instructed “เริ่มทำ”. This authorizes one fresh standalone internal20 W3
four-hour replacement with --publisher-clock-recovery on the refactor receipt,
unchanged profile/guard/financial/latency/pool/fault criteria. Run preflight once,
retain old Incomplete, stop/report and clean owned fixtures on any failure. Fresh
artifact root f17-endurance20-clock01-20261115; no source edit or Git action.

## NC_F17_CLOCK_01 replacement execution result — 2026-11-15

[StepD receipt](evidence/endurance20-20261115/clock01-four-hour-checkpoint.md):
Incomplete. Measured14400.002106s and completed28200commands;7fault observations
RECOVERED, no clock recovery used. Final-tail cursor collection exceeded the60s
shared budget; finalfinancial/rebuild/global acceptance NotRun. Cleanup independently
verified, old results retained. Stop/report before any replacement or source change.
NoGit action; F17 notCompleted. Next needs a bounded final-tail investigation plan.
