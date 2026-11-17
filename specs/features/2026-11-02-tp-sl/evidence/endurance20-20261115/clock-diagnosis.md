# Read-only clock diagnosis — 2026-11-15

สถานะ: Diagnostic complete; original four-hour attempt remains Incomplete.
Authority: owner instructed “เริ่มทำ” after the read-only diagnosis recommendation.
[Original failure](checkpoint.md), [bounded probe receipt](clock-diagnostic-summary.json).
No application/test source, clock setting, safety criterion or trading data changed.

## Confirmed and still unknown

The original guard received book/verified timestamp06:43:51.554265 Bangkok and
later guard_now06:43:51.554035 on2026-11-15:230us reversed ordering. Both are
PostgreSQL clock_timestamp reads in one publication transaction. The source locks
its row through a MATERIALIZED CTE before reading guard_now. The readiness observer
calls the original guard and captures its actual immutable arguments, scoped to the
parent publisher task. Source code contains no host-clock timestamp in that book.

PostgreSQL16.15/aarch64 has run since2026-11-13 21:11:40 Bangkok; container restart
count0. Current Linux clocksource arch_sys_counter, Docker Desktop4.96.2,
guest kernel7.0.14-linuxkit. This is environment metadata, not proof of a defect in
any named component/version. No PostgreSQL clock-jump/startup message was found in
retained logs over06:41–06:46. Host timed recorded cmd,SYNC at06:42:35.693,75.861s
before the guard event, but no logged adjustment/slew/settimeofday at the exact
failure time was found. No actual Sleep/Wake event was found in that bounded pmset
window. Current caffeinate assertion is context, not proof about historical clock
behavior. Some VM init logs have shorter retention than the event age; absence of
a matching message cannot exclude a clock correction. Unrelated feature-flag text
matching clock words is not an actual clock event and was excluded from analysis.

Consequently the immediate rejection is established, but the VM/OS/time-correction
mechanism is **not established**. Do not label this confirmed NTP, sleep, Docker bug,
PostgreSQL bug or a financial-calculation defect.

## One fixed read-only probe

Executed2026-11-15 08:38:02–08:43:02 Bangkok,300.046466s. One psql connection on
maintenance DB postgres, explicit READ ONLY, local2s statement/200ms lock limits,
parallel workers disabled only for that transaction. No application tables, orders,
fixtures, DDL, clock updates, persistent config or service restart involved.

300batches of10000 ordered clock_timestamp samples, at most one batch/second:
3000000samples/2999700intrabatch adjacent pairs. Same backend throughout; readonly
verified in every batch; no negative adjacent delta and no negative interbatch gap.
Connection closed normally and its backend verified absent afterward.

Important coverage limit: the sum of dense sample spans is only0.754434s; maximum
unsampled interbatch gap1.010958s. This is a300s observation window with brief bursts,
**not continuous300s coverage**. No reproduced reversal does not disprove the earlier
230us reversal, establish clock stability or authorize a new passing workload grade.
Do not repeat short low-coverage probes simply to accumulate passing counts.

## Interpretation and next step

Official PostgreSQL16 docs define clock_timestamp as actual current time, changing
within statements; it is not a transaction-frozen timestamp. Linux documents that
CLOCK_REALTIME can jump backward after clock corrections. These explain why such a
mechanism is possible, not which mechanism caused this local event:

- https://www.postgresql.org/docs/16/functions-datetime.html#FUNCTIONS-DATETIME-CURRENT
- https://docs.kernel.org/core-api/timekeeping.html

Keep production future/stale-input rejection unchanged. Re-running four hours now
without a correction could stop on the same event. Next decision is a separately
reviewable plan: either establish/stabilize the reference clock environment or design
fixture-publisher recovery after a rejected publication. A recovery proposal must
prove rollback/no accepted invalid input, preserve source ordering/identity, bound
any retry, retain all failed attempts/wait time and unchanged financial/resource
assertions. It is not authorized by this read-only diagnostic; no tolerance,
backdating, silent retry or recovery source patch implemented here.

No commit/push/PR, timed replacement or new pilot/opening authorization. Prior PR75
CI and prior workload grades remain as recorded; original4h20 attempt Incomplete,
100-account Release and remaining dependencies pending, F17 notCompleted.
