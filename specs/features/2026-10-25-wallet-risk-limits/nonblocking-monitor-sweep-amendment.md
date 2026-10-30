# F18-R15 — Nonblocking bounded standalone monitor sweep

สถานะ: Approved — owner approved R15 on 2026-10-28

## Evidence

R14 reduced same-clone monitor diagnostic misses11340→3735 and max4.316→2.182s,
but all100owners had some late acknowledgements. Equivalent timeout/owner-lock
SQL batching passed16tests+oneactual timeout-configuration check; its diagnostic
still failed5061late/max2.619s (slightly different realized price-frame count,
so no causal performance improvement claimed). Owner acknowledgement intervals
in that run:median1.0065s,p95 1.5990s,max3.1682s. A default20-owner gather round
waits for all candidates, including up to100ms owner-lock waits, before scanning
another page. Current throughput has insufficient margin for every-input1sSLA.
No RAM/OOM issue established: idle PG289MiB/3GiB, no memory-limit/OOM events.

## Proposed experiment

Only standalone monitoring changes; financial callers retain blocking owner locks.

1. Reuse the existing pg_try_advisory_xact_lock owner-hint pattern in
   infra/paper_orders/{request_dispatch,dispatch}. Same transaction-level lock,
   same paper-wallet:<owner> namespace and same RLS-checked session.
2. If monitor cannot acquire its owner lock immediately, return deferred with
   no owner/source read or projection/latch/audit mutation. Owner remains due;
   next sweep retries. Once acquired, existing R14 replay and owner lock through
   commit remain mandatory. No unlocked evaluation is published.
3. Standalone service calls existing bounded run_risk_monitor_round(limit=100)
   rather than default20. Its validated scanner ceiling is already100. At most
   FOUR active owner transactions/semaphore slots and pool4 remain unchanged;
   each candidate is evaluated at most once per sweep. Preserve owner cursor
   ordering, wrap fairness and normal20ms sleep after the sweep. No busy spin or
   extra per-owner in-transaction retry.
4. Reuse existing timeout configuration100ms/700ms; it still bounds other SQL.
   Nonblocking owner acquisition avoids consuming a slot just waiting for an
   existing financial owner transaction. Keep all source/fence/frame/boundary/
   financial checks. Request/stop loops, workers, pools,CPU/RAM/rates/durations,
   retry schedules,60s deadlines and every-ready-input1sSLA remain unchanged.

## Tests and acceptance

Real blocked owner: immediate deferred, no mutable owner state changes, next due
owner progresses; after release, original owner is eligible and processed.
Four-slot ceiling under100hints, every eligible owner progresses across sweeps,
no duplicate evaluation/financial mutation. Full owner/catalog/publication fence
contracts and transient-breach/R6API/R13queued-intake checks remain intact.
Standalone loop wiring test verifies bounded100 call; helper validation retains
existing blocking callers. Use affected safety/static checks before one bounded
same-clone monitor comparison. Only grounded improvement justifies native W1;
W2/W3 only after W1 passes. No overlapping diagnostics/workloads/tests.

If busy owners starve or safety/readiness/progress worsens, restore blocking
monitor/default20 and retain failed evidence. A try-lock can improve throughput
but can also miss a busy owner's release window; tests/measurements must prove
fairness and1sSLA. No assurance of success or threshold relaxation is implied.

## Approval boundary

This changes monitoring owner-acquisition and scanner-round scheduling after R14.
plan.md301 requires “ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md forbids implementing
changed methods first. Owner approved R15 before implementation. Prior approvals remain valid.

## Experiment outcome — 2026-10-28

Implemented with44safety checks and actual limit100/four-slot check passing.
Same-clone bounded probe still failed5850late/max3.289925s and price publication
slowed. Per rollback terms restored blocking monitor/default20, removed unused
try-lock helper; rollback checks7passed. No W1/W2/W3 or activation pass claimed.
Evidence: M5 checkpoint and monitor-probe-r15 artifacts. Approval remains history;
this scheduling experiment is inactive on the current source.

## Re-evaluation with approved R17 — 2026-10-28

R17 increased observed Paper throughput and reduced transaction median but did
not pass monitor SLA. Re-test this already-approved try-lock100/four-slot method
with that changed contention profile. Prior failure remains; this is a separate
combination experiment, not a claimed pass. Same safety/rollback/gates apply.
