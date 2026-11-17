# NC-F17-LEASE-02 — short-load diagnostic checkpoint

สถานะ: **Incomplete — aggregate pool inventory mismatch; stop/report**
วันที่:2026-11-15. [Approved plan](../../publisher-lease-load-diagnostic-plan.md).

## Actual execution and useful observations

One preflight Passed,7samples. Only then created one fresh isolated DB and labelled
Redis. Exactly one PAPER_INTERNAL20_V1 SMOKE campaign ran:20owners,400baseline orders,
600/600commands completed,0rejected,120cycles,240fills,120cancels,120replays. Measured
301.051s against300s target; final-tail drain1.417s. Total including external preflight,
setup and cleanup **469.132s (7min49s)**, within1200s. No retry/replacement campaign.

Publisher recorded **3087RETURNED,0failed**, generation1/source identity retained;
3011measured book inputs >=3000required. Details bounded at64recent/16slowest, no
controlled delay or recovery. No lease loss occurred in this five-minute workload.
This does not establish that the historical four-hour stall is fixed or identify
its cause. Recorder has explicit precommit probe overhead; not performance acceptance.

Slowest recorded tick2124 (heartbeat, no price update) took377.768ms; precommit book
TTL margin4.773621s. Its book renew15.915ms, publication22.838ms, price renew188.231ms;
commit-start-to-normal-session-exit109.528ms. SQL intervals total250.012ms overlap
outer stage spans and must not be added to them. Exit interval includes driver/
scheduling/close work and is not isolated server commit time. These short spans do
not explain the earlier4.75s historical publication. No failure witness was needed
in this successful publisher run; real-PG failure-witness safety tests cover that path.

Original checks: all20owner balance/reservation/held/cost financial oracles Passed;
global invariants Passed (0duplicate fill effects/unlinked fills/invalid reservations/
invalid positions/wrong mode). Engine p95/p99171.290/238.707ms, target and current
processing criteria Passed; these are engine times, not end-to-end commands
(p95/p991.662/1.930s). Original base/resource-base assertions Passed. W1–W3 position
snapshot/rebuild is **NotRun** in SMOKE; do not promote this to full financial/rebuild
or four-hour acceptance.

## Why the final grade is Incomplete

I added the declared witness MARKET_DATA pool(size1,overflow0) to the parent tracker
inventory but missed the independent aggregate validator. Parent tracker and all
20worker trackers individually finalized Passed, with0errors/0outstanding borrows
and normal disposal. However `profile_owned_pools.validate_reports` line517 still
compares the parent to the original hardcoded PARENT_CONFIGURATION. It therefore
correctly rejected the extra declared observer pool as
`PoolInventoryMismatch:parent.owned-pools.json`. Aggregate incomplete list contains
that mismatch, violations list empty. This is a harness integration omission, not
evidence of a leaked connection or trading-rule failure. The root/workload
**Incomplete** grades are retained unchanged; no offline regrading to Passed.

The targeted tests verified the witness pool lifecycle, but did not exercise that
aggregate validator with the opt-in inventory. Record this test gap explicitly.
A future scoped correction should bind the aggregate expected inventory to the
explicit diagnostic option, default unchanged, and negatively test missing/extra/
wrong-capacity pools before any separately authorized new campaign. This checkpoint
does not implement that correction or authorize a repeat.

## Implementation and verification

Harness only: reuse LeaseTrace with a normal-publication descriptor/in-memory sink,
dedicated bounded load controller and opt-in CLI wiring. Original fixed-case delay
validation retained; load recorder cannot inject a delay. Workload cadence/SQL/guards/
5s leases/commit policy/public APIs/schema/trading calculations unchanged. Default
observeroff path retained. Ephemeral buffers are diagnostic state, not application
sessions or persistent business truth. No actual owner/Live orders.

57distinct targeted cases Passed incrementally:39LEASE-01/readiness cases and18load
observer cases. Initialcombined55Passed/26.54s; updated18Passed/6.68s then18Passed/5.10s;
4witness-path cases with owned-pool lifecycle integration Passed/5.14s. Private logs
under `validation-artifacts/f17-clock-recovery-tests-20261115/`, attempts
1794754496544723000,1794754585388041000,1794754693065209000,1794754801694095000.
Scoped5-file Ruff/format/mypy and whitespace Passed before campaign. Do not substitute
these targeted results for the aggregate campaign gate that remained Incomplete.

Candidate/config/migrations/source/copied runner pinned before preflight; source
unchanged at end. Private runner adapts only root, dedicated Redis and verified reuse
of the single preflight receipt. Actual schema recorded before workload. Raw evidence:
`validation-artifacts/f17-lease02-20261115/`; includes private development configuration,
so do not publish wholesale. Sanitized [summary/source hashes](lease02-summary.json).

Cleanup completed: independent verification DB absent,0connections/0advisory locks,
owned Redis absent. Owner PostgreSQL healthy and owner Redis running, restart0both;
no owner service/image/volume affected. No retained campaign resources.

## Stop checkpoint and next step

One authorized campaign consumed. No subsequent source fix, repeat,4h run,Git or CI.
All old Incomplete/finalfinancial/rebuild/Release/opening/bot/notification/Live gates
retained; F17 **notCompleted**. Next owner-directed review should cover the new
observer and the explicit aggregate-validator integration finding before correction.
No automatic claim that changing the5s lease is warranted by this diagnostic.
