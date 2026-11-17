# NC-F17-REPLAY-01 — short evidence-reader diagnostic

สถานะ: **Diagnostic complete — no historical regrade or production fix**
2026-11-16, owner instructed เริ่มทำ; engineering delegation2026-11-14 applied.
[Amendment recorded before source](../../replay-read-diagnostic-plan.md).

Added task-scoped ReplayReadObserver and4targeted tests under execution_market.
Original production reader,SQL,decoder and ownerUserSession/RLS retained. No money,
quantity,positionformula,session/infrastructure architecture,tradingretry or lease
change. ContextVar counters are transient diagnostic timing only,not persistent
business/session storage. Wrapper calls originals once and restores them on error/
cancellation. Foreign task inheriting context cannot contribute to parent counters.

4tests Passed,including actualPG enumeration/RLS/financial-no-write,decodererror
identity/original-once,async cancellation/restoration and inherited-task isolation.
Test log: validation-artifacts/f17-replay01-tests-20261116/attempt-1794781971566445000.log.
Scoped2-file Ruff/format/mypy Passed; unused type-ignore comment removed aftertest,
no behavior change. No fullsuite/CI/repeatedcampaign.

## One run and actual observations

Single120s/7sample preflight Passed before creating owned migratedDB. Copiedrunner,
configuration/schema/source pinned; sourceunchanged. Two synthetic owners,owner1
96000valid source records seeded with reused500batch helper,owner2empty for RLS.
Explicit generatedDB ANALYZE keys/input tables retained. One original reader
4096page enumeration in one ENGINE read-only owner session,unchanged60s budget,
then2originalSELECT EXPLAIN ANALYZE BUFFERS under same role/RLS(first/latepage).
No command sent,no newRedis,no ownerdata copied.

Diagnostic complete202.624665s total (3min22.6s),37.011320s seed,
36.706661s enumeration.96000records in exact1..96000sequence,25SQLcalls (24nonempty
pages plus emptyterminal),96000originaldecoder calls. Owner2 cannot readowner1;
existing financial_state before/after exactlyequal. This is fixture-only no-write
proof,not F17 final ownerfinancial/global verification.

Within enumeration, SQL+driver result span8.658598s,decoder span27.637752s.
These wall-clock spans include scheduling; do not call SQLspan pure servercost or
claim exactCPU attribution. Mapping/result/caller/session remainder retained,
not excluded to improve elapsed. [All25pages and2plans](replay01-summary.json).

Firstpage serverplan: HashJoin returns96000records,externalmerge Sort of payloads
beforeLimit4096;sort138408kB disk,execution504.373ms. Latepage after94208:
keySeqScan removes94208rows,NestedLoop with actual1792payloadrows,quicksort,
execution12.346ms. These prove query shape on this explicitly analyzed fixture;
they do not recover the old20ownerDB plan/cache/payload statistics or fully explain
why historicalowner14 exceeded60s. Both repeated decoding and fetching/sorting
payloads are relevant optimization candidates; no checks were skipped or rewritten.

## Blocker evidence, cleanup and next checkpoint

Static evidence audit confirms sampler's first sampleTimeoutError is recorded only
as an errorcounter and ends the monitor. No failure timestamp/stage/association was
saved in the oldreceipt. It is impossible to recover a blocker identity from those
artifacts aftercleanup. A future bounded failure envelope should retain stage/partial
progress/task association without extending1s/500ms/200msbounds or loggingSQL/secrets;
that change has not been made here. Historical0samples must not become0contention.

Docker was initially unavailable,then started normally. The two existing stopped
PostgreSQL/releaseRedis containers were started for verification; no otherservice
was stopped/reset and no owner/Live commands sent. Owned fixtureDB normaldropped;
independent maintenanceDB check: absent,0connections,0advisorylocks. ExistingPG
healthy/restart0,existingRedisrunning/restart0. No retainedresources,newRedis,forcedrop.
Raw local configuration private; do not publish artifact directory wholesale.

Authorized shortdiagnostic completed; stop/report under amendment. Preserve original
FENCE-02Incomplete and all oldergrades. Fullfinancial/global/rebuild20owner/resource/
100accountRelease and otherF17 dependencies remain pending; F17 notCompleted.
Next: review the new diagnostic harness and prepare the smallest evidence-backed
reader/decoder optimization plus bounded sampler-failure envelope with exact result,
RLS,financial-no-write and cancellation proof. No furthermeasurement/4h/Git/CI in
this scope; no timeout relaxation justified by this diagnostic.
