# N4 functional acceptance harness - 2026-10-12

Scope: approved R2-N4, excluding full-load/resource acceptance deferred to phase 9.
Implementation is ready for review; aggregate F-11 completion is not claimed.

## Implementation and reuse

`backend/tests/api/profile_numeric_concurrency.py` extends the existing actual
container `Probes` harness and numeric-window DB clock. Containers mount current
workspace code read-only and use the builder role with a two-connection pool.
The existing probe gained optional test-clock support, barriers immediately
before/after numeric publication, checkpoint bounds traces, and observed peak
connection counts. Production code, formulas and migrations are unchanged.

The test injects a real out-of-range source value through the existing test-only
numeric-domain fixture; `Money` validation and numeric publication are real.
The bad bar remains within all tested windows. No synthetic numeric exception,
claim success, publication result, or verified-stop evidence is substituted.

## Scenarios and evidence

| Scenario | Assertions | Trace |
|---|---|---|
| RUNNING across three H4 boundaries | Owner paused before numeric publication; contender cannot build; concurrent coalescers keep one newest desired window, active token/cycle/budget unchanged; GC-expired generation cannot publish; next candidate starts at newest bounds with fresh initial checkpoint | `n4-running.json` |
| Crash before publication | Same pending-window sequence, then real container kill; no takeover before actual Docker stop verification and fenced reap; committed attempt is not refunded; next attempt retains the original eligibility/deadline | `n4-crash_before.json` |
| Crash after committed numeric publication and outage | Durable numeric failure survives kill/restart without computing the same input; three windows pass with no active builder, metadata polls coalesce the newest one; new window creates one new initial candidate | `n4-crash_after.json` |

Every scenario also checks:

- A second actual container is denied while the new owner holds the global lock;
  PostgreSQL observes exactly one granted global advisory lock. Completed build
  traces report a peak of exactly two connections.
- Repeated coalescer calls use independent SQL sessions; maximum job-row count per
  series/formula is one. Intermediate windows do not create extra candidates.
- GET is 503 while pending, 422 only with a valid numeric manifest, and 503 after
  manifest GC. Responses contain no partial rows. Job and derived-table snapshots
  do not change; captured API SQL contains no DML; outgoing async HTTP is forbidden.
- Real GC removes a test-expired manifest while preserving the durable failure key,
  input version, attempts, cycle, first eligibility and availability deadline.
  Two restarted contenders then return NO_JOB with no claim/source/CPU/hash trace.

The test-only GC setup marks the manifest EXPIRED without advancing the clock;
this isolates same-key suppression from normal window advancement. Time is
controlled in the existing isolated fixture and restored on teardown. The original H4 case does not isolate deadline rejection from GC expiration.
Separate tests below prove deadline fencing with simulated time, not a 120-second
wall-clock load run. Source sessions are closed before the numeric barriers.

## Regression and execution

`../n4-tests.xml`: **49 passed**, no failures/errors/skips, **88.344 seconds**:

```powershell
uv run pytest tests/api/profile_numeric_concurrency.py tests/services/indicator_builder/test_scheduler_validation.py tests/services/indicator_builder/test_failure_recovery.py tests/services/indicator_builder/test_numeric_windows.py -q --tb=short --junitxml=../specs/features/2026-10-10-backend-indicators/profiling/n4-tests.xml
```

Use the existing isolated Docker test network, PostgreSQL at port 55433, Redis at
56379, and role URLs from the earlier F1-F6 run. Set
`TIEWTRADE_GLOBAL_EVIDENCE_DIR` to this directory to write the JSON traces.
The `profile_` module is explicitly invoked; normal pytest discovery does not
silently start Docker acceptance workloads.

Scheduler/failure regressions prove the shared three-attempt cap, exact 30/60s
backoff, no counter reset on clock/reconnect, and unchanged availability deadlines.
Numeric-window regressions cover all six timeframes and independent oracle/full
scan/digest behavior. Those are complementary tests, not claims that the three
container scenarios exhaust every transient-fault permutation.

## Limits

Full 30-series/two-replica load, sustained GC pressure, resource ceilings and
availability under load remain deferred to phase 9 (C/G7 gates). These short
functional results do not replace those measurements or enable production.
Database/network outage recovery remains evidenced separately by G4; this N4
outage scenario is an actual stopped worker, not a database restart.

Final strengthened HTTP SQL/episode assertions: `../n4-final-tests.xml`,
**3 passed** in **37.052 seconds**. This rerun overlaps the 49 tests above.
Ruff check/format passed for all three changed test modules; strict mypy passed
348 source/test files; import-linter kept all seven architecture contracts.
No production changes or additional migration were needed. Functional status:
**Passed, ready for review**; full-load acceptance remains **Deferred**.

## Review correction: isolate deadline from GC

The review found that the old H4/GC test could pass through the publisher's
EXPIRED shortcut before claim/deadline validation. Its earlier 120s claim above
has been corrected; the original passing runs do not prove that isolated gate.

- `test_numeric_deadline_without_gc_or_expired_lease`: actual container paused
  before numeric publication at T+119, T+120 and T+121 seconds. No GC/coalescer is
  called. Before release, assert STAGING, unexpired manifest, both leases valid,
  unchanged source epoch/revision/floor and valid triggers. T+119 publishes
  FAILED_NUMERIC; T+120/T+121 publish SUPERSEDED with OWNERSHIP_LOST and no numeric
  failure view. The inclusive 120-second boundary is now the distinguishing gate.
- `test_multiple_minute_windows_publish_before_deadline`: M1 attempt starts at
  boundary+59s; concurrent polls cross the next two minute boundaries within
  61 elapsed seconds. Both leases and deadline remain valid. The old candidate
  publishes a real numeric failure; GET for the newest bounds remains 503.
  Coalescing dispatches only the newest bounds from an initial checkpoint, reaches
  numeric 422, preserves episode eligibility/deadline, and a restart cannot repeat
  that failed input. A second container is denied during the active attempt.

New traces: `n4-deadline-119.json`, `n4-deadline-120.json`,
`n4-deadline-121.json`, `n4-live-windows.json`. No production code change.

Correction run: `../n4-review-fixed-tests.xml` **7 passed**, 0 failures/errors/skips,
**54.357 seconds** (four new cases plus the original three).
Ruff/format and strict mypy (348 files) passed. Ready for re-review.
