# F-38 native-harness diagnostic checkpoint — 2026-10-26

Status: **Diagnostic Passed; historical API_RESOURCE_LIMIT cause unresolved.**
Acceptance remains Pending. `full_validation_credit=false`.

## What this closes

Earlier reduced diagnostics awaited each parity audit before scheduling another
probe. This run calls the original `profile_capacity_steady.run` with its normal
source producer, 10-second observer/snapshots, 60-second loaded probes and
independently queued/deduplicated parity oracle. Only an explicit diagnostic
duration/label and opt-in telemetry were added. The acceptance mode still uses
3,600 seconds; no limits or thresholds were increased.

API and builder were cloned from C1-r5 image/config on the isolated r5 network:
image `sha256:6cacc3bc9d9df1ce8b0fb31374fd89e489f2ffa264466d7f6a9372b6ceeb1210`,
production source `12bf632`, schema 0042. API cpuset 6–7, builder 4–5, each 2 CPU /
1 GiB, infra cpuset 0–3. Both diagnostic runtime containers are now stopped.

## Results

- Preparation, 300-second measurement and audit/cleanup completed successfully
  within the runner's 720-second bound; telemetry spans about 8 minutes total.
- `phase/result.json`: `DIAGNOSTIC-steady=PASSED`, measured 300.001 s, failure null,
  `diagnostic=true`, `full_validation_credit=false`.
- Every BTC timeframe: readiness observations **30/30**, correct probes **5/5**.
- Measured accepted requests **40**, BUSY 503 **100**, RATE 429 **100**; total **240**.
- Max measured request lag **4.493 ms**, max RSS delta **64,057,344 bytes**.
- Raw metrics including preparation had a higher lag (~30.4 ms); preparation
  metrics are not substituted for the measured-phase slice.
- Cgroup throttled periods/time remained zero throughout collected telemetry.
- Watchdog captured 71 gap samples across setup and measurement. The largest
  275.817-ms sample is Argon2 password verification during login before T0.
- Measured phase T0: `2026-10-26 12:41:47.159265+00:00`. Gap records during that
  interval have outer asyncio-runner frames and are below 100 ms (largest captured
  about 83.2 ms). They did not coincide with an indicator request violation.
  Outer runner frames cannot identify a C-level callback; do not attribute them
  to a specific application operation.
- 489 VM scheduling samples: cgroup CPU counters, CPU pressure, PID-1 schedstat
  and VM aggregate CPU counters; 245 host `vm_stat` snapshots with UTC/monotonic
  timestamps. No causal link to the historical spike can be established without
  reproducing that spike.

## Evidence map

- `phase/`: original harness observations, oracle references, probes/rejections,
  worker attempts, metadata and diagnostic-only result.
- `metrics/diagnostic-callbacks.jsonl`: uvloop heartbeat/watchdog stack locations.
- `metrics/diagnostic-scheduling.jsonl`: Linux VM/container scheduling telemetry.
- `host-vm-stat.jsonl`: macOS VM counters; not proof that host scheduling never
  delayed the Docker VM.

## Review and checks

Changed only diagnostic scripts, optional diagnostic branch in the harness and
its boundary tests. Targeted smoke/scope/gate checks: **68 passed**. Ruff check,
format and Mypy passed for all four affected Python files.

Review confirmed: default smoke/acceptance selection is unchanged; explicit
diagnostic mode rejects incompatible modes and durations beyond 60–300 seconds;
the output cannot unlock full dirty/combined prerequisites. The runner uses a
separate API entrypoint and containers. Stack records contain locations without
frame locals; response bodies/cursor tokens and environment credentials are not
persisted by the added diagnostic code.

Instrumentation can affect timing. This success neither explains the old failure
nor proves 60-minute stability. No production fix is justified; do not repeat an
identical short run merely to accumulate Passed attempts.

## Remaining work

Current C1/R2-7 evidence and targeted checks remain available. Root cause,
merged-candidate full resource acceptance, affected fairness/aggregate provenance
and required final CI/review remain Pending. A future longer capture may be needed
for this intermittent event (historically seen after ~32 minutes), but its scope,
purpose and duration must be announced before launch. No such run was started.

No production source/migration/lock/threshold change, commit, push, merge or Live
order was made. This checkpoint completes the requested native diagnostic work,
not F-38 acceptance for current HEAD.
