# REPLAY-03 replacement — criterion review, 2026-11-17

สถานะ: **Diagnostic Complete; no acceptance-criterion change**

Owner reported Docker opened after blocked attempt. Docker daemon was available but
both existing dependency containers were exited; started only tiewtrade-postgres-1
and tiewtrade-f18-release-redis, no volume/data deletion. PostgreSQL healthy and Redis
PONG before one original120s preflight. Initial Incomplete/no-fixture attempt preserved.

## Results

One fresh database,144364 valid synthetic records for owner1,empty owner2,RLS ENGINE
reader,original4096page size and60s bound. All144364 decoded exactly once in contiguous
cursor order;37pages including terminal empty. Reader55.346359s,SQL+driver20.312467s,
decode34.372482s;these instrumented phases are not server-only and do not explain exact
historical W3 elapsed time. Full run245.796008s (4m05.796s),including preflight/seed/cleanup.
Owner2 could not read owner1 records;financial_state unchanged;source/runner/helper
bindings unchanged. No trading/API/production/schema/query changes or financial retry.

First-page EXPLAIN (taken after enumeration): joins144364rows,external merge sort uses
208128KiB (~203.25MiB) disk,then LIMIT returns4096. Execution1491.772ms. Late-page
(after143360) plan returns1004 with memory sort,25.491ms. These two selected plans do
not prove all pages used the same plan and are not CUT01's historical plan.

Independent cleanup confirmed database absent,zero connections/locks. No new Redis.
Raw: validation-artifacts/f17-replay03-r2-20261117/.

## Criterion decision / next recommendation

Keep60s for now. Reader alone consumed55.35s,leaving4.65s for position/cash/checkpoint
and session work under full replay. This explains why margin is small,not proof of the
exact cause of CUT01's timeout or proof that60s is intrinsically wrong. Prior96000-record
rebuild evidence covers a smaller volume; do not extrapolate it as144364-record proof.

There is concrete query-plan inefficiency to investigate before relaxing the criterion:
bound the ordered owner/episode/pair cursor keys before fetching wide evidence payloads,
using existing indexes where possible. Proposed only; require exact old/new enumeration
and decoded-result equivalence under real RLS,foreign-owner negatives,generation/REBASE/
partition/cursor boundaries and no missing/duplicate rows. Verify referential constraints
and inner-join visibility before moving LIMIT; no skip of validation/digests/financial oracle.
Only after this bounded comparison should an explicit time-budget amendment be considered
if full replay still lacks sufficient headroom. No four-hour rerun now.

One replacement consumed; stop/report. No source optimization/commit/push/CI/merge.
W3 Incomplete and F17 Pending Full Validation remain unchanged. Next step needs owner
instruction to prepare/implement the evidence-backed query amendment under project rules.
