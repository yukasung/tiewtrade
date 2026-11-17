# TAIL-02-refactor — standalone internal20 W3 confirmation

สถานะ: **Incomplete — source writer lease expired before the four-hour boundary**
Owner explicitly instructed “เริ่มทดสอบสี่ชั่วโมง” after the reviewed/refactored
query correction. Exactly one fresh campaign executed, no automatic retry.

## Scope and candidate

PAPER_INTERNAL20_V1 W3,20owners/400baseline/28200commands/14400measured seconds,
unchanged2commands/s scheduling and seven scheduled faults; original monetary,
processing/snapshot/rebuild/pool and60s final-tail criteria retained. Approved
NC_F17_CLOCK_01 opt-in remains capped at1event/1retry/1s; no lease reacquisition,
longer TTL, relaxed guard, time tolerance or financial POST retry introduced.

Base b0d5580 plus current TAIL-02 runtime and [R1/R2 refactor receipt](tail02-refactor-source-bridge.json).
All affected fingerprints verified before/after; campaign candidate_unchanged=true.
Copied root-bound campaign runner/dedicated Redis binding reversibly checked and
hashed; source/config/schema/schedule pinned. Fresh output root preserves all old
results. No source or acceptance change during/after this execution.

## Result and exact stopping point

Preflight Passed7/7. Measurement14371.934354s (3h59m31.934s),28.065646s short of the
14400s requirement; campaign14549.504159s (4h02m29.504s), exit1/Incomplete.

Counters at failure: offered28155, admitted28151, completed28143, rejected0,
fills11257,cancels5628,replays5629,cycles5625. Required28200commands/5640cycles not
complete. Partial in-flight/cancelled HTTP work is not a proven final reconciliation;
zero rejected commands does not prove final financial/order/balance correctness.

All7scheduled fault observations recorded RECOVERED under the existing harness
contract; no worker process failure recorded. Publisher last successful input143387,
same source owner/generation1. At13:30:04.284694UTC (20:30:04 Bangkok),
renew_book_writer raised WriterLeaseLost at order_book_storage.py:207. Its initial
_locked check had returned after checking owner/generation/live lease under row lock,
but the following UPDATE with lease_until>clock_timestamp() returned no row. The
lease was no longer live at that UPDATE; automatic reacquisition was correctly not
attempted. No accepted source/financial operation was retried for this failure.

Maximum successful publish duration4.750327s. Last successful input received_at
13:29:59.256179UTC, guard returned at13:29:59.277600; last publisher progress
13:30:03.966538. These are observed timestamps, not a trace of every statement,
lease_until, transaction start/commit wait or scheduler pause. Exact DB/commit/clock
contribution to expiration is not established. Last sampled host load1m28.391 on
the configured8logical CPUs and sampled lock_waits0 are correlations, not proof of
another application or autovacuum causing the failure.

## Clock recovery exercised

At tick/input6663, the original guard rejected a791us future book timestamp.
Explicit rollback was confirmed, normal session exit recorded, and the same logical
input/owner/generation committed on the one allowed fresh attempt after125.801708ms
from the first guard. recovered_count1, warning=true, terminal_rejection=null.
Both attempted timings/rejection preserved. This exercises the opt-in policy under
load; it does not repair the host clock or make the overall campaign Passed.

## Coverage and limits

Final-tail drain was NOT reached. Neither final per-owner financial oracle, global
financial/input-lag invariants, final snapshot/rebuild nor final owned-pool acceptance
ran. The TAIL-02 SQL correction therefore remains supported by its targeted/isolated
comparison evidence; this run does not prove its accumulated-W3 final drain passed.

Partial informational metrics reconstructed with existing transaction-start/fault
exclusions:398831engine samples, p95=203.603416ms/p99=376.610833ms.4800periodic
snapshot calls RETURNED across20owners, p95=36.912583ms/p99=93.444667ms. These are
not overall processing/financial/rebuild/full-duration acceptance grades.

## Cleanup

Preserve campaign cleanup_complete=false: its first cleanup receipt saw1active
backend, an autovacuum worker,0advisory locks. During launcher cleanup only that
maintenance backend was present; it exited naturally after four recorded1s waits.
No application connection remained, no backend was terminated. Launcher then used
normal DROP without FORCE and stopped/removed only its labelled dedicated Redis.
Independent final check: fixture DB absent,0connections/0locks, fixture Redis absent;
owner PostgreSQL healthy and original PostgreSQL/Redis running/restart_count0.
Do not rewrite the earlier cleanup receipt as if it had initially passed.

[Summary](tail02-four-hour-summary.json). Private root
validation-artifacts/f17-endurance20-tail02-20261115 retains manifests/source/schema/
runner, failure/processing-window/readiness/recovery records, HTTP intake, all worker
and position/resource samples, maintenance wait and cleanup/verification receipts.
Fixture identifiers<=63ASCII bytes; exact ownership recorded. No other containers,
images, volumes/databases or owner/Live accounts touched; no reset/prune/force action.

## Stop and next step

Stop/report under the approved one-run scope. No source/TTL/safety/criteria change,
new campaign, commit/push/PR/CI/merge. Owner prefers consolidating publication later;
respect that preference. Both previous Incomplete results and this new Incomplete
remain distinct. F17 not Completed; original100-account Release, finalfinancial/
rebuild and bot/notification/Live/opening dependencies remain pending.

Recommended next scope: a bounded short fixture/real-PG investigation of renewal
remaining TTL across the book/price publication transaction, separating DB acquisition,
locked read, UPDATE, price writes and commit spans. Preserve fencing/5s lease and
fail-stop; reproduce controlled delays before proposing any fix. No4h repeat or lease
policy change until that evidence/reviewable plan is approved. This is a recommendation,
not an execution authorization; await owner instruction for the next plan.
