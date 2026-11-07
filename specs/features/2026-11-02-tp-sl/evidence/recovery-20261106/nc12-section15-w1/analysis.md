# NC12 §15 W1 — Incomplete, 2026-11-07

Preflight passed:7 samples, mean CPU idle66.817%, services ready.
Stopped the owned campaign via SIGINT at274.262s after detecting invalid resource
instrumentation; the30-minute measurement was not completed. No performance or
financial acceptance is claimed from this partial run.

Root cause: `profile_workload._run` calls `internal.require_empty_database()` within
the new pool observer scope. That function creates the existing read-only admin
engine. `OwnedPools.register` converts every engine username to `DatabaseRole`,
which excludes the test admin role, recording ValueError. Thus the parent inventory
observed12 application engines but omitted the admin observer engine. The real-DB
ASGI/worker tests did not exercise this complete startup path. This is a harness
defect; passing component tests did not prove complete campaign inventory.

Parent retained ValueError1. All20 workers finalized RETURNED with no observer
errors; registered parent/worker loans returned before disposal. Cleanup verified
0connections/0advisory locks. Candidate and runner hashes unchanged. See raw
campaign-result.json, cleanup.json, preflight.json and run/*.owned-pools.json[l].
No W2/overflow/W3/W4 started and no automatic replacement run. Prior results remain.

Next: proposed§16 explicitly accounts for the existing admin observer pool, tests
actual empty-database startup inside observation, then one replacement W1 only on
owner approval. No production fix or relaxation of pool-return conditions proposed.
