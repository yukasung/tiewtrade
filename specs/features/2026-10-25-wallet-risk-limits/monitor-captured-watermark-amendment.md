# F18-R14 — Standalone monitor commits its captured watermark

สถานะ: Approved — owner approved R14 on 2026-10-28

## Evidence

W1r23 (R12/R13,R10on,R11off) failed its60s cycle with479completed/78cycles.
Offline partial SLA:47305acks,23175late,657unacknowledged,max14.143885s.
Its monitor failure blocks classify2035publication-fence waits versus458owner
lock waits (text classification, not an execution trace of every transaction).
The cloned no-new-command monitor-probe, same10Paper+1risk/4CPU2GiB,5s warmup+
20s observation, still had58602acks,11340late,1398unacknowledged,max4.316069s.
This diagnostic is not W1 acceptance; old native queued work remains genuine.
Concise typed timeout logging passed7affected tests and retained defer behavior.

## Proposed bounded experiment

Change only the standalone monitor scheduler's call from
replay_monitor(publication_fence=False, final_publication_fence=True) to the
existing captured-watermark path with both flags false. Reuse the already
implemented immutable frame/boundary replay, owner lock,100frame/20boundary
budgets, durable cursor, pause/latch/stop handling and200ms scheduling.

A monitor captures the committed publication watermark and evaluates every
retained frame through that cut under its owner lock. It commits that cursor;
frames published later remain for the next round. It may therefore commit a
valid READY evaluation with a cursor behind the latest publication. Existing
R6API price-tail verification remains authoritative for API intake; a stale
hint never authorizes an order. No new hint relaxation is included here.

Financial writers keep their owner/catalog/SHARED publication fences through
commit and replay to their authoritative cut before any money/order action.
Price/feed writers keep EXCLUSIVE publication fencing and all database guards.
Reset, bridge/intake and native matching do not opt into this monitor-only path.
Owner locking prevents a financial boundary from changing while the monitor
replays; future owner changes are recorded in existing boundary markers and
consumed in order on the next monitor round. No frame skipping/coalescing,
financial formula, source gate, latch timing rule or retry/backoff change.

No pool/worker/CPU/RAM/rate/duration/deadline/SLA increase. Every ready input must
still be acknowledged<=1s; no percentile substitution or fault reclassification.
The experiment may fail on owner contention or CPU and must retain that failure.

## Verification / rollback

- Real publisher advances while monitor holds owner lock: monitor commits only
  captured cursor; next round consumes later frames and detects transient breach.
- Publisher need not wait for a standalone monitor's final phase. Assert monitor
  has no shared publication fence, while financial writers still block publisher
  and recheck a newer breach before changing money.
- Boundary/reset/correction/rollback/claim/latch/stop/idempotency tests unchanged;
  run affected monitor/policy/matching/API tests and relevant static checks.
- One bounded same-budget monitor comparison first; only on grounded improvement
  run native W1. W2/W3 only after W1 passes. No overlapping workload/diagnostic.
- If readiness/fairness/safety is worse or acceptance does not improve, restore
  standalone final drain and retain failure. Application admission stays gated.

## Approval boundary

This changes standalone monitor publication scheduling after R5's final drain.
plan.md301 says “ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md prohibits implementing
changed methods or new trading assumptions before approval. Owner approved R14 before implementation. R6–R13 approvals and completed authorized repairs remain valid.
