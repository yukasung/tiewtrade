# F18-R23 — defer the initial financial replay fence until the bounded final tail

สถานะ: **Approved** — เจ้าของตอบ “อนุมัติ R23” วันที่ 2026-10-28
วันที่: 2026-10-28

## Evidence and hypothesis

Current candidate uses approved R10 alternation plus R22 valuation reuse, monitor4,
R9 standalone preference/R11 retry off, original4CPU/2GiB and100owners×20orders.
The native60s concurrent diagnostic completed500commands/100cycles and all three
risk scenarios, but transactionp95=.284737s exceeds.250s;12ready evaluations
exceeded3s(max3.115111s). Historical failure is retained, not acceptance.
A monitor-stage diagnostic passed all87604acknowledgements(max2.058944s), but
transactionp95=.298494s still failed. This does not prove consistent riskSLA.

The separate Paper-stage diagnostic records2928processing transactions,218over
250ms. For those218, per-transaction medians are:317.31ms total,219.93ms SQL,
116SQLcalls,90.33ms in risk_financial_fence(),0.82ms connection acquisition and
2.72ms transaction close. Median fence/transaction ratio is28.6%. These medians
are not additive; no sum of parallel transactions is presented as single latency.
The fence is the largest SQL category in this slow cohort. Instrumentation adds
overhead; this is attribution evidence, not a controlled speed comparison.
Evidence: external f18-20261027/r10-r22-timing/processing-breakdown.json and
per-worker *.timing.jsonl. The run completed all500commands but its final drain
failed due to the separately fixed normal-shutdown recorder cancellation race.
Do not use that run as full safety/performance acceptance.

Hypothesis: historical replay before acquiring the shared publication fence can
shorten the time it is held and reduce publisher/financial-writer contention.
It might not help enough: per-input processing after acquisition still holds the
same fence, and replay itself may be a small share. One controlled comparison is
required. Do not change worker counts, deadlines, SLA or retry to obtain a pass.

## Exact proposed scope

- Reuse infra/risk_limits/monitor.py::replay_monitor's existing bounded final-tail
  path with publication_fence=False,final_publication_fence=True for configured
  Paper BUY policy replay in TransactionalRiskPolicy.resolve/execution_context.
  Remove only the redundant upfront shared acquisition for that path. Preserve
  the original fenced fallback for unconfigured/unsupported paths.
- Keep the existing owner/catalog lock order, immutable financial book/source
  proof, setting revisions and every historical price frame. Preliminary replay
  is not authorization and may not create order/position/cash effects.
- Acquire the same SHARED transaction advisory fence before final tail replay,
  re-read committed watermark and consume the complete tail within the existing
  total100-frame budget. Revalidate readiness, freshness, settings, controls,
  loss/latch and exact financial evidence before authorization. Keep the lock
  through commit. Insufficient budget or missing/inconsistent evidence must fail
  closed/defer under existing semantics, with durable breach persistence intact.
- Preserve financial_boundary marker/fence protocol unchanged, including before
  any actual financial mutation; its before-state/watermark must remain accurate.
  Preserve per-input final recheck and cache invalidation after fills from R5.
  Never reuse preliminary evidence as an authoritative fenced context.
- No change to standalone monitor R14, API R6, cancellation/reduction paths,
  reset/correction/initialization protocol, publication EXCLUSIVE writer lock,
  schema, role grants, public API, financial formula or Money/Quantity.
- Only these existing callers may opt into late acquisition. Do not change the
  replay_monitor default or broaden the optimization to all financial writers.

## Safety and decision gates

Before timing, exercise existing real-DB publication/financial boundary tests plus
barriers that publish breach/recovery, source outage/generation change, freshness
expiry or disabled admission between preliminary replay and final acquisition.
Prove no preview money/order effect, no missed transient breach, unchanged loss/
latch/revision, owner isolation, rollback, duplicate prevention and accurate marker
watermarks; include tail-budget exhaustion and concurrent financial writers.
Verify final evidence and lock are held through actual mutation/commit. If the
existing final-tail implementation cannot establish these properties, stop and
report the gap rather than relaxing checks or expanding scope.

Use the same native concurrent short profile and the same bounded attribution
instrumentation before/after. Retain failures; no repeating unchanged runs hoping
for success. If hold/wait time or progress does not improve, roll back this method.
Only after every targeted gate passes, freeze/review and proceed W1→W2→W3→W4 and
regression/final review under the approved closure plan. Paper hard3s,target1s,
Live1s pending,transactionp95<=250ms/p99<=1s,60scommanddeadline and all original
loads/resources/durations remain unchanged. No success/time guarantee.

## Approval boundary

Plan.md lines460–462 restrict final_publication_fence to the standalone scheduler
and retain full fenced replay for financial callers; R14 also preserves that rule.
Plan§5 requires “ขอ plan amendment ก่อนเปลี่ยนวิธี”. R5 explicitly keeps new-order
admission fully fenced; R23 changes when that fence is acquired during preparation,
while still requiring it before authorization/mutation and through commit.
AGENTS.md forbids implementing a method different from the approved plan before
approval. This request is only for the new financial replay timing, not reapproval
of R10/R22, oracle fixes, tests, review or the existing closure workflow.

## Experiment outcome — rolled back 2026-10-28

Implemented only the two approved policy callers.73affected safety/caller cases
passed (initial stale-test error corrected to MAX_PRICE_AGE; failures retained).
Same boundedPaperobserver/60scommandprofile yielded2852processingtransactions.
The slow cohort fence median remained89.93ms versus90.33ms before; the hypothesis
was not supported. Comparable processing p95 in observer rows was334.11ms versus
289.71ms. One noisy diagnostic cannot establish a universal regression, but does
not justify retaining the change. Wholeprofile p95=.337683s;3/76204ready inputs
exceeded3s,max3.293155s,zero missing/clockerrors.500commands/100cycles and all
financial invariants passed; book613>=600. This is Failed/diagnostic,notacceptance.

Restored original policy.py and monitor.py exactly; experimental14barriertests
and source archived in external r23-timing/source with raw evidence/comparison.
No R23 runtime remains. Do not re-enable or repeat this experiment unchanged.
Current candidate retainsR10+R22 and the separately proven harness fixes. Full
W1–W4/finalregression remain pending. The next analysis must address actual fence
holding work/contention, not assume moving historical replay reduces its wait.
