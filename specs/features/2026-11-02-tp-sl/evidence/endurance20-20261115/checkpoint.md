# Standalone internal20 four-hour attempt — 2026-11-15

สถานะ: **Incomplete — stopped before four hours; no automatic retry.**
[Execution scope](../../endurance20-four-hour-execution.md), [sanitized receipt](summary.json).
Candidate: merged main b0d5580364268be7619f5369dc8488d440f12160, PR75.
All1017 recorded source paths unchanged. No application/test source edit or criterion change.

## Actual result

Planned20owners/400baseline orders/28200commands/14400measured seconds.
Preflight Passed7/7samples; mean CPU idle53.3614%. Baseline400orders completed.
Measured2411.131889s (**40min11.132s**), total campaign2582.465396s (~43min2.465s).
At interruption: offered4755, admitted4754, completed4753, rejected0, fills1901,
cancels950, replays951, cycles950. These are partial counters, not a complete
financial/reconciliation verdict. Final exact financial oracle/rebuild Not Run;
full latency/resource/endurance acceptance Not Evaluated/Incomplete.

820snapshot observations returned, no snapshot observation errors. Only the first
scheduled worker-restart fault occurred; actual33.225192s and existing harness
statusRECOVERED; new restart-0 worker activity observed. Remaining six faults Not Run.
This does not prove all-owner per-fault recovery or four-hour stability.

## Direct stopping cause

The parent publisher called production publish_input, which called unchanged
BookState.require_ready. Input24197 had ready=True/rebase=False/source_at=None:

| Actual guard argument | UTC |
|---|---|
| received_at / verified_at |2026-11-14T23:43:51.554265+00:00|
| guard_now |2026-11-14T23:43:51.554035+00:00|

Thus received_at and verified_at are230microseconds later than guard_now. The strict
future-input check correctly raised SourceUnavailableError("book readiness cannot
be proved"). The prior two retained successful guards had ages0.887/0.768ms.
The bounded readiness artifact retains the last64 of24197checks; it is not a full
history. This rejection is a negative age, not an old-input/30s age-limit failure,
cycle timeout or evidence that the engine-processing performance limit failed.

Both times originate from PostgreSQL clock_timestamp() in the same publication
path: profile_workload.publish_market reads the first timestamp; publish_input's
_locked reads clock_timestamp after its materialized row lock. Earlier chat wording
attributing this to a host-generated book timestamp was incorrect and corrected
immediately after inspecting source. The observations prove time ordering reversed;
they do not establish whether the underlying cause is VM/OS clock adjustment or
another clock behavior. No clock tolerance/backdating/retry/guard waiver applied.

A secondary connection-termination CancelledError appears during teardown; the
recorded primary cause remains SourceUnavailableError. No worker failure was
reported before the publisher exception. No claim that full pool acceptance passed.

## Cleanup and evidence

Campaign cleanup: zero connections/backends/advisory locks. Proven task database
removed normally. Dedicated Redis ownership label verified, stopped and removed;
owner PostgreSQL/Redis remained up/healthy, no owner/Live action or volume/image
operation. Raw evidence retained locally under validation-artifacts/f17-endurance20-20261115/,
including exact guard arguments, source/config/schema/runner hashes, resource samples,
worker records and cleanup receipts. Do not publish raw logs/dumps/secrets.

The external progress reader initially used system Python3.9's different monotonic
clock origin; switched to project Python3.12. This affected only transient chat
progress arithmetic, not the campaign or any acceptance artifact. Actual measurement
uses failure_observed-started from the Python3.12 processing-window receipt.

## Next checkpoint

Stop timed execution as specified. Recommend a bounded read-only investigation of
PostgreSQL clock ordering and existing Docker/host clock evidence before selecting
a correction or replacement campaign. No new clock diagnostic experiment, production
change, safety relaxation, timed retry, commit/push/PR performed. Existing PR75 CI
success and prior scoped Passed/Failed results retained. Four-hour20 and100-account
Release, opening and bot/notification/Live dependencies remain pending; F17 notCompleted.
