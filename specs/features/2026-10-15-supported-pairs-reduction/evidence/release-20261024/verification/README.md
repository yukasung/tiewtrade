# F-38 final local verification — 2026-10-26

## Backend

- Full regression: **Passed** — 3,219 passed, 2 deselected, 0 failed in 628.19s.
  Evidence: `backend-full-r3/tests.xml`, `backend-full-r3/pytest.log`.
- The preceding `backend-full-r2` run is retained as invalid environment evidence. The host slept
  during the run and the database clock jumped by more than 25 minutes, causing time-sensitive
  lease/retention failures. It is not used for acceptance.
- Ruff check: **Passed**.
- Ruff format check: **Passed** — 507 files formatted.
- Mypy: **Passed** — 464 source files.
- Import contracts: **Passed** — 7 kept, 0 broken.
- Capacity/evaluator targeted regression after final formatting: **Passed** — 27 tests.

The accepted full regression ran on a fresh PostgreSQL 16 database at host port 55469 and a
fresh plain Redis 7 database at host port 56419, with `caffeinate -dimsu` preventing the clock
jump that invalidated the prior run. No application worker or venue connector ran alongside it.

## Frontend and generated contracts

- ESLint: **Passed**.
- TypeScript typecheck: **Passed**.
- Frontend tests: **Passed** — 257 tests.
- Generated OpenAPI/API type drift: **None**.
- `npm ci` reported three pre-existing dependency vulnerabilities; this checkpoint did not change
  frontend dependencies.

## Candidate provenance

- Capacity image: `tiewtrade-f38-release-20261025-r9:latest`.
- Image ID/digest: `sha256:c194273af4d61c86ff267e11fcc13420858cf4d826e944474dac01a84665635b`.
- `../provenance/r9-source-ast.json` proves that every changed production module in the measured
  image and the final working tree has an identical executable Python AST. The only later
  production-source change was formatter output.

## Remaining external gate

Required GitHub candidate CI has not run because this working tree has not been committed or
pushed. Repository policy requires an explicit owner instruction before either Git operation;
local results do not replace CI on the final commit.
