# NC-F17-TAIL-01 — Bounded final-tail read diagnosis

สถานะ: **Approved — owner authorized harness, targeted checks and one diagnostic, 2026-11-15**
วันที่: 2026-11-15 (Asia/Bangkok)
Feature: F17 amendment; existing branch validation/f17-paper-endurance20-20261115.
Base: b0d5580 plus the preserved approved/refactored NC_F17_CLOCK_01 harness.
Owner instructed “เริ่มทำ” after the recommendation to prepare this diagnostic plan.
This planning instruction does not authorize a new workload or modify an old grade.

## 1. Problem and source of truth

[Replacement receipt](evidence/endurance20-20261115/clock01-four-hour-checkpoint.md)
and [summary](evidence/endurance20-20261115/clock01-four-hour-summary.json): measured
14400.002106s, completed28200commands, seven fault observations RECOVERED, no clock
recovery used. Final-tail alone timed out: first watermark44.965377s, publisher
stopped45.010735s, final watermark returned59.153554s, final cursor group started
59.154384s and all20reads were cancelled by the shared60s deadline.

Queries in profile_workload.wait_for_input_recovery and drain_final_tail aggregate
max(input_id) over paper_execution_input_keys joined to paper_order_activity.
Finalhead144513. Poll attempts show both gate waiting and reader time; they do not
contain actual cursor values or EXPLAIN plans. The original fixture was cleaned up,
so a new fixture can diagnose a reproducible query shape, not recover the original
physical query plan or prove its exact historical root cause.

The existing primary key is episode/base/quote/generation/input_id/decision_kind
(backend/migrations/versions/0034_paper_orders.py). Ordering by input_id alone is
not assumed equivalent or index-bounded across all these dimensions and RLS.

## 2. Proposed requirements — diagnostic only

RQ-T1: Reproduce the read shape/history scale on a fresh, isolated migrated DB:
20synthetic users, one Paper episode each, BTC/USDT, generation1 baseline history
through144513input IDs per episode (2890260key rows, matching referenced evidence).
Use valid synthetic evidence and existing initialization/fixture patterns; retain
schema checks, append-only rules, role permissions and RLS. No owner-data copy,
real account, exchange requests, order submission, real strategies or financial
command replay. This fixture proves read behavior, not financial reconciliation.

RQ-T2: Run the exact current SELECT under the same authorized engine user_session
and RLS settings used by the harness. Keep parent pool5/overflow10 and poll gate4;
record these actual values. Measure gate wait, connection acquisition, transaction/
role setup, execute/result-read and session exit separately, including total time.
No schema/index/RLS/pool/server setting changes for an attractive result.

RQ-T3: Compare one-owner-at-a-time reads with20owner reads through the same four-slot
gate. One serial pass and one concurrent pass,20reads each, fixed owner order,
retain all observations. Capture SELECT-only EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) for
owners1/10/20 under that same role/RLS after those passes. No repeated campaigns,
cache-flush, VACUUM/tuning or choosing the fastest sample. Fresh fixture statistics
are recorded; any fixture ANALYZE before measurements is explicit and scoped to
this generated DB, and is not represented as the old fixture's statistics.

RQ-T4: No acceptance change: retain shared60s drain budget, all20distinct owners,
READY checks, target cursor/minimum watermark, nonnegative lag<=20 and original
financial/processing/source/fault/pool rules. Do not add retry, extend timeout,
skip final cursor evidence or regrade either historical Incomplete.

RQ-T5: Record provenance and cleanup. Use a fresh output root, copy/hash runner and
configuration, pin current candidate/source/schema before preparation and verify
after. Preserve clock recovery work, earlier raw artifacts and documents. Fixture
DB identifiers must be ASCII<=63bytes and exact ownership recorded immediately
upon creation; never repeat the previous identifier truncation. No new Redis is
needed for this database-read diagnostic; no unrelated service is stopped.

