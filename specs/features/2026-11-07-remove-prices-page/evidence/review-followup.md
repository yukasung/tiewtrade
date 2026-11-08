# Review follow-up — 2026-11-07

Status: Low finding fixed; Medium validation blocker isolated, not closed.
Candidate: uncommitted feature/remove-prices-page, base f15596df0b1ced53107964a8ed9bb657fda9d336.
Owner authorized fixes and bounded baseline diagnosis with “เริ่มทำ”.

## Findings and checks

- Removed retired `prices` entry from `frontend/e2e/risk-limits.spec.ts:8`.
  All remaining kill-switch assertions are unchanged. Static comparison confirms the nine
  entries equal runtime accountPages; targeted ESLint and git diff --check passed.
  Full risk/trading E2E was not rerun for removing a redundant fallback visit.
- An unchanged detached worktree at the implementation's main base failed the same
  chart recovery READY assertion: [baseline log](review-baseline-recovery.log).
  Tracked baseline files were unchanged; dependencies were installed from the frozen lockfile.
- Temporary instrumentation outside the repository traced the candidate's live HTTP path:
  admission was cancelled in 0–2ms, before `_live` or a DB read began.
  [Trace](review-live-boundary-trace.log). No parameters, tokens or credentials were logged.
- A standalone Python 3.12.15 probe measured uvloop loop.time() minus time.monotonic()
  at approximately +2103.989 seconds on this host. `asyncio.timeout_at(time.monotonic()+2)`
  timed out immediately under uvloop, whereas standard asyncio completed a 10ms await.
  This is an observed clock-origin mismatch, not a DB timeout or proof of slow Redis.
- `chart_routes.py:173–175` passes a time.monotonic deadline to asyncio.timeout_at,
  which uses the event-loop clock. `indicator_http.py:175` has the same pattern;
  its full impact was not tested in this scoped investigation.
- One candidate recovery run using temporary config with `uvicorn --loop asyncio` passed
  READY → RECOVERING → READY in 8.3s: [log](review-asyncio-recovery.log).
  No deadline, assertion, fixture or runtime source was changed. This confirms the local
  failure mechanism but is not a pass for the normal auto/uvloop configuration.

## Decision required

V-03 remains Partial/Failed on the normal configuration. The failure also occurs on the
unmodified base and is not caused by removing the prices panel. Required CI remains Not Run.
The bounded investigation is complete; no additional retries are planned.

Recommended next scope: a separate backend deadline-correctness feature with its own
requirements/plan/validation and approval gates. Use a consistent clock for scheduling
relative/absolute timeout budgets in chart_routes/indicator_http; retain the existing
2-second chart limit and indicator budgets, session checks and cancellation cleanup.
Add a clock-offset regression and run the default-loop recovery flow before closing V-03.
The precise implementation must account for the injected clock used by indicator tests.
Do not silently force asyncio in committed configuration to mask the runtime defect.

No backend/configuration source, financial logic or Live orders were changed. No commit,
push or PR was performed. Refactor has not started; the Medium blocker is still open.
