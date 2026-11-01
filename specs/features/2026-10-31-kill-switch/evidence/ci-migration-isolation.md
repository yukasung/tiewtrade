# F-19 CI migration isolation — 2026-11-01

สถานะ: Local verification Passed; required CI on the next candidate Pending.

## Failure and correction

CI runs 41286926224 and 41286928547 on `1cdb314` both completed with
4031 passed and 2 failed. Earlier API tests created immutable F-19 stop history.
Migration 0061 then correctly refused downgrade before the older guards checked
by the writer-fence and optional-limit tests. The earlier 129-test local run did
not include those preceding API tests.

The two guard tests now carry `isolated_migration` and each runs in its own
newly migrated database. Existing failure-message, revision, RLS and financial
assertions are retained. Both downgrade checks restore `head` in `finally`.
CI runs normal tests, the two isolated tests individually, and fresh global-state
tests using the shared `backend/scripts/reset_ci_test_database.sh` before each
isolated phase. Its destructive target is the fixed `tiewtrade` database inside
the explicitly supplied disposable test PostgreSQL container.

## Local evidence

Environment: macOS host, Python 3.12.15, dependencies from `uv sync --frozen`,
PostgreSQL 16.15 (`postgres:16`, as specified in `config/postgres.env`),
`track_commit_timestamp=on`, Redis 7 Alpine. Role URLs, signup, cookie and price
origin settings follow backend CI, with isolated host ports 55464 and 56380.
These results do not replace required GitHub CI on Linux.

| Phase | Result | Pytest duration |
| --- | --- | --- |
| Normal suite | 4031 passed, 21 deselected | 909.80s |
| Writer-fence migration guard, fresh database | 1 passed | 3.65s |
| Optional-limit migration guard, fresh database | 1 passed | 2.01s |
| Fresh global state, fresh database | 17 passed, 4035 deselected | 4.83s |

Collection partition: 4050 non-venue tests = 4031 normal + 2 isolated + 17 fresh.
The sets are disjoint and cover all non-venue tests. JUnit reports independently
confirm 4050 distinct executed tests, each exactly once, with zero failures,
errors or skips. Final database revision is 0061. Existing deprecation warnings
remain (5 in normal tests, 1 in fresh global tests).

Normal tests include migration ordering, trading safety/concurrency and
`test_platform_exclusive_fence_waits_for_shared_order_admission`, which passed.
Other migration tests were inspected: schema replay and grant/projection
roundtrips run before immutable history; direct indicator migration checks use
transaction rollback or expect a refused transaction. Paper-wallet downgrade
already restores `head` in `finally`.

Static checks passed: Ruff check and format (680 Python files), mypy (614 source
files), import-linter (7 contracts), Bash syntax, workflow YAML parse and
`git diff --check`.

Logs, JUnit XML, collection counts, final revision and the exact local command
sequence are retained under `validation-artifacts/f19-ci-isolation-20261101/`.
The disposable containers are removed after verification; reports remain.

## Reproduction and next gate

From `backend/`, configure the seven role URLs and Redis URLs for disposable
containers, enable commit timestamps, bootstrap and upgrade to `head`, then run:

```sh
uv run pytest
bash scripts/reset_ci_test_database.sh "$test_postgres_container"
uv run pytest -m isolated_migration tests/infra/execution_market/test_initialization.py::test_managed_history_refuses_fence_downgrade_and_keeps_force_rls
bash scripts/reset_ci_test_database.sh "$test_postgres_container"
uv run pytest -m isolated_migration tests/infra/risk_limits/test_execution.py::test_unset_manual_request_reaches_one_fill_without_synthetic_risk_rows
bash scripts/reset_ci_test_database.sh "$test_postgres_container"
uv run pytest -m fresh_global_state
```

Commit/push requires the owner's Git instruction. After push, monitor required
CI on that SHA through completion. No production behavior, public API, schema,
trading rules or workload criteria changed. W1–W3 and Pending Full Validation
remain at the previously approved checkpoint; this evidence does not close them
or establish that F-19 is Completed or ready to merge.
