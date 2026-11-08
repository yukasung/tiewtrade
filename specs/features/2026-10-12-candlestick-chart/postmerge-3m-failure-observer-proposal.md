# Native3m post-merge timeout — failure-only browser evidence

สถานะ: **Approved A — owner explicitly approved failure observer, targeted checks, PR/publication and one CI round on 2026-11-08; no automatic merge**
Date: 2026-11-08 Asia/Bangkok
Current main29e394601dea7068809e6416522087d357bfa8d3 (PR64 merged).

## Repeated evidence / uncertainty

Post-merge CI42492026828 failed the same native3m BTC/ETH browser case at
candlestick-chart.spec.ts:356 (default30s bound),19other main-browser cases Passed.
Earlier merge58e2299 had the same timeout; approved isolated diagnostic then
Passed12.5s and one E2E rerun Passed42. Pre-merge PR63/64 E2E also Passed42.
Repeated failures mean a successful retry has not diagnosed/resolved the issue.

Both failure contexts show BTC/3m, exact fixture price200.000000000000000001,
ETH available in the selector, no disabled selector, and an open candle. Both
snapshots happen to align at minute57; that correlation is not a proven cause.
There are no per-call traces, and the existing native-fetch observation summary
is attached only after all assertions complete, so timeout loses the data needed
to identify missing history/live READY or incomplete fetch/body operations.
Security on main29e3946 Passed. Backend later Passed all4926cases, including atomic pool writer regression and all isolated gates.

## Approved requirements / plan amendment

Diagnostic-only update to the existing3m browser observer in
frontend/e2e/candlestick-chart.spec.ts; no production/chart/API/DB change.
Keep default30s, original assertions, BTC/ETH exact values/timeframe/READY checks,
abort/shape bounds, no-order proof and fixture behavior unchanged. No retry or
threshold extension to make the test pass.

Record bounded started/completed/aborted/pending request observations for the two
existing public chart paths only, without extra API requests or response changes.
Reuse the existing completed observer and allowlist path/base/timeframe/status/
rowCount plus elapsed timings. A failure-only afterEach hook should capture these
and current public chart selection before page teardown, including on timeout.
Do not retain headers, URLs with arbitrary query data, cookies, tokens, passwords,
account data, raw response bodies or raw network trace. A diagnostic-read failure
must attach an unavailable marker without masking the original failure.

## Approved validation / checkpoint

Use a separate F12 follow-up branch/worktree from current main. Record approval in
the relevant chart plan/validation before edits. Scoped ESLint/typecheck; verify
failure-path collection with a controlled private test and synthetic public
observer data, ensuring sensitive sentinel fields are omitted and original
failure remains failed. Run the original affected3m case once against a fresh
isolated DB without changing its criteria. If local checks pass, normal commit/
push, new diagnostic PR and one required CI round (about25–30min including checks),
then stop/report. No automatic merge or rerun on failure; if CI passes, report
instrumentation verified but the intermittent timeout root cause still open.
A main-event reproduction, if still needed, requires an explicit later decision.
Do not claim F17 Completed or consume the successful old-SHA results as new proof.
Approval recorded before source edits; implementation results remain Pending until checked.

## Final post-merge checkpoint

PR64 merged29e3946. CI42492026828 finished Failed solely at native3m browser
timeout (19other main cases Passed; later catalog/Paper/risk browser steps Skipped).
Backend4926Passed and all static/contract/container checks Passed.
Security42492026736 finished Passed. The pool publication repair is verified on
main; this observer proposal is a separate F12 diagnostic follow-up. No source
change, new commit/PR, test rerun, branch deletion or rollback performed here.

Approved implementation local checkpoint: [evidence](evidence/postmerge-3m-failure-observer/checkpoint.md). Required remote CI remains Pending; no runtime fix or root-cause resolution claimed.
