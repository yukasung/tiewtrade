# REBUILD20-05 — representative full replay20

สถานะ: **Passed — scoped offline financial/history/full replay20**,2026-11-17.
[Plan](../../rebuild20-representative-history-plan.md) · [Summary](rebuild20-05-summary.json).

## Candidate and scope

Owner instructed เริ่มทำ after REPLAY05 query comparison and recommendation to verify
complete financial replay20 at representative144364input history. Reused REBUILD20-04
runner operations unchanged except history head/counts,runidentity and current safety
bindings. AST equivalence checked for operations after numeric head substitution;
remaining()/mark()/4200s budget/reserve120 unchanged. No production/test-source edits
this turn. Retained valid existing fixture/cleanup proofs and REPLAY05 safety cases.

Startup candidate matched REPLAY05 final tested inventory. Pin source inventory,HEAD+
diff/untracked state,config,migrations/schema,runner/helper hashes before one120s
preflight. PreflightPassed. Final source/runner/helper bindingPassed. Raw private files:
validation-artifacts/f17-rebuild20-05-20261117/. Do not publish credentials/helpers.

## All required scoped checks passed

-20synthetic owners/400baseline/282cycles each:28200offered/admitted/completed,
 zero rejected;11280fills,5640cancels,5640idempotentreplays,5640cycles.
-20financial oracles Passed before history and at final verification. GlobalPassed:
 17320orders,11280fills,5640cancels,400expectedpending baseline;0unlinkedfills,
 invalidreservations,invalidpositions,wrongmode,duplicatefilleffects;finalinputlag0.
-Publichead144364;private144364perowner,2887280total. Exact economic digest unchanged
 acrosspadding;post-rebuild digest completed successfully and explicit receipttrue.
-20snapshots,p95=9.302ms,p99=9.650ms within250ms/1s.
-All20complete financial replaysReturned,each144364evidence/1position/1checkpoint.
 Perowner44.047–46.732s,each≤original60s;serialsum905.767s. Includes all query/driver/
 decode/fold/session work under the original per-owner timer;no reset/exclusions/retry.
-All21poolreportsPassed,errors/violations/incomplete empty.20ownedworkerexitcodes0.
 Streamedpoll155435attempts=finished=JSONLrecords,active0,truncatedfalse.
-711resource samples;sampledpeakRSS442449920bytes,ru_maxrss450822144bytes (both<1GiB).
 Peakconnections58;lastsample15 is before disposal,not finalleak evidence. Peaklockwait1,
 end0. Databasegrowth5615935488bytes. No criteria relaxation or canceled-error waiver.

## Time and cleanup

Total3784.202s (**63min04.202s**) including preflight/fixture/verification/cleanup,
within4200s. Work verification finished at3783.355s,before4080s workdeadline;cleanup
reserve120s preserved. Stages: economic fixture1509.388s;publicextension281.504s;
privatepadding/digests/counts951.014s;fullverification912.172s. These are coarse runner
stage spans,not isolated server query timings.

Only owned freshDB removed. Independent maintenance query confirmed DBabsent,
0connections/0locks;all20ownedworkerprocess identifiers inactive. No newRedis,forceDROP,
other-service stop,volume removal or owner/Live trades. Intermittent read-only progress
queries against the ownedDB ran within elapsed time;no observed samples were excluded.

## Meaning and next checkpoint

The full20owner replay gap at144364records is closed on this candidate under the
original60s bound. This result supports keeping that criterion. It does not reproduce
all historical CUT01 data or prove4h stability/100accountRelease or remaining bot/
notification/Live dependencies. HistoricalCUT01W3Incomplete and all earlier Failed/
Incomplete remain;F17 still Pending Full Validation,notCompleted.

Current one-run scope ends stop/report. Next: prepare/pin the original four-hour W3
20owner campaign on this candidate,verify its remaining prerequisites andfreshpreflight,
then run that separately when instructed. No automatic4h rerun/Git/CI/merge executed.
