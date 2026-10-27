# F-38 host-load A/B checkpoint — 2026-10-26

Status: **Experiment complete; lower-average host load achieved, stable low-churn
environment not achieved. Root cause and full acceptance remain Pending.**

## Authorized environment action

Following the owner's instruction to start the proposed A/B, stopped only the
obsolete F-38 r4 containers:

- `tiewtrade-f38-merge-r4-20261026-postgres`
- `tiewtrade-f38-merge-r4-20261026-redis`

Exact names, running status and mounts were checked first. PostgreSQL data and
Redis data volumes remain, as do containers and all Failed/Partial evidence.
The action is reversible with `docker start` for those names. They remain stopped.
The r5 test database/Redis and application development database/Redis were not
stopped. No user application was closed or killed. Docker/host RAM settings and
per-process limits were not changed.

## Baseline observations

Three host-only 30-second captures, with `vm_stat` every 2 seconds, produced:

| Window | Median churn MiB/s | Max churn MiB/s | Swap-in delta pages |
|---|---:|---:|---:|
| Before stopping r4 | 327.9 | 1,048.9 | 410 |
| Immediately after stopping | 193.8 | 1,266.0 | 3,798 |
| Later settled window | 92.4 | 244.3 | 930 |

The churn metric is compression plus decompression page-counter movement, not
unique bytes moved or physical memory bandwidth. These successive observational
windows do not prove the container stop alone caused a reduction.

The settled window justified a short B capture to determine whether the reduced
host churn persisted under workload. No new 40/60-minute run was started.

## Workload B

`../environment-ab-b5m-r1/` uses the unchanged candidate image/schema and original
native scheduler/oracle with the same API/builder CPU/RAM/cpuset limits. The only
intentional environment change is that the two obsolete r4 services are stopped.
Other host activity is not controlled, so this is exploratory A/B rather than a
randomized or otherwise fully controlled experiment.

- Measured 300.001 s, `DIAGNOSTIC-steady=PASSED`, no full acceptance credit.
- All eight timeframes: readiness 30/30, audited probes 5/5.
- 240 measured requests, max request lag 4.226 ms, RSS delta 63,574,016 bytes.
- API/builder B containers stopped after completion.

## Equal-window comparison

`a-first-5m.json` analyzes the first 300 seconds of the prior 40-minute run;
`b-first-5m.json` analyzes the 300-second B run. Both use the same telemetry
analysis and 148 host intervals wholly inside their measured windows.

| Metric | A, first 5 min | B, 5 min |
|---|---:|---:|
| Median host churn MiB/s | 448.5 | 285.2 |
| Max host churn MiB/s | 1,815.9 | 2,509.6 |
| Deduplicated >=40-ms heartbeat-gap events | 13 | 10 |
| Deduplicated >100-ms heartbeat-gap events | 1 | 3 |
| Container CPU throttling | 0 | 0 |

Median churn decreased ~36%, but maximum burst activity increased. B's >100-ms
gaps were 155.4, 133.1 and 134.2 ms, all sampled at outer asyncio runner frames.
Main-thread CPU deltas were 0.76, 0.56 and 8.70 ms. Their host intervals ranked at
the 99.3rd or 100th churn percentile in B. Some gaps share one host interval.

**Conclusion:** removing old containers lowered average activity but did not
produce consistently low host memory churn or eliminate heartbeat gaps. The
association with memory activity persists; causation of the original request
failure is still unproven. Neither run reproduced that request-level failure.
Do not claim a latency fix from the lower average or promote B to acceptance.

## Review/checks and next boundary

The new host-only probe and optional duration slice in the analyzer pass Ruff,
format and Mypy. Timestamp ordering, positive intervals, page size and VM counter
consistency are checked by the data-analysis scripts. No production code,
threshold or financial behavior changed; the existing gate tests need no repeat.

This checkpoint completes the scoped experiment. Another identical run on this
uncontrolled host has no identified value. A stronger experiment requires a
dedicated validation environment or an explicit choice of other host workloads
that may be stopped. Do not close user applications, change global Docker memory,
provision paid infrastructure or trigger long CI workloads without that scope.
The self-hosted-CI closure document was checked: that approach is retired and is
not evidence of an available isolated machine.

No commit, push, merge, production activation or Live order was performed.
Current C1/R2-7 remains available; merged-candidate resource acceptance and
root-cause closure remain Pending.