RQ-T6: Run once after safety checks and one existing120s/7-sample preflight pass.
Missing/bad evidence, unexpected write, timeout, cancellation or failed invariant
stops Incomplete. No automatic retry or source correction inside this campaign.

No API/schema/session/business/production-code change is proposed. No new feature
or branch fork: this is the existing F17 validation amendment and retains its work.

## 3. Reuse and implementation plan after approval

- profile_workload.py: exact SQL from both read sites, user_session/poll_session,
  wait_for_input_recovery and drain_final_tail as the behavioral reference. Keep
  their runtime bodies unchanged for this diagnostic; label a copied diagnostic
  SELECT with source location/hash and verify it still matches before running.
- profile_parent_poll.py: ParentPollGate and existing attempt/queue evidence,
  test_parent_poll.py cancellation/join patterns. Do not invent a second gate.
- execution_market/conftest.py: isolated DB creation/bootstrap/migrations and
  ownership-safe normal cleanup. Reuse schema/production initialization functions
  and real-DB fixture shapes from test_evidence.py/positions fixtures. Seed in
  bounded batches; validate FK/unique/dimensional relationships and actual counts.
  No disabling constraints, triggers, RLS or append-only protections. Fixture-only
  generation may write valid synthetic source evidence without sending commands;
  readers must only SELECT under normal owner roles.
- remaining_paper_campaign.py: source pinning and current service/preflight checks;
  profile_internal.py run_preflighted, existing output-reuse protections. Reuse
  launcher-owned resources only; do not rerun W3 or alter its argument/profile table.
- Test-local read observer wraps existing session/connection timing, not queries
  returning business data. Record counts/timing/plan nodes and pseudonymous fixture
  identities, no connection strings, cookies, secrets or credentials. Do not log
  unrelated process environments or PostgreSQL settings beyond existing evidence.

Add a small dedicated harness only if no existing entry point supports this scope.
Keep all implementation in backend/tests/infra/execution_market and evidence/specs.
Do not refactor unrelated production readers or optimize SQL before the diagnosis.
Review the fixture construction and observers with real-DB tests before the timed
campaign. Any inability to create representative valid evidence is a blocker,
not permission to bypass domain/storage integrity.

## 4. Time/resource budget and deterministic execution

Expected planning/implementation/targeted checks/initial analysis45–90min. The
single diagnostic campaign is expected15–25min including one120s preflight, seed,
reads/plans and cleanup; maximum25min from preflight start. Preparation/seed and
measurement elapsed times are recorded separately; no duration is called4h.
SELECTs use a transaction-local10s statement timeout, bounded gate waits and overall
measurement cap5min. These are diagnostic limits, not changes to W3's60s SLA.
The plan captures slow/timeout outcomes rather than quietly extending these bounds.

Keep at least2GiB free during preparation and between bounded seed batches; stop
if unavailable. Before/after capture PG health and relevant service restart state.
After measurement dispose/close all owned sessions and join tasks, then verify
zero fixture connections/locks and remove only the exactly recorded database with
normal DROP (no FORCE). If normal cleanup cannot be proven, retain that resource
with its ownership receipt and report it; do not terminate unrelated connections.
Cancellation/cleanup have bounded existing session lifecycle handling; exceeding
campaign budget is Incomplete, never a reason to drop a DB with active readers.

## 5. Validation

