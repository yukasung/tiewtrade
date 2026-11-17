# REPLAY05 original four-hour W3 replacement

สถานะ: **Incomplete**,2026-11-17; stopped/reported, no automatic replacement.
[Execution](../../endurance20-four-hour-execution.md) · [Summary](w3-replay05-summary.json).

## Scope and readiness

Owner instructed เริ่มทำ after REBUILD20-05 Passed. Candidate matched both retained
REPLAY05 tested inventory and REBUILD20-05 inventory (1046paths). Existing coordinator
source hash and seven-event fault schedule unchanged. Private launcher compiled and
matched CUT01 AST after run-identity normalization. Existing correctness/safety proofs
remain valid; no shared runtime source changed. One120s preflightPassed, then fresh
owned database/Redis and20synthetic accounts. Same14400s measurement/18000s totalbudget,
120s cleanupreserve,28200commands,originalfaults/flags/leases/money/resource checks.
Raw private artifacts: validation-artifacts/f17-w3-replay05-20261117/.

## Observed failure and power evidence

Publisher tick10473 rejected at book renewal with WriterLeaseLost. Previous10472
publications returned; last tick10472 took45.007ms with PostgreSQL precommit time
04:47:13.731185UTC and confirmed session exit. Failed attempt took4.822ms, before guard
or publication. Independent failure witness recorded committedcursor10472,generation1,
sameowner and lease_until04:47:18.707218UTC, while db_now was04:56:40.107926UTC.
No replacement publication, reacquire, clock recovery or safety waiver occurred.

Read-only macOS pmset evidence identifies Idle Sleep at **11:47:10+0700**,569seconds,
then DarkWake at **11:56:39+0700**, immediately before rejection11:56:40. This establishes
host sleep overlapping the publication gap and lease expiry. Monotonic publication
spans do not include that suspended wall time; do not infer a fast continuous wall-time
operation or attribute this gap to SQL/server commit. System sleep explains this run's
lease expiry; this is not proof about the causes of earlier failures.

Measurement timer reached1042.037s (17min22.037s); total runner monotonic1201.360s
(20min01.360s). Wall time includes sleep and is longer; neither figure represents a
completed continuous4h run. No scheduled fault was reached. Runtime timer alone must
not be used to claim uninterrupted host availability.

## Partial workload and remaining validation

At failure:2081offered/admitted,2079completed,0rejected;831fills,416cancels,
416idempotent replays,415cycles. HTTP receipts2081Returned,360snapshotsReturned.
Two admitted commands not counted completed at failure are not claimed lost, duplicated
or fully verified; no final economic oracle was reached. Finaltail/full20rebuild/final
financial andglobal oracles/aggregate acceptance **NotRun**. Earlier REBUILD20-05 remains
Passed for its own candidate/scope; it does not convert this W3 toPassed.

207resource samples:peak61connections,0lockwaits,peakindividualRSS106430464bytes.
Not a completed resource acceptance result.20workerpoolreportsPassed;parentreport
False with outcomeWriterLeaseLost,retained as-is. Parent borrows all0beforefinaldispose;
no parent resource_errors recorded. These cleanup facts do not waive the failed outcome.

## Cleanup and next step

Original launcher removed only ownedDB/Redis. Independent maintenance query confirmed
DBabsent,0connections,0locks;Redisabsent;20ownedworkerPIDs inactive. NoforceDROP,
other-service stop,volume removal,owner/Live orders orGit action.

Next recommendation: use a process-scoped macOS sleep assertion during the next entire
campaign (including preflight and cleanup),verify it is active and released on exit;
keep all trading/lease/duration criteria unchanged. It prevents idle sleep rather than
changing permanent power settings; explicit sleep/lid closure must still be avoided.
Record the launcher amendment before another run and preserve this Incomplete. This
one-run checkpoint stops here; no additional4h campaign automatically launched.
F17 remains Pending Full Validation,notCompleted.
