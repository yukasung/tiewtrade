# Checkpoint latency isolation after NC-SET4-05

สถานะ: **Approved A — owner approved the bounded paired campaign on 2026-11-06**
วันที่: 2026-11-06
Decision: NC-SET4-06. Owner requested analysis and a concrete next plan after the
single approved checkpoint diagnostic failed. This document is that plan, not a
change to the approved trading rules or a claim that a production fix is known.

## Evidence and unresolved cause

[Offline comparison](../2026-11-02-tp-sl/evidence/batch-20261106/checkpoint-offline-comparison.json)
uses only existing traces. All350candidate source hashes still match the last run.
No new SQL, workload, tests or source edits were needed to prepare this proposal.

| Same first180s trace window | Previous direct writer | Current batch writer |
|---|---:|---:|
| Order-processing transactions | 6839 | 4831 |
| Mean client queries per processing transaction | 61.13 | 57.56 |
| Mean processing transaction | 248.18ms | 351.99ms |
| Mean client query in processing | 3.31ms | 5.10ms |
| Mean claim transaction | 26.58ms | 39.57ms |
| Mean publisher transaction | 107.05ms | 142.47ms |
| Command/status polling transactions combined | 18163 | 25046 |

The pinned checkpoint test proves11→6client calls in that function. It does not
prove a45% reduction for the whole worker: it retains the underlying writes and
adds identity/metadata checks. Different transaction mixes and host conditions
prevent causal inference from these two workload runs. Original whole-worker
partial p95=951.215ms/p99=1.892955s and60.115s timeout remain Failed/Incomplete.

The batch query itself accounts for136.668s of1700.456summed processing seconds
(5504calls); this is a client envelope around several server statements. Remaining
processing also slowed. Polling acquisition occupies about74–75% of its transaction
durations and is a plausible source of load amplification, but the direction of
causality is unknown: slower processing also causes more polls. Processing
acquisition is only about2.9% of its own summed duration. Pool enlargement, polling
changes or removal of guards are not justified as fixes by these data alone.

DB metadata is mostly unavailable:5294of5381connection observations lack state,
5295lack wait type; two observations report blockers. Nulls are Unknown, not CPU
or no-wait evidence. The generic SQL trace ends at180s while timeout occurs around
248s. The per-cycle timeline is available, but cannot recover missing query/commit
observations. Final-tail was not reached. Do not label it fixed or failed by this run.

## Option A — bounded paired checkpoint experiment (recommended)

Implement a test-only measurement entry point, then one predeclared paired campaign.
Purpose: test whether the writer change reproduces a latency penalty in isolation
at small and20-order state sizes. This is a prerequisite for choosing a production
fix, not a new acceptance profile and not a substitute for100-owner/full W1 tests.
No production changes, scheduler/pool/polling changes or full workload are included.

### Reuse and source identity

- Extend `tests/infra/execution_market/profile_checkpoint_fixture.py` with an
  optional fixture-size argument, preserving its current default and equivalence
  snapshot normalization. Reuse `prepare`, canonical `admit_order`/`cancel_order`,
  `Money`/`Quantity`, `checkpoint_snapshot`, deterministic fixture operations,
  existing counting hook, `save`, and `profile_workload.percentile`.
- Add only the small test-only orchestration/measurement needed for this campaign;
  use the existing real-DB fixtures/tests in `test_checkpoint_batch.py` for context.
  Avoid adding a general benchmark framework or a permanent second writer.
- Direct writer: extract the exact legacy `matching_storage.py` from pinned
  98ff2f840fe08dc46ab5eb9976f17bdf32b062b1 into a temporary isolated source tree;
  verify it against `checkpoint-legacy-source-proof.json` and the old snapshot
  evidence before execution. Batch writer: current350-file hash manifest and0065.
  Both variants use the same0065schema, dependencies, harness and domain code;
  only the persistence implementation differs. Never switch the live worktree file
  during execution. If the legacy hash cannot be established, stop/report.
- Reuse the previous verified-fresh role URL/actual database checks and schema0065
  function-source proof. Credentials stay outside logs/artifacts. Both writers run
  as ENGINE under existing owner RLS/fences; admin/migrator is setup only.

### Fixed data and run order

Two prepared templates, each prepared once and then cloned before every arm:
1. Existing fixture:2BTC+2ETH LIMIT headers;4accepts,1BTCcancel,1ETHinput checkpoint
   =6operations. Retains cross-pair revisions and terminal-history coverage.
2. Same fixture with20BTC+2ETH headers;22accepts,1BTCcancel,1ETHinput checkpoint
   =24operations. Reuse existing prices/sizes, Money/Quantity and canonical domain
   constructors; declare its new fixture identity. This models checkpoint row
   cardinality, not the full workload's matching, throughput or financial oracle.

