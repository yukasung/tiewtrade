# LEASE-02 replacement short diagnostic

สถานะ: **Incomplete — actual publisher WriterLeaseLost captured; stop/report**

Owner instructed “เริ่มทำ” after proposal for one replacement on the corrected/
refactored pool candidate. Same20owners/400baseline orders/600targetcommands,
5measured minutes, original5s leases/guards/rate/financial criteria. No code change
or repeated tests:14affected +54unchanged tests/static proof reused with source hash
verification. Original LEASE-02 Incomplete remains on its original candidate.

One120s/7sample preflight Passed before fixture creation. Fresh owned DB and Redis.
This one replacement stopped **67.509869s into measurement**, not a completed5min
run. Total incl preflight/setup/cleanup **243.660953s (4min04s)**. Counters at failure:
100offered/100admitted/88completed/0rejected,35fills,17cancels,18replays,15cycles.
Worker3 also exited1; no retained worker error classification proves its cause.
Do not count pending commands as completed or claim final money/rebuild acceptance.

## Captured boundary

556publications RETURNED, then **tick557** failed WriterLeaseLost; actual flags
update_price=false,heartbeat=true,0injections. Previous tick556 returned in122.252ms.
Failed publication took10.074001s:

| Stage | Client-observed duration/outcome |
|---|---|
| Book renewal |44.805ms, RETURNED |
| Book publication/guard |77.025ms, RETURNED |
| Price renewal |9.885515s, WriterLeaseLost |
| First SQL within price renewal |**9.848372s**, RETURNED |
| Following feed-row locked read |36.085ms, RETURNED; original lease check then rejected |

Current unchanged `realtime_storage._locked` issues exactly
`SELECT risk_publication_fence()` first, then the materialized feed-row FOR UPDATE
query with PostgreSQL clock. The trace observed both statements in that order;
there was no price renewal UPDATE, price read/write or successful commit exit for
tick557. In the current immutable implementation the first statement is the F18
exclusive transaction advisory fence. Thus the new evidence localizes the long
client-observed interval to that fence call, before feed lease validation.

This interval includes DB execution/lock wait/driver/process scheduling; it is not
proof that all9.848s were lock wait or that a particular worker held the lock.
Resource samples near the event reported0lock_waits, but are sparse and cannot
exclude an intervening wait. Host load1min rose18.47→28.82; that correlation does
not establish cause. Docker logs for15:23:50–15:24:25UTC returned no lines; PG
logging_collector=off/current_logfile null. No server blocker/wait-event timeline
was retained. Do not claim a proven deadlock or that this is the identical root
cause of the earlier four-hour book-renewal failure.

## Rollback / safety evidence

Last book check within tick557 returned at15:24:05.012153UTC with4.890799s TTL
remaining. The publisher later rejected price lease expiry. Independent state
witness at15:24:14.814562UTC obtained FOR UPDATE NOWAIT and showed committed head
**556**, buffer exactly1..556, unchanged book owner/generation and the previous
committed lease15:24:09.739003UTC restored. Tick557 and its attempted book renewal
were not partially committed. Price observation remained at last actual price
tick550. No retry, reacquisition, guard tolerance or synthetic recovery applied.

Readiness evidence present,557guard observations; load recorder preserved the
failed trace plus bounded recent64/slowest16 and counts. Independent witness returned
before normal cleanup. Finalfinancial/global/snapshot/rebuild and aggregate pool
acceptance **NotRun** after early publisher failure. Parent pool report finalized
with WriterLeaseLost outcome,0recorded pool errors; it is not a Passed pool gate.
The corrected aggregate validator was not reached in this run, so do not claim a
campaign-level validation of that fix from this result alone.

## Cleanup / candidate / checkpoint

Source unchanged; copied runner/config/migrations pinned. Coordinator adaptations
limited to fresh output/Redis ownership names; one preflight receipt reused once.
Independent verification: DB absent,0connections/0advisory locks; owned Redis absent.
Owner PostgreSQL healthy and owner Redis running, restart0both. No retained resources
or owner/Live actions. Raw `validation-artifacts/f17-lease02-r2-20261115/`; private
configuration must not be published wholesale. [Sanitized summary](lease02-r2-summary.json).

Replacement authorization consumed; stop/report with no source fix, repeat,4h/Git/CI.
F17 notCompleted; preserve all prior Incomplete and finalfinancial/rebuild/Release/
opening/bot/notification/Live gates. Next proposed scope is an evidence-led review of
F18 publication-fence/financial-lock ordering and a bounded blocker/wait-event
observation plan. Do not extend leases or change locks without an approved safe plan.
