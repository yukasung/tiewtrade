# NC-F17-REBUILD20-03 — streamed-evidence replacement campaign

สถานะ: **Incomplete — overall work deadline during post-rebuild economic digest**.
2026-11-16. [Approved execution scope](../../rebuild20-streamed-execution.md) ·
[Sanitized summary](rebuild20-03-summary.json).

## What passed

One120s/seven-sample preflight Passed before isolatedDB creation. Candidate source/diff,
config,migrations/schema,copiedrunner and explicit reviewed externalhelper copy/hash
were pinned;finalsource/runner/helper binding stable. Prior113realPG/process/replay
safety cases and28postrefactorfocused cases reused;4extracted-runner handoff/lease/
monetary/evidence failure checks Passed before this single campaign. No runtime source
changed during execution.

All400 baseline orders and28,200 workloadcommands completed/admitted;zero rejected.
11,280fills,5,640cancels,5,640idempotentreplays,5,640cycles. All20 financial owners Passed
both before private history and again immediately before final snapshot/fullreplay.
Global invariants Passed:17,320orders/11,280fills/5,640cancels/400expectedpending baseline
dispatches;zero unlinkedfills,invalidreservations/positions,wrongmode,duplicateeffects.
Final inputlag0. First pre-padding lag78290 was a transitional fixture state,not a
finalacceptance result;the completedfanout subsequently closed it to0.

Committedpublichead96000;exact96000privateinputs for each of20owners(total1920000).
Digest comparison across privatepadding Passed: no economicfacts changed by padding.
Streamedpoll evidence complete:170913attempts/finished/JSONLrows,active0,truncatedfalse.
This runtime crossed the previous100000-row stop and completed preparation without
removing the default guard or dropping pollattempts.

**Final positions/snapshots/fullreplay Passed:**20snapshots returned(p95=23.723ms,
p99=24.215ms);all20fullreplays returned,each checked96000evidence records and1checkpoint.
Per-owner elapsed34.222–47.742s,all≤60s. Sum737.618s(12min17.618s) across20serialreplays.
position-result.json explicitly says passedtrue. These are scoped successful results,
not permission to regrade the whole campaign.

## Why the campaign remains Incomplete

Overallbudget3600s reserved120s for cleanup,so operations had to stop at3480s.
Controller's asyncio.wait_for timedout at that absoluteworkdeadline. Final evidence
shows all20replays andposition-result had alreadyreturned successfully. Cancellation
occurred in verify_rebuild's **post-rebuild economic_digest/table_digest**, confirmed
by ADMIN_OBSERVER cancellation await-chain and the successful positions object in the
partialverification report. The post-rebuild digest comparison did not finish;cannot
assert economicfactimmutability across replay or waive that mandatory check.

Actual phases(elapsedfromcampaignstart):economicfixture127.407→1901.290s;
publichistory1901.290→2082.969s;financialbeforehistory2082.969→2085.581s;
privatehistory2085.581→2736.841s;fullrebuild2736.841→workdeadline3480s.
Preparation through finalrebuildentry consumed45min36.841s;serialreplays alone needed
12min17.618s,leaving onlyabout5.5s for other verification work inside the58minworkbudget.
This demonstrates inadequate budget/headroom for the complete orchestration on this
run;it is not evidence that the60s per-owner correctness/performance bound failed or
that table_digest itself requires optimization. No server/query stage timing was added
to establish a digest bottleneck. Never infer cause beyond these observed bounds.

Totalelapsedincludingnormalcleanup3480.913s(58min00.913s),not a3600s expiry. The explicit
120s reserve was retained;none was silently reassigned to finish the experiment.
Initial live commentary used the lastheartbeat's19receipts to describe an in-progress
lastowner;finalfiles corrected that interpretation:20fullreplayscompleted before the
post-check cancellation. This document andsummary use finalreceipts exclusively.

## Resources / pool result / cleanup

647samples:sampledpeakprocessRSS170409984bytes,peakconnections64,peaklockwaits1,
lastsamplelockwaits0,DBgrowth3892101120bytes. Positionchecks additionallyrecorded
ru_maxrss251969536bytes;sampledRSSalone does not represent the cumulativeprocesspeak.
Both observedpeaks remain below1GiB,but finalaggregateacceptance was not reached.

All20ownedworkers exited0 andtheirpoolreportsPassed. Parentreport remainsFailed:
ConnectionResourceError1 from ADMIN_OBSERVER cancellation duringeconomicdigest;
aggregateFailed/Incomplete with PoolFinalEvidenceIncomplete. Finalallfiveparentpools
checked_out0/final_disposedtrue does not override those validatorresults. No new
cancellationexception/whitelist was introduced. Post-stop resource/pool summaries are
retained as observations,not a retroactivePassed campaign.

NormalDROP removed only the provenownedDB;independentmaintenancecheck confirmsDBabsent,
0connections/0advisorylocks,noownedchildPIDs. ExistingPostgreSQLhealthy/restart0;
Redisrunning/restart0. No newRedis,service stop,forceDROP,owneraccount orLivecommands.
Rawprivate artifacts at validation-artifacts/f17-rebuild20-03-20261116/;do not publish
configuration/helpers/wholeartifacttree wholesale.

## Next proposal / stop

The approvedreplacementrun has ended. No automaticrerun,sourceoptimization,4h,Git,
CI ormerge. F17notCompleted. PreviousREBUILD20-02Incomplete/poolFailed andall4W3Incomplete
remain;this is a scopedoffline run,not a fifth/sixth four-hour enduranceattempt.

Next decision should review **campaign budget and phase accounting** from measured
preparation45m37s +serialreplays12m18s +mandatoryclosingdigest/resource/cleanup. Keep
all20owners/history/financialoracles/60s-per-owner/poolrules;do not extend the owner
rebuildbound based on this result or call unfinisheddigest optional. Prepare a bounded
revised orchestration/budget proposal before another experiment;do not repeat nearly
onehour merely for confidence. Any new budget/retained-fixture/checkpoint approach must
be explicit and approved before implementation/execution. No such change made here.
