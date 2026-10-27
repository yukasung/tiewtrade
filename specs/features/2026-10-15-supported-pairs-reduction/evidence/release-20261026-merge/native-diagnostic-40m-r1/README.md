# F-38 authorized 40-minute native diagnostic — 2026-10-26

Status: **Diagnostic Passed; original request-level failure not reproduced.**
Resource acceptance and historical root cause remain Pending.

## Authorization and scope

Owner explicitly requested the proposed 40-minute capture after the short native
diagnostic failed to reproduce an event historically observed after ~32 minutes.
The diagnostic-only duration bound was extended to 2,400 seconds; default
acceptance remains 3,600 seconds. No production source, schema, dependency lock,
resource limit or acceptance threshold changed.

Same candidate image as C1-r5, production revision `12bf632`, schema 0042;
isolated r5 PostgreSQL/Redis, API cpuset 6–7, builder 4–5, 2 CPU / 1 GiB each,
infra cpuset 0–3. Uses the original steady harness source producer, observer,
loaded probes and independent parity oracle queue. API telemetry is diagnostic
instrumentation and can itself affect timing; this run grants no acceptance credit.

## Measured results

- Measured **2,400.001 seconds**. `DIAGNOSTIC-steady=PASSED`, failure null,
  `diagnostic=true`, `full_validation_credit=false`.
- Every one of eight BTC timeframes: readiness **240/240**, audited probes
  **40/40**, no envelope/parity failure.
- **1,920** measured requests: accepted **320**, BUSY 503 **800**, RATE 429 **800**.
  Rejected error contracts and zero candle-query checks passed in the harness.
- Maximum measured request lag **57.517 ms**, RSS delta **64,167,936 bytes**
  (~61.2 MiB). Highest request lag was accepted HTTP 200 at
  `2026-10-26 13:11:43.193888+00:00`.
- VM/container telemetry: **2,569** samples, cgroup throttled periods/time zero.
- Measurement T0: `2026-10-26 13:02:41.465340+00:00`.
- Original API_RESOURCE_LIMIT was not reproduced, including after 32 minutes.
  This does not invalidate previous failures or prove 60-minute acceptance.

## New observation: gaps outside measured requests

The watchdog captured 181 heartbeat-gap samples across setup and measurement.
During the measurement there was a **306.263-ms** gap at VM monotonic
`7231.667298621`, between UTC scheduling samples `13:29:48.866272` and
`13:29:49.914502`. Main-thread CPU increased only **0.1925 ms**, process CPU
~26.78 ms, and the sampled Python stack was at the outer asyncio runner.
These are heartbeat observations, not request-level acceptance failures.

Nearby PID-1 schedstat samples show ~68.62 ms additional runqueue wait over that
approximately 1.05-second sampling interval, with no cgroup quota throttling.
This does not account for the entire 306-ms gap or identify the native operation.

Host `vm_stat` snapshots from `13:29:48.230070` to `13:29:50.240563` show:

- compression counter +116,368 pages;
- decompression counter +127,216 pages;
- swap-in counter +187 pages; swap-out counter unchanged;
- reported page size 16,384 bytes.

**Inference only:** the gap has little main-thread CPU activity and coincides
with host memory-management activity. Host/VM scheduling or a native-runtime wait
is worth isolating before changing Python computation/serialization. These coarse
snapshots cannot prove the cause of this gap, much less the earlier request spike.
Do not claim that memory pressure, GC, encoding or CPU pinning is the root cause.

## Evidence and checks

- `phase/result.json`, `api-metrics.json`, `probes.json`, `rejected.json`,
  `oracle.json`, metadata and worker attempts: original harness evidence.
- `metrics/diagnostic-callbacks.jsonl`: heartbeat/CPU/stack observations.
- `metrics/diagnostic-scheduling.jsonl`: UTC/monotonic VM scheduling counters.
- `host-vm-stat.jsonl`: UTC/monotonic host VM snapshots.
- Targeted smoke/scope/gate tests **69 passed** after the diagnostic bound change;
  Ruff/format/Mypy passed. Default acceptance still requires its original duration;
  diagnostic output cannot satisfy combined/dirty acceptance prerequisites.

## Checkpoint decision and pending work

The authorized 40-minute diagnostic is complete. No production fix is justified
by this evidence. Do not run another identical timed diagnostic automatically.
If investigating further, first isolate host/runtime waiting with a concrete
environment hypothesis and an appropriate targeted diagnostic; announce the
purpose/duration before any new long measurement.

Current C1/R2-7 and prior targeted checks remain usable. Merged-candidate full
resource acceptance, affected fairness/aggregate provenance and final required
CI/review remain Pending. The 40-minute run is not upgraded to acceptance, and no
current-HEAD Completed claim is made.

API/builder containers stopped after completion. Isolated databases and all
Failed/Partial/diagnostic artifacts remain. No commit, push, merge, production
activation or Live order was made.
