# F-38 merged-candidate dirty/recovery checkpoint — 2026-10-26/27

Status: **R2-C3 PASSED + R2-C5-dirty PASSED.**
The two combined 60-minute measured phases are now complete for this candidate.
Fairness/aggregate and final release checks remain Pending.

## Provenance and prerequisite reuse

- Production revision `12bf6328b1d927115c8ac095285a3aeedb53dcb3`; immutable API/
  builder image `sha256:6cacc3bc9d9df1ce8b0fb31374fd89e489f2ffa264466d7f6a9372b6ceeb1210`.
- Isolated r5 stack, schema 0042, PG 55484 / Redis 56434.
- API 2 CPU / 1 GiB / cpuset 6–7; builder 2 CPU / 1 GiB / cpuset 4–5;
  infra cpuset 0–3. Normal acceptance API entrypoint, not diagnostic watchdog.
- Prerequisites reused: `../c1-r5/` and `../combined-steady-r7/`, both Passed.
- Only post-steady harness adjustment allows an expected post-admission
  `INDICATOR_DATA_NOT_READY` 503 to wait for barrier completion. This preserves
  accepted-200 behavior and rejection handling. All accepted steady probes were
  200, so that evidence remains applicable. No production/threshold/limit change.
- r1 was stopped during preflight before dirty burst/T0 when that harness issue
  was found; preserve its partial evidence. Targeted regression/boundary checks
  after the fix: **78 passed**, Ruff/format/Mypy passed.
- Host preflight (`../../acceptance-dirty-preflight/host.json`): median churn
  56.214 MiB/s, max 440.190 MiB/s; swap-in +8 pages, swap-out +0.

## Measured results

- T0 `2026-10-26 16:31:05.002933+00:00`; completion after midnight Bangkok,
  2026-10-27. Measured **3,600.001577 seconds**, failure null.
- `R2-C3=PASSED`, `R2-C5-dirty=PASSED`, `diagnostic=false`,
  `full_validation_credit=true`.
- Dirty burst invalidated the old prepared proof before recovery observation.
  Readiness initially 0/8; all workload series recovered by **60.075708 seconds**,
  within the unchanged 600-second deadline.
- Per-series valid observations: BTC/1m and 5m **355/360**; other six timeframes
  **354/360**. All post-recovery readiness remained valid, and every series passed
  the approved dirty-phase threshold.
- Every timeframe: correct probes **59/60**; the first dirty-period probe was
  unavailable as expected, followed by correct GET 200 after recovery.
- **2,880** measured request records: accepted-kind **480** (including initial
  dirty-period unavailable responses), BUSY 503 **1,200**, RATE 429 **1,200**.
  Expected rejection details and zero candle-query coverage passed in the harness.
- Maximum API lag **53.816 ms** <=100 ms; RSS delta **62,418,944 bytes**
  (~59.5 MiB) <=128 MiB.
- **64** distinct oracle references, all true, linked from accepted probe records.
- **124** worker attempt records; maximum acquisition/attempt/cleanup **41.093 s**
  <=120 s; max incremental RSS **1,486,848 bytes** <=128 MiB.

## Pinned harness and external telemetry

Before/after SHA-256 values match:

| File in backend/tests/services/indicator_builder | SHA-256 |
|---|---|
| profile_capacity.py | bb8c53de1e4a6be00030096f433016ddda350c7b43fdd6a8d0c0818ac22424a3 |
| profile_capacity_steady.py | dec2c3ba6c7744a1ad3b32dcf3c56d0a08c14663e729b2fadc1ef25d278dfce0 |
| profile_capacity_app.py | d986f2d2ef1ebd3d696329a2d6ba7948b952e5aaf46662145eed3022e1133105 |
| profile_capacity_acceptance_telemetry.py | 756016dd7694735f144f87884e4073b69803d9dfa41b6650a93245389008aca8 |

External read-only telemetry is in `../../combined-dirty-r2-telemetry/`: **737**
valid VM samples, observed cgroup throttled periods zero. This includes preparation
and cleanup; acceptance calculations use the measured raw slice in this directory.
No diagnostic heartbeat/watchdog was installed in the acceptance API process.

## Checkpoint handoff

Merged-candidate C2/C5-steady and C3/C5-dirty now Passed, totaling two full measured
hours. Do not repeat these phases merely because work resumes or documentation is
updated. Current C1/R2-7 remains available.

Remaining: affected fairness/S5 evidence, raw aggregate C4/C6 and final review/
required CI/document crosswalk. This checkpoint does not declare current HEAD
Completed or ready to merge. Historical Failed/Partial results remain preserved;
these successes do not prove the precise cause of older intermittent failures.

API, builder and external collector stopped after completion. DB/Redis and all
artifacts remain. No production source/migration/lock change, full regression,
new long run, commit, push, merge, production activation or Live order was made.
