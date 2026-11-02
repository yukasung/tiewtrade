# F-19 NC19 replacement W1 — Failed on verified fresh DB

Owner authorized `approve W1 fresh DB rerun` on 2026-11-02. No production/runtime edits,
acceptance relaxation, Git or deployment in this checkpoint. Preserve the earlier aborted
setup and invalid-environment attempt separately; this report covers **nc19-w1-r3** only.

## Verified execution

- Runner started09:37:12 and exited1 at09:41:27 Bangkok on2026-11-02; not OOM.
- Fresh DB `tiewtrade_f18_release_set5_nc19_w1_r3`: all nine roles connected to that actual
  database before migration; public schema empty. After migration revision0062, users,
  commands, risk settings and price frames all0 before seeding. Safe proofs:
  `nc19-w1-r3-database-inventory.json`, `nc19-w1-r3-migration-inventory.json`.
- Frozen source hash `78057f30fd2c13b13c6584120011b7e4586edf6016fd994545ea209377f5e53a`
  matches the tested NC19 candidate. No additional instrumentation in the workload.
- VM3,043,373,056bytes/8CPUs; PostgreSQL4CPUs/3GiB; monitor4/request1/stop2/scan3 pools;
  ten Paper workers, child publisher5Hz,100core owners x baseline20, unchanged F19 criteria.
  Source/resource/launcher/guard hashes and command are retained in the artifact root.
- Setup211.108 recorded monotonic seconds: baseline20/20 and dedicated partial fill,
  LOSS_LIMIT stop effects, RESET attempt1 APPLIED, opening probe blocked all completed.
  Manual/BOT resting setup also completed and the measured load began09:40:48.816 Bangkok.

## First failure and bounded conclusion

Child publisher recorded BOOK `SourceUnavailableError` at09:41:25.540931 Bangkok,
recorded monotonic+36.758s after load. Parent stopped at recorded+37.594s
(wall timestamps span37.560s). The error is
`F18_SOURCE_CHILD_FAILED:BOOK:SourceUnavailableError`, **not** the prior BOT setup rejection.
See original `publisher-failure.json`, `failure.json`, `phases.jsonl` and runner log.

Counters at interruption:277offered,234admitted,233completed,0rejected,85fills,
41cancels,52replays,29cycles. Cancellation leaves incomplete in-flight work; these counters
are not the final financial oracle. Scheduled RESET0/100; stop schedule starts at+50s,
so no stop journal, one-shot injection or NC17 partial barrier was exercised in this window.
The 600s source window and risk SLA **were not completed/evaluated**. W1 is **Failed**;
no W2/W3/W4 followed, and prior NC17 Failed risk-SLA evidence remains unchanged.

Reachability inspection narrows the regular BOOK publication path to
`_publish_books -> f15.publish_market -> publish_input -> BookState.require_ready`.
The fixture constructs READY=True, received_at=verified_at from a PostgreSQL clock read,
source_at=None. The guard rejects an input whose timestamps are in the future or older
than30s. This is a **code-path inference**, not a captured leaf-condition proof:
no failing guard arguments/call-site stack were recorded. Do not claim a proven scheduler
regression, source lease loss,30s staleness or clock-root-cause from the exception category.

Last durable BOOK input1227/generation1 committed09:41:24.819159 Bangkok, received/verified
at09:41:24.807692, READY=True, failure_code=NULL, lease_until09:41:29.786652. The receipt's
source xmin and input xmin are both538358. These timestamps are from the original DB,
not a restored dump. Last commit was0.721772s before the publisher's error timestamp.
This does not reveal the timestamps passed to the next, rolled-back publication guard.

## Confirmed recorder clock anomaly; causal link not yet proved

The **single parent recorder's original file order** in `source-commits.jsonl`:

| Line | Receipt | observed_at UTC | monotonic |
|---|---|---|---|
|3606|PRICE ETH/USDT|02:41:25.558264|1471.480342127|
|3607|BOOK BTC/USDT1227|02:41:25.541407|1471.499074377|

Wall time decreased16.857ms while monotonic advanced18.732250ms. Their offset changed
by-35.589250ms. `record_source_receipt` writes both fields synchronously in one callback,
without await, through the parent stream. Therefore this is a wall-time ordering anomaly;
**monotonic did not decrease**. Earlier commentary compared per-channel groups and named
the clocks incorrectly; the ordered-pair analysis above corrects that statement.

The anomaly is adjacent to the child failure (02:41:25.540931/1471.498616627). It is
consistent with a future-timestamp readiness rejection if the clock moves back between
building the book and checking it. **The actual failed SQL clock and book timestamps
are missing**, so this is a supported hypothesis, not an exact causal proof. Do not add
future-time tolerance, extend freshness/leases, change pools or weaken fail-closed rules.
A read-only system snapshot reports aarch64 with clocksource `arch_sys_counter`; it does
not identify an OS/hypervisor/NTP cause.

Adjacent receipt checks found one wall-time reversal/zero monotonic reversals in3607rows
of this run. No reversal was observed in the inspected NC17(11412rows),NC18(6600rows) or
invalid NC19-r2(3433rows) journals. These samples do not prove earlier clocks were globally
stable or alter previous acceptance results. Reproduction script and exact pairs are in
`nc19-w1-r3-analysis/clock-order.json` and its saved analysis script.

## Cleanup, partial safety and evidence

- Scheduler:11527scans,14002selections, max selected4/max in-flight4;
 13622processed/376deferred/4cancelled/0unexpectedfailed, active0atclose.
- All13pool files finalized/checked_out0; remaining DB connections0.
-92FILL events checked: duplicate execution identities0/null execution IDs0;
 negative positions/reservations0, terminal command rejections0, breach/audit mismatches0.
 Wallet snapshot reuses `get_wallet` and `Money`; negative balance checks are partial,
 not the full workload conservation oracle. See `wallet-snapshot.json`.
- Asyncpg termination CancelledError warnings after source failure are retained. Cleanup
 counts above do not erase those warnings or establish full validation.
-72original run files hashed; actual fresh failed DB dump16,414,891bytes+SHA256 retained.
 Commands, original DB-clock commit facts, guard/freshness proofs, launcher and saved
 analysis scripts are under `validation-artifacts/f19-set5-20261101/`.

No runtime tests/static checks repeated: tested backend/harness unchanged. Documentation
is checked for consistency and `git diff --check`. V-20 remains Failed/Pending Full
Validation; V-21..24 remain Pending Dependency.

## Next checkpoint

Stop after this authorized acceptance attempt. Proposed **NC-F19-20** records the exact
book/DB-clock values only when the existing freshness guard fails, in a scoped test-only
observer, and runs one60s non-acceptance diagnostic after targeted checks. It preserves
all trading decisions, resources and thresholds. No instrumentation or new timed run
until owner approval; detailed scope is in plan.md/validation.md.
