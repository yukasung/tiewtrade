# F-38 bounded diagnostic r2 — 2026-10-26

Status: **Completed diagnostic; root cause unresolved.** No acceptance credit.

The runner added the normal BTC source producer, 10-second readiness/metadata
observer and real parity audits to the existing loaded probe helper. It ran on the
unchanged candidate image, schema 0042 and existing isolated r5 stack, retaining
2 CPU / 1 GiB and CPU pinning. The run completed all three rounds within its
360-second bound and stopped API/builder afterwards.

- 144 measured requests; maximum API lag 64.382 ms; RSS delta 66,928,640 bytes.
- Accepted GET/parity: 24/24 HTTP 200 and 24/24 exact audit success.
- Rejected load: 60 BUSY 503 and 60 RATE 429 with expected error details.
- 20 observer snapshots; parity audits took 64.606, 65.018 and 63.854 seconds.
- Cgroup throttled periods/time remained zero in every before/after pair.
- No request exceeded 100 ms. This small sample does not exclude an intermittent
  spike in a longer run.

Review found that `asyncio.Handle._run` is not the callback implementation used
by the image's uvloop. Consequently **callback/stack coverage is invalid in r2**;
do not infer absence of slow callbacks from absence of that artifact. Existing
ASGI request metrics and cgroup evidence do not depend on this hook.

The diagnostic wrapper was corrected to use an independent thread watchdog and
event-loop heartbeat, sampling frame locations without locals. Before r3, a
controlled self-check on the same image and 2 CPU/1 GiB limits used `uvloop.run`:
async idle 100 ms produced 0 gap records; blocking sleep 80 ms produced 3 gap
records with low thread CPU; a CPU-bound 80-ms loop produced 2 gap records with
high thread CPU. All assertions passed. These artificial delays were executed
only in the disposable self-check process, never against the application.

Production source, schema, lockfiles and acceptance thresholds remain unchanged.
No commit/push or 60-minute acceptance run was performed.
