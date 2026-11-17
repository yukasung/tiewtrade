# OBS-05 M1 cleanup failure — 2026-11-17

สถานะ: Fixed; waiting for owner refactor instruction. Campaign Not Run.

Prefix cleanup now checks every joined task result, distinguishes requested cancellation
from unexpected cancellation, and attempts all owned resource finalizers despite failures.
It preserves the original exception and records phase/type-only secondary errors. A cleanup
failure writes `prefix-cleanup-failure.json` and marks diagnostic evidence Incomplete;
existing Failed status is preserved. Receipt IO errors do not replace the primary exception.
Changes are limited to prefix harness cleanup and regression tests; production is unchanged.

## Checks

- 170 targeted tests passed, including real PostgreSQL rollback/lock-release proof,
  parent cutoff fault injections for resource/position/fault/publisher tasks, multiple
  failures, primary exception retention, receipt IO failure, and unexpected cancellation.
- Initial non-DB check: 40 passed. Initial mypy failed due to exception-variable name reuse;
  the name was corrected. Final Ruff, format and mypy passed for all 3 impacted files.
- Independent cleanup: test database absent, zero connections and locks. No Redis created.
- Raw evidence: `validation-artifacts/f17-obs05-m1-tests-20261117/`.
- Earlier OBS-05 400-test evidence remains valid for unaffected behavior.

No workload, preflight, commit, push, CI or merge performed. Earlier W3 Incomplete and
F-17 Pending Full Validation remain unchanged. Next: owner-authorized refactor, then
its affected checks and the approved one-campaign checkpoint.
