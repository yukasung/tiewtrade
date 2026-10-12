# A-D execution: disconnect contract failure (NC-38)

Date: 2026-10-12. Status: **Historical finding; owner approved NC-38 and correction implemented.**
Current results: [A–D validation](ad-validation-report.md). The original failed
regression below is retained as before-fix evidence.

**Medium - ASGI disconnect does not cancel the indicator reader.**

Location: `backend/src/tiewtrade/services/api/indicator_routes.py::indicators`.
Approved `plan.md`, "Deadline, cancellation and errors", requires a disconnect
watcher to cancel/join the reader, no response after disconnect, bounded cleanup,
and keeping the local slot until reader/query/connection shutdown completes.
This remains a functional V-15/PV-8/R2-10 gate, not deferred load testing.

The current route uses `asyncio.timeout_at` but never receives disconnect events.
Its SafeInputRoute wrapper only sanitizes validation errors. Installed Uvicorn
h11 connection_lost marks the cycle disconnected and wakes its receive event;
it does not automatically cancel the request task. Caller cancellation tests
therefore cannot replace an actual `http.disconnect` test.

Reproduction: `backend/tests/test_indicator_disconnect.py` calls the real route
and IndicatorBudget with a Starlette Request backed by an ASGI message queue.
Admission is accepted by a test double; the reader is paused at a deterministic
barrier. The test sends `http.disconnect` after the reader starts, without calling
task.cancel. Reader cleanup does not begin within 2.5s, so the test fails. Only
test teardown cancels the task. No DB, Redis, live venue or trading data is used.
This isolates disconnect orchestration; it does not claim real DB cleanup proof.

Evidence: `api-disconnect-before-fix.xml`, **1 failed**, no skips. An active read
can continue after its client has gone, holding the one-per-process budget until
normal completion or the existing 30s deadline. Production data corruption or
unintended orders are not alleged.

Proposed correction, preserving the approved plan:

1. Add bounded disconnect observation alongside the reader/deadline tasks at the
   service layer. Keep core pure and retain current auth/admission/error codes.
2. Cancel and join the reader on disconnect; do not manufacture a success response.
   Keep the budget until the existing bounded transaction cleanup has completed.
3. Test disconnect versus success/timeout/cancellation, stalled DB cleanup, slot
   reuse and absence of orphan/background tasks. Then continue packages A-D.

At the original finding, AGENTS.md required stopping for the code/spec conflict.
The owner subsequently approved NC-38. The correction and A–D evidence are now
implemented and ready for review; no acceptance thresholds were changed.
