# F-11 R2-S1–S4 scheduler validation

Date: 2026-10-11. Implementation evidence complete; ready for review.
Scope: approved performance-plan-v2.md S1–S4. No production code, grants,
requirements or acceptance thresholds changed. S5/full-load remains phase 9.

## S3 review correction — 2026-10-11

Replaced gather-only overlap with two observed PostgreSQL transaction barriers.
The real coalesce function runs in an operator transaction kept uncommitted;
a test-only stronger control-row lock makes the competing claim/reap wait.
Release occurs only after `pg_blocking_pids()` reports that exact transaction as
blocker and `pg_locks` confirms the contender holds advisory key 711/1 and has an
ungranted lock. This proves transaction overlap, not simultaneous CPU execution
inside the two SQL functions. No production code, grants or timeouts changed.

The observer cannot read another role's SQL text, so the claim observation uses
lock ownership and also matches its PID to the eventual `claim_committed` event.
The reap SQL text is visible. `s3-crash-round.json` now includes both barrier
traces, blocker/waiter PIDs, and observe/release/commit times. Assertions retain
the consumed attempt and served round after reap, require a new non-null token
for round 2, and allow exactly one committed successor claim. Timestamps are
nondecreasing because Windows clock resolution can give adjacent events equal
values; the lock observation, not timestamp separation, establishes overlap.

Latest targeted rerun: **1 passed, 0 failures/errors/skips, 10.911 seconds** in
`review-fix-tests.xml`. The preceding `review-fixed-tests.xml` records 30 passing
cases and one timestamp-assertion failure, corrected by that targeted rerun.
It is retained as development history, not described as a green full run.
The original 179-pass evidence below predates this correction. No unchanged
148-case regression rerun was needed for this harness-only fix. Ruff/format and
full mypy (340 files) passed. Ready for re-review.

## New evidence

`tests.xml`: **31 passed, 0 failures/errors/skips, 73.594 seconds**.
27 cases in `backend/tests/services/indicator_builder/test_scheduler_validation.py`
and 4 real-container cases in `profile_fair_scheduler.py`.

| Criterion | Evidence and assertions |
|---|---|
| S1 | `s1-unexpired.json`, `s1-expired.json`: actual workers/PG; older-deadline A receives a relevant write every attempt, eligible stable B is served between A1 and A2. A is explicitly made eligible before B dispatch. Rounds A1/B1/A2/A3 = 1/1/2/3; every competing process is blocked without scan/hash/core. Actual CPU starts follow the previous writer close; A terminates after attempt 3. |
| S2 | Mixed SOURCE_CHANGED/TRANSIENT/SOURCE_CHANGED after actual scans, shared budget 3, exact 30/60-second eligibility and rejection 1 microsecond early. Physical sessions and owners replaced between attempts; counters/served markers survive. Coalesce across two window boundaries and elapsed cooldown alone cannot revive the terminal job or scan/hash/claim. Separate real-process restart/crash evidence is in S1/S3; the mixed-failure case itself uses pool disposal, not process termination. |
| S3 | Rolled-back round-2 claim restores counters/token/round; committed claim with lost acknowledgement remains orphaned and consumed, without CPU/hash. A locked unserved B prevents premature round advancement. `s3-crash-round.json`: actual process kill, blocked orphan contender, concurrent reap/coalesce, preserved committed budget, B first, then two replicas race for one A round-2 claim. Repeated pending-window coalescing retains the single job identity/latest bounds. NO_JOB/LOCK_BUSY scheduler paths wait rather than spin. Existing pool-two/timeout regression and G1–G6 supply resource/shutdown coverage; container claims also assert the 120-second deadline bound. |
| S4 | 18 source-event cases: three failure categories × event before/after failure × cooldown 600s−1µs/equal/+1µs. Operational failure does not auto-resume. Three concurrent duplicate real-CLI cases preserve the request's durable response and original episode. `s4-lease-retry.json`: live expired owner cannot be reaped or bypassed; actual kill/wait then verified reap consumes the third attempt, immediate retry is rejected, old rejected request remains rejected after cooldown, fresh request queues a new cycle and actual successor reaches READY. First eligibility/deadline/served/missed markers survive recovery, including the paused failed interval. |

## Test controls and limits

- Isolated PostgreSQL at port 55433 and Docker test network only; application and
  capacity databases untouched. Containers use the existing probe image with current
  workspace source mounted read-only. This is not a release-image rehearsal.
- Exact timing uses the existing `test_numeric_windows.db_clock` fixture: SQL clock
  calls and source-session clock reads are controlled, then restored. That reused
  fixture also temporarily widens candle `high` to numeric; these S cases inject no
  numeric overflow. Real-clock container profiles run after fixture restoration.
- Container fairness accelerates only `retry_not_before`; lease recovery accelerates
  slot expiry and terminal cooldown. Exact eligibility boundaries are independently
  checked by the clock matrix. No claim that these profiles wait 600 real seconds;
  G3's previously recorded real 151-second pause remains separate evidence.
- Transient and ambiguous acknowledgement faults are injected at writer method
  boundaries around actual PostgreSQL transactions. Real process termination is
  exercised separately, not simulated by those exceptions.
- Test development corrected two harness assertions: coalescing legitimately moves
  desired bounds, and cycle IDs are UUIDs rather than integer counters. No production
  defect was discovered or patched in this run.
- `container-tests.xml` is the initial three-case fairness/crash run;
  `tests.xml` is the authoritative final four-container-case + 27-case run.
  The earlier `../scheduler-tests.xml` records the initial 26-case run only.

Ruff and formatting passed for both new modules. Full backend mypy passed:
340 source files. Related claims/scheduler/attempt/recovery/maintenance regression:
**148 passed, 0 failures/errors/skips, 36.959 seconds**, in `regression-tests.xml`.
Total for this final validation: **179 passed**. Historical full-suite totals are
not updated by these runs.

F-11 remains In Progress. Review of this harness and the remaining non-deferred
validation gates is still required; no Development Complete, Completed, production
PREPARED activation or merge is claimed.
