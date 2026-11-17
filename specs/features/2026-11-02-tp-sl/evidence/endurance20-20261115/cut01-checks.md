# CUT-01 correction, review and refactor checkpoint — 2026-11-17

Owner explicitly authorized continuous correction through four-hour testing without
repeated questions. Reproduction: 2 tests failed on the original grouped-task cleanup,
showing cancellation sent twice and interruption of a child's finally. Both now pass.
This is a proven harness defect; exact historical OBS05 borrower attribution is unknown.

Reused finish_observed_cleanup and factored shared join_owned_tasks for bounded_map's
opt-in joined path and scheduled cycles. Pending cancellation is not reissued. Owned
join is shielded against repeated caller cancellation, retains primary exception and
phase/type-only secondary notes, and precedes engine disposal. No new sleep, retry,
financial logic, production change or pool waiver. Default unjoined map is unchanged.

Review: callers, exception ordering, normal completion, sibling failures and repeated
caller cancellation checked. Refactor removes duplicate cancellation/join loops using
one helper. No remaining finding identified within this correction. 269 targeted tests
passed including real PostgreSQL locks/transactions/pools, delayed connection close and
repeated cancellation; 2 real-PG cases prove zero borrows before disposal and no advisory
lock remaining. Prior 40 prefix tests/170 M1 evidence retained. Ruff/format/mypy passed
for 2 changed files. Initial lint/type formatting issues corrected before this final run.
Independent DB audit: database absent, zero connections and locks; no Redis created.

Raw: validation-artifacts/f17-cut01-tests-20261117/. Continue to one original W3 after
preflight; no 40-minute repeat required because deterministic real-PG regression proves
this cancellation lifecycle. No claim the old sampler timeout root cause is solved.
