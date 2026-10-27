# F-38 low-churn workstation checkpoint — 2026-10-26

Status: **Host preparation and targeted harness repair verified.**
Historical API_RESOURCE_LIMIT cause not conclusively established; acceptance Pending.

## Host condition

Read-only 30-second `host.json` capture showed median compression/decompression
churn **2.308 MiB/s**, max **19.712 MiB/s**, swap-in +40 pages and swap-out +0.
Host swap usage was ~2,824 MiB, down from ~4,189 MiB in the earlier audit. The
agent did not close user applications or change host/Docker RAM settings.
Obsolete r4 PG/Redis remained stopped; r5 and development services remained.

This was a materially different host condition from the earlier hundreds of
MiB/s median churn and justified one short native workload check.

## First attempt exposed a separate harness bug

`../environment-lowchurn-b5m-r1/` aborted after the first measured minute with
`TimeoutError` waiting for the admitted probe's barrier. It has partial evidence
and no result file; it must not be counted Passed.

Raw evidence shows:

- First barrier request completed 200 at `14:59:59.594381+00:00`.
- Its rejected-rate batch crossed the Redis UTC minute boundary: **4 returned
  200 and 16 returned 429**, rather than all 20 returning 429.
- That batch consumed the new fixed-window quota. The next planned admitted
  barrier probe returned **429** at `15:00:59.314697+00:00` with zero candle queries.
- The harness kept waiting for a barrier that could never be entered and masked
  the actual admission rejection with its 5-second wait timeout.

This is a diagnosed harness timing defect, distinct from the historical resource
lag failures. The Redis limiter correctly implements the existing policy; it was
not weakened or changed.

## Harness-only repair

- Use real `Redis TIME` to align measured phase T0 five seconds inside a fixed
  minute window, allowing the normal loaded-probe batch to complete before the
  boundary. Only the pre-T0 start is aligned; probe cadence remains 60 seconds.
- No counter reset, new identity rotation, limit increase, measured retry or
  acceptance-threshold change.
- Await the HTTP and barrier tasks together. A non-200 response before admission
  now reports `CAPACITY_BARRIER_REQUEST_REJECTED_<status>` immediately, cancelling
  the unused barrier, rather than waiting for a misleading timeout.
- Record the actual Redis alignment in `admission-phase-alignment.json`.

Regression/boundary checks: **76 passed** (alignment, smoke, scope and evaluator
gates). After the Awaitable-compatible scheduling adjustment, the 7 new alignment/
barrier cases passed again. Ruff/format/Mypy passed on the affected Python files.
Review confirmed default acceptance duration, quotas, source operations and
resource limits are unchanged. C1/R2-7 do not use the rejected-load barrier or
steady-phase alignment and remain available without a new source change.

## Successful short verification

`../environment-lowchurn-b5m-r2/` completed **300.000 s**,
`DIAGNOSTIC-steady=PASSED`, failure null, `full_validation_credit=false`.

- All eight timeframes: **30/30** readiness observations and **5/5** correct probes.
- **240** request records; max request lag **4.267 ms**, RSS delta **63,250,432 bytes**.
- Redis alignment waited 10.546844 s before T0; actual phase began at
  `2026-10-26 15:07:05.002026+00:00`. Five probe rounds completed without the
  prior boundary rejection or barrier timeout.
- Measured host churn median **31.406 MiB/s**, max **218.160 MiB/s**; cgroup
  throttled periods/time zero.
- **Zero deduplicated >=40-ms heartbeat gaps** during the measured interval,
  compared with 13 in the first five minutes of the earlier high-churn A run.

The outcome is consistent with the host-load hypothesis but not proof of the
historical failure's cause: runs are sequential, host activity is uncontrolled,
sample length is short, and harness phase alignment also changed. Do not treat
the comparison as a clean causal attribution or infer 60-minute stability.

## Checkpoint

The workstation is substantially quieter in this observed window, and the newly
found harness boundary race is fixed and verified. No further identical short
diagnostic is justified. Full merged-candidate resource acceptance and applicable
fairness/aggregate/CI work remain Pending; announce rationale/duration before any
new long run and retain the failed/partial attempts.

Diagnostic API/builder containers stopped after both attempts. No production
source, migration, dependency lock, rate limit, order behavior, commit, push or
merge changed. No Live order was sent.
