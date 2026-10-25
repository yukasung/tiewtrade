# F-11 capacity checkpoint — 2026-10-24

## Local candidate review — 2026-10-24

Branch `validation/f11-capacity-checkpoint`, uncommitted candidate: migration0039,
exact-fixture lifecycle-clock correction, explicit smoke mode/tests and approved
workflow documentation. Reviewed changed code, publication guards/ACL preservation,
clock/deadline dependencies and smoke/full prerequisite separation. No outstanding
Critical/High finding identified in this review. No production Python, frontend,
API contract or dependency changes; no production activation or Live requests.

- Full backend Ruff check and format passed (502 files); mypy passed (458 files);
  import-linter passed all 7 contracts. Existing focused migration/publication
  evidence remains valid; no timed smoke or capacity workload rerun.
- Candidate regression on host Python3.12/macOS, isolated PG16 database
  `tiewtrade_f11_migration_tests` at port55434 and Redis DB15 at port56380.
  All seven role URLs targeted that test database, never capacity DB `tiewtrade`.
  Signup enabled/cookie Secure disabled only for tests; price origins localhost5173.
- First command: `.venv/bin/pytest --maxfail=1 --junitxml=../specs/features/2026-10-10-backend-indicators/profiling/release-20261024/candidate-tests.xml`.
  Result **929 passed / 1 failed / 2 venue-contract deselected**, 253.61s.
  Failure: `test_server_log_policy_still_applies`; this dedicated database lacked
  the log-redaction settings in `db/bootstrap/00-roles.sql`. Applied that existing
  bootstrap using postgres to this test database only; no application code fix.
- Resumed with the same environment and `pytest.main`, an explicit trylast
  collection hook retaining items from the failed node onward after asserting
  its index was929. Thus only the already-passed prefix was deselected, not any
  untested case. Result **2285 passed / 931 deselected**, 356.45s, in
  `candidate-tests-remaining.xml` (929 prior passes + 2 default venue exclusions).
  Combined **3214 distinct tests passed, zero skips**; original environment failure
  retained, failed case passed on recheck. No source edits between the two runs.
- Frontend/contract checks not repeated locally: their sources, contracts and
  dependencies are unchanged. Required CI (including Linux backend, frontend,
  API contract, browser and container jobs) on the final commit is still Pending;
  local results do not replace it. Commit/push/merge require owner commands.

C5/C4/C6 workload-dependent acceptance remains deferred to set9, not Passed.
F-11 remains Development Complete; this checkpoint is not production readiness.

## Development smoke interrupted by owner — 2026-10-24

Owner requested deferring repeated workload runs until system acceptance.
Stopped the running `smoke-steady` process with SIGINT; asyncio cleanup completed
and process exited 130. Last progress was 180s with BTC readiness 8/8; this is
partial observation, not a Passed verdict or full validation credit. Retain raw
artifacts in `smoke-steady/`; dirty/rejected-load smoke was not started.
Do not automatically rerun this smoke at each task completion. Full workload
remains deferred to set 9 under the existing approval; risk-based correctness,
safety regression and mandatory candidate gates remain required.
Harness development checks before this run: 17 tests passed, scoped Ruff/format
passed, mypy with `src` included passed (197 files). Initial mypy invocation
without `src` failed import discovery; no production code was changed to suppress it.

Status: **Partial / exact-fixture setup failed; C2 not started**.

Owner approved a new isolated capacity database while preserving the old one.
Old postgres/redis/api/builder containers were stopped and renamed with suffix
`-archive-20261024`; volumes remain intact. Development containers/data untouched.
New capacity PG16/Redis7 retain dedicated localhost ports 55434/56380 and network.
Bootstrap and migrations through 0038 succeeded. No exchange or order requests.

Candidate `tiewtrade-f12-v17:r21` (`sha256:5e94ba9b762c9682bcf60ee2ba0a17aeb7471838b1ae3fd9baf699c0872241f0`):
all 195 Python source hashes match main `076a4b2`. Existing containers referenced
the older `f2e3a9f...` image, so they were not reused for this candidate.

## Invocation and evidence

From backend, with existing synthetic role credentials bound only to dedicated
capacity ports and `PYTHONPATH=.:src`:

