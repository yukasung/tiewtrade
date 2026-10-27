# Bounded API lag diagnostic — 2026-10-26

Status: **Diagnostic complete; root cause not reproduced / unresolved.**

Correction from follow-up review: the image uses uvloop; the initial
`asyncio.Handle._run` hook does not instrument uvloop callbacks. Callback/stack
coverage in r1 is invalid. Request metrics, response statuses and cgroup counters
remain useful; absence of callback events is not evidence of short callbacks.
The wrapper was subsequently replaced with a loop-independent heartbeat/watchdog
and self-checked on uvloop before diagnostic r3.

This is diagnostic evidence only and closes no acceptance gate. Candidate
production source remains `12bf632`; no production code, threshold or resource
limit was changed. The API was cloned from the C1-r5 container's image and
environment, with separate output and the diagnostic entrypoint.

## Method

- Reuse `profile_capacity_steady.login`, `loaded_probes`, and normal source
  append/readiness helpers on the isolated r5 database.
- Three probe rounds, at least 61 seconds apart, bounded by a 240-second runner.
- API remains 2 CPUs, cpuset 6–7, 1 GiB; infra cpuset 0–3; schema 0042.
- Record cgroup `cpu.stat` before/after each round, callback wall/thread/process
  CPU time above 40 ms, and stack locations when a callback remains active.
- Stack records contain filenames, line numbers and function names only; no
  locals, credentials, tokens or response bodies are saved by the new runner.
- Diagnostic API and builder stopped after completion. DB/Redis and all evidence
  remain available. No commit or push was performed.

## Observations

- `diagnostic-result.json`: runner completed all three rounds without timeout.
- `api-metrics.jsonl`: 144 requests; maximum recorded loop lag
  0.027426833 seconds, no request above the 0.1-second acceptance threshold.
- Accepted probes: 22/24 returned 200. Round 1 and round 3 returned 200 for all
  eight timeframes. Round 2 returned 503 for BTC/5m and BTC/15m.
- The runner did not retain error details for those two responses. Their cause
  cannot be attributed to freshness, capacity or a specific failure from this
  artifact. Do not claim 24/24 successful accepted probes or correctness parity.
- All three rounds had 20 BUSY and 20 RATE requests using the existing helper;
  raw response details remain in `diagnostic-result.json`.
- `nr_throttled` and `throttled_usec` remained zero before/after every round.
  Before this run, the original r5 API container also reported both counters zero
  over its lifetime, including the r6 spike. Container quota throttling therefore
  has no supporting evidence for that spike. Host/VM scheduling is not excluded.
- No callback artifact was emitted. The follow-up correction above means this
  cannot establish whether callbacks reached 40 ms.

## Review and verification

Ruff check, Ruff format check and Mypy (`MYPYPATH=src`) passed on both diagnostic
scripts. The actual run exercised authentication, the barrier, accepted/rejected
probes, cgroup collection, result serialization and runtime cleanup. No full
regression, new timed smoke or long acceptance run was started.

Review: production/default acceptance entrypoints do not import the diagnostic
wrapper. Instrumentation is opt-in through the distinct Uvicorn entrypoint;
results explicitly carry `diagnostic_only=true`. The new callback hook and
watchdog change process timing, so these results must not be promoted to
acceptance evidence. A 3-round sample cannot disprove an intermittent event
previously observed after 1,930 seconds.

## Checkpoint and next work

The root cause remains **Pending**. The short run narrows the evidence: no
container CPU throttling, no reproduced slow callback, and insufficient data to
choose a production fix. Do not alter serialization, GC, resource limits or
thresholds based on this run.

For the next diagnostic, retain non-200 error codes and refresh metadata, and
maintain source continuity using the existing producer throughout probes. To
capture an intermittent spike, collect a bounded diagnostic on the original
capacity topology including source producer, observer and parity audit activity;
this reduced run does not reproduce all competing activity from the full harness.
Preserve the same limits and correlate a reproduced event with stack/CPU/host
scheduling before selecting a fix. Any longer measurement must be explained and
scoped before launch.

Current C1/R2-7 and the prior targeted checks remain valid. Merged-candidate
steady/dirty capacity, applicable fairness/aggregate provenance and final CI/review
remain Pending as listed in `../checkpoint-audit.md`. This is the checkpoint
delivery, not a claim that current HEAD is Completed or ready to merge.
