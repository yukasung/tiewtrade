# NC-F17-TAIL-02 — Preserve cursor semantics without the grouped history sort

สถานะ: **Approved — owner authorized implementation, targeted checks and one comparison, 2026-11-15**
วันที่:2026-11-15 (Asia/Bangkok)
Feature:F17 existing validation branch, dependent on NC-F17-TAIL-01 diagnostic.

## Evidence and bounded objective

[TAIL-01 receipt](evidence/endurance20-20261115/tail01-diagnostic-checkpoint.md):
20episodes/2890260keys, all43read/plan observations returned. The current grouped
left join materializes144513rows per owner and sorts them on disk solely to group
availability from a single activity row (episode_id primary key). The historical
59s wait was not reproduced; worker contention/physical history/statistics remain
unresolved differences. Do not describe this optimization as its proven root fix.

Goal: remove this unnecessary grouped history sort from the harness cursor reader
without changing what it verifies or the single60s drain deadline. No index,
production, shared session, pool, RLS, trading or four-hour-profile modification.

## Proposed requirements and SQL contract

The same owner/ENGINE session must return the same availability and maximum input
ID across ALL visible keys in that episode, including multiple pairs/generations
and INPUT/REBASE decisions. Empty keys yield0; absent/invisible activity yields no
row and the existing failure; no pair/generation narrowing, cached cursor, skipped
owner, reuse of an earlier snapshot or optimistic READY. Each read remains a single
SQL statement with its existing isolation/snapshot behavior.

Proposed equivalent shape (subject to real-DB equivalence tests):

```sql
SELECT a.availability,
       coalesce((SELECT max(k.input_id)
                 FROM paper_execution_input_keys k
                 WHERE k.episode_id = a.episode_id), 0) AS input_id
FROM paper_order_activity a
WHERE a.episode_id = :episode
```

One activity row is guaranteed by its existing primary key. The correlated scalar
aggregate returns one maximum without joining/sorting every key by availability.
It still scans the visible history when the existing index cannot answer a global
max directly; do not claim constant-time/index-only behavior or remove the RLS scan.

## Implementation/reuse after approval

- Consolidate only the two identical harness reads in profile_workload.py into one
  small shared SQL/reader helper using the existing UserSession. Call it from
  wait_for_input_recovery and drain_final_tail's final cursor reader; retain both
  independent observations, all20owners, task joining, gate4, pool5+10, exceptions,
  source fencing/watermarks/lag bounds and the original60s total deadline.
- Update TAIL-01 SQL binding/tests for the new shared location. Preserve the exact
  historical old SELECT from pinned base b0d5580 and its recorded normalized digest
  as the comparison control, not a retrospectively modified baseline. Check source
  provenance before timed reads. Do not alter unrelated global-invariant queries.
- Reuse TAIL-01 valid bounded seed fixture, read-only timing observer, preflight,
  campaign ownership/budget/cleanup; no new retry or general performance framework.
- Keep MONEY/Quantity, balances, fills/cancels/position/risk and API/schema untouched.
  Existing production/clock recovery safety evidence remains valid unless impacted.

## Feature validation before one short comparison

1. Real-PG old/new exact result/exception equivalence: no keys, one/many keys,
   maximum across pairs and generations, duplicate INPUT/REBASE identities,
   READY/UNKNOWN/CONFLICTED activity, missing episode and cross-owner RLS.
2. One-statement reads under concurrent append use valid snapshots and never report
   more than committed keys; no earlier result reused for final confirmation.
3. Existing final-tail success/source mismatch/lag/timeout/error/cancellation tests
   and parent-poll joining tests. All20distinct-owner and future/negative-lag checks
   retained; no increase to60s, retries, gate, pool or source freshness tolerance.
4. Financial before/after read snapshots unchanged; reader remains read-only;
   scoped Ruff/format/mypy/whitespace Passed. No full suite or4h repeat at this point.

## One bounded old/new campaign after Feature checks pass

One fresh migrated DB,20episodes/144513keys each, original TAIL-01 valid evidence
shape; one120s preflight. Same fixture and role/RLS for every arm. Fixed order:
old serial20, new serial20, old concurrent20 through gate4, new concurrent20 through
gate4; then3old/3new plans for owners1/10/20.86observations total. Retain every timing,
including startup/cache/order effects; this is one ordered comparison, not random
sampling or proof of4h contention. No warmup removal or cache/server tuning.

Same25min total cap from preflight,5min measurement cap and local10s statement
limit; at least2GiB free before/between batches. Expected20–25min including seed/
cleanup, in addition to implementation/targeted checks; approximately45–90min total.
Valid fixture counts/payload/RLS, exact old/new output equality and no financial
writes are mandatory. Explain must show the new shape no longer needs the grouped
join's disk Sort; report all timing/regressions without inventing a new SLA.
If unsuccessful/inconclusive stop/report; no automatic query change or extra run.
Do not use an isolated faster query to certify W3's60s final drain or financial proof.

