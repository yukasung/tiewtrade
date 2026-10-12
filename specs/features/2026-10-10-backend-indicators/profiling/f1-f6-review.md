# F1–F6 correction and validation — 2026-10-12

Scope: NC-37 correction and the short functional F1–F6 gates. N4 and phase-9
full-load acceptance are separate. Final run evidence is recorded below.

## NC-37 — corrected

The original boundary test reproduced a typed Money failure before STAGING commit
being classified OPERATIONAL because numeric publication had no manifest row.
The original `f1-staging-boundary-tests.xml` (1 failed / 1 passed) is retained as
before-fix evidence, not a current failure. The owner authorized correction with
“แก้ไข”; no requirement or formula changed.

`backend/src/tiewtrade/infra/indicators/scan.py` retains the captured immutable
snapshot and tracks successful initialization. On typed Money failure, it closes
the source transaction and joins heartbeat first. If initialization did not finish,
it uses the same snapshot to initialize manifest metadata once, then rethrows the
original typed error for the existing fenced numeric publisher. It does not
recapture source, repeat calculation, create checkpoints, or reset retry budget.

Review of the error path: ownership/lease/deadline/source proof still gate writes;
committed source changes supersede the candidate, while rolled-back changes allow
the failure manifest. Epoch or expired lease prevents stale publication. Database
errors and ambiguous commits do not enter this Money-only path. Cancellation and
heartbeat errors retain the existing cleanup and operational handling. A failure
before a valid snapshot exists cannot fabricate a numeric input identity.

The precommit test injects Money after the real initialize SQL but before commit,
forcing transaction rollback. The postcommit case injects at checkpoint creation.
This is fault-injection evidence of the contract, not a claim that ordinary input
currently triggers Money inside the SQL initialization operation.

## Clause-to-evidence mapping

Paths below are relative to `backend/tests/`. New tests use existing PostgreSQL,
DB-clock, API, and builder fixtures; fault setup uses the test migrator only.
Actual operations run under their production API/builder roles.

| Gate | Evidence and assertions |
|---|---|
| F1 | `services/indicator_builder/test_failure_contracts.py`: before/after STAGING commit yields FAILED_NUMERIC, zero checkpoints/digest, sanitized metadata, no subsequent claim; identical captured snapshot after precommit failure, source already closed, write/rollback/epoch/lease matrix. `api/test_failure_contracts.py`: both boundaries return exact 422 with no Retry-After, repeated GET cannot compute/claim or fall back to an old READY head; a valid separate cursor remains usable. `api/test_numeric_windows.py` and worker numeric-window tests exercise real Money failure outside the output page and compare recovery with the independent oracle/full-scan/digest. |
| F2 | `test_scheduler.py` numeric suppression and `test_numeric_windows.py` cover stable aligned bounds, time, reconnect/new owner, other-series fence, metadata changes, append outside U, manifest GC, relevant writes and changed bounds. `test_maintenance.py` rejects manual retry of unchanged numeric input. `infra/indicators/test_publication.py` now runs the actual source-writer commit/rollback barrier for both READY and numeric publication, plus numeric epoch/floor/trigger/deadline/lease/rollout proof matrix. Current formula remains indicators-v1; no new formula revision is approved or executed by these tests. Future formula deployment requires its own approved revision validation. |
| F3 | `api/test_failure_contracts.py`: numeric failure view invalidation by epoch, floor, desired bounds, expiry, codec and GC gives first-page 503; epoch/floor invalidates continuation with 409, other-candidate faults preserve valid continuation. A real source correction builds a newer READY; an explicitly injected older failure candidate cannot mask it. `test_prepared_indicators.py` covers token/proof rejection and missing manifests without old-head fallback. |
| F4 | `test_failure_recovery.py`: real PostgreSQL 40001 abort, attempts at T/T+30/T+90, no claim 1 microsecond early, exactly three attempts then terminal failure. Logical source sessions, backend PIDs, snapshots and stream objects are fresh after abort; reconnect/coalesce/clock advance cannot reset cycle. First eligibility and availability deadline stay fixed. `test_attempt.py` covers typed numeric, codec, configuration and operational classification/exclusion from transient retries. |
| F5 | `test_failure_recovery.py`: actual builder-only CLI processes at 600s−1µs, exactly 600s, and +1µs; repeated request ID retains its original result; concurrent duplicates create one request/cycle. Processes are killed at barriers before and after commit, then the identical command is replayed and reaches real READY. Original availability deadline is preserved. READY retry is rejected; `test_maintenance.py` supplies RUNNING/numeric rejection and atomic/concurrent maintenance coverage. |
| F6 | `infra/indicators/test_global_permissions.py`, publication and maintenance privilege tests exercise actual roles, denied function calls/mutations and absence of PUBLIC EXECUTE; API base-table denials and sanitized view reads are covered by publication tests. New HTTP tests hide private numeric/checkpoint markers and distinguish numeric 422 from codec 503. New actual CLI tests reject injection strings in both UUID arguments with fixed UUID_REQUIRED, no reflected payload/traceback and unchanged DB state. Existing worker/CLI fixed-error tests plus core arithmetic/indicator regression retain NC-33 Money behavior. |

The F3 ordering fixture deliberately restores the older candidate pointer to test
read precedence; normal scheduling does not create that inconsistent fixture.
DB-clock replacement and widened numeric test domain are restored by fixture
teardown. Tests use isolated PostgreSQL port 55433 and Redis port 56379.

## Remaining risks and scope

- These are functional correctness results, not full-load availability or resource
  acceptance. F4/F5 deadline accounting is checked; deadline performance with all
  30 series, two replicas and continuous pressure remains phase 9 / G7/C gates.
- N4 and remaining aggregate validation mapping are not closed by this work.
- No new trading/order behavior, formula, grants or migration was introduced by
  NC-37. No production PREPARED enablement, commit, push or merge was performed.
- F-11 stays In Progress until its remaining non-deferred gates and final review
  are complete. Future formula revisions are not certified by v1-only tests.

## Final evidence and review result

- `f1-f6-regression-tests.xml`: **241 passed**, 0 failed/error/skipped,
  **137.754 seconds** across the 14 scoped test modules.
- `f45-final-tests.xml`: **8 passed**, 0 failed/error/skipped,
  **13.935 seconds**, after strengthening fresh snapshot/stream identity
  assertions. This rerun overlaps the 241 cases; counts are not added together.
- Earlier focused runs: `f1-fixed-tests.xml` 79 passed;
  `f1-f6-new-tests.xml` 70 passed. These also overlap the final suite.
- Ruff check/format for the five changed Python files passed; strict mypy passed
  all 347 source/test files; import-linter kept all seven architecture contracts.
  `git diff --check` passed (existing LF/CRLF notices only).

No outstanding Critical/High/Medium/Low finding identified in this correction.
F1/F2/F3/F6 functional gates pass for the approved v1 formula; F4/F5 functional
gates pass with full-load acceptance deferred to phase 9. This review does not
approve aggregate F-11 completion, production rollout, or phase-9 capacity.

APPROVED
