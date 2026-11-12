# PR66 main synchronization checkpoint — 2026-11-12

Owner instructed synchronization with main followed by required CI. Candidate
`a4217a10d1660fb79354c9c255f7f3a154f88f2b` merges main
`f7c94f5379aea19ef52bf347dbf9fb63d355435a` without conflicts. Imported changes are
CI tooling/workflow and documentation; no production, migration or F17 harness
changes. Local CI policy tests: 58 Passed; staged diff check Passed. No merge of
PR66 into main was performed.

Previous head `e4b100b6b180639cc6f4be35b001cef9bc02dec8` remains historical:
[PR CI](https://github.com/yukasung/tiewtrade/actions/runs/42652614920),
[restored push CI attempt 2](https://github.com/yukasung/tiewtrade/actions/runs/42652603183),
and [Security](https://github.com/yukasung/tiewtrade/actions/runs/42652614702)
all Passed. The restored push run completed 4,892 main tests plus 99 isolated
test executions. These results do not certify the new candidate.

## New candidate results

- [CI 43152232403](https://github.com/yukasung/tiewtrade/actions/runs/43152232403):
  Failed. Configuration, frontend, API contract, container and browser checks
  Passed. Browser: 42 Passed, including all seven F17 cases.
- [Security 43152232424](https://github.com/yukasung/tiewtrade/actions/runs/43152232424):
  all seven jobs Passed on the new candidate.
- Backend lint/format/types/import checks Passed. Main pytest: 1 Failed,
  4,891 Passed, 31 deselected, five warnings in 1,017.04 seconds. Later isolated
  protection/migration/fresh-global/rollback stages were Skipped, not Passed.
- Failure:
  `tests/services/indicator_builder/test_scheduler.py::test_catalog_and_control_gate[PREPARING]`,
  line 87: concurrent `coalesce_jobs()` calls returned
  `DatabaseTimeoutError`, SQLSTATE `55P03`. PostgreSQL log confirms lock timeout
  on `SELECT public.coalesce_indicator_build_jobs()`.

The failed test and scheduler implementation were unchanged by this merge.
Neither blocking transaction identity nor the reason the lock remained held is
established by the available log. This is not classified as runner flakiness or
proven unrelated interference. No retry, timeout relaxation, assertion change,
or indicator source modification was performed.

PR66 remains blocked. Next proposed scope is targeted read-only lock diagnosis
for the failed scheduler test with unchanged assertions/timeout and an isolated
database; owner instruction is required before extending this synchronization
task to that work. No automatic rerun. Existing Paper campaign results retain
their original candidate/profile; F17 Full Validation/dependencies remain pending.

This receipt and associated status updates are kept locally for the next related
change; no CI-only documentation commit/PR was created.

## Owner-authorized targeted lock diagnosis — 2026-11-12

Owner answered “เริ่มทำ” to the proposed targeted diagnosis. Ran the exact failed
PREPARING test once, unchanged, on a newly bootstrapped/migrated disposable
PostgreSQL 16.15 database. Python 3.12.15, asyncpg 0.31.0, SQLAlchemy 2.1.1,
pytest 9.1.1. No application services or Live paths were started. Docker was
initially stopped; it was opened, inventory was empty, and only a dedicated
diagnostic container with temporary filesystem storage was created.

Command after bootstrap/migration:
`backend/.venv/bin/python -m pytest -q 'tests/services/indicator_builder/test_scheduler.py::test_catalog_and_control_gate[PREPARING]'`
(working directory `backend`, so the executable was passed as an absolute path).
The private launcher `/tmp/tiewtrade-f17-lock-diagnostic-20261112.py` prepared
role-specific local fixture URLs, invoked this unchanged test and observed from
a separate admin connection with read-only transactions. It polled activity at
10ms intervals, storing only role/PID/state/wait/blocker/age metadata and a boolean
for the known coalescer statement; no query parameters, SQL text, tokens or owner
data were retained. The raw lock snapshot/private output stays outside the repo.

[Sanitized result](scheduler-lock-diagnostic-20261112.json): test **Passed**, exit0,
1.385 seconds across the test subprocess/observation, 118 samples, no observer
errors, two coalescer activity samples, one blocked activity sample. PID87 waited
on `transactionid` held by PID86; both were indicator-builder coalescers. PID86
was `idle in transaction` and its transaction age at that snapshot was12.377ms.
This is transaction age, not measured total wait or commit latency. The separate
lock snapshot followed release and cannot identify the exact blocked row.

The production helper retains its original200ms lock/500ms statement timeouts.
The SQL function seeds jobs then locks jobs for update; concurrent calls can
therefore contend. This observation establishes self-contention locally but does
**not** reproduce the CI failure or prove which backend blocked the failed CI
call, why its wait exceeded200ms, or that this is infrastructure flakiness.

Cleanup: zero test database connections after observer close, database dropped
normally, dedicated container stopped and removed, no owner database/volume
modified. No test/production changes, extra test iteration, CI rerun, commit,
push or merge. Timing for preparation/read/bootstrap was not separately measured;
the1.385s observation is not the total task time.

Current diagnostic scope is complete. PR66 still has Failed CI on a4217a1.
Next recommendation: capture the same bounded, sanitized lock evidence in the
failing CI environment before choosing any fix. That extends beyond this local
diagnosis and needs owner instruction; keep timeout/assertions and old Failed
result unchanged. Existing F17 Full Validation/dependencies remain pending.
