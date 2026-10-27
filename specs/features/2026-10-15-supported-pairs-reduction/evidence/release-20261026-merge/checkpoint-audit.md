# F-38 merged candidate checkpoint audit — 2026-10-26

Status: **Merged-candidate capacity/fairness C1–C6 and S1–S5 Passed; local review
and crosswalk complete; final candidate CI Pending.**

Current handoff: [final crosswalk](README.md). Older next-step/pending statements
below are historical audit snapshots, superseded by this handoff.

Latest [fairness/aggregate checkpoint](fairness-aggregate-checkpoint.md): 31
targeted S1–S4 tests Passed on fresh schema 0042; fresh same-image S5 Passed all
eight workload series with original deadlines preserved. Raw C4/C6 evaluator
Passed 57/57 checks, no failures. Current C1/steady/dirty evidence was reused,
not rerun. No commit/push/merge or current-HEAD Completed claim was made.

Latest [dirty/recovery checkpoint](capacity/combined-dirty-r2/README.md) completed
3,600.001577 s: C3/C5-dirty Passed, all-series recovery 60.075708 s, correct probes
59/60 per timeframe, max API lag 53.816 ms and RSS 59.5 MiB. Targeted preflight
fix permits the expected post-admission recovery 503; steady's accepted-200 path
is unchanged and its evidence remains valid. Both 60-minute phases now Passed;
no fairness/aggregate or other release run started automatically.

Latest [combined steady checkpoint](capacity/combined-steady-r7/README.md): normal
acceptance entrypoint completed 3,600.000492 s, C2/C5-steady Passed, readiness
360/360 and correct probes 60/60 per BTC timeframe. Max API lag 73.586 ms, RSS
59.7 MiB. Before/after harness hashes match. C1/R2-7 reused; dirty/recovery,
fairness/aggregate provenance and final review/CI remain Pending. No subsequent
long run started automatically. Historical diagnosis notes below are preserved.

Latest [quiet-host checkpoint](environment-readiness-r2/README.md): substantially
lower host churn observed. First short attempt diagnosed a Redis-window harness
race (expected rejected probes consumed the next window); aligned pre-T0 start
and fail-fast barrier handling repaired it. 76 targeted tests passed; subsequent
300-second diagnostic passed with 4.267-ms max request lag and no measured
>=40-ms heartbeat gap. No acceptance credit; original lag causation not proven.

Latest [host-load A/B](environment-ab/README.md): stopped obsolete r4 PG/Redis
recoverably and completed a 5-minute B diagnostic. Median host churn fell ~36%
in equal measured windows, but bursts and >100-ms heartbeat gaps persisted.
No original request failure reproduced and no root cause established. A stronger
experiment needs an isolated environment or explicit scope for other host loads.

Follow-up [host/runtime audit](host-runtime-audit/README.md) compares 1,190 host
sample intervals: median compression/decompression churn in gap intervals is
~2.92 times that in comparison intervals. All 10 deduplicated >100-ms heartbeat
events occurred above the 82.4th churn percentile. This supports an environment
A/B hypothesis, not causation of the original request failure. No new workload or
environment mutation was performed; root cause/acceptance remain Pending.

Latest: [authorized 40-minute diagnostic](native-diagnostic-40m-r1/README.md)
completed 2,400.001 s with 240/240 observations and 40/40 correct probes per
timeframe. Max request lag 57.517 ms, throttling zero; no original request failure
reproduced. A 306-ms heartbeat gap outside a measured request had little main-thread
CPU and nearby host memory activity; causation remains unproven. No acceptance credit.

Latest checkpoint: [native harness diagnostic](native-diagnostic-r1/README.md)
completed the original oracle/probe scheduling for 300 s. All eight series passed
30/30 observations and 5/5 correct probes; measured request lag max 4.493 ms,
throttling zero. No historical spike reproduced; no full acceptance credit.

Latest follow-up: [diagnostic r3 checkpoint](diagnostic-r3/README.md) completed
producer/observer/parity investigation with corrected uvloop instrumentation.
Accepted/parity 24/24; max indicator lag 24.850 ms; historical spike not reproduced.
R1/r2 callback coverage was invalid and their READMEs now state the limitation.

Follow-up: the authorized bounded diagnostic is complete; see
[`diagnostic-r1/README.md`](diagnostic-r1/README.md). It did not reproduce the lag
spike and does not close capacity acceptance. Root cause remains unresolved.

No additional tests were started for this audit. No commit or push was made.
User instructed reuse of valid evidence, diagnosis before further long runs, and
checkpoint delivery without expanding to all release work.

## Candidate comparison

- Previously validated candidate: `bfb6ab0`; measured image and source AST mapping
  are recorded in `../release-20261024/README.md` and its `provenance/` directory.
- Current candidate: `12bf632`; measured image
  `sha256:6cacc3bc9d9df1ce8b0fb31374fd89e489f2ffa264466d7f6a9372b6ceeb1210`.
