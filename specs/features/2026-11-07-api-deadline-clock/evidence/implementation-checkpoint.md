# API deadline clock — implementation checkpoint

วันที่: 2026-11-07
สถานะ ณ implementation checkpoint: Ready for Code Review.
Latest: [post-review/refactor checkpoint](refactor-checkpoint.md) — review approved, refactor validated; CI pending.
Branch: fix/api-deadline-clock
Base: f15596df0b1ced53107964a8ed9bb657fda9d336
Candidate: uncommitted working tree; runtime/test diff identity in [runtime-test-diff.sha256](runtime-test-diff.sha256).

## Implementation

Changed only chart_routes.live and indicator_http.indicator_response runtime timeout entry:
pass max(0, deadline - application_clock()) to asyncio.timeout. Retained the absolute
application deadline for work/query_budget and synchronous serialization checks.
Chart budget remains 2 seconds; shared indicator budget remains 30 seconds.
No backend configuration, dependency, DB schema, auth/session storage or trading changes.

Added behavior regressions to the existing boundary suite for both directions of clock
origin offset, successful yielded work, actual asynchronous timeout, exhausted/remaining
budget, shared admission/work deadline and live serialization boundary.
Parameterized existing repeated-cancellation cleanup coverage with negative/zero/positive
clock offsets. Reused existing real database contract and cleanup tests.

## Evidence

Published log copies normalize trailing whitespace only; test output content/results are preserved.

- Before fix: corrected regression setup produced 4 failures / 4 passes in offset cases.
  Negative application offset cancelled normal work immediately; positive offset failed to
  cancel stalled work before the watchdog. [Log](regression-before-fix.log).
  An earlier test-writing run omitted required ChartLiveQuery fields; that setup error was
  corrected before collecting this red evidence and before changing runtime code.
- Pure boundary/cleanup: 41 passed (`pytest tests/services/api/test_chart_response_boundary.py
  tests/test_indicator_disconnect.py -q -k 'not postgres'`). [Log](boundary-cleanup.log).
- PostgreSQL/Redis API/cleanup: 69 passed (`pytest tests/api/test_chart_routes.py
  tests/api/test_indicator_routes.py tests/test_indicator_disconnect.py -q`).
  [Log](api-database-cleanup.log). These groups overlap; do not sum as unique tests.
- Changed-file Ruff check and format check passed. Mypy: 678 source files passed
  ([log](mypy.log)); import-linter: 7 contracts kept ([log](import-linter.log)).
- Unmodified playwright.chart.config.ts, default Uvicorn auto loop: recovery 1 passed,
  10.4s ([log](recovery-default-loop.log)). UVICORN_LOOP override was unset; installed
  Uvicorn auto_loop_factory selects uvloop when available. Python 3.12.15, uvloop 0.22.1.
  Host clock offset remains approximately +2103.990 seconds ([probe](clock-environment.log)).
- Standard asyncio via temporary external config: same recovery 1 passed, 8.8s
  ([log](recovery-asyncio.log)). The committed config remains unchanged.
- git diff --check and authored spec local links passed.

Backend validation used disposable PostgreSQL 16/Redis 7 and guarded database
`tiewtrade_e2e_deadline_20261107`. Chart E2E used existing ports 18012/18174.
Task containers were removed after validation; original dev services were left intact.
No external exchange/Live orders, full regression or workload campaign was run.
Existing Starlette TestClient deprecation warning remains non-blocking.

## Checkpoint and remaining gates

Local V-01..06 and V-08 passed. V-07 review/required CI not run.
No review was started automatically; no refactor, commit, push, PR or merge was performed.
Next: owner `review code`; after review/fixes, obtain the separate refactor decision.
Required CI must run on the final PR candidate after owner-authorized Git actions.

This backend branch does not contain the uncommitted prices-page removal. Its V-03 remains
Partial/Failed until an authorized combined candidate passes that feature's checks.
These results do not close F-11/F-12 Batch/Release gates or mark the consumer Completed.
