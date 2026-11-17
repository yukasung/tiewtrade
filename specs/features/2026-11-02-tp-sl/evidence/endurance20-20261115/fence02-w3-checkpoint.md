# NC-F17-FENCE-02 — one observed four-hour W3 checkpoint

สถานะ: **Incomplete — rebuild owner14 exceeded60s; blocker evidence incomplete**
Execution started2026-11-15; terminal failure2026-11-16 03:57:08+07:00.
F17 remains notCompleted. [Approved amendment](../../publisher-fence-endurance-plan.md).

## Scope, implementation and safety checks

Owner explicitly authorized plan/adaptation/safety tests/one4h run. Existing
PAPER_INTERNAL20_V1 W3:20fixtureowners,400baselineorders,20concurrentworkers,
282cycles/owner,28200commands,14400measured seconds,original7fault schedule.
No production source/API/schema/trading rule,5s lease,financial formula,deadline or
retry allowance changed. Combined lease/fence observation was enabled only for this
exact W3 combination with existing CLOCK-01 flag; other disallowed combinations
still reject. Guard counting observes original calls once in the selected task;
postrollback observer probe is skipped without reopening a completed transaction.
192distinct targeted cases Passed before the run (191combined44.09s plus foreign-task
case4.95s), including real-PG rollback/commit/recovery/negative/cancel/default/pool
proof. Scoped4-file Ruff/format/mypy and whitespace Passed. No new CI claim.

Single120s/7sample preflight Passed before fixtureDB/Redis. Candidate/config/schema,
exact schedule/copied runner/launcher pinned; sources unchanged through cleanup.
HEAD b0d5580364268be7619f5369dc8488d440f12160 plus pinned uncommitted harness;
[summary includes source/runner hashes](fence02-w3-summary.json). This instrumented
20account diagnostic is not original100account/no-observer Release acceptance.

## Actual result

**Incomplete**,15353.547435s total (4h15m53.5s), inside18000s outer cap.
Measurement14400.000637s completed. All28200offered/admitted/completed,0rejected;
5640cycles,11280fills,5640cancels,5640idempotent replays. No worker failures recorded.
All7declared fault windows have restored endpoints; complete recovery acceptance
was not finalized because final workload result is absent. Do not promote these
partial records to a whole-campaign pass.

Final-tail completed24.060770s within60s; all20owners at finalhead144249,lag0.
4820/4820periodic+final snapshots RETURNED; posthoc original percentile formula
p95/p99 36.742/71.382ms. These snapshots alone do not certify rebuild/position gate.
13owner domain replays RETURNED (largest59.728058s); owner14 timed out under the
unchanged60s asyncio budget, observed61.086243s including cancellation/unwind.
Its recorder captured29queries/94777returned rows. Remaining6owners NotRun.
Stack: profile_positions.py:122/124 → profile_restore.py:249 → production
paper_orders/storage.py:418 read_execution_inputs → session.execute/asyncpg fetch.
This identifies the interrupted read, not proven server execution cost or blocker.
Driver/scheduling/server contributions have not been separated.

The replay exception precedes final verify()/verify_global_invariants(), aggregate
pool/resource grading and result publication. **Final20owner financial oracles,
global invariants,full position/rebuild/resource acceptance: NotRun/incomplete.**
Counts do not establish balance correctness. No claim of corruption or absence of
corruption is inferred from partial output.

Posthoc engine measurement using original transaction-start attribution and only
original7declared fault intervals:346803samples,p95/p99 246.556/449.197ms,80worker
reports across initial/restart generations (20concurrent,not80concurrent). Numerical
latency values meet both current500ms/2s and original250ms/1s targets, but are partial
evidence,not a campaign pass. No slow samples trimmed or resource waiver applied.
81individualpoolreports:80workersPassed; parentFailed with ConnectionResourceError1
and outcomeTimeoutError during the rebuild read cancellation. All final checked-out
counts0. Original pool inventory matched; aggregate acceptance NotRun. This does
not establish a connection leak; parent failure is retained,not reclassified away.

## Publisher and observer limits

144249publications RETURNED,144249actual guards/readiness checks,0publishererrors;
maximum publication2.928980s. No lease loss reproduced; CLOCK-01 used0events/0retries,
no warning. This does not prove the previous9.848s stall is fixed.
Fence monitor recorded TimeoutError1,0successful blocker snapshots; monitor joined.
The first sampling attempt timed out and the monitor stopped by existing policy.
Consequently blocker evidence is incomplete even though publisher continued; the
lease finalizer preserved the primary replayTimeoutError and attached
`lease observer evidence failed: ValueError`. Do not interpret0samples as0contention.
The recorded error type has no complete statement/blocker association or failure
instant; do not invent a blocker or timing attribution. Independent failure witness
is null because the publisher itself did not fail.

## Cleanup and checkpoint

Coordinator normally removed only its ownedDB and labelledRedis after joining work.
Independent maintenanceDB check: database absent,0connections,0advisorylocks;
ownedRedis absent. OwnerPostgreSQL running/healthy/restart0 and ownerRedis
running/restart0. No retained resources, force drop, owner/Live order or owner service
change. Raw local artifacts are under validation-artifacts/f17-fence02-w3-20261115
and include private configuration: do not publish wholesale.

Historical Failed/Incomplete results remain unchanged. One approved run completed
through terminal evidence and independent cleanup; no rerun,production/harnessfix,
commit/push/PR/CI/merge. Stop/report per approved plan. Next recommended scope is a
short isolated replay investigation using representative~96kinput histories and
review of sampler failure evidence, before proposing fixes or another4h run.
Keep60s/financial/lease criteria; no evidence supports relaxing correctness/safety.
F17 original100account Release/opening/bot/notification/Live dependencies remain.