```text
.venv/bin/python -m tests.services.indicator_builder.profile_capacity \
  --output ../specs/features/2026-10-10-backend-indicators/profiling/release-20261024/c1-current \
  --image tiewtrade-f12-v17:r21 \
  --metrics ../specs/features/2026-10-10-backend-indicators/profiling/release-20261024/metrics
```

- Fresh BTC/ETH × 8 timeframe source fixture; no synthetic READY heads.
- C1 observed readiness 0/16 initially, 8/16 at 60s, 16/16 from 120s through
  the remainder of the 600s observation interval. Raw observations/probes/cutoff
  are in `c1-current/`; no aggregate Passed verdict was produced.
- Subsequent R2-7 exact-fixture generation failed:
  `CAPACITY_EXACT_FIXTURE_BUILD_FAILED:QUEUED:TRANSIENT:TRANSIENT` (exit 1).
- PG log at 2026-10-24 02:27:42 UTC (09:27:42 Asia/Bangkok) reports statement
  timeout executing `public.publish_indicator_ready(...)`.
- Last worker attempt: BTC/1m, RELEASED/TRANSIENT, 39.724s total,
  lag 0.03186s, RSS delta 4,071,424 bytes. Job is QUEUED with one attempt used.
  This is not evidence of the older API_RESOURCE_LIMIT failure recurring.
- Harness currently raises on any nonempty failure_reason after an attempt,
  including QUEUED transient; it does not wait for the production retry policy.
  Record separately from the underlying publication timeout; no policy changed.
- Cleanup stopped API/builder, removed exact clock marker and restored functions;
  `capacity_indicator_clock_state` no longer exists. New PG/Redis remain available
  for diagnosis. C2/C3/C5 not run; no acceptance thresholds/timeouts weakened.

Next: diagnose publication timeout and review transient handling against approved
retry semantics before rerunning affected setup. Do not rerun the 600s observation
or 60-minute C2 blindly, and do not treat partial readiness as aggregate acceptance.

## Read-only diagnosis — 2026-10-24

- `infra/indicators/claims.py` applies 500ms statement timeout to publication.
  `attempt._reason` maps DatabaseTimeoutError to TRANSIENT; release left the job
  QUEUED with one attempt used, consistent with the approved shared three-attempt
  budget and 30s/60s backoff (`performance-plan-v2.md`, retry contract).
- `profile_capacity.py:657` aborts exact-fixture preparation whenever attempts_used
  and failure_reason are nonempty, including this nonterminal QUEUED state.
  This prevents observing a normal recovery; it does not explain the SQL timeout.
- Exact-fixture clock pinning also covers SQL clock_timestamp calls. A retry-aware
  harness must account for retry_not_before under that clock; simply ignoring
  the transient could stall instead of proving the normal retry contract.
- Read-only EXPLAIN ANALYZE on surviving BTC/1m READY data: 527 checkpoint boundary
  lookups use the existing `(generation_id,next_open_at)` primary key; 4.679ms.
  Source-trigger validity SELECT: 2.637ms. No current lock-wait sessions.
  Diagnostic SELECTs used a transaction-local 5s safety cap and rolled back;
  production timeout/configuration were not changed.
- These post-event samples do not reconstruct the failed generation (already
  cleaned up), publication locks or the instrumented clock at failure time.
  Root cause of the original 500ms overrun remains unproven; do not claim missing
  index, lock contention or CPU pressure as established causes.
- No code/index/migration/timeout/retry changes or workload rerun in this diagnosis.
  Next bounded reproduction needs sanitized publication-stage timing/lock evidence
  and a reviewed exact-clock/transient strategy before modifying the harness.

## Confirmed clock-scope conflict — approval boundary

Read actual database definitions and harness replacement logic:

- `prepare_exact_r2_7_generation` selects every public indicator function containing
  `clock_timestamp()` and replaces every occurrence with one frozen timestamp.
- `complete_indicator_build_attempt` computes retry_not_before as observed +30s
  (or +60s). `claim_indicator_build_job` compares it to observed. Both are frozen,
  so simply waiting after QUEUED/TRANSIENT cannot make this retry eligible.
