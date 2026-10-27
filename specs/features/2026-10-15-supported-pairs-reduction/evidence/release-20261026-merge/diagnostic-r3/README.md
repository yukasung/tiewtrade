# F-38 diagnostic checkpoint r3 — 2026-10-26

Status: **Bounded diagnostic complete; historical API lag root cause Pending.**

## Instrumentation correction

The initial r1/r2 callback hook targeted asyncio internals, but the image runs
uvloop. Their request/cgroup evidence remains available; absence of callback
records cannot rule out long callbacks. Both attempt READMEs now state this
limitation. Historical Failed gates remain unchanged.

R3 uses a 5-ms loop heartbeat and a separate 10-ms thread watchdog, recording
stack locations and main-thread/process CPU deltas for heartbeat gaps >=40 ms.
It does not replace the event loop. The artifact confirms `uvloop.Loop`.

A disposable process using the same image, uvloop and resource limits verified:
async idle produces no gap; blocking sleep produces a gap with low main-thread
CPU; a busy loop produces a gap with high main-thread CPU. All assertions passed
before the application run. Artificial stalls were never injected into the app.

## Scope and results

- Unchanged production candidate `12bf632`, image cloned from C1-r5, schema 0042.
  API cpuset 6–7 / 2 CPU / 1 GiB; infra cpuset 0–3.
- Reused normal source producer, observer/snapshots, loaded probes and parity
  audit. Three rounds completed within 360 seconds without timeout/failure.
- 144 request records; max indicator lag **24.850 ms**, RSS delta max
  **66,981,888 bytes**. No indicator resource violation.
- Accepted HTTP 200 plus exact parity: **24/24**.
- Rejected BUSY 503 and RATE 429 with expected details: **60 each**.
- 19 readiness/metadata snapshots. Each full parity audit took about 60–61 s.
  Audits are awaited per round here; this differs from the full harness's
  independently queued oracle and is not a full topology equivalence claim.
- Cgroup throttled periods/time remained **zero** in every before/after pair.
- Watchdog captured 43 gap samples, all with top frame
  `argon2.low_level.verify_secret`, during the five fixture logins before probes.
  Largest startup gap: 132.196 ms. This verifies stack capture; it does not
  attribute the historical indicator-period spike to login.
- No indicator-period >=40-ms heartbeat gap was captured. Sampling/watchdog
  scheduling has finite resolution; absence is not a bound on every callback.

## Checkpoint decision

No production fix is justified. The historical spike was not reproduced; quota
throttling, GC or encoding must not be declared its cause. CPU pinning remains an
unproven remedy (r6 already exceeded 100 ms while pinned). Current C1/R2-7 and
targeted API/static evidence remain usable.

Another identical short run has no identified additional value. The next
investigation must target the remaining mismatch: full harness scheduling with
independently queued audits and correlated host/VM scheduling evidence. Explain
any longer measurement before launch. Merged-candidate resource acceptance and
dependent aggregate remain Pending; this checkpoint does not assert Completed.

## Review and cleanup

Both diagnostic scripts pass Ruff check/format and Mypy (`MYPYPATH=src`). Review
found and corrected the uvloop mismatch; startup capture and controlled self-check
verify the replacement. Instrumentation is opt-in through a separate entrypoint,
records frame locations without locals/secrets/tokens, and emits no acceptance
gate. Instrumentation affects timing; these runs do not close 60-minute criteria.

Production source/schema/lock/thresholds remain unchanged. API and builder stopped
after completion; isolated DB/Redis and all artifacts remain. No full regression,
60-minute acceptance, commit, push, merge or production activation was performed.
