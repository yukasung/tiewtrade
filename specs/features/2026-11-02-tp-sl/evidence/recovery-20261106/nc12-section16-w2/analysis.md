NC12 §16 W2 — Failed throughput duration,2026-11-07. Total1136.363s;
measurement963.571s exceeds600s target+60s allowance=660s. This is the sole failed
acceptance predicate. Completed12000/12000commands,2400cycles,4800fills,2400cancels,
2400replays,0rejects; all20financial/global/snapshot/rebuild checks passed.
Engine p95=363.782ms/p99=492.133ms passes approved pilot500ms/2s; original250ms
p95 target missed and performance_warning=true retained. This does not waive the
separate throughput/duration criterion. Measured inputs9635/6000, workers no failures,
resource/pool checks all passed; all registered loans returned before disposal.
Parent13pools/workers20×2 inventory complete, observer errors none. Snapshots20/20
p95=18.214ms/p99=18.502ms; rebuild max1.068s. Input lag4 remained within the existing
bound. Final cleanup0connections/0advisory locks; candidate/runner unchanged.

The cohort's effective completed throughput is12.454commands/s over963.571s. This
closed-loop observation does not establish an absolute capacity or prove which
query/queue/worker stage is the bottleneck. No causal root-cause claim is made.
Evidence:campaign-result.json, run/result.json, gate-assessment.json, raw samples/logs.

Stop checkpoint: W1 Passed is retained; W2 Failed retained. No W2_OVERFLOW/W3/fullW4
started, no automatic rerun, source fix or further threshold relaxation. F17 remains
Pending Full Validation. Next requires owner decision on the next scope: retain the
20commands/s burst requirement and investigate/fix throughput, or explicitly approve
a distinct lower-load internal profile while retaining the20commands/s requirement
for the original release gate. Any concrete profile requires declared rate/counts/
duration before execution; do not choose numbers from this failed run to relabel it.