- Current production source equals `aae5079` (`git diff --quiet aae5079 HEAD --
  backend/src` succeeds). The experimental encoding offload was reverted.
- Comparison is against the validated source, not merely the merge commit.
- `uv.lock` is unchanged. The pyproject change adds a CLI entry point, not a
  dependency version. Runtime image identity differs; do not infer runtime equality
  from lockfile equality alone.
- Indicator read now calls `require_active_pair`. API lifespan adds catalog-related
  imports/routes/capability source and an environment-gated heartbeat.
- Indicator publication now queries runtime catalog and conditionally records
  timeframe readiness. Builder/supervisor also gained protocol heartbeat support.
- Migration 0039 changes publication checkpoint SQL. Migration 0040 adds catalog
  behavior; 0041–0042 add manual-order infrastructure. Current schema is 0042,
  whereas original capacity evidence used 0038.
- Core indicator calculations, prepared reader and chunked response serializer
  have no source diff in the comparison. Their unchanged behavior remains useful
  evidence, but does not establish integrated resource acceptance after the above
  dependency changes.

## Evidence disposition

| Evidence | Disposition and reason |
|---|---|
| Original completed release run | Preserve its Passed result for its candidate/environment; it is historical evidence, not blanket approval of the merged candidate. |
| Original calculation/parity and migration-0030 restore drill | Retain for the behavior actually measured. No reason to repeat solely because HEAD changed; current-schema restore coverage remains a separate impact decision. |
| Current C1 r5 and R2-7 | Passed on current image/schema: readiness 16/16; exact cold/warm lag max 45.933 ms, RSS delta max 4,321,280 bytes. No new source change invalidates these results. |
| Current API regression/static checks | Prior checkpoint recorded 44 API tests passed, Ruff/format/Mypy passed on restored source. Reuse; this audit did not rerun them. |
| Smoke steady r1 | Passed 300 s, max lag 31.193 ms; useful bounded evidence only, with `full_validation_credit=false`. It does not cover full combined acceptance. |
| Combined steady r1/r2/r3 | Failed `API_RESOURCE_LIMIT`; preserve failures and raw metrics. r1 is Failed, not merely interrupted/partial as previously described. |
| Combined steady r4/r5/r6 | Interrupted runs do not close a gate. r6 was stopped during this audit before completion. Raw metrics also contain a 117.101 ms violation. |
| Merged candidate steady/dirty, fairness and aggregate | Pending affected acceptance. Read/publication/catalog and schema changes require impact-specific validation; do not rerun every unrelated gate. Diagnose lag before another long run. |

## API_RESOURCE_LIMIT diagnosis from existing logs

The evaluator fails if any measured request exceeds 100 ms event-loop lag or
128 MiB RSS delta (`profile_capacity_steady.py`, `resource_failure`). Existing
violations are lag violations, with RSS below the limit:

| Attempt | Evidence |
|---|---|
| r1 | Rejected BUSY 503: 114.292 ms lag, zero candle queries and zero recorded GC; accepted 200: 115.698 ms lag, GC pause 0.330 ms. |
| r2 | Accepted 200: 126.789 / 139.110 ms lag; RSS 59,228,160 bytes; GC pauses 0.871 / 2.705 ms. |
| r3 (encoding offload) | Accepted 200: 217.099 ms lag; RSS 61,976,576 bytes; GC pause 0.650 ms. Reverted; this run does not isolate causation. |
| r6 (infra pinned) | Raw `metrics-r5/api-metrics.jsonl` includes accepted 200 at `2026-10-26 10:54:01.267611+00:00`: 117.101 ms lag, RSS 63,184,896 bytes. |

These observations do **not** establish CPU contention, encoding, or GC as the
root cause. CPU isolation did not eliminate the issue. The monitor measures
wall-clock wakeup delay of a coroutine, including scheduler delay; it cannot
separate loop-blocking code from container throttling/host scheduling. GC counters
are request-context scoped, so they do not exclude every process-wide cause.
Historical logs lack correlated stack/phase timing and cgroup CPU throttling data.

## Necessary next step and remaining release work

Before another long run, use a bounded diagnostic on the same immutable image:
correlate event-loop gaps with request phase timings, cgroup `cpu.stat` deltas and
process/host scheduling. Reuse the existing accepted and rejected probe helpers;
no threshold change. Instrumentation must remain diagnostic and must not be used
as acceptance evidence. This audit does not start that diagnostic or a new run.

After identifying the cause, select targeted checks for the actual fix/environment
change. Announce any necessary long run, the specific criterion it proves, why
short/historical evidence cannot close it, and expected duration before starting.
Combined steady and dirty acceptance each require 60 minutes if still necessary;
do not launch them while the cause remains unknown.

Release remains Pending for the merged candidate: affected capacity/resource
acceptance, applicable fairness/aggregate provenance and final required CI/review.
The prior roadmap Completed entry refers to `bfb6ab0`; this checkpoint does not
assert that current HEAD is Completed or ready to merge. No production activation
or Live order is authorized by these results.
