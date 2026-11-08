# PR63 post-merge browser timeout — diagnostic proposal

สถานะ: **Approved A — owner authorized one targeted diagnostic and conditional one E2E-only rerun, 2026-11-08; no source change authorized**
Date: 2026-11-08 Asia/Bangkok
Merged PR63:58e2299e1d179607f5a2e5e4671e48beb7a01009
Approved pre-merge candidate:e38bf344f32cc9be13ba42fbe3bbdcd29762cb9b
Git trees identical; no additional runtime diff introduced by merge.

## Evidence / uncertainty

Pre-merge CI42468187011 and Security42468187004 Passed.
Post-merge Security42487118837 Passed all jobs. CI42487118978 browser job
128751381263 Failed:19passed/onefailed in2.3min. Existing
frontend/e2e/candlestick-chart.spec.ts:356 native3m BTC/ETH case hit default30s
test timeout. There is no failing assertion or per-call trace to identify which
await consumed the time. Artifact contains error-context only, no trace archive.
The final snapshot shows BTC/3m and fixture price200.000000000000000001 with an
open candle; this alone does not prove live READY or observer/history completion.
Later catalog/F16/F17/risk E2E steps were Skipped, not Passed on this merge SHA.
Backend still running at proposal preparation. Do not call this flaky or a
production regression without more evidence. Main merged; no rollback performed.
Raw downloaded artifact kept in private local state, not committed/published.

## Proposed bounded next step

No production/test source or timeout/assertion changes. Use the existing3m test
and existing real API/fake-feed composition on a fresh isolated test database,
with Playwright retain-on-failure trace enabled for one targeted run, no retries.
Keep30s test bound, exact BTC/ETH history/live precision and no-order assertions.
Use a separate checkout/branch if source changes become necessary; do not reuse a
merged feature branch for unrelated chart fixes. Keep raw trace private; publish
only allowlisted step durations, public candle observer state/counts and sanitized
error codes. Never expose headers, cookies, test passwords, OTPs or response bodies.
Estimated2–4min, overall diagnostic budget10min. If it fails, stop/report and
propose a source fix only after diagnosis. If it passes, rerun only the failed
post-merge CI E2E job once (about5–8min), retaining current-SHA successful backend
and Security proof; no full backend rerun or Security rerun needed. Track result,
preserve the first failure, stop/report if still failing. No automatic test retry,
threshold relaxation, source change, extra trade or F17 Completed claim.

Next owner authorization should explicitly cover this targeted diagnostic and
one E2E-only rerun on the same merge SHA. Current merge instruction has been
executed; remaining post-merge failure is a new diagnostic checkpoint.

## Approved diagnostic result — 2026-11-08

Owner chose A. Created detached checkout of58e2299 and fresh database
tiewtrade_e2e_merge3m20261108. Reused original composition/test and assertions,
changed only external local runner ports to18013/15113 and isolated Redis DB11
(initial DBSIZE0); enabled retain-on-failure trace, no timeout/retry changes.
Existing PostgreSQL/test Redis were stopped and started for this diagnostic;
no container/volume removed and no owner database changed.

Two preparation invocations executed zero tests: external config module format
then overly anchored grep. Corrected private runner only; --list confirmed exactly
one case before actual execution. The single actual targeted test Passed12.5s.
Because it passed, retain-on-failure produced no trace, and no claim is made that
the first CI timeout cause is now proven. No source diff. Raw artifacts remain
private. Conditional approved E2E-only rerun triggered on the same merge SHA;
its outcome remains pending until observed.

Backend independently Failed: test_real_worker_cli_records_pools_and_exits_cleanly
[True], profile_diagnostics.py:356, read empty pools JSON during polling;4820passed,
onefailed. Subsequent isolated backend gates Skipped. This is outside E2E-only
authorization and has not been changed or rerun. Security on merge SHA Passed.

## Final E2E checkpoint

Approved E2E-only rerun completed Passed: job128756360168, CI42487118978
attempt2 on unchanged58e2299. Main20/catalog2/F16seven/F17seven/risk6 =42Passed.
Security42487118837 remains Passed. Backend was not rerun; its original failure
remains blocking (4820Passed/oneFailed). Overall CI remains Failed. The3m first
timeout is retained as historical Failed; no claim that its cause is corrected.
Diagnostic database dropped after zero-connection check and detached worktree
removed without force after removing only created dependency symlinks.
No source or monetary mutation, no new commit/PR/branch deletion. Next proposed
backend harness repair is postmerge-pool-evidence-atomic-proposal.md and requires
owner approval; current E2E diagnostic/publication scope is complete.

Subsequent owner approval: atomic pool-evidence follow-up Approved A, tracked in [proposal](postmerge-pool-evidence-atomic-proposal.md); its publication is a separate PR and not another3m test rerun.
