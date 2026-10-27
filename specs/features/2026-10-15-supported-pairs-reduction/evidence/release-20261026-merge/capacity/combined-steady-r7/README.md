# F-38 merged-candidate combined steady checkpoint — 2026-10-26

Status: **R2-C2 PASSED + R2-C5-steady PASSED.**
This checkpoint does not close all F-38 merged-candidate release validation.

## Scope and provenance

Owner instructed this 60-minute acceptance run after the quiet-host check and
targeted Redis-window harness repair. This is the normal acceptance entrypoint
`profile_capacity_app:app`, not the diagnostic heartbeat/watchdog wrapper.

- Production revision `12bf6328b1d927115c8ac095285a3aeedb53dcb3`.
- API and builder image:
  `sha256:6cacc3bc9d9df1ce8b0fb31374fd89e489f2ffa264466d7f6a9372b6ceeb1210`.
- Prefix `tiewtrade-f38-merge-r5-20261026`; PG 55484, Redis 56434; schema 0042.
- API 2 CPU / 1 GiB / cpuset 6–7; builder 2 CPU / 1 GiB / cpuset 4–5;
  infra cpuset 0–3. Obsolete r4 services remain stopped.
- C1/R2-7 reused from `../c1-r5/`: same production image/schema, no affected
  production/dependency change since those results. New harness changes affect
  steady-phase start alignment and the rejected-load barrier, not C1/R2-7.
- Preflight host-only 30-second observation in `../../acceptance-steady-preflight/`:
  median churn 30.083 MiB/s, max 345.577 MiB/s, swap-in +4 pages, swap-out +0.

Harness SHA-256 values recorded before measurement and verified unchanged after:

| File in backend/tests/services/indicator_builder | SHA-256 |
|---|---|
| profile_capacity.py | ff4feaa29950ff42c10521aeef56964323363b0153d00deb97084aa473867716 |
| profile_capacity_steady.py | dec2c3ba6c7744a1ad3b32dcf3c56d0a08c14663e729b2fadc1ef25d278dfce0 |
| profile_capacity_app.py | d986f2d2ef1ebd3d696329a2d6ba7948b952e5aaf46662145eed3022e1133105 |
| profile_capacity_acceptance_telemetry.py | 756016dd7694735f144f87884e4073b69803d9dfa41b6650a93245389008aca8 |

## Results

- T0 `2026-10-26 15:22:05.002819+00:00`.
- Measured **3,600.000492 seconds**, failure null.
- `R2-C2=PASSED`, `R2-C5-steady=PASSED`, `diagnostic=false`,
  `full_validation_credit=true`.
- BTC workload covers all eight timeframes. Every series: valid readiness
  **360/360**, correct accepted probes **60/60**; no missing scheduled samples.
- **2,880** measured request records: accepted **480**, BUSY 503 **1,200**,
  RATE 429 **1,200**. Rejection detail/status/query coverage passed in the harness.
- Maximum API event-loop lag **73.586 ms** <=100 ms.
- Maximum API RSS delta **62,627,840 bytes** (~59.7 MiB) <=128 MiB.
- **64** distinct oracle references, all true; reused references remain linked
  from every accepted probe.
- **118** worker attempt records; longest attempt including acquisition/cleanup
  **42.462 s** <=120 s, max incremental RSS **1,073,152 bytes** <=128 MiB.

Runtime readiness/bootstrap 16-series evidence remains in C1-r5. This steady
acceptance is BTC-only workload 8 series under the approved scope; it does not
upgrade ETH workload acceptance or another feature's pending gates.

## External telemetry and cleanup

`../../combined-steady-r7-telemetry/` contains read-only host `vm_stat` and
container/VM CPU/scheduling snapshots every 5 seconds. **763** samples have valid
VM reads; maximum observed `nr_throttled` is zero. Collector span includes
preparation and cleanup, so request acceptance uses only the harness's measured
slice in this directory.

The external collector did not replace the API entrypoint or install a heartbeat
task/watchdog in the API. Its own process/exec overhead was present during this
run; limits were not increased. It emits no separate acceptance gate.
Collector, API and builder stopped after completion; database/Redis and evidence
remain. No production source, migration or dependency-lock change occurred during
measurement. No commit, push, merge, production activation or Live order occurred.

## Checkpoint handoff

This closes only merged-candidate **C2 and C5-steady**. Do not rerun this passing
phase solely because work resumes or documentation changes.

Remaining release work: combined dirty/recovery C3+C5-dirty (60 minutes when
started), affected fairness/S5 and aggregate C4/C6 provenance, and applicable final
review/required CI/document crosswalk. Current C1/R2-7 remains available. No dirty,
fairness or full-regression run was started automatically at this checkpoint.

Historical resource failures, partial runs and diagnostic-only successes remain
preserved. This pass is not proof of the exact cause of earlier intermittent
failures and does not justify changing thresholds or declaring current HEAD
Completed before the remaining validation is closed.