## Stop gates

A. Owner approves this amendment before implementation and timed comparison.
B. Implement and pass targeted Feature checks, then run the one bounded comparison.
C. Stop/report with source bridge/evidence and remaining uncertainty. Owner-directed
review/fix/refactor gates remain. No Git or4h replacement authorized by this plan;
any new4h execution requires a separate instruction after those checks.

Both prior4h results remain Incomplete. Final financial/global/rebuild acceptance
and100-account Release/opening/dependencies remain pending. F17 not Completed.
Current change: proposal only; no runtime query/source/timeout/criteria change.

## Owner approval

Owner replied “อนุมัติ”. Steps B–C authorized; stop/report after the one comparison.
Use a shared harness SQL constant/reader for both existing call sites. Bind current
diagnostic to that reader/constant and both callers; preserve the control via
immutable b0d5580 source and TAIL-01 recorded normalized SQL digest. No4h/Git action.

## Execution checkpoint

Approved B–C executed: [receipt](evidence/endurance20-20261115/tail02-comparison-checkpoint.md).
123local targeted tests/static checks Passed and one86-observation comparison
completed in20m17.443s. New plans removed Sort/tempIO; results equal. Stop/report.
Known publication blocker: git-based baseline retrieval is not shallow-checkout
portable; report for owner review/fix gate, no post-campaign candidate edit. No4h/Git.

## Owner-directed review corrections — 2026-11-15

Owner instructed “แก้ไข” for Medium R1/R2 after the read-only review. Package the
exact verified historical SELECT in a small fixture with revision/path/normalized
digest; runtime loading must work without ancestor objects or Git commands and
reject missing/corrupt/mismatched control data. Strengthen AST binding to require
the actual awaited execute/reader-call expressions, SQL and episode arguments,
not name counts alone; preserve positive formatting tolerance and add negative
concatenation/non-call/wrong-argument tests. Remove the obsolete runtime historical
source extractor once the fixture is pinned. Keep actual old/new SQL and runtime
reader/drain unchanged; bridge retained comparison evidence without rerunning any
timed campaign. Run targeted tests/static checks, then ask for the separate required
refactor instruction. No4h, workload, Git or CI execution authorized here.

Review corrections implemented and targeted validation Passed: [R1/R2 receipt](evidence/endurance20-20261115/tail02-review-fixes.md).
No timed campaign/Git/CI; await separate owner refactor instruction.

## Owner-directed R1/R2 refactor — 2026-11-15

Owner instructed `refactor the code`. Limit changes to the reviewed corrections:
reuse the identical caller-binding expression, traverse each function AST once
and compare matching statement kinds, name the verified digest once, and align
new test imports with existing module-level patterns. No new abstraction or change
to accepted/rejected bindings, error messages, fixture/query/transaction behavior.
Run affected binding/control and real-PG equivalence tests plus scoped static checks;
retain unchanged parent-poll/final-tail/workload evidence with a source bridge.
No new timed run, Git or CI; stop/report and identify the next existing gate.

Owner-authorized R1/R2 refactor and affected validation Passed: [receipt](evidence/endurance20-20261115/tail02-refactor.md).
No workload/Git/CI action; publication instruction and separate4h execution gate remain.

## Owner-authorized four-hour confirmation — 2026-11-15

After review corrections/refactor and affected validation, owner instructed
“เริ่มทดสอบสี่ชั่วโมง”. Authorize one fresh standalone PAPER_INTERNAL20_V1 W3 on
the current TAIL-02-refactor source receipt:20owners/400baseline/28200commands,
14400measured seconds and unchanged seven-fault schedule, original financial,
snapshot/rebuild, processing, resource and60s final-tail acceptance. Retain the
approved NC_F17_CLOCK_01 opt-in cap1event/1retry/1s; no new relaxation. Preflight
once, isolated owned DB/Redis, stop/report and cleanup on failure without retry.
Artifact root f17-endurance20-tail02-20261115. Pin source/config/schema/runner, keep
old outcomes intact and no commit/push/PR/CI/merge under this execution request.

## TAIL-02-refactor confirmation outcome

[Execution receipt](evidence/endurance20-20261115/tail02-four-hour-checkpoint.md):
Incomplete at14371.934s/28143commands due WriterLeaseLost before final-tail. Approved
clock recovery succeeded once in125.802ms; overall4h/financial/rebuild acceptance
not reached. Campaign cleanup initially false for autovacuum; final owned cleanup
independently0/0 and resources absent. Stop/report, no new retry/source/TTL/Git action.
