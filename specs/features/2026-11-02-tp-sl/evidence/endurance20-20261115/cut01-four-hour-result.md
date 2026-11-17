# CUT-01 four-hour W3 — 2026-11-17

สถานะ: **Incomplete — first-owner final replay exceeded the unchanged 60s budget**

Owner authorized continuous correction through four-hour testing. Harness double
cancellation was reproduced, corrected and reviewed/refactored; [269-test checks](cut01-checks.md)
passed before execution. No production change, criteria relaxation or financial retry.

## Observed results

- One preflight Passed before owned fixture creation. Candidate/config/schema/runner
  and original fault schedule pinned; source unchanged throughout.
- Measured 14400.000672s (full four hours). Total
  14671.304175s (4h04m31.304s), including preflight/failure/cleanup.
- 28200 offered/admitted/completed commands, zero rejected; 11280 fills, 5640 cancels,
  5640 replays, 5640 completed cycles. These counters do not replace the final financial oracle.
- All seven fault observations RECOVERED: three worker restarts, two connection churns,
  two dedicated Redis outages. Original offsets/durations preserved in raw receipts.
- Final-tail completed in 49.640753s within60s; all20 cursors READY,
  lag0 at final head144364.
- All4820 snapshot reads RETURNED; p95 17.738ms,
  p99 36.657ms, max 159.034ms.
- Publisher144364 RETURNED, no lease failure or clock recovery event; natural sampler
  NO_TRIGGER/zeroerrors/taskjoined. No proof the earlier intermittent timeout root cause
  is solved; it did not recur during this run.

## Why Incomplete

First owner's replay timed out after60.522797s,33 completed queries/111161 returned rows.
Stack and resource receipt locate cancellation in read_execution_inputs from
replay_owner_domain. The configured budget remains60s; wall duration includes cleanup.
No completed replay receipt for this owner; other19 owners NotRun. Final financial/global
verification and final processing/resource acceptance aggregates were not reached.
Do not infer full money/PnL correctness merely from completed command counters.

All pool generations returned borrows before final disposal (zero), including ENGINE.
All80 worker pool receipts Passed. Parent pool remains Failed because the actual replay
query cancellation is recorded as ConnectionResourceError; do not waive or regrade it.
This run validates return-at-dispose behavior but is not itself a repeat of planned prefix
cutoff; deterministic real-PG regression supplies that specific cancellation proof.

## Cleanup and next step

Independent audit: owned database/Redis absent, zero database connections/locks,
80 worker PID receipts inactive. Source/config/runner bindings unchanged. Previous
Failed/Incomplete results retained. F17 remains Pending Full Validation, not Completed.

Recommend a short isolated replay-read investigation using existing ReplayReadObserver
and representative W3-size fixture to separate SQL/driver/decode time while preserving
full evidence/financial checks and60s criterion. Existing failure shows location, not exact
cause of the latency; historical query content is not available after normal owned cleanup.
Do not repeat another four-hour run or modify production/criteria automatically.

This approved campaign is consumed; stop/report. No commit/push/CI/merge.
Raw evidence: validation-artifacts/f17-w3-cut01-20261117/.
See [machine summary](cut01-four-hour-summary.json).