- The same replacement reaches lease/deadline calculations. This conflicts with
  validation's stated snapshot-only clock scope. It is a harness correctness issue,
  not evidence that production retry is broken or that it caused the SQL timeout.
- Per AGENTS.md, stopped before changing the approved approach. Added NC-F11-CLOCK.

Proposed amendment, not implemented: pin only calculation/source-snapshot bounds
for the exact 525,600-slot fixture; retain real lifecycle time, retry delays,
lease/deadline and the existing 500ms publication timeout. Reuse the current helper,
not a separate runner. Add targeted tests for exact bounds, 30/60s retry eligibility,
terminal failure, deadline expiry and function/marker restoration on every exit.
Bounded reproduction would capture sanitized publication timing and lock waits;
no parameter values, credentials or financial data in logs. Preserve current failure
artifacts; do not rerun full C1/C2 before the corrected fixture checks pass.

No code or database definitions changed in this diagnosis. Existing clock changes
remain restored; only isolated PostgreSQL/Redis are running. Publication timeout's
original cause still needs measured reproduction after this approval boundary.

## Approved harness correction — development checkpoint

Owner instructed implementation after NC-F11-CLOCK proposal. Plan/validation now
record approval. Removed broad SQL clock replacement: only calculation-bounds
function uses fixture boundary; worker wrapper changes calculation window while
retaining real snapshot as_of and fence. Retry/lease/deadline functions untouched.
Exact helper waits through nonterminal transient, stopping on FAILED_* or its
existing 600s limit. Production code/migrations/timeouts remain unchanged.

- New snapshot tests: 5 passed, including elapsed 1/30/60/121s and no-marker path.
- Ruff/format: 3 files passed; mypy with src and changed harness/tests: 198 files passed.
  Initial type invocation omitted src and was corrected; final checks pass.
- Isolated PG transaction smoke: patched calculation bounds produce 525600 slots;
  claim/release/require-claim functions still use real clock. Rollback verified
  exact original definition restored and temporary clock absent.
- Not yet proven: real worker publication/retry under corrected bounds and helper
  failure/cancellation cleanup. These remain necessary before C2; unit/SQL smoke
  is not an acceptance result and does not diagnose the original SQL timeout.

## Corrected-clock bounded worker reproduction

Used the existing isolated database and real builder role/image, without reseeding,
rerunning the 600s C1 observation window, or changing production parameters.
Advanced fixture source with the existing `append` helper; invoked the existing
`prepare_exact_r2_7_generation` at the next minute boundary.

- Boundary: 2026-10-24 02:43:00 UTC; age at preparation 0.411222s.
- Source rows/logical slots: 525,600; checkpoints: 527.
- READY generation: `0ca88793-f0c7-4453-b214-469d7fa299e7`.
- Bounds: 2025-10-24 02:43:00 UTC through 2026-10-24 02:43:00 UTC.
- Real snapshot as_of: 2026-10-24 02:45:56.867537 UTC, not the fixture clock.
- Final claim: 02:45:56.862168 UTC; deadline: 02:47:56.862168 UTC.
  READY finished at 02:46:41.748954 UTC (44.890253s including acquire/cleanup).
- Worker owner `89fd0dab-cfad-45ee-95c1-25280bbabeb4` in the appended
  `metrics/worker-attempts.jsonl` identifies this run, preserving earlier evidence.
- Publication statement timeouts recurred at 02:43:54.345 and 02:44:47.003 UTC.
  Retry progressed instead of being aborted/frozen; final job READY, attempts reset
  to zero, no failure reason. Before the final attempt the observed job had
  attempts_used=3 and retry_not_before=02:45:47.009070 UTC; final claim was later.
  This proves recovery, not the underlying cause of publication timeout.
- Worker stopped cleanly. Marker absent; temporary table/function absent;
  no public function body references capacity_indicator_clock after restoration.
- Focused tests: 8 passed, including QUEUED retry, terminal failure and cancellation
  cleanup with mocked dependencies. Real success cleanup separately verified above.
  Ruff/format passed for three affected Python files; mypy 198 files passed;
  git diff --check passed.

