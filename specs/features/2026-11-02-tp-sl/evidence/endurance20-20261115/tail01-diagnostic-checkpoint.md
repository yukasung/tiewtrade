# NC-F17-TAIL-01 — Diagnostic checkpoint

สถานะ: **Diagnostic Complete — stop/report; not W3 acceptance**
Owner approved the diagnostic plan on2026-11-15. Exactly one campaign executed.

## Changes and safety checks

Added only profile_tail_reads.py and test_tail_reads.py under backend/tests/infra/
execution_market. Exact SQL extracted from both unchanged runtime read sites and
checked for drift; pool5+10/gate4 and actual ENGINE user_session/RLS retained.
Existing seed_owners, production evidence preparation/decoder, source pinning,
preflight, gate and session lifecycle patterns reused. Bulk fixture CTE inserts
referenced evidence and keys under each owner with all schema/FK/unique/append-only
protections enabled; no order commands or strategy engine ran. Read transactions
are explicitly read-only with local10s statement timeout. Admin access was limited
to the generated DB's schema capture/explicit fixture statistics and cleanup.

Incremental safety coverage:17new diagnostic cases and64existing parent-poll/final-
tail regressions. First run74Passed/1Failed: a three-ID test fixture has only two
unique sample points (1,1,3); corrected that assertion, retaining decoding and ID
assertions. The failed case and preflight/output-reuse regression then2Passed;
six additional identifier/head/real-statement-timeout cases6Passed. No assertions
weakened for mutation/RLS/cancellation. Scoped Ruff/format/mypy and whitespace Passed.
Original logs retained privately:
- attempt-1794728132432472000.log:74Passed/1Failed.
- attempt-1794728177508447000.log:2Passed.
- attempt-1794728247203075000.log:6Passed.

## Campaign

Total1208.716450s (20m08.716s), including one120s/seven-sample preflight Passed;
seed1079.406218s, measurements5.568668s. Verified20synthetic episodes with144513keys
and valid referenced evidence each:2890260keys,60decoded representative payloads.
Serial pass20reads; concurrent pass20reads through gate4;3SELECT-only EXPLAIN plans.
All43observations returned. Candidate/source unchanged, financial snapshot unchanged.

- Serial20reads:3.825242s wall, query mean185.649ms/max284.996ms.
- Concurrent20reads:1.333227s wall, query mean247.473ms/max350.887ms;
  pool acquisition mean7.470ms/max41.057ms; gate waiting dominates later readers.
- Three plans each read144513key rows using existing primary-key bitmap scans,
  then an external-merge disk Sort of144513rows before the grouped Aggregate.
  Each spills3688KiB and records461temp-read/463temp-written blocks. Plan execution
  around126.798–134.911ms. No index or schema change made.

The historical59s final-tail delay was NOT reproduced. This quiescent fixture has
no worker/publisher contention, was explicitly ANALYZEd, and is physically seeded
owner-by-owner rather than interleaved over4h. These differences prevent claiming
an exact historical root cause or a proven fix. What is proven: the old query does
an avoidable full-history sort, and pool acquisition alone was small in this run.
It is inappropriate to loosen60s or mark the previous4h result Passed from this.

## Cleanup and provenance

[Summary](tail01-diagnostic-summary.json), [source receipt](tail01-source-bridge.json).
Private root validation-artifacts/f17-tail01-20261115 retains runner/launcher,
source/diff/schema bindings, full valid fixture counts, raw43reads/3plans, gate
attempts and receipts. Identifier was<=63ASCII bytes; exact ownership recorded.
Normal DROP succeeded after zero owned connections; independently DB absent,
0connections/0locks. No Redis created, both owner services still running/restart0,
PostgreSQL healthy. No force/prune/reset or unrelated data/service change.

All prior NC_F17_CLOCK_01 source hashes unchanged. No old evidence regraded, no4h
rerun, production fix, commit/push/CI/merge. F17 remains Pending Full Validation,
not Completed; original Release/opening/bot/notification/Live dependencies remain.

## Next scoped proposal

[NC-F17-TAIL-02](../../final-tail-query-improvement-plan.md) proposes a scalar
aggregate in both harness read sites to avoid the grouped join's external sort,
with exact RLS/empty/multiple-pair/generation/INPUT/REBASE equivalence and short
same-fixture old/new comparison. This is a proposal only. Stop here for approval;
no runtime query has been changed and no additional campaign is authorized.
