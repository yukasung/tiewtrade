# F18-R13 — Defer queued NEW while bounded risk replay is pending

สถานะ: Approved — owner approved R13 on 2026-10-28

## Evidence

R12 diagnostic removed observed book gaps>1s (1453intervals,max0.472444s), but
baseline stopped after1429native results on an intake rejection. The rejected
request result, risk_owner_state and risk_limit_evaluations have the SAME xmin
2072667: ORDER_SAFETY_UNAVAILABLE, cursor2490, replay_pending=true,
RISK_SOURCE_UNAVAILABLE. Current watermark after shutdown2495. Thus the bridge
committed bounded replay progress and a permanent safety refusal together.
This is not evidence of a financial violation or proof of eventual SLA success.

## Proposed behavior (new approval boundary)

For a queued Paper NEW using TransactionalRiskPolicy, when authoritative owner
state after bounded replay is specifically replay_pending, do not turn that
transient condition into an immutable terminal rejection. Commit the replay
progress and defer the SAME intake claim atomically, with existing claim CAS,
owner lock, attempts and1s/5s/30s/5m schedule. Do not create a native order command,
reservation or fill until the ordinary full policy check succeeds on a later
attempt. Reuse request_dispatch.defer_request_claim and the existing service
processed/deferred counters; expose an explicit deferred outcome from the bridge.

Scope of the exception is narrow:
- Must have existing configured risk limit, same owner/wallet/episode and setting
  revision, and a live claim. Derive pending from canonical state under owner lock.
- Latch/breach/queued-stop cutoff always wins: preserve terminal refusal.
- Unset limit, missing policy, wrong use, catalog removal, malformed request,
  actual loss-limit rejection and other non-pending failures retain existing
  behavior. No generic catch-and-retry conversion.
- Cancellation/reduction paths and native matching retry protocol unchanged.
- Do not raise an exception that rolls back replay progress and then repeatedly
  replays the same100frames. Pending progress and claim deferral commit together.
- No extra attempt/claim in a round, no new retry schedule, no polling within a
  transaction, no frame skip/coalescing, no bypass of the final financial fence.
- Lost commit reply/restart must preserve idempotency and recover via existing
  immutable intake key/claim/result guards. All resource/SLA/deadline gates stay.

## Verification

Real PostgreSQL queued opening with>100price frames: first attempt advances
bounded cursor, leaves result/command/reservation absent, releases claim with
ordinary backoff; subsequent fully checked attempt transfers exactly once.
Breach in replay, reset/stop cutoff, claim loss/rollback/lost acknowledgement,
wrong owner/use/unset limit and ready path remain covered. Test service counters
and no duplicate native command. Use existing manual bridge/risk/recovery tests,
then affected static checks; reuse unaffected evidence. R12 harness remains
subject to its approved rollback/acceptance rules. Workloads run sequentially.

## Approval boundary

This changes queued-intake behavior from terminal refusal to bounded retry for a
specific pending condition. plan.md301 requires “ขอ plan amendment ก่อนเปลี่ยนวิธี”
and AGENTS.md prohibits inventing trading requirements or implementing changed
methods before approval. Owner approved R13 before implementation. Prior R6–R12 approvals remain
valid; this request is only for the new pending-intake behavior.