No full C2 started. This is bounded fixture/retry proof, not aggregate C1/R2-7
acceptance. Cold/warm API checks and audit remain necessary before accepting the
current prerequisite; historical failed/partial results remain unchanged.
Transient worker lag reached 145.284ms on one failed attempt; do not treat this
reproduction as passing the resource gate. No production code or thresholds changed.

## Resumed prerequisite checks and C2

Docker was stopped on continuation; started only the isolated capacity services.
The previous exact generation was outside freshness, so refreshed source with the
existing append helper and regenerated the exact fixture before API measurement.
No reseed, production changes, or threshold changes.

- `cold-warm-resume/`: R2-7 PASSED, correctness 6/6 (cold1/warm5), 525,600
  calculation slots, 1,000 response rows, 7 candle queries/request; maximum API
  lag 47.641458ms and RSS delta upper bound 66,940,928 bytes. Exact preparation,
  audited responses, metrics and audit result are retained in that directory.
- `c1-audit-resume/`: completed the existing audit against the original C1's
  60 observations and 80 probes. Original evidence was not overwritten. Applied
  the existing C1 aggregation criteria; R2-C1 PASSED (16 runtime readiness series,
  8 workload series). Later source invalidations remain reflected in the audited
  probe results; no unsuccessful probe was relabelled correct. The original exact
  DB T0 was not persisted before the exception and is not fabricated; this resumed
  report does not establish C4/fairness acceptance.
- Started the existing steady harness for `c2-current/`, using the resumed C1
  prerequisite and shared append-only metrics. Full 3,600s interval required;
  early failure cannot pass. `caffeinate -i` is scoped to this command to prevent
  host idle sleep during measurement. C2 result pending.

### C2 result — FAILED, publication retry missed freshness

`c2-current/result.json`: measured 1,270.129650375s, not the required 3,600s;
failure `VALID_FRESH_HEAD_GAP`. T0 2026-10-24 03:07:01.047994 UTC.
At T+1270.061s, BTC 1m head age was 606.757808s (limit600s); other15 series
remained valid. Original result/observations/probes/metadata and attempts preserved.

- BTC 1m published at 03:18:45.599351 UTC from its 03:18:04.256007 snapshot.
- Next cycle became eligible 03:25:54.256007; availability deadline03:28:04.256007.
  Claim03:26:02.322629 released TRANSIENT03:26:44.712437 after42.389856s.
- Retry claim03:27:25.676552 released TRANSIENT03:28:07.637699 after41.965151s.
  PostgreSQL logged statement timeouts in `publish_indicator_ready` at
  03:26:44.701 and03:28:07.633 UTC, matching those attempts.
- Job retained QUEUED/attempts_used2, next retry03:29:07.635736, deadline miss
  recorded03:28:05.799330. Retry remains operational but cannot preserve freshness
  in this observed sequence. This does not authorize changing retry/timeout/SLA.
- API maximum lag74.592417ms and RSS delta66,904,064bytes, below existing budgets.
  This run's failure differs from the historical API_RESOURCE_LIMIT failure.
- Read-only EXPLAIN ANALYZE of the publication checkpoint-boundary anti-join on
  the retained READY generation: custom plan7.928ms, generic plan2.753ms; both
  used527 primary-key index probes. This post-event diagnostic does not identify
  the original SQL timeout cause or rule out transient waits elsewhere.
- Existing PostgreSQL log_error_verbosity is terse; no inner SQL context was
  recorded. Left logging settings unchanged. No production source/migrations,
  resource budgets, or timeouts changed; no immediate rerun or C3 started.
- Harness cleanup stopped API/builder; isolated PostgreSQL/Redis retained.

Next checkpoint: bounded publication diagnostics to localize timeout (sanitized
timing/lock evidence), then assess any fix against the approved plan before edits.
C2 remains Failed; C3/C5/C4/C6 and release closure remain outstanding.

## Publication timeout localized — bounded diagnosis

Ran candidate image in separate diagnostic container
`tiewtrade-f11-publication-diagnostic-20261024` (same network, builder role,
2CPU/1GiB), calling the existing worker serve/scheduler with a180s stop signal.
This is diagnostics, not supervised workload acceptance. SQLAlchemy error hook
captured only SQLSTATE, elapsed time and allowlisted function/line frames;
no statement arguments or raw error text persisted. Original capacity worker/API
remained stopped; database logging configuration was unchanged.

