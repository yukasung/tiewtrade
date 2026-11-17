# Standalone internal20 W3 — NC_F17_CLOCK_01 replacement

สถานะ: **Incomplete** — measured four hours completed; final-tail acceptance timed out.
Owner authorized one replacement by “เริ่มทำ” after the refactor checkpoint. No
retry, threshold/source change, Git publication or opening performed afterward.

## Candidate and scope

Base b0d5580364268be7619f5369dc8488d440f12160 plus the approved/refactored harness
identified by [source receipt](clock-recovery-refactor-source-bridge.json).
Source hashes verified before and after; campaign reports candidate_unchanged=true.
Runner, schema, source inventory/config and seven-fault schedule pinned at startup.
A new artifact root preserves the original no-retry Incomplete and all prior grades.
Opt-in --publisher-clock-recovery selected, default production behavior unchanged.

20 simulated owners,400 baseline orders,20 workers,282 cycles/owner,28200 commands,
14400 measured seconds, original2commands/s scheduling and seven scheduled faults.
One120s/7-sample current approved preflight Passed. Fresh task-owned DB/Redis only.
No owner account or Live requests, no owner services paused/stopped.

## Observed result

- Measurement14400.002106s, campaign14617.360182s (4h03m37.360s), exit1/Incomplete.
- Offered/admitted/completed28200, rejected0;11280fills,5640cancels,5640replays,
  5640completed cycles. These are command counters, not a final financial oracle.
- All7 scheduled fault observations recorded RECOVERED:3worker restarts,
  2connection churn and2dedicated Redis outages. Do not infer per-owner/per-fault
  guarantees beyond the existing observation contract.
- Publisher reached144513inputs including setup/final drain. No clock reversal was
  observed by this run's recovery evidence: event=null, recovered_count=0, no warning.
  This is not proof of an OS/VM clock fix or of exercising recovery under load.
- Informational reconstruction using the unchanged transaction-start attribution
  and original fault exclusions:406752engine samples, p95=193.550333ms,
  p99=361.495417ms.4800periodic snapshots returned across20owners; p95=29.954792ms,
  p99=55.503875ms. This does not make overall acceptance Passed.

## Exact failure and limits of diagnosis

Final-tail shares a single60s budget. Initial watermark144063 was reached by all
owners after44.965377s; publisher stopped at45.010735s with finalhead144513 and
target144493. The next watermark read completed at59.153554s. Final cursor reads
for20owners then began at59.154384s, leaving about0.846s. All20 were cancelled by
the outer60s deadline while collecting final cursor evidence (TaskGroup); parent
pool returned checked_out0. Actual recorded drain60.045394s includes cancellation.

Drain polling recorded60successful input_recovery reads; maximum attempt24.545501s
including maximum gate wait20.098416s. The final-cursor group had4immediate DB
borrows and16waiting readers; all were cancelled at deadline. Retained data proves
where the time went, but has no query plan or final cursor values to prove the
underlying scan/DB cause. Large accumulated input-history reads are a hypothesis
from the query shape and144k head, not an established database-plan diagnosis.

The final per-owner financial oracle, global balance/position/input-lag invariants,
final snapshot/rebuild and final owned-pool acceptance were after this step and
were not executed. No claim of fully correct balances, no duplicates or final
financial reconciliation can be made solely from the completed command counters.
Processing-window retains the original measurement end; controller failure report's
window_end is later because the generic failure path records the drain failure time.
No window extension or exclusion was used to regrade this result.

## Cleanup and evidence

Campaign cleanup recorded0connections/0advisory locks. Launcher removed its DB via
normal DROP without force and stopped/removed only its ownership-labelled Redis.
PostgreSQL truncated the requested67-byte fixture identifier to63bytes; requested/
canonical mapping retained in database-canonical-name.json. Independent final check
used the canonical name and confirmed database absent,0connections/0locks; fixture
Redis absent. Owner PostgreSQL remains healthy, both original services running with
restart_count0. No prune/reset/images/volumes or other databases removed.

[Sanitized summary](clock01-four-hour-summary.json). Private artifact root:
validation-artifacts/f17-endurance20-clock01-20261115/ containing original manifest,
candidate binding, runner/launcher, campaign.log, preflight, processing window,
final-tail-drain, poll timeline, counters, resource samples, worker metrics,
position snapshots and cleanup receipts. Original source/evidence untouched.

Next: propose a bounded final-tail/query investigation and targeted real-PG tests
on representative accumulated input history before requesting any new4h campaign.
Keep60s/financial/safety criteria; do not automatically repeat or regrade this run.
Current execution is stopped/reported as required by plan stepD. No new fix or
experiment authorized here; owner instruction/approval required for the next plan.
F17 remains Pending Full Validation, original100-account Release and other
bot/notification/Live/opening dependencies unchanged; not Completed.
