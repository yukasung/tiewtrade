NC12 §18 V2 W2 — Failed resource contract,2026-11-07. Total1445.897s;
measured1241.602s passes1200s+60s allowance=1260s. All12000commands completed,
2400cycles,4800fills,2400cancels,2400replays,0rejections. All20financial/global/
position checks passed; snapshot p95=16.945ms/p99=17.360ms,20rebuilds,max3.415s.
Engine p95=363.444ms/p99=541.362ms passes500ms/2s pilot ceilings; performance_warning
retained because original250ms target missed. Inputs12395/12000,input lag9 within
existing bound, no worker failures. The relaxed throughput/duration gate passed.

The only failed gate is the owned-pool contract: parent recorded4 active-work
ConnectionResourceError entries, all original_exception=CancelledError,sqlstate empty,
quiescing=false. Inventory complete(parent13,workers20×2); all borrowed connections
returned before final disposal; all20worker reports passed. Final cleanup0connections/
0advisory locks and candidate/runner unchanged. No proven connection leak is reported.

The evidence does NOT identify which pool/task/query was cancelled or at what time.
Do not silently treat these as normal shutdown cancellations or assume a trading
transaction failed. Parent completed normally; this alone does not establish the
origin/safety of those4cancellations. Existing API price-read code has bounded read
deadlines, so deliberate read cancellation is one candidate, not a proven cause.

Stop checkpoint: preserve Failed and all prior results. No overflow/W3/fullW4,
replacement W2, further threshold change, production edit or Git/deploy action.
Existing§16 W1 remains Passed. Internal pilot and F17 remain open.

Recommended next scope: add test-only cancellation provenance(timestamp,pool role/
identity,task or named operation,quiescence/deadline context; never SQL,binds,secrets),
and targeted real-DB regressions distinguishing a known read-only deadline from
worker/financial cancellation, disconnect and leaked borrow. Reuse OwnedPools and
existing API lifecycle/readers. Establish a specific rule only after the origin is
known; no new timed campaign is proposed or authorized at this checkpoint. Current
source/harness is unchanged after the failed gate. A next implementation/campaign
requires a concrete approved scope under§18's stop rule.
