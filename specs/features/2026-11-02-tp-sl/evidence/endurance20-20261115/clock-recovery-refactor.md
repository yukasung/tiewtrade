# NC-F17-CLOCK-01 refactor checkpoint — 2026-11-15

สถานะ: Owner-authorized refactor and affected Feature validation Passed.

Owner instructed `refactor the code` after the R1–R3 corrections. Only the new
recovery controller and its tests changed relative to the review-fix source receipt.

- Reuse one typed published_input_ids helper for the identical ordered buffer query
  in six tests. Keep each caller's existing authorized session, query ordering,
  expected IDs and transaction/cleanup scope.
- Bind the first recovery attempt once during commit evidence validation. Remove
  the unreachable fallback for an absent first attempt, already rejected by that
  validation. All checks, error messages, evidence values and persistence order
  remain unchanged. No new abstraction, retry policy or transaction helper.

## Affected validation

- All 62 recovery cases Passed in 12.01s, no skips, including the real-PG successful
  recovery/financial invariants, rollback/close/unknown-commit failures, source
  advancement, parent/child isolation, timing boundaries, cancellation and evidence.
- Ruff check, format check and mypy Passed for all five harness/test paths.
- Whitespace check Passed. No production, frontend or database/schema changes.
- Isolated parent test DB removed normally by the owner-receipt-scoped launcher.
- Private test log retained: validation-artifacts/f17-clock-recovery-tests-20261115/
  attempt-1794711594057758000.log. Raw artifacts remain private/untracked.

The earlier 101/56 regression runs remain valid: integration wiring, readiness
observer, publisher body, campaign options, processing windows and deadlines did
not change in this refactor. This is affected Feature validation after refactor;
no full suite, required CI or timed workload was run without authorization.

Recovery control remains ephemeral fixture-only data, not a login/session or
persistent business source. Existing PostgreSQL business/session storage and
multi-instance production behavior are untouched. No safety criteria were relaxed.

[Source receipt](clock-recovery-refactor-source-bridge.json) records the current
candidate and preserves both historical source receipts. The original 4h20 result
remains Incomplete; no evidence proves the underlying OS/VM clock issue fixed.
F17 is not Completed; original Release/opening/dependency gates remain pending.

Next: plan step D requires explicit authorization for one fresh 20-account four-hour
replacement (opt-in NC_F17_CLOCK_01), with preflight and cleanup, estimated total
4h15–30min. This refactor command does not authorize that run or commit/push/merge.
