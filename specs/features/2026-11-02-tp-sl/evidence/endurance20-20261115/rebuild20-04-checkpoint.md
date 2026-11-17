# NC-F17-REBUILD20-04 — complete scoped offline rebuild proof

สถานะ: **Passed — offline full rebuild20 only**,2026-11-16.
[Approved A budget amendment](../../rebuild20-budget-amendment.md) ·
[Sanitized summary](rebuild20-04-summary.json).

## Candidate and readiness

Owner approved one campaign with4200s total/reserve120s/workdeadline4080s. The only
runner changes from REBUILD20-03 are run/outputidentity,totalbudget and explicit final
verification receipt after the original verify_rebuild returns normally. No production
or harness runtime source change. Previous113realPG/process/replay safety cases and
28postrefactorfocused cases retained with exactsource fingerprints;fiveextracted-runner
cases Passed for success,lease rejection,money/evidence/closingdigest failure,plus AST
andbudget/reserve consistency before execution. One120s/seven-sample preflight Passed.

HEAD+workingtree diff/untrackedsource inventory,config,migrations/schema,runnercopy/hash
andreviewedexternalhelpercopy/hash pinned. Finalsource/runner/helperbinding Passed.
HEAD alone does not identify this tested candidate;the uncommitted sourceinventory and
diffhash are retained in the summary. Rawprivate evidence:
validation-artifacts/f17-rebuild20-04-20261116/;do not publish wholeconfiguration/helpers.

## Workload and exact financial/source evidence

All400 baseline orders prepared. All28,200commands offered/admitted/completed;zero
rejected.11,280fills/5,640cancels/5,640idempotentreplays/5,640cycles match the fixedprofile.
All20owners' financialoracles Passed beforepadding andagainbeforefinalverification.
Global checks Passed:17,320orders/11,280fills/5,640cancels/400expectedpending baseline
orders;zero unlinkedfills,invalidreservations/positions,wrongmode,duplicatefilleffects.
Finalinputlag0. Uses originalMoney/Quantity/cash/reservation/held/cost checks without
new rounding,amounts or financialfloat arithmetic.

Publichead96000 andexactprivate96000recordsperowner(total1920000). Privatepadding
economicdigest comparison Passed. Streamedpoll evidence177002attempts=finished=JSONLrows,
active0/truncatedfalse;originaldefault100000memoryguard unchanged. No records dropped,
leaseextension/reacquire,command/publication retry oracceptanceexception added.

## Final rebuild and closing gates — all Passed

20snapshots returned,p95=8.568ms,p99=8.580ms (original250ms/1s).
All20fullreplays returned,each96000evidence records and1checkpoint. Elapsed
34.085–42.024s/owner,all≤60s. Sumserialreplays712.043s;no timer reset,
query/decode/session exclusion or missingowner. position-result.passed=true.

Originalverify_rebuild completed the **post-rebuild economic_digest comparison** and
returned normally. Runner then recorded final_verification_including_post_rebuild_digest_passed=true.
This is evidence of completed comparison,not inference from20replay receipts alone.
No economicfacts changed acrosspadding orrebuild according to the originaldigests.

All21poolreports(parent+20workers) Passed the unchangedvalidator:errors=[],violations=[],
incomplete=[];20ownedworkers exited0.This run collected657resource samples. SampledpeakprocessRSS171720704bytes;
positionrecordedru_maxrsspeak245121024bytes,both<1GiB. Peakconnections58;lastactive
sample15 is not a finalleakmeasurement. Poolreturn/disposal and independentcleanup
provide that proof. Peaklockwaits1,last0. DBgrowth3892535296bytes. No poolwaiver or
whitelist of priorCancelledError was used. Shortoffline resources do not prove W3
long-term stability or100accountRelease acceptance.

## Actual time and cleanup

Total3531.425s (**58min51.425s**) inclpreflight/seed/history/verification/normalcleanup,
within approved4200s. Finalverification returned before resource stage3530.657s;
cleanup started3531.057s. Reserved120s was retained,not consumed to extend work after
its deadline. Changing budget did not change60s/owner or any correctness/safety gate.
PriorREBUILD20-03 staysIncomplete;its workdeadline cancellation is not regraded using this run.

Normalcleanup removed only theownedDB. Independentmaintenancecheck confirmedDBabsent,
0connections/0advisorylocks,noownedchildPIDs. ExistingPostgreSQLhealthy/restart0;
Redisrunning/restart0. No newRedis,other-service stop,forceDROP,owneraccount/Liveorders.

## Checkpoint and next scope

Scoped offline20owner financial/history/snapshot/fullrebuild/postdigest/resource/pool/
cleanup proof is now **Passed on this candidate**. The previousInterrupted/Incomplete
campaigns andtheirpoolFailures remainunchanged,including REBUILD20-03 despite its
successfulsubchecks. No4h/Git/CI/merge followedthisoneapprovedcampaign.

F17 remains **notCompleted / Pending Full Validation**. This offlineproof does not
replace fourhourW3,original100accountRelease,leasecause/sampler gaps orbot/notification/
Live dependencies. Next: check the observer/failure-cleanup readiness required by the
four-attempt review before proposing another explicitly approved four-hour profile.
Do not launch anotherlongrun solely because this scoped checkpoint Passed. The current
approvedscope ends stop/report;no sourceoptimization or newcampaign was started.
