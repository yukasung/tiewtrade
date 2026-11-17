# NC-F17-LEASE-01 — diagnostic checkpoint

สถานะ: **DIAGNOSTIC_COMPLETE — stop/report, not four-hour acceptance**
วันที่: 2026-11-15

Owner approved [the five-case diagnostic](../../publisher-lease-diagnostic-plan.md).
Only `profile_publisher_lease.py` and `test_publisher_lease.py` were added for this
step; existing workload, production lease/SQL/clock/session policy and financial
logic were not changed. No publication recovery, lease reacquisition or retry.

## Results

One 120s/seven-sample preflight Passed; exactly five cases then ran on five fresh
migrated isolated databases. Total from preflight launcher through cleanup was
**164.961s**, below the 600s limit. No financial/order/strategy commands or workers.

| Case | Observed result | Publication session | Book lease margin at precommit |
|---|---|---:|---:|
| L0-H: heartbeat tick2 | Committed once | 7.222ms | 4.996s |
| L0-P: price tick10 | Committed once | 9.728ms | 4.993s |
| L1-H: heartbeat + one4.5s pause | Committed once | 4.5125s | 0.4914s |
| L1-P: price + one4.5s pause | Committed once | 4.5122s | 0.4909s |
| L2-U: pause after first locked read | Original WriterLeaseLost; rollback confirmed | No successful commit | Not observed; no precommit probe on rejection |

L2-U's original locked read had **4.963072s** remaining. Its one controlled wait
was **5.251145s**; the original renewal UPDATE returned **rowcount0**. Independent
FOR UPDATE NOWAIT witness proved lock release, unchanged committed owner/generation/
head/buffer/price facts and lease expired by **0.295573s** at the witness clock.
Negative margins were retained, not clamped. No new input was accepted for L2-U.
The successful heartbeat cases left price facts unchanged; price cases wrote the
intended tick10 observation. Six financial tables remained empty in every case.

Successful commit-start-to-normal-session-exit intervals were 0.508–1.299ms.
These are client-observed exit intervals, **not isolated server commit durations**.
Per-stage SQL, checkout/role setup, actual locked DB timestamps and the explicitly
counted precommit-clock probe are retained. `book_publish` spans for L1 include the
controlled pause; its separate span is nested, so summing both would double-count.
After-state DB time is from an independent lock/state witness, not an exact commit
timestamp. Host scheduling, driver waits and server time are not independently
identified by these spans.

## What this establishes and what remains unknown

The original guard correctly rejects renewal if the lease expires between the
locked check and UPDATE, and rollback prevents a partial publication. A4.5s pause
consumes most of a5s lease even when the remaining SQL is fast. The isolated price
path was ~2.5ms longer than heartbeat without delay in this single observation;
this is neither a benchmark nor proof that price writes caused the historical loss.

The historical four-hour stall was **not reproduced with its original cause**.
There was no background20-account workload here. PostgreSQL contention, commit,
process scheduling and clock contributions to that event remain unproven. These
results do not justify automatically extending leases, reacquiring ownership,
ignoring failures or grading W3 Passed. All prior four-hour **Incomplete** grades,
final financial/rebuild acceptance and Release/dependencies remain unchanged.

## Safety/static evidence

- **37 distinct targeted cases Passed** (40 invocations across incremental checks):
  17 new observer cases plus20 existing heartbeat/readiness cases. Real PostgreSQL
  checks cover expired UPDATE, rollback/independent lock release, cancellation and
  ambiguous commit. Negative tests cover foreign-task injection, unsupported SQL,
  evidence IO failure preserving the original error and rejected scope.
- Scoped Ruff check/format and mypy on both new files Passed; diff whitespace Passed.
- Tests: private logs `validation-artifacts/f17-clock-recovery-tests-20261115/`
  attempts1794750864633039000 (30/15.96s),1794750974319842000 (6/16.14s),
  1794751107542402000 (3/10.31s),1794751313899018000 (1/0.59s).
- Source inventory pinned before preflight and verified unchanged before/after
  each case and at end. Config, case flags/ticks, copied harness/coordinator hashes,
  candidate diff, migration inventory and per-case schema dumps retained privately.
- All five owned DBs removed normally; independently verified DB absent,
  0connections/0advisory locks. PostgreSQL healthy and Redis running, both restart0.
  No owner service/container/volume/image was stopped or removed.
- A coordinator evidence-copy NameError occurred **before preflight or fixtures**.
  Its separate Incomplete startup receipt/copy was preserved; corrected the local
  path reference before the single preflight/experiment. No case was repeated.

Sanitized [summary/source hashes](lease01-summary.json). Raw evidence lives at
`validation-artifacts/f17-lease01-20261115/` and includes private local launcher/
configuration material; do not publish that directory wholesale.

## Checkpoint / next step

F1–F6 targeted evidence and D1–D2 diagnostic complete. R1 full W3/financial/rebuild/
Release remains Incomplete/Pending. F17 is **not Completed**. No Git/CI actions.
Stop here as approved §7D requires. Next: owner-directed `review code` of the new
observer/tests, followed by any separately authorized fix/refactor or evidence-led
proposal. No additional diagnostic or four-hour run is authorized by this result.
