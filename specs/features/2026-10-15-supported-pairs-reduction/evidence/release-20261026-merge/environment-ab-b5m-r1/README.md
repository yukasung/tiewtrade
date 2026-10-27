# Host-load B workload — 2026-10-26

Status: **Diagnostic Passed, not acceptance evidence.**

The original native harness measured 300.001 seconds after obsolete F-38 r4
PostgreSQL/Redis services were stopped. Same candidate image, schema and API/
builder resource limits as A. All eight timeframes passed 30/30 readiness and
5/5 audited probes; 240 request metrics, max lag 4.226 ms, RSS delta 63,574,016
bytes. `full_validation_credit=false`.

Host churn bursts and three >100-ms heartbeat gaps persisted despite lower
median churn. See [comparison and limitations](../environment-ab/README.md).
The original request-level API_RESOURCE_LIMIT did not recur and no root cause
or production fix is established. Runtime containers stopped after completion.
