# REPLAY-03 criterion review — 2026-11-17

สถานะ: **Incomplete — Docker unavailable before fixture creation**

## Evidence review

CUT01 completed14400s/28200commands but the first-owner replay exhausted60s in
read_execution_inputs. Its receipt recorded33queries/111161rows and60.523s including
cancellation cleanup. Publichead was144364; no full per-owner read completed.
Prior REBUILD20-04 Passed20fullreplays at96000records/owner,34.085–42.024s each.
These volumes differ materially. Scaling those times linearly is only a hypothesis:
query plans, payloads, concurrency and host conditions can change with size.

The60s bound includes position/cash rebuild, complete validated evidence enumeration,
checkpoint read and session lifecycle. It is distinct from live processing latency,
but remains an approved acceptance criterion. Neither repeated failure nor completed
command counts justify waiving financial checks or extending it without evidence.

## Attempt

Reused reviewed/corrected REPLAY01 runner with144364syntheticrecords,original4096page
limit/60s timeout,secondownerRLSnegative and unchanged production SQL/decoder.
Pinned candidate/config/runner,exact old helper hash and copied helper. No production
or shared harness code changed. Source binding remained unchanged.

One preflight stopped at initial service check: Docker daemon socket unavailable;
docker inspect failed. No readiness samples, database fixture, seed, enumeration,
EXPLAIN or trading commands ran. No database-created receipt exists. No Redis was
created by this scope. No cleanup required for resources never created; no assertion
about unrelated databases/services is made. Raw result retained:
validation-artifacts/f17-replay03-20261117/.

## Conclusion / next

Not enough new evidence to change60s. Recommend first completing the same bounded
reader diagnosis after Docker is available, then choosing query/decoder work versus
an explicit owner-approved time-budget amendment. Preserve all correctness checks,
full evidence coverage and original Failed/Incomplete grades. No4h repeat now.
No retry/start of other services,sourceoptimization,commit/push/CI/merge performed.