- Two actual publication failures at0.500933s and0.500521s, SQLSTATE57014.
- Frames: `publish_indicator_generation` line50 IF; nested
  `market_timeframe_advance` line3/4 and `market_timeframe_floor` line3.
  This localizes cancellation to checkpoint boundary completeness validation.
- 50ms pg_stat_activity sampling during those calls: no wait_event and zero
  blocking PIDs in all19 samples (not proof that no shorter wait ever occurred).
- Known generation EXPLAIN uses527 indexed boundary probes. An ID absent from
  column statistics instead estimates2 checkpoint rows, materializes the generation
  rows, and puts market_timeframe_advance in the anti-join filter.
- Controlled temporary-table reproduction copied only checkpoint identity/time
  keys, ANALYZEd the baseline, then inserted527 rows for a new ID without ANALYZE.
  Same predicate took517.392ms, with138,601 rows removed by join filter and
  repeated boundary function evaluation. ANALYZE of that temporary table changed
  the plan to indexed probes and2.286ms. This explains why post-event probes on
  older READY generations did not reproduce the slow path.
- Proposed query-only experiment materialized expected boundaries once:18.114ms
  despite the same138,601 cheap timestamp comparisons. Complete data accepted;
  missing final checkpoint rejected under500ms. All temporary changes rolled back;
  no production table/function/migration, timeout or threshold changed.
- Diagnostic worker exited0 and sampler completed. No C2/C3 rerun.

Root-cause evidence supports planner cardinality underestimation for fresh
generation IDs causing repeated expensive boundary evaluation, rather than a
missing index. Proposed production fix requires a new migration and approval of
the pending plan/validation amendment. Do not work around this with per-generation
ANALYZE, a longer timeout, or a weakened completeness predicate.

## Approved migration0039 implementation checkpoint

Owner instructed continuation after the proposed plan/validation amendment;
both marked Approved before implementation. Added0039 (parent0038), replacing
only the reviewed checkpoint-boundary predicate with a MATERIALIZED expected
boundary CTE. Count/digest guards, formulas, identity/source checks, locks,
timeouts, retry policy and publication writes are unchanged. Downgrade restores
the exact previous predicate; replacement fails closed on definition drift.

Validation uses a new database `tiewtrade_f11_migration_tests` on the isolated
capacity PostgreSQL, not the capacity evidence database. Bootstrap event triggers
and all migrations through0039 applied using existing bootstrap/Alembic workflow.
-75 tests passed: new boundaries/migration roundtrip plus existing publication
 atomicity, privileges, source locking, numeric-failure and stale-identity tests.
-74 tests passed: claims, global lock ordering/permissions, snapshot harness and
 single migration head. Total149; separate from historical test counts.
-New cases cover all8 timeframes, custom/generic plans, fresh527-checkpoint
 generations without ANALYZE after insertion, missing first/interior/end,
 wrong boundary and count. Existing stale-generation tests cover identity mismatch.
-Migration roundtrip compares exact function body, owner, ACL and settings.
 Scoped Ruff/format passed; mypy197files passed; diff check passed.
-Applied0039 to the isolated capacity database with API/builder stopped.
 Runtime Python remains the same immutable candidate image; DB revision is0039.

First exact reproduction encountered pre-existing FAILED_TRANSIENT from the
diagnostic run (retry budget already exhausted). Helper reported that terminal
failure; do not label the helper invocation Passed. During cleanup, the worker's
existing recovery logic eventually published generation
`d62a2b26-9f16-4655-b5d7-206ff161b483` READY in39.090055s, exact bounds at03:42 UTC,
without publication timeout. No manual retry or direct job-state reset was issued.
Retained metrics owner `4af2d9b5-30d9-4bcb-909e-1de2d38e95dc` identifies that run.
Started a second exact invocation from READY, separate evidence directory
`migration0039-exact-r2`; outcome pending. C2 Failed result remains unchanged.

