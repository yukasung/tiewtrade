# F18-R19 — Oldest-due execution within the existing monitor page

สถานะ: Approved — owner approved R19 on 2026-10-28

## Evidence

After a graceful Docker VM restart, the same default4-slot/R10off/R11off,
100-owner/2000-order comparison reduced host paging to1.66MiB swap-in/zero
swap-out and maximum event-loop lag49ms. SLA still failed405late/58587acks,
1413tail-unacknowledged,max1.580120s. All405late samples correlated to actual
monitor transactions; only18 had a preceding failed attempt during their delay.
The same low-paging8-slot R18 comparison failed1209late/max2.162473s; runtime
was returned to4slots. More slots are not the supported next fix.

A specific1.580120s missed input for owner08442134-e754-49f1-a4cc-5564f72e0e1f:
- Input4418 commits at t=0. The previous snapshot at t=-.044883 captured4417.
- Previous cursor save completes at t=-.041718, scheduling next due about+.158s.
- Round54 scan completes at+.158070, just before the200ms due boundary, and the
  owner is absent from that page. Exact server clock lies within the measured
  SQL interval; the sub-millisecond boundary is approximate, not a new tolerance.
- Round55 queues at+.782882 but places this owner last (rank78/79), because
  existing UUID rotation starts after the prior page's last candidate.
- It acquires a slot at+1.562475 and commits at+1.580120; its own active work is
  only17.645ms. This owner has no failed attempt during that input's delay.

This establishes an avoidable second queue wait for an overdue owner, not proof
that the proposed order will resolve every miss. Artifacts: monitor-correlated-
vmreset/risk-stages.jsonl, late-stage-attribution.json and late-stage-summary.json.

## Bounded change

1. Keep the existing scanner WHERE predicates, due_at200ms rule, evaluation hints,
   UUID wrap ordering, page limit100 and original candidate page unchanged. Add
   o.due_at to the selected metadata. No additional SQL statement or schema/API
   change. The scanner remains non-authoritative and bypasses RLS only as already
   approved; all actual owner work remains under the existing scoped session.
2. Preserve the ORIGINAL candidate list and its last owner for next_owner. Sort
   a separate execution list by due_at ascending, with NULL first for uninitialized
   owners. Python stable sorting retains original UUID-page order for equal times.
   This changes only which already-selected owner starts first; every candidate
   remains attempted at most once and all page tasks are awaited as before.
3. Retain four concurrent transactions/pool4,100ms blocking owner lock,700ms
   statement timeout,20ms inter-round sleep, frame100/boundary20 budgets and all
   request/stop pools, CPU/RAM, processes, source rates and deadlines.
4. No early eligibility, extra retry, priority outside the selected page, financial
   caching, price readiness bypass, risk arithmetic or financial/publication fence
   change. Preserve request/stop progress and all role/rollback contracts.

## Reuse and tests

Reuse services/engine/risk_limit.py::run_risk_monitor_round and current scheduler
barrier/isolation fixtures. Do not introduce a scheduler service or second replay
algorithm. Add deterministic real-DB cases proving oldest due starts first among
selected owners, NULL/equal-time ordering, future-due exclusion except the existing
hint path, and original page cursor/wrap progress even when execution order differs.
Keep the existing transaction bound, busy-owner progress, request/stop pool and
captured-watermark tests; run affected concurrency/stop/fence safety and static
checks. No automated Live orders.

## Decision gates

Run one same-clone/same-instrumentation low-paging4-slot comparison after safety
passes. Observe every ready input, owner progress, actual source cadence, slot
queue and transaction spans, host paging and pool/resource failures. Historical
failed evidence remains. If order does not improve the identified queue cause,
restore original execution order; do not rerun hoping for a pass or increase pools.
No speedup or passing SLA is promised by this proposal.

Only when all acknowledged inputs meet1s and any cutoff tail is explicitly
accounted for, use the existing authoritative final-drain oracle to prove coverage;
then check the existing60s full command cycle. Native W1/W2/W3, applicable W4,
final regression/review and outstanding CI/manual gates remain mandatory under
the approved closure plan. V22/V23 remain Pending Dependency.

## Approval boundary

This changes the execution order specified by the existing monitor sweep. It is
outside R18's concurrency-only experiment. plan.md:301 requires “ขอ plan amendment
ก่อนเปลี่ยนวิธี”; AGENTS.md forbids implementing a changed approved method before
approval. R6–R18 and the evidence-first closure workflow remain authorized.

## Experiment outcome

37affected safety cases passed. Both comparisons failed: first918late/max1.339450s;
first-after-VM-restart879late/max1.940027s. Ordering alone did not establish benefit
sufficient to retain the method. Reverted execution sorting and its selected due_at
column, archived candidate source/tests, restored original UUID page execution.
No R19 runtime behavior remains. See M5 for trace, environment limits and rollback.

### Re-evaluation with approved R20 eligibility

R19-alone rollback above remains historical fact. R20 changes which owners enter
the page; its native baseline still exhibits the identified missed-scan + final-
queue-position delay. Re-enable this exact approved ordering under R20 for one
controlled comparison; no new priority or fairness rule.74composed safety cases
and static checks passed. Active outcome and rollback condition tracked in M5.
