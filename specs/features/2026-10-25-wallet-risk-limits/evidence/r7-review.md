# F18 current review checkpoint — after R6/R7 and monitor SQL tuning

วันที่: 2026-10-27 (Asia/Bangkok)
สถานะ: **CHANGES REQUIRED — V21 Failed/Partial; R8 safety221passed; full W1r13 in progress**

Source of truth: [requirements](../requirements.md), [plan](../plan.md),
[validation](../validation.md), approved R5/R6/R7 amendments and repository standards.
Current branch remains uncommitted; no commit/push/merge/Live order authorized or done.
Detailed chronology, commands, failed invocations and provenance: [M5](m5-final-candidate.md).
This review extends the existing M4/M5 review only for changed paths/dependencies.

## Open finding

### High — integrated cycle exceeds the approved progress bound

- Location: `backend/src/tiewtrade/services/engine/paper_order_main.py::serve`,
  `services/engine/{manual_order,paper_order}.py` round selection, and
  `tests/infra/risk_limits/profile_workload.py::breach_reset`.
- Problem: W1r12 completes2,000 baseline and partial-fill oracle, but the selected
  owner's breach/reset/reseed cycle exceeds60s during command-result waiting.
  Measured partial counters445completed/70cycles; no W1 capacity pass.
- Impact: Paper order progress/readiness is not proved under the agreed load;
  production activation and Completed remain blocked. No evidence of a permitted
  unsafe fill should be inferred from fail-closed source/price refusals.
- Evidence: requests transfer in~.1–.2s, then wait~3–4s for command processing.
  The separate10s probe records Paper956rounds/375processed/3deferred/578skipped.
  Skipped combines claimNone/claim-lost; it does not prove all skips are the same
  owner or that the proposed scheduling change will fix throughput.
- Recommended next change: [R8](../claim-budget-amendment.md), bounded20 hints,
  stop after1successful claim including deferred/failed claimed work. Existing
  ordering/claim/CAS/fences/default behavior and all acceptance limits remain.
  Owner approved R8 and its plan incorporation before implementation. Selector/
  composition tests26 and real-DB safety221 passed; current W1r13 capacity proof
  remains pending. ProbePaper427/427phases processed work, not a capacity pass.

## Closed finding

### High — healthy claims incorrectly inflate failure backoff

- Location: `infra/paper_orders/dispatch.py::{finish_claim,reschedule_processed_orders}`.
- Problem: lifetime claim attempts also drove failure backoff, so a long-lived
  healthy command could wait5minutes after one transient source failure.
- Fix: a committed healthy/idle round and siblings covered by its persisted pair
  checkpoint reset only the backoff counter. Claim revision remains monotonic;
  unchanged1s/5s/30s/5m sequence applies to consecutive failures.
- Evidence: stale-claim rejection, exact four-step failure delays, covered vs
  other-pair/pending/cancel/claimed schedule isolation and100affected tests passed.

## Requirement/plan and risk review

| Area | Current assessment |
|---|---|
| Requirements | Approved financial/risk/reset/stop/idempotency behavior remains; V21 failed, V22/V23 dependencies pending. No extra business/trading rules added. |
| Plan | R6/R7 incorporated before implementation. R7 runtime/harness limits agree and standalone F15 default20 remains. R8 draft is not treated as approved. |
| Architecture | Same owner-scoped DB sessions/roles, pure core evaluator, financial writer and Paper isolation; no new scheduler authority or venue credentials. |
| Quality | Shared setting decoder and scoped joined owner read replace redundant reads. Cursor CTE compares prior book/source/episode in DB; no owner/result cache. |
| Security | No grants expanded; API read-tail cannot write latch/stop/baseline/financial facts; owner/RLS/mode/episode boundaries retained. Live remains closed. |
| Error handling | Missing/corrupt/over-budget/stale financial evidence fails closed. Durable evaluation hints remain non-authoritative; newer ENGINE breach rejects after API acceptance. |
| DB/transactions | Evidence bulk copy keeps each immutable source identity/digest and permanent registry. Post-evidence/pre-registry failure rolls back. Cursor/pair updates share the original transaction and owner lock. |
| Concurrency | Owner lock, monotonic claim revision, CAS/leases and catalog/publication fences retained. Runtime batch selection remains the open progress risk. |
| Idempotency | Existing request/command/economic identities unchanged; replay/correction/stop duplicates covered. Restore verified no duplicate financial/cancel effects. |
| Precision | New comparisons/conversions use Money/Quantity; formulas, financial rounding, fee/quantity/PnL rules unchanged. No raw Decimal/float money arithmetic added. |
| Trading cases | Duplicate/unintended fills, cash/held/reservation mismatch, per-fill breach, transient breach recovery, journal corruption and reset revision checks covered. Futures/leverage/margin/liquidation/Live and bot dependencies are not invented or declared passed. |
| Network/recovery | Existing source disconnect/reconnect and unknown commit tests retained; W3 full fault/endurance still pending, so no full WebSocket/exchange-failure recovery acceptance claim. |

## Coverage and evidence limits

- Existing full backend invocation:3607passed/2venue-contract exclusions; it predates
  later tuning. Reuse unaffected coverage with affected final checks; do not call
  it a fresh full invocation on the current source hash.
- R6/post-bulk affected execution/manual/risk/API coverage passed through the
  recorded corrected invocations (intermediate failures retained).
- Final retry bookkeeping changes:100affected tests passed66.83s.
- Final monitor SQL:116risk/API tests passed66.60s; dedicated price-only vs real-fill
  pair persistence test passed1.72s. API outage/recovery and real-reset stale-setting
  checks passed after the documented constructor-key test correction.
- R7 composition/supervision/scheduling-hint:24passed1.16s. Whole mypy559files and
  ruff passed; prior7import contracts remain valid (same dependency paths).
- Frontend296tests/types/lint/build/browser evidence reused; no frontend/API shape
  changed during R6/R7/monitor tuning. No extra frontend run without a new impact.
- W4r9 Passed on0055/current cursor/retry code: canonical restore, roles/RLS,
  expired claims, real risk-policy retry, two terminal cancels/zero duplicate effects,
  unchanged financial facts and reset baselines.
- W1r12 **Failed/Partial**, W2/W3 **not run**. Partial processing samples pooled
  setup+measurement (p95.21737s/p99.35295s) are not a measured-only W1 gate pass.
- External diagnostic mistakes (restarted trade IDs, correction-link/stop-command
  totals, preexisting pending reservation effects) and failed checks remain stored.
  Corrected frozen-state postconditions are diagnostic only, never full acceptance.
- Remote required CI is not run for this uncommitted candidate. No Git operation
  is inferred from code-review or amendment approval.

## Remaining risks

1. V21 progress/latency/queue/resource acceptance under final sustained load.
2. W2 stress/overflow4097 and W3 fault/endurance/RSS gates on final runtime.
3. V22/V23 bot/Live/notification and actual protective-type fixture dependencies.
4. R8 selection improvement is still a hypothesis requiring approval and proof;
   do not raise budgets, shorten datasets or relax thresholds to obtain a pass.

CHANGES REQUIRED
