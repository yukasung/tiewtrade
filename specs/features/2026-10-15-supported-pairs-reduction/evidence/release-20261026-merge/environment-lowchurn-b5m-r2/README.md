# Low-churn verification r2 — Diagnostic Passed

Completed 300.000 seconds after the harness Redis-window alignment repair.
All eight series passed 30/30 readiness and 5/5 correct probes. Measured requests
240; max lag 4.267 ms, RSS delta 63,250,432 bytes. No barrier timeout or measured
>=40-ms heartbeat gap. `full_validation_credit=false`.

See [host condition, repair and limits](../environment-readiness-r2/README.md).
This is targeted verification, not full release acceptance. Containers stopped
after completion; evidence retained.