Second invocation PASSED: generation `0ee7aa3b-82a6-4a4f-b477-0a84c085ba6c`,
boundary03:45 UTC, age0.243698s, 525600 rows/slots and527 checkpoints, real
as_of03:45:01.151566 UTC. Helper exited0 after cleanup; no publication timeout.
Full C2 rerun started in `c2-migration0039/` (not overwriting `c2-current/`).
Reuse C1 audit and API R2-7 evidence: Python/API/input/formula/threshold unchanged;
0039 only optimizes the equivalent completeness predicate, with149 targeted tests
and actual exact worker proof above covering its affected path. C2 remains pending
until all3600s and correctness/resource gates finish; no C3 started.

### C2 on migration0039 — PASSED, full interval

`c2-migration0039/result.json`: PASSED, measured3600.000502333s;
T0 2026-10-24 03:47:00.960960 UTC (10:47:00.960960 Bangkok), failure=null.
- Runtime readiness16/16 valid in all360 observations.
- BTC8series each valid360/360 and correct60/60; total480 correct API probes.
- API maximum lag0.088037791s and RSS delta upper bound66,838,528bytes.
-127 worker attempts, allREADY (no TRANSIENT); maximum attempt45.777891979s
 and RSS delta upper bound3,715,072bytes. Existing resource limits passed.
- Candidate Python image remains sha256:5e94ba9b762c9682bcf60ee2ba0a17aeb7471838b1ae3fd9baf699c0872241f0;
 DB revision0039. Migration file SHA256
 `93e66d19939568783820c94f7c2fb062acaf368d6538ec5eb772bec2ef56e773`.
- Builder and API exited0; PostgreSQL/Redis and historical databases preserved.
 Generated the existing fairness/resources report from retained full-run evidence;
 this does not by itself close C4/C6 or other release gates.
- Final scoped Ruff/format5files passed; all affected migration/harness/test files
 included in final type check. No production Python, formula, timeout, retry or
 threshold edits; migration changes only the approved boundary predicate.

This completes the approved publication-fix/C2 checkpoint, not F-11 acceptance.
Remaining: C3/C5, incomplete C4/C6 and other release mappings; full candidate gates
and required CI before merge. No commit/push/merge performed or authorized here.

## C3 dirty/recovery continuation

Started `profile_capacity_steady --phase dirty` into `c3-migration0039/`, requiring
the PASSED `c2-migration0039/` result and retained C1 audit. Same0039 database and
immutable Python image, unchanged thresholds. Approved pair scope: historical
OHLC burst across BTC8 workload series; runtime readiness observer still checks
BTC/ETH16. Recovery deadline600s, phase3600s, availability>=80% including recovery
and100% after recovery. Historical C3 failures remain retained; this run is pending
until the full result exists. C5 will not start before C3 passes.

### C3 on migration0039 — PASSED, full interval

`c3-migration0039/result.json`: PASSED, measured3600.002225791s;
T0 2026-10-24 04:51:00.607948 UTC (11:51:00.607948 Bangkok), failure=null.
- Readiness recovered16/16 at70.074796s; all workload series had their first
  correct200 by120.305785s, within600s. No valid/fresh-head gap after recovery.
- BTC1m:353/360 valid samples and58/60 correct probes. Other7 workload series:
 357–358/360 valid samples and59/60 correct probes. Minimum head availability
 98.06%, minimum API availability96.67%, both above80% across the full phase.
 The9 initial NOT_READY probes remain in the denominator; none excluded.
-480 total API requests; maxlag0.087476667s, RSS delta upper bound66,969,600bytes.
-128 worker attempts, allREADY; maxattempt57.992841818s, RSS delta1,429,504bytes.
- Existing fairness/resources report: claim metadata complete, observer cadence
 complete, maximum observation skew0.145984s, resource budgets passed. Report is
 supporting evidence, not automatic C4/C6 or R2-S1..S5 acceptance.
- API and builder exited0. Capacity PostgreSQL/Redis and historical evidence
 retained; no application/production PREPARED activation, Live orders or Git writes.

No code changes this continuation; reused prior149tests and lint/type evidence
because runtime/migration/harness were unchanged. Documentation diff check passed.
Next checkpoint: C5 steady and dirty under controlled rejected-request load,
each full3600s; then remaining C4/C6 and release/candidate mappings. C3 historical
failures preserved. F-11 remains Development Complete, not Completed.