For each fixture, run three blocks in the fixed order Direct–Batch–Batch–Direct.
Exactly24arms in total and360checkpoint operations (12×6 +12×24). These are
predeclared comparisons, not automatic retries. Each arm starts from its own clone
of the same prepared template, with identical IDs/input/state/statistics. No state
from one arm feeds the next. Verify template/fixture digests and counts first.

Use one application process/one owner at a time, the same ENGINE connection settings,
and one sequential transaction per checkpoint as in the existing replay. Perform
identical connection warm-up in both variants; do not drop OS/DB caches, tune pools,
change Docker resources, stop unrelated workloads or configure new extensions.
Record environment and unrelated-load observations if available; absence is Unknown.
Do not describe ABBA order as eliminating all host/cache effects.

### Measurements and correctness gates

For every operation retain fixture/block/arm/source identity, operation index/kind,
row cardinality, client statement count, `persist_checkpoint` monotonic elapsed time,
and the full owner transaction elapsed time through context exit. Report the two
boundaries separately; context exit time is not automatically pure server commit.
Place comparison snapshot reads after commit in separate owner transactions so
measurement does not include verification reads. The original production
transaction boundaries, canonical payloads, audit and locks stay intact.

Compare the normalized ten-table snapshot after each corresponding operation
against the direct-writer reference for the same fixture. Reuse only the approved
allowlist of generated recording metadata; never normalize financial values,
business timestamps, order/decision identities or revisions. Keep raw snapshots.
Any identity/authority/row-count/semantic mismatch, SQL error, timeout or cancelled
transaction stops the campaign immediately, retains the failure and blocks later arms.
Do not adjust correctness or latency thresholds to obtain a successful report.

Report per-arm/per-operation timings and block-level Direct versus Batch ratios;
retain all runs. With these small samples, do not assert statistical significance
or apply the250ms worker SLA to this different microbenchmark. State whether the
same directional penalty repeats across the predeclared blocks and row sizes;
mixed results are Inconclusive. Do not select the fastest run or hide warm-up/order
effects. Query-count reduction alone is not the success criterion.

Before timed execution, targeted tests must prove: default fixture unchanged,
20BTC+2ETH operation/count construction, independent clones and role/database
identity rejection, exact arm order/denominator, correctness mismatch abort,
original exception/cancellation preservation, timing excludes snapshot reads,
and streams/connections close. Reuse valid production safety results; run only
harness/caller checks and applicable Ruff/format/scoped mypy for new changes.
No full suite/CI/frontend validation is implied.

### Time, artifact retention and stopping

Announce approximately5–10minutes including setup, with a15-minute total campaign
cap and60-second per-operation cap. A cap failure is Incomplete, not grounds for
extending the run or trying a replacement. Record actual timing and all failures.
Only new, uniquely named scratch databases for this campaign may be created.
Keep failed/current diagnostic databases, their history, images and volumes intact.
Retain manifests/snapshots/logs and record scratch DB names; no broad cleanup/prune.

After exactly this campaign, stop/report. It authorizes no production patch,
100-owner diagnostic, full W1/W2/W3/W4, deployment or commit/push/merge.
If a repeatable isolated batch penalty appears, prepare a narrow DB-function plan
based on the responsible operation/cardinality; any guard/SQL change needs review
and owner approval before implementation. If not reproduced, report Inconclusive
for the100-owner cause and propose a separately bounded concurrency/polling/
environment investigation. Do not silently proceed to that second experiment.

## Option B — stop experiments and retain current checkpoint

Keep the checked implementation, failed evidence and all pending acceptance gates.
No code changes or runs. This saves further investigation time but leaves the
latency cause, full final-tail result and new-writer W4 unproved.

## Acceptance mapping and authorization boundary

Both options preserve p95<=250ms, p99<=1s,60s cycle/drain, final lag<=20, original
financial rules, Money/Quantity, RLS, transaction/idempotency/lock/freshness rules,
and default-off Live Trading. Persistent state remains in PostgreSQL. Temporary
benchmark measurements are observations, never session/business authority.
W1 stays Failed/Partial, W2/W3NotRun;0065writer W4PendingRevalidation, old0064W4Passed;
F17V18Partial/Failed and integrated NC-SET4-01 remain open. No new acceptance Passed.

Owner approved A before harness edits: implement the scoped test-only changes,
pass targeted checks, run the one predeclared paired campaign, then stop/report.
This approval supersedes the prior experiment stop only for the scope above; it
does not authorize production optimization, a100-owner trial, full W1 or Git publication.
