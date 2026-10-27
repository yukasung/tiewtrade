# F-38 host/runtime evidence audit — 2026-10-26

Status: **Read-only audit complete; host memory activity is a supported hypothesis,
not an established root cause.** No new workload run or environment mutation.

## Method

`profile_capacity_host_audit.py` analyzes existing native-diagnostic-40m-r1 data.
It restricts analysis to the measured phase, deduplicates repeated watchdog samples
from the same unchanged heartbeat, maps VM monotonic times to UTC using nearby
scheduling samples, and matches events to surrounding host VM sample intervals.
The generated `summary.json` is reproducible from those raw artifacts.

Host memory churn below means compression plus decompression counter deltas times
page size divided by elapsed seconds. It is a comparison metric, not measured
physical memory bandwidth or unique bytes processed.

## Whole-run comparison

| Metric | Result |
|---|---|
| Host intervals fully within measured phase | 1,190 |
| Deduplicated measured heartbeat-gap events | 120 |
| Intervals with one or more gap events | 102 |
| Other intervals used for comparison | 1,088 |
| Median churn, intervals with gaps | 1,096.5 MiB/s |
| Median churn, comparison intervals | 375.6 MiB/s |
| Ratio of medians | ~2.92 |
| Gap intervals with swap-in activity | 96/102 (~94.1%) |
| Comparison intervals with swap-in activity | 953/1,088 (~87.6%) |
| Cgroup throttled periods/time | zero throughout |
| VM-reported steal-tick delta | zero |

All **10 deduplicated gaps above 100 ms** occurred in host intervals at or above
the **82.4th percentile** of churn in this run. The 306.3-ms event's interval was
at the **99.3rd percentile**. Some events share one host interval; they are not
independent observations. Swap-in activity is frequent in both groups and alone
is a weak discriminator. High churn also occurs without recorded gaps.

The longest gap used ~0.19 ms main-thread CPU and appeared at an outer runtime
frame. Other gaps include higher CPU activity (~110 ms in one event) and a
SQLAlchemy pool-ping frame. Therefore neither pure host starvation nor a single
Python operation explains all observed gaps. The stack sampler cannot resolve
native uvloop waits or prove whether a sampled frame caused the preceding delay.

Zero quota throttling narrows the investigation away from the container CPU quota.
Zero VM steal ticks does not rule out macOS/hypervisor scheduling delays; exposure
of those counters depends on the virtualization stack.

## Current host snapshot (after the measured run)

Read-only commands `sysctl`, `memory_pressure`, `vm_stat`, `docker info` and
`docker stats` showed:

- macOS host RAM **8 GiB**, 8 CPUs;
- Docker VM memory **4,106,604,544 bytes** (~3.825 GiB), 8 CPUs;
- host swap allocated 5,120 MiB, used **4,189.69 MiB**;
- `memory_pressure` reports **43% system-wide memory free percentage**; this is
  not a 43% pressure reading and low immediately-free page count alone is not
  proof of a shortage;
- compressor occupies 187,620 pages (~2.86 GiB) at the sampled instant;
- six active containers include application PG/Redis plus old r4 and r5
  diagnostic PG/Redis stacks. r4 PG/Redis showed about 196.6 MiB combined resident
  usage. These containers were not stopped or deleted by this audit.

Allocated Docker memory, observed resident process memory and compressed/swapped
memory have different accounting; do not add them as if they were disjoint RAM.
The post-run snapshot corroborates memory-management activity, but does not prove
what was happening at the old request failure.

## Conclusion and next bounded experiment

Host memory-management activity correlates with heartbeat gaps in the captured
40-minute run. This supports testing the host/environment hypothesis before
changing indicator serialization, GC or application limits. It does **not** explain
the original API_RESOURCE_LIMIT: that request-level event did not recur, and its
historical logs do not contain these host counters.

The useful next experiment is an A/B capture with the same candidate, fixture,
probe/oracle schedule and 2 CPU / 1 GiB limits, on an environment with demonstrably
lower host memory churn. Record host telemetry for both conditions. Prefer an
isolated validation machine if available; on this machine, reducing unrelated
host activity requires deciding which workloads may be stopped first. Do not
increase Docker RAM automatically on an 8-GiB host or kill user applications.
An uninstrumented acceptance run and full 60-minute criterion remain separate.

No repeat 40-minute run was launched, no host settings were changed, and no
container/application was stopped. No production fix, commit, push or merge was
made. Prior C1/R2-7 evidence remains available; merged-candidate acceptance and
root-cause closure remain Pending.

## Verification

Ruff check, format check and Mypy passed for the standalone analysis script. The
script checks sorted timestamps, positive interval lengths, expected page-size
metadata and nondecreasing VM counters. It does not import or execute the capacity
workload. No regression or timed smoke was necessary for this read-only analysis.
Review confirmed the interpretation separates correlation, measurement limitations
and acceptance status.
