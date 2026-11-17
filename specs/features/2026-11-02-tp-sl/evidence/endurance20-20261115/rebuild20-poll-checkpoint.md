# NC-F17-REBUILD20-POLL-01 — streamed fixture evidence checkpoint

สถานะ: **Scoped implementation/safety checks Passed; awaiting owner code review**.
2026-11-16. [Approved amendment](../../rebuild20-poll-evidence-plan.md) ·
[Sanitized test summary](rebuild20-poll-summary.json).

## Changes / reuse

Parallel rebuild fixtures now exclusively create parent-poll-attempts.jsonl before
publisher/worker tasks are spawned and pass it to the existing ParentPollGate streaming
path. Default single-worker in-memory mode and100000 guard remain unchanged. Both modes
save parent-poll-gate.json after seed tasks and owned mutators have joined. Summary
failure preserves the original exception/cancellation and still attempts the separate
fixture-progress receipt. No poll concurrency/cadence/deadline/financial/source change.

The directly related ParentPollGate trace-write error path now preserves an already
active body exception/cancellation instead of replacing it with evidence IO failure.
It does not increment finished_count when the row was not saved, so summary consistency
still fails closed. A trace-write failure with no earlier error propagates normally.
This engineering extension was recorded before source edit; no validator waiver or
expected-cancellation whitelist was added. Original parent pool failure remains Failed.

## Validation

Final83 targeted cases Passed in31.217s including fresh isolated realPostgreSQL,
actual20-worker small fixture,Money/Quantity/global/RLS/source/padding-no-economic-write/
fullsmallreplay and pool proof; existing parentpoll regression/deadlines/identity tests.
Tests cover100001 streamed attempts without in-memory rows,originaldefaultguard,
streaming concurrency4/wait cancellation,primary/summary/stream IO combinations,
summary after join,partial receipt on failure and previous trace rejection before tasks.
Realparallel fixture also asserts stream row count equalsattempt/finished count,
active0,truncatedfalse,cadence0.25,peak≤4. No mock replaces DB/process proof.

Earlier implementation checkpoint81casesPassed before the additional simultaneous
operation/cancellation+traceIO tests; retained privately. Initial scoped mypy errors
were confined to test double annotations after formatting; corrected with explicit
AsyncEngine casts. Final four-file Ruff/format/mypy/whitespace Passed. Independent
maintenance connection confirms the final test DB absent,0connections/0advisorylocks.
Private logs: validation-artifacts/f17-rebuild20-poll-tests[-r2]-20261116/.

No production code/API/schema/session/risk/Live change. Process handles and trace rows
remain transient harness state, not application persistent business/session storage.
Existing financial/decoder/ownedpool proofs outside this diff remain scoped valid.

## Stop / next scope

No full-profile replacement,fullrebuild,four-hour run,Git,CI ormerge in this amendment.
REBUILD20-02 remains Incomplete and parent aggregateFailed/Incomplete; PREP20 result
retains its provenance limitation. F17 remains notCompleted. Next owner code review
of this harness fix,then authorized fixes/refactor/affected validation as appropriate.
A replacement full rebuild campaign still needs explicit approved scope; do not start
one from these targeted tests or claim the100000 trace issue was runtime-validated
under the full28200-command history profile.
