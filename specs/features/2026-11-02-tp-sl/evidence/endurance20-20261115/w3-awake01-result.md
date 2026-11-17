# AWAKE01 — observed original four-hour W3

สถานะ: **Passed — scoped observed PAPER_INTERNAL20_V1 W3**,2026-11-17.
[Execution amendment](../../endurance20-four-hour-execution.md) ·
[Sanitized summary](w3-awake01-summary.json).

## Candidate, environment and scope

Owner instructed เริ่มทำ after the sleep-related REPLAY05 Incomplete. Recorded AWAKE01
amendment before preparing launcher. Reused REPLAY05 launcher unchanged except run
identity; normalized AST/compilePassed. Candidate matched both tested REPLAY05 and
REBUILD20-05 inventories. No shared production/test-source changes in this turn.
Existing safety/review/refactor evidence retained; no new Git/CI/merge.

Native `caffeinate -is` surrounded the entire launcher. Success and failure child tests
both proved active owned idle/system-sleep assertions and removal on exit. AC confirmed;
owned assertions independently observed during real preflight and periodic monitoring.
No persistent power configuration or display assertion. One120s preflightPassed before
fresh ownedDB/Redis fixture. Scoped pmset log inspection found no Sleep event between
assertion-start and post-cleanup check. Assertions and process absent after completion.

Preserved20synthetic accounts,400baseline orders,282cycles/owner,28200commands,2/s,
20workers,poll4,claimcoordination and all seven scheduledfaults. Original5s lease,
financial/original60s per-owner replay/resource bounds unchanged. Existing observer,
clock recovery andfailfast options retained; no retry/reacquire added. Original18000s
outerbudget and120s cleanupreserve preserved. Source/runner/config/fault bindings
unchanged throughout. Raw private evidence validation-artifacts/f17-w3-awake01-20261117/.

## Results

- Measured **14400.000262s**, complete continuous4h. Total including preflight,
  preparation,finalverification andcleanup **15666.953s =4h21min06.953s**,within5h budget.
- **28200offered/admitted/completed**,0rejected;11280fills,5640cancels,
  5640idempotent replays,5640cycles. All20finalownerfinancialoraclesPassed.
- GlobalinvariantsPassed:17320orders,11280fills,5640cancels,400expectedpendingbaseline;
  unlinkedfills,invalidreservations,invalidpositions,wrongmode,inputlag,
  duplicatefilleffects all0. Pendingbaseline400 is expectedfixture,not unmatchedwork.
- Sevenfaults allRECOVERED:workerrestart33.078s,connectionchurn30.121s,
  Redisoutage60.183s,restart33.501s,churn30.031s,Redisoutage60.218s,restart34.048s.
- Finaltail **27.916s≤60s**. Publisher144278Returned,144000measuredinputs≥141000;
  noWriterLeaseLost,no clock recovery. Fence observer1sample,errors{},taskjoined;
  observer presence does not prove absence of all contention.
- Engine transaction p95 **108.916ms**,p99 **193.857ms**,596882samples;both approved
  pilotlimits500ms/2s andtargets250ms/1sPassed,performancewarningfalse. Only original
  scheduledfault exclusions applied,no new sample filtering. End-to-end command
  p95=1.600s,p99=1.965s,max=6.901s is a distinctmetric,not the transaction SLA.
- **4820/4820snapshots**,p95=15.751ms,p99=30.727ms.
- **20/20fullfinancialreplaysReturned**,143070–143352evidence records/owner;
  each51.858–56.567s≤60s,oneposition/checkpoint each. No cursor reset,shortcut,
  mock,retry orlimit relaxation. Representative REBUILD20-05 remains separatePassed.
- All81poolreports(parent+80worker generations)Passed;errors/violations/incomplete[].
  ResourceassertionsPassed;2864samples,peakconnections61,end55beforepooldisposal,
  0lockwaits. Peak sampledprocessRSS128548864bytes;replaypeak220577792bytes.
  RSS endurancegrowth−1.789%,Passed. DBgrowth9037283328bytes. Finalconnectionzero
  is independently verified below,not inferred from pre-disposal sample55.

## Cleanup, interpretation and next checkpoint

Only ownedDB/Redis removed normally. Independent maintenance query provedDBabsent,
0connections/0locks;Redisabsent.83ownedprocessidentities(parent,80workergenerations,
launcher andcaffeinate)inactive. No other service stopped,no forceDROP/volume removal,
no owner/Live orders. Sleepassertionreleased;permanentpower settings unchanged.

Underlying runner/campaign both **PASSED**. Observer metadata remains diagnostic_only;
this is scoped observed original4h W3 evidence for internal20,not100accountRelease,
unobservedperformancebenchmark or F17Completed. Preserve historicalREPLAY05/CUT01
Incomplete and allolderFailed/Incomplete;this does not rewrite their outcomes or
establish their causes. Engineering/source changes accumulated before this run are
still unpublished on this worktree.

This one-run checkpoint is finished;noautomaticextra workload. Next consolidate this
candidate's valid Paper evidence and audit remaining release/publication gates before
publication or broaderacceptance. No new4h rerun is justified solely for confidence.
F17 remains Pending Full Validation until all applicable gates/dependencies pass.
