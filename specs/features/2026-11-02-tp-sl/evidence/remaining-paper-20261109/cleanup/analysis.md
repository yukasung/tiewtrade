# Cleanup lifecycle diagnostic — 2026-11-09

Status: **Observation complete — original D20 symptom not reproduced**.
Owner instructed “เริ่มทำ” after the scoped diagnostic proposal. One new isolated
empty database, no owners/orders/protection requests or20worker workload.
Production de3bdcb unchanged; current harness/source bound in candidate manifests.

Targeted observer URL/isolation, allowlisted events/listener cancellation cleanup,
and actual parent-lifecycle error/cancellation tests5passed (5.84s). Scoped
Ruff/format/mypy Passed. One diagnostic after those checks,15.575513s of observation,
within300s cap. No automatic retry or further timed phase.

[Result](result.json), [timeline](timeline.json), [pool events](pool-events.json),
[parent pool evidence](parent.owned-pools.json),
[after-process-exit observation](after-process-exit.json).

## What was actually observed

Separate read-only observer connects to postgres, outside the generated target;
current_database and transaction_read_only are asserted. Each statement uses
AUTOCOMMIT, avoiding a retained pg_stat_activity snapshot. Recorded data is limited
to timestamp/PID/role/state/backend type/wait/application/transaction-open and pool
connect/checkout/checkin/close events; no SQL text/credentials/session values.

- Actual initial empty guard and manifest engine creation/disposal left0target
  connections before parent lifecycle.
- Actual parent path reused5parent engines, internal_intake(empty owners), real
  ASGI lifespan, resource_sampler and original teardown order. Only isolated fixture
  protocol rows are temporarily activated/restored by existing context; no trading
  commands, user sessions or financial facts created.
-11idle client backends were visible before shutdown. After intake closed,5parent
  backends remained. Disposing MARKET_DATA→MIGRATOR→API→ENGINE→ENGINE_SCAN reduced
  observed counts4→3→2→1→0. The intermediate1 was ENGINE_SCAN before its own disposal,
  not a backend remaining after final cleanup.
- Parent owned-pool contract Passed,13pools, no errors. At one-shot cleanup0target
  connections. Fixed later samples at50ms/250ms/1s/5s/15s were also0. They are
  observations, not a retry-to-pass loop or a substitute for one-shot cleanup.
- After diagnostic process exit no target backends remained. Launcher dropped its
  generated source normally. No force termination/drop or owner database changes.
- Source/runner unchanged throughout; subsequent content hash verification matches
  pinned inventory. No production/domain/API/schema/dependency change.

## What this does not prove

The D20 original connection lacked PID/role/state; it cannot be identified by
matching this later run. This small empty-parent lifecycle does not reproduce
20-worker activity, request/session creation, active-load shutdown or their timing.
Do not infer absence of a load-dependent leak, permanent runtime defect, or a
specific server shutdown race. Do not retrospectively waive the original cleanup.
D20 campaign remains **Incomplete**, W4 Not Run; controlled20 Passed retained.
This diagnostic is not an accepted replacement D20 or F17 completion proof.

## Next checkpoint

Diagnostic scope complete and stopped. An additional empty-parent repeat has no
specified evidence gap it would resolve. Recommended next is one owner-approved
replacement D20 retaining all assertions, with allowlisted backend identity added
at its existing one-shot cleanup query and a separate post-process observation;
if that campaign passes, one W4 under original criteria. No such source change or
campaign performed/authorized here. See [concrete proposal](../../../remaining-paper-d20-identity-proposal.md).
No commit/push/PR/merge/deploy/Live action. Original100-account/4h/bot/notification/
Live and owner manual gates remain pending.
