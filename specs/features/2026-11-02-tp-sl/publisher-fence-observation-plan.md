# NC-F17-FENCE-01 — read-only blocker evidence

สถานะ: **Authorized engineering follow-up — owner requested ทำแบบต่อเนื่อง**
2026-11-15. Existing F17 amendment, not new business/strategy requirements.
Owner requested continuous follow-up after LEASE-02R2 captured a9.848s fence call.
Use AGENTS engineering delegation for necessary bounded diagnostics; record plan
before source. No permission to relax safety/change production/locks/leases/Live/Git.

## Requirements and evidence

R1 Current5s lease and F18 shared/exclusive financial boundary remain unchanged.
Static review confirms publisher price fence precedes feed locks; financial writers
hold shared fence through financial commit. Book reads used by matching are MVCC;
no demonstrated book/financial row-lock cycle from static code. No proven deadlock
or named blocker from prior client spans. Do not fix/extend leases on that assumption.
R2 Add --publisher-fence-observer(defaultoff), only alongside existing lease observer
on internal20 V1 SMOKE. Reject worker/clock recovery/controlled delay/other diagnostic
profiles. Normal and existing LEASE-02-only paths unchanged.
R3 Recorder may capture backend PID via asyncpg driver metadata (no extra SQL).
While an actual publisher statement has been outstanding >=1s, one diagnostic task
samples at most4Hz from the same isolated DB: PGclock, pg_stat_activity's PID/role/
state/wait_event/type/xact/query start times, pg_blocking_pids and pg_locks identity/
mode/granted fields. Never select SQL query text, params, cookies, tokens or user rows.
R4 Use existing readonly_admin same-local-fixture guard, explicit readonly transactions;
server statement timeout500ms,lock timeout200ms, per-observation timeout1s. Bound128
activity rows and8192lock rows; overflow/failure reported Incomplete, no silent evidence
loss. Retain64latest snapshots and counts; no per-tick disk IO. On observation error
preserve publisher error and mark evidence incomplete, never retry publication.
R5 Observer owns one additional declared ADMIN_OBSERVER default5/10 pool but one
monitor task/connection at a time. Extend exact trusted inventory under the new flag
only; original pools/caps/return/disposal still mandatory. Join monitor and dispose
on all exits. Separate failure-witness pool remains unchanged.

## Plan / reuse

Reuse LeaseTrace spans/sink and LoadLeaseObserver task/lifecycle/finalization. Add a
small read-only fence sampler module, not a retry or trade framework. Wire optional
flag through campaign/workload/aggregate selector before fixtures. Existing role/
session/grants/schema/public API, financial fence SQL/order and publisher body unchanged.
Observe statement metadata only; no injected delays in campaign. Synthetic held-lock
barrier safety test may prove snapshots identify actual shared-holder/exclusive-waiter
on a fresh fixture without financial commands or lease manipulation.

Feature tests: option matrix, default unchanged, real-PG READ ONLY and actual blocker
identity, no SQL/private data retained, bounded retention/limits, task join/cancellation,
query/final IO failure preserves primary and yields Incomplete, explicit pool inventory
and negative tests. Reuse other valid safety evidence and scoped Ruff/format/mypy.

## One campaign / stop

After safety checks: one fresh internal20 V1 SMOKE with lease+fence observers,
20owners/400baselineorders/600commands at2/s,5measured minutes, sameworker/poll/claim/
finaltail/financial/resource checks. One120s preflight before fixture/Redis, expected
10–15min/max1200s from preflight incl setup/cleanup. Pin source/config/schema/runner.
Only owned fixture DB/labelled Redis; normal cleanup and independent0connections/locks.
If failure: preserve failed PID/timeline,blockers and rollback witness; stop/report.
If no event: report not reproduced, no automatic extension. No second campaign,
production fix,4h or Git action. Original grades retained and F17 notCompleted.
Code review/refactor owner gates remain after implementation/campaign checkpoint.

## Execution checkpoint

[One diagnostic Passed](evidence/endurance20-20261115/fence01-checkpoint.md):
600commands,302.801s measured,3115publisher successes,21pool reports Passed. No
SQL>=1s trigger/0blocker samples,monitor joined/errorfree.111distinct tests/static
Passed, source unchanged and independentcleanup complete. Historicalcause remains
unproven and originalIncomplete preserved. Stop/report; scoped observer review next.
No extra experiment/production fix/4h/Git/CI authorized/performed by this checkpoint.

## Review fixes M1/M2 — owner instructed แก้ไข

Before source changes: review reproduced cancellation of close() disposing the
engine while its shielded monitor stayed alive (M1), and a statement completing
mid-snapshot retaining its old stage without an overlap marker (M2). Owner requests
both corrections. Use one owned cleanup task protected from caller/repeated cancel;
join/cancel monitor before disposal, finish disposal before propagating the original
cancellation/error. Keep shutdown failures incomplete and preserve primary error.
Reuse existing shield/join patterns without production driver abort or force actions.
Freeze statement identity at capture start, record capture/activity/locks intervals
and statement completion status at capture end. Mark association unverified/overlapped
unless the same statement remained current and unfinished through capture. Keep raw
views and explicitly state non-atomic views; no guessed blocker attribution or silent
sample deletion. Add cancellation/repeated-cancel/disposal failure and statement
transition tests plus real-PG regression/owned pool proof. No new campaign/Git/CI or
change of prior diagnostic grade, leases, locks, SQL policy or financial behavior.

[Review fixes complete](evidence/endurance20-20261115/fence01-review-fixes.md):
42affected tests/static Passed, no timed campaign or old regrade. Await owner
refactor instruction; F17/four-hour/Release dependencies unchanged.

## Owner-authorized M1/M2 refactor

Owner instructed `refactor the code`. Refactor only the latest correction: replace
nested association conditional with explicit if/elif/else, name the first captured
caller cancellation explicitly, and make race-test expected associations literal
parameter cases instead of mirroring implementation branching. Do not alter cleanup
task ownership/shielding/join/dispose order, exceptions, snapshot fields or queries.
Run20affected fence cases/static checks; retain22unchanged load regressions from42.
No extra campaign/Git/CI or old-grade change. Scoped checkpoint only, F17 pending.

[Review refactor/affected validation complete](evidence/endurance20-20261115/fence01-review-refactor.md):
20affected cases/static Passed,22unchanged retained. No campaign/Git or old grade
change. Scoped work complete; no long-run option/experiment authorized here.