| ID | Criterion | Phase | Evidence |
|---|---|---|---|
| F1 | Correct isolation, <=63byte identifier, exact ownership, output reuse rejection, source/SQL drift fails before sampling | Feature | Targeted unit/real-PG tests; negative ownership/source cases |
| F2 | Fixture has exactly20owners and2890260keys with expected per-owner history and valid FK evidence; baseline query results match known latest IDs/availability | Feature | Small real-PG seed tests plus full fixture counts/integrity checks before campaign |
| F3 | Owner A cannot read B; empty history returns existing zero semantics; mixed pair/generation and INPUT/REBASE cases preserve exact aggregate semantics | Feature | Real-PG RLS/edge cases, fixtures only |
| F4 | Read observer preserves returned results/exceptions, single call, role/session lifecycle; timings reconcile without removing waits | Feature | Fault/cancellation tests and measured nested spans |
| F5 | Gate cap4, no query/write/mutation retry; statement/overall timeout cancels and joins readers; no connection leak or unexpected financial writes | Feature | Real-PG error/cancellation tests, existing parent-poll/final-tail regressions |
| F6 | Scoped Ruff/format/mypy and whitespace pass for changed harness/tests | Feature | Actual command receipts, no unrelated full-suite repetition |
| D1 | One preflight, one fixed serial/concurrent campaign and3plans; all observed counts/durations/plans retained with actual role/schema/config | Batch diagnostic | New owned fixture and private raw evidence, no performance passing grade |
| D2 | Source unchanged, per-phase budget/resource checks and cleanup proved; explain limitations and remaining unknowns | Batch diagnostic | Sanitized report, cleanup and source bridge |
| R1 | Original full W3/financial/rebuild/release acceptance | Release / retained | Both Incomplete results unchanged; no4h repeat authorized by this plan |

Use existing test_final_tail_drain.py, test_parent_poll.py and relevant profile/
evidence tests first; add only new diagnostic fixture/observer gaps. The earlier
62clock-recovery cases and prior101/56regressions remain valid unless their source/
callers/configuration are affected. No passing diagnostic replaces required CI.

## 6. Approval and stop/report checkpoint

A. Owner approves this diagnostic amendment before source changes/execution.
B. Implement the scoped fixture/read observer, run targeted correctness/RLS/cleanup
and static checks. Stop if safety cannot be demonstrated or after repeated failures
under the existing AGENTS rules; do not start timed work on failed checks.
C. Run the single bounded diagnostic campaign, collect evidence, cleanup and report.
D. Stop after that campaign. Propose the smallest evidence-backed query/reader fix
with equivalence, RLS, concurrency, financial-no-write and deadline tests. Such a fix,
review/refactor/Git publication and any4h replacement are separate later gates;
none is implicitly authorized here. If diagnosis remains inconclusive, report the
specific missing observation and bounded next option instead of another4h run.

No requirements/acceptance relaxation proposed. F17 remains Pending Full Validation,
not Completed; bot/notification/Live/100-account Release/opening dependencies remain.

## Current planning checkpoint

This proposal and links only. No source, fixtures, database, tests, campaign, process,
service, timeout or criterion changes have been made for NC-F17-TAIL-01. Await owner
approval for steps B–C; prior four-hour execution authorization is exhausted.

## Owner approval and implementation binding — 2026-11-15

Owner replied “อนุมัติ”: steps B–C approved, stop/report after one diagnostic.
Use existing seed_owners and production evidence preparation/decoder for synthetic
payloads. Seed in bounded fixture-only CTE batches under owner ENGINE sessions,
following storage.append_execution_inputs INSERT/RETURNING/key-FK pattern; keep
all constraints/profiles/RLS and verify sampled payload digests via the production
decoder. This avoids millions of20-item production command transactions while
retaining actual reference rows; no money/order state is simulated by raw writes.
SQLAlchemy checkout/begin event timestamps distinguish pool acquisition from
transaction/role setup; unobserved spans fail rather than becoming zero. Reader
transactions explicitly read-only with10s local statement timeout. No SQL rewrite.

## Execution checkpoint

Approved B–C executed once: [diagnostic receipt](evidence/endurance20-20261115/tail01-diagnostic-checkpoint.md).
Diagnostic complete in20m08.716s;43observations returned, exact historical delay not
reproduced. Full-history disk Sort is proven on the fixture. Stop/report under D;
TAIL-02 is a separate proposal, no query rewrite/additional experiment authorized.
