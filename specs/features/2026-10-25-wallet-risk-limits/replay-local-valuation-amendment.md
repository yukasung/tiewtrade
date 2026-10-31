# F18-R22 — Replay-local reuse of identical valuation inputs

สถานะ: Approved — owner approved R22 on 2026-10-28

## Evidence

R21 eight-slot trial failed and was restored to4. Scheduler changes alone have
not qualified the candidate. Existing stages locate most missed-input delay before
transaction execution, while greater concurrency increases active transaction time.
A single CPU-attribution run on restored4 retained all source/financial checks and
used cProfile solely to locate synchronous work. It is NOT a speed measurement:
profiler overhead severely worsened SLA and its result remains Failed.

Artifact r21-cpu-attribution/risk-cpu.prof:122931415calls in77.165profile seconds;
synchronous evaluate_risk196705calls/50.261cumulative seconds; Money context
wrapper4556052calls. This supports reducing repeated valuation arithmetic, not
changing Money's implementation or increasing concurrency. Do not sum overlapping
async cumulative times or present profiled durations as native latency.

## Narrow proposed method

Add a pure replay-batch evaluation path sharing the existing evaluate_risk
implementation's validation, valuation and decision helpers. Within ONE call of
_evaluate_frames, the book is immutable. Reuse only a successfully computed loss
for identical validated valuation inputs of that same book. No module/global LRU,
no persistence, no cache across owners, calls, transactions or financial boundaries.
At most100entries, bounded by the existing frame budget; discard on function exit.

Every frame must still pass existing completeness/checksum decoding, price tuple/
pair validation and price_at(frame.captured_at) readiness/lease/generation/freshness
checks. Build the valuation key from the resulting exact Money-or-unavailable
marks in canonical book-pair order, bound to that exact immutable book/scope.
No approximate prices, float, rounding change, or raw Decimal arithmetic.
A missing/unready mark must preserve the current held-versus-zero-position
semantics; never reuse a ready result simply because an amount is unchanged.

Reuse only the value calculation for identical inputs. Each frame still creates
its own evaluation at its own timestamp and current setting revision/limit/latch,
checks the threshold, and persists every transient breach or pause transition
exactly as _evaluate_frames currently does. Recompute decisions after a latch
transition. Do not memoize exceptions or bypass any checks after a failed value
calculation. Changing book at a financial boundary starts an empty local memo.
Single-input evaluate_risk and final current-time evaluation retain their public
contract and share the exact arithmetic helpers; no second financial formula.

Keep monitor4, R19/R20 scheduler, schema0058, source cadence, default flags, workers,
CPU/RAM, frame/boundary budgets, financial locks/fences, all deadlines and SLA.
No change to Money/Quantity or shared F02/F14 modules, API, schema or Live code.

## Proof before performance

- Compare every batch result and error behavior with repeated existing single-
  frame evaluate_risk calls using identical inputs and latch evolution. Cover
  identical amounts with different freshness/lease/generation, source unavailable,
  duplicate/malformed prices, empty and zero-held books, multiple pairs, mixed
  positive/negative realized amounts, allowance after reset, precision/overflow,
  threshold exact/below/above and transient breach followed by recovery.
- Prove scope/call isolation and no reuse after financial boundary/book changes;
  replay pending, rollback, durable latch/stop idempotency, concurrent writers,
  publication fences and request/stop progress remain covered by affected suites.
- No profiler in qualification. First use a deterministic same-input before/after
  valuation comparison with identical instrumentation to prove less repeated
  arithmetic. Then one native full-cycle/idle preflight with every-input SLA,
  original60s deadline and financial oracle. Preserve failures and stop on a
  contradictory result; no repeated tuning to obtain a lucky pass.
- Only a fully passing preflight proceeds to review and W1→W2→W3→W4/regression.
  All shared-runtime performance results require revalidation; V22/V23 remain
  Pending Dependency. No activation, Live orders, commit/push/merge.

## Approval boundary

Earlier R17 cached public execution decoding only and explicitly excluded financial
state. This proposal reuses derived valuation locally, so it is a NEW method and
must not be inferred from R17/R21 authorization. plan.md requires amendment before
changing methods; AGENTS.md requires explicit approval for financial-method gaps.
The formulas and criteria stay fixed, but this reuse strategy needs owner approval.
