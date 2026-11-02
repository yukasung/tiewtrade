# NC-F19-23 clock-setter capability preflight — 2026-11-02

Status: **Incomplete / capability gate failed; stopped before instrumentation**

This is diagnostic evidence only. `acceptance_result=false`; it does not change the
original F-19 SLA verdict or pass V-20.

## Scope and environment

- Existing Docker VM:8 CPUs,3,043,373,056 bytes, LinuxKit7.0.14, aarch64.
- Existing pinned runner image:
  `sha256:75ec49eb0803666de94a6248d9edd5fa258c7b651531dbc5ea3d9ff8b1735f88`
  (arm64).
- Observer `tiewtrade-f19-nc23-preflight-r1`: root, host PID namespace,
  `CAP_SYS_ADMIN` only after cap-drop ALL, privileged=false, network none,
  read-only root,0.1CPU/64MiB,32PIDs and no Docker socket.
- Read-only mounts were limited to `/sys/kernel/tracing` and frozen preflight source.
  Docker reported `no-new-privileges` and engine-added `label=disable`; no seccomp or
  AppArmor override was requested. No runtime, NTP or Docker setting was changed.

The source SHA-256 is
`54ed1e12b94ab30a887228100b75a4b2ed1d9e58218c260176e770d3739d8636`.
Exact sanitized command, source, result and stderr are retained under
`validation-artifacts/f19-set5-20261101/nc23-clock-setter/preflight/`.

## Result

The observer exited1 after0.565s, without OOM. The bind destination `/tracefs` existed,
but `/tracefs/trace_clock` did not. Therefore the read-only gate could not establish:

- a usable tracefs filesystem and private tracing instances;
- availability/selection of trace clock `mono`; or
- entry/exit events for `clock_settime`, `settimeofday`, `adjtimex` and
  `clock_adjtime`.

Classification: **Incomplete**. This is not `Not Reproduced`: no trace was started, so
absence of setter events was not observed. No private instance, event enablement or
buffer was created; cleanup was therefore not required beyond the observer's normal
exit. The exited container is retained with the evidence. No90s run, trading worker,
PostgreSQL, Redis or W1 run occurred.

Per the approved stop rule, no attempt was made to mount tracefs inside the VM, install
tools, restart Docker, relax confinement, add capabilities, use another tracer, or repeat
the probe. Full observer code and its conditional controlled tests were not created or
run because their prerequisite failed.

## Independent NC19 source check

The three relevant current files still exactly match the measured NC19 candidate manifest:

| File | SHA-256 | Result |
|---|---|---|
| `backend/src/tiewtrade/services/engine/risk_limit.py` | `573903ba372d057bfea6bebe3df7b67ca269e825417d3ffe4b0d38f7ed7914ab` | Match |
| `backend/src/tiewtrade/services/engine/risk_limit_main.py` | `326b98dfd079d3e6b7c7f8924fb8d3cf1c4f3f47fb6a1fb62ddca9c5f6877ded` | Match |
| `backend/tests/test_risk_limit_main_scheduler.py` | `129e1923b81d1f9d8f229e50b798a8f8963dc6931f71b07e0000d96db5bb2a01` | Match |

Thus the previously reviewed candidate remains the source under inspection: the owner
evaluation uses the existing authoritative user transaction and owner lock; scheduler
concurrency stays4; the UUID cursor/exclusion scheme and >100-owner test retain fairness;
and cancellation joins all active tasks before engine disposal. No scheduler code or test
was changed or rerun in NC23, and prior targeted/DB safety evidence remains applicable.

## Conclusion and stop

NC23 did not identify a userspace setter because the approved observation mechanism is
unavailable in the current Docker VM exposure. The actor remains **Unknown**; the NC21
kernel/hypervisor evidence gap remains open. Existing NC17/NC19-r3 failures are not
regraded, and V-20 stays **Failed/Pending Full Validation** with W2/W3/W4 not run.

The next step requires owner direction and a new amendment: either allow a narrowly
specified Docker-VM tracing enablement/change with rollback, or stop clock-setter work
and choose an evidence-backed alternative. The current approval does not authorize
either option, a production/environment fix, or another W1.
