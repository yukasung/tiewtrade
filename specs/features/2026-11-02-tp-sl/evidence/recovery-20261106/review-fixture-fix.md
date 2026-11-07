# Recovery review finding: NC12 test database isolation — 2026-11-07

Owner requested the Medium finding fix (`แก้ไข`); locally resolved. Required remote
CI on the final published candidate remains pending.

## Change and reuse

The execution-market conftest builds a clean session-owned schema template using
existing `db/bootstrap/*.sql` and Alembic `upgrade head` under MIGRATOR. Only affected
NC12 tests opt into function-owned clones. Bootstrap reapplies database ACLs/log
settings, which PostgreSQL template cloning does not copy. Role credentials remain
unchanged; scoped role/admin URLs are restored afterwards. All created databases
are removed after dependent engines are disposed. No shared ambient DB cloning,
reset/deletion or forced connection termination.

Empty-startup, authenticated HTTP, restored-domain, admin observer and routing tests
use these fixtures; routing reuses the database factory for its second target. The
mocked V3 parent test supplies valid fake config instead of relying on ambient URLs.
Production guards, assertions, workloads, trading rules and migrations are unchanged.
Two real-DB regressions prove fresh clones after occupied history, cleanup on normal
and error exit, database removal and ambient configuration restoration.

## Checks and retained outcomes

- Initial scoped run:204 passed /3 failed in42.39s. All3 failures were missing local
  Redis API URL; with the existing Redis endpoint configured, all3 passed in8.92s.
  See `review-fixture-targeted.*` and `review-fixture-config-recheck.*`.
- CI-compatible mixed run on a separately created non-`internal20` ambient DB:
  206 passed /1 failed in41.43s. This exposed the mocked V3 unit test's remaining
  ambient guard dependency. After the fake-config fix, that test passed in0.70s
  with no database/Redis environment required. See `review-fixture-ci-compatible.*`
  and `review-fixture-unit-recheck.*`.
- Thus207 distinct scoped cases have passing applicable evidence, across these
  runs. This does not claim a single final207-case green invocation or remote CI.
- Cleanup:0 new fixture databases left,0 ambient connections after pytest; the
  separately owned CI-like ambient DB was then dropped normally. See
  `review-fixture-cleanup.json`.
- Ruff/format passed7 affected Python files. Mypy with `MYPYPATH=src` passed the
  same7 files (`review-fixture-final-mypy.log`). Initial mypy without source
  discovery could not resolve local typed modules; it is not passing evidence.
  `git diff --check` passed.

No workload rerun: only fixture setup/teardown and mocked configuration changed.
Prior production safety/workload proofs retain their declared candidate/profile
scope. No historical Failed/Incomplete result changes. Final required CI and the
opening/Release/dependency gates remain. No Git/deploy/Live action or F17 completion.

Next checkpoint: owner decision on separate refactor per AGENTS.md, then affected
validation and owner-authorized publication/required CI. This fixture fix alone
does not justify another workload campaign.

## Owner-authorized refactor and affected validation

Owner invoked `refactor the code`. Only the newly added fixture implementation in
`conftest.py` changed: reuse `profile_restore.database_url` instead of repeating URL
construction, centralize bootstrap for both template/clones in the scratch database
lifecycle, and parse each role URL once in the same-server validation. Configuration,
bootstrap SQL, schema, role credentials, teardown order, guards and test assertions
remain unchanged. No production file or other test source changed in this refactor.

The same207-case mixed suite passed together in37.17s on the post-refactor candidate,
including occupied-database rejection, real HTTP/owner isolation, restored-worker
routing, pool lifecycle and V1/V2/V3 profile contracts. Logs/XML:
`review-fixture-refactor-tests.*`. Cleanup left0 new fixture databases
(`review-fixture-refactor-cleanup.json`). Ruff/format and mypy with `MYPYPATH=src`
passed the changed conftest; unchanged files retain their prior scoped checks.
`git diff --check` passed. Candidate hashes: `review-fixture-refactor-candidate.json`.

This is affected validation after the refactor, not a workload rerun or remote CI.
Retain prior safety/financial/workload evidence in its unchanged scope. No further
local work remains for this refactor. Next: final admission/opening gate audit and
owner-authorized Git publication/required CI; all pending F17 Release/dependency
gates remain. The prior refactor decision checkpoint above is now fulfilled.
