# F18-R12 — Independent book and price fixture publication

สถานะ: Approved — owner approved R12 on 2026-10-28

## Evidence and problem

W1r21 with approved R10 and source-clock SQL still failed its60s cycle. The
follow-up r10-clock-trace diagnostic failed baseline (not a reproduction of the
same measured failure), recording701source deferrals:610at read_inputs readiness
and91at BookState.require_ready. Its1085retained book commit intervals included
43over1s, maximum3.641188s. This establishes actual source gaps in the diagnostic,
not the precise cause of every earlier defer. No capacity/SLA pass is claimed.

Fixture.publish currently awaits book publication, then price publication and
price-frame evidence recording, before the next book tick. Price publication
uses the exclusive financial publication fence. A stalled price phase therefore
also delays the independent book source. Existing per-source1s gates correctly
refuse such stale inputs; do not relax them or change retry delays.

## Proposed scope

Allow the integrated F18 test fixture to run two supervised asynchronous tasks
inside the existing API/Paper container and event loop: one serial book/trade
publisher and one serial BTC/ETH price publisher. This changes fixture publication
scheduling only; it does not change the production financial fence or matching.
Reuse existing f15.publish_market(update_price=False), publish_input, renew_writer,
write_price, source acquisition, immutable evidence and worker supervision patterns.

- Each source retains its own ordered10Hz schedule, writer lease, monotonic input
  or trade IDs and native freshness checks. No concurrent writers to one source.
- Reuse the existing market engine/pool and aggregate4CPU/2GiB,10Paper+1risk.
  No new process, worker, connection-pool limit or resource allocation.
- Price BTC/ETH frame ordering and every committed frame remain unchanged; no
  coalescing, dropping or fabricating price inputs. Book/price are separate
  committed sources already; do not invent a cross-source atomic guarantee.
- Existing deterministic scenario controls, partial-fill quantities, price-gap
  fault duration and book/trade continuity remain authoritative. Record each
  source's actual publication and readiness times independently.
- Both tasks must be supervised: failure of either fails the fixture and stops
  both; cancellation joins both; no orphan publisher or false success.
- Keep R10 an explicit experiment and R11off initially. No application-default
  change, source lease reacquisition change, retry change or Live order.
- Keep all deadlines, rates,600/300/1800s,W4, resource and financial/SLA gates.
  Book independence may help, but price/monitor contention may remain and must
  still fail acceptance if outside its criteria.

## Verification and rollback

Focused tests: blocked price transaction does not serialize book ticks; single
writer/order guarantees for each source; propagation of each task failure;
cleanup/cancellation; price suspension preserves book progress and correct
readiness; existing partial-fill/breach/reset/correction/fault oracles unchanged.
These tests validate scheduling/supervision, not capacity. Then one bounded
comparison for source gaps and real defer causes; only if justified run native
W1, followed by W2/W3 only on pass. W4/full regression evidence is reused only
where unaffected. Preserve all failed artifacts. Revert scheduling if it adds
ordering/supervision failures or does not help; never weaken acceptance gates.

## Approval boundary

This is a new publication scheduling method, beyond the equivalent SQL tuning
and R6–R11. plan.md section5 says “ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md
forbids implementing a different approved-plan method before owner approval.
Approval is requested for this specific experiment, not prior authorized work.
Owner approved this experiment before implementation. Application defaults remain
unchanged and F18 remains Failed/Pending Full Validation until the gates pass.
