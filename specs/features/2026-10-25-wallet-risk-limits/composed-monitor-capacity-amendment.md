# F18-R21 — Bounded capacity trial for the R19 + R20 scheduler

สถานะ: Approved — owner approved R21 on 2026-10-28

## Evidence and decision

The native R19+R20 idle preflight acknowledged60300/60300 inputs with zero misses
(max0.997677s). Its full positive command cycle passed financial assertions and
60s deadline (48.5705s) but failed every-input SLA:24867late/144907,max2.705409s.
This is not a release candidate and W1 has not started.

One correlated repeat after a separately preserved clock-reversal setup failure
completed in46.8172s with the same exact financial postconditions. SLA failed:
23976late/140107,zero unacknowledged,max2.647939s.132403trace events,zero overflow.
Of58completed monitor rounds,33exceeded1s; median1.031169s,max1.696489s.
Exact owner d4b86523-eef2-4a82-a08c-f2866cbaac28 / price input11900 / round45:
ready1793195929.021587,commit1793195930.171541; prequeue260.722ms,
semaphore queue845.706ms,active43.527ms, no prior failed attempt.
These are correlated phases of one input, not summed parallel transactions.
23943late price inputs matched monitor commits;33did not match the10ms monitor
association tolerance and remain unexplained by this attribution (not discarded
from SLA).315matched inputs had a preceding failed attempt.

Risk process had zero cgroup CPU throttle during the trace, approximately43.14CPU
seconds over61.1s. Parent API/Paper was throttled (499periods,72.68aggregate throttle
seconds); that aggregate is NOT latency of any individual transaction. Host still
compressed/decompressed memory substantially (1148223/1112619pages), with123swap-in
and548swap-out pages. These confounders remain; extra concurrency is not guaranteed
to help. R18's earlier eight-slot trials failed on earlier scheduling and are not
superseded or relabeled by this proposal.

## One controlled change

Reuse the existing approved/tested R18 concurrency capability, with the now-active
R19 stable due ordering and R20 committed-price eligibility. Change only native
MONITOR_CONCURRENCY4→8, including its existing pool/warm-up/round wiring. No new
scheduler, query, cache, public API, table or grant. Keep UUID page/cursor,100hints,
20ms sleep,100ms owner lock,700ms statement limit, frame/boundary budgets, source
cadence,10Paper+1risk processes, default R9/R10/R11off and all financial fences.
Keep risk1CPU/512MiB, parent3CPU/1536MiB, PostgreSQL4CPU/3GiB unchanged. At most
four additional DB connections, as in R18. Never overlap workloads.

Hypothesis: additional slots overlap existing SQL/commit waits and reduce measured
semaphore delay enough to keep page completion below the input SLA. CPU/memory
pressure, lock contention and starvation may instead worsen; no pass promised.

## Stop rules and checks

1. Reuse existing scheduler4/8-slot barrier, page fairness and request/stop progress
   tests; run the affected suite and static checks after the one-constant change.
   Existing R19/R20 financial/replay safety evidence is reusable only if unchanged.
2. Run one same correlated full-cycle diagnostic from the original w1-v2-r9 clone,
   upgraded0058, with the exact same instrumentation, flags, financial oracle and
   resource bounds as cycle-trace2. Record clock stability and host pressure;
   distinguish environment differences from code effects. Keep all failed evidence.
3. If it fails to improve the proven queue bottleneck or creates safety/progress
   failures, restore4 and stop tuning. If diagnostic passes, verify native idle
   and full-cycle oracles once (zero late/unacknowledged,cycle≤60s), then existing
   review/W1→W2→W3→0058W4/regression gates. Diagnostic is never acceptance.
4. Any shared runtime change invalidates prior W1–W3 results for this candidate.
   V22/V23 stay Pending Dependency; no activation, Live orders or Git publication.

## Why approval is required

R20 explicitly fixed concurrency at4. Prior R18 approval is not treated as an
implicit override of that newer composition constraint. plan.md requires approval
before changing method. This proposal asks only for the composed capacity trial;
existing testing/review authorizations remain effective. Implementation follows approval.

## Trial outcome

Approved trial performed; SLA failed11322/150607 evaluations,max2.492380s despite
financial/deadline pass50.3986s. Runtime restored4; no further capacity tuning.
Full evidence and remaining attribution gap are recorded in M5.
