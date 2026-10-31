# F18-R10 — bounded admission priority alternating with R8 fairness

สถานะ: **Approved** — เจ้าของตอบ “อนุมัติ R10” วันที่2026-10-28 ก่อน implementation
วันที่: 2026-10-28

## Evidence and hypothesis

The owner authorized analysis and repair of the remaining W1 progress finding.
External timing instrumentation ran alone on fresh0056 with both bootstrap scripts,
100owners×20baseline orders,10Paper+1risk,4CPU/2GiB and R8 selection (R9 disabled).
No domain code, financial calculation, claim budget, rate or per-owner60s changed.
The diagnostic's outer65s cap only bounded observation and is not acceptance.

`engine-timing/failure.json`: full2000baseline and partial-loss0.05 oracle passed;
original owner60s expired during reseed,455completed/73cycles. Preserve Failed.
Twelve completed selected-owner reseed requests have matched PostgreSQL commit
and external claim/transaction timestamps (`selected-breakdown.json`):

| Interval | Median |
|---|---:|
| Request commit → bridge commit |229.97ms|
| Bridge commit → successful native claim function start |2699.03ms|
| Claim transaction |7.32ms|
| Native process function |196.74ms|
| Native process transaction including connection/commit |234.17ms|
| SQL inside process transaction |166.51ms|
| Commit/close acknowledgement |1.64ms|
| Bridge commit → engine result commit |2988.22ms|

Medians are separate summaries, not additive components of one representative
request. Instrumentation adds overhead; these are diagnostic observations, not
SLA/capacity proof. Existing uninstrumented W1r17 likewise had1809.8ms median
bridge→result for18reseed results. No queue loss or financial defect is inferred.

Matching completed2467transactions in approximately60s across100owners; its
normal fairness pass therefore has an order-of-seconds service interval. R9
only substituted within an owner's original global position and failed actual
W1. Another within-owner-only retry has no supported reason to succeed.

Hypothesis: bound admission queueing with alternate priority rounds, while
continuing every other native round under exact R8 owner fairness. This changes
global selection order and requires approval. It does not establish that
processing capacity, p95/p99, monitor1s or any full gate will pass.

## Proposed bounded method

1. Opt-in F18 runtime/harness only, initially disabled. Standalone F15/default
   functions retain existing selection. Same10Paper+1risk,4CPU/2GiB,pools,tick,
  20returned candidate hints/1successful claim per phase, rates and all gates.
2. Each Paper process starts its native matching sequence with an exact R8
   round, then alternates R8 / admission-priority / R8 / admission-priority.
   Manual intake phase remains unchanged. Advance the phase on every attempted
   native round, including scan failure, skip, defer and processing error; do
   not advance it on successful admissions only. Restart starts R8 and never
   clears a persisted R9 preference guard. No extra work or parallel phase.
   This bounds priority attempts to one between two normal fairness attempts;
   it is not a claim that half of successful claims or CPU time are guaranteed.
3. In a priority round, derive the original eligible head per owner first, using
   the same R8 due/lease/busy ordering and exclusions. Reuse R9 eligibility:
   head is an admitted active NEW; earliest unfinished due command is NEW in
   same episode/pair; configured/unlatched READY nonpending hints; no due CANCEL
   or unknown hint for that owner; unused original(head_id,due_at) guard.
4. Rank qualifying preferred owner heads ahead of ordinary heads **before**
   limiting the returned hints to20. Within each group retain original head
   next_attempt_at/command_id order. The DB still reads routing/status metadata
   only. Owner heads not qualifying for preference retain original candidates;
   if none qualifies, returned selection is R8. Do not just reorder the old
   first20heads, which leaves excluded owners' queueing unchanged.
5. Reuse R9 canonical owner-locked proof, original/candidate due CAS and atomic
   one-preference-per-anchor guard unchanged. It never proves cross-owner
   global rank, and must continue proving the original head and earliest
   unfinished candidate **within** the owner. Stale hint returnsNone and uses
   bounded fallback; no second successful claim in that phase. No new scanner
   privilege, financial hint, lease or scheduling write is introduced.
6. Priority can delay another owner's service until a normal round; normal
   R8 rounds continue every other attempt to prevent starvation. Within-owner
   due CANCEL suppresses preference and a failed preferred NEW cannot consume
   the same anchor again. Pending reductions retain FIFO within their owner
   and all existing unavailable-risk SELL/cancel paths. Add explicit
   cross-owner cancel/reduction/resting progress tests under a sustained stream
   of qualifying NEWs; do not claim that cross-owner cancellation is instant.
7. Selected NEW invokes unchanged admission, matching checkpoint, per-input
   financial/risk fences, FIFO/eligible_at, source freshness, UUIDs, fees,
   quantities, ledger and position transitions. No merged/skipped input or fact,
   bypassed authorisation, per-transaction work increase or automatic retry.
8. Reuse0056routing metadata/guard; no schema change expected. Preserve existing
   R9 default/per-owner selector behavior for its callers/tests. Expose this
   priority mode explicitly, rather than silently redefining R9's bool. Keep
   production/harness phase selection and manifests consistent using existing
   engine composition patterns, without a new scheduling framework.
9. Enable the experimental runtime/harness option only after affected real-DB
   safety and composition pass. Run uninstrumented frozen60s progress and fresh
   full W1; only if W1 passes continue W2→W3 sequentially. If it does not help or
   introduces safety/fairness regression, disable back to R8, preserve failures
   and stop changing selection methods without another approved amendment.

## Required evidence

- Existing R9 claim/CAS/FIFO/owner/episode/lease/rollback/lost-ack guards and
  unavailable-risk SELL/cancel/stop/reset/financial oracles pass unchanged.
- New selector ordering checks cover an owner outside original first20,
  earliest other-pair NEW, due CANCEL, unknown/stale risk hints, guard used,
  two workers and expired claim. Original R9 cross-owner order remains intact
  when this separate priority mode is not requested.
- Runtime/harness start R8, alternate on success/failure/skip/defer, and start
  R8 again after restart with existing guard retained. Multi-owner sustained
  NEW must leave normal/resting/cancel/reduction progress, no duplicate order,
  extra claim, lost fact or financial difference. Default F15 remains unchanged.
- Targeted safety/static checks cover changed dependencies. Reuse3675full
  regression where still valid; expand/full rerun only if actual impact demands.
- Uninstrumented acceptance retains100×20,10Hz,10/100/10rates,W1/W2/W3
 600/300/1800s,60sprogress,p95≤250ms,p99≤1s,eachREADYevaluation≤1s and all
  financial/resource/fault gates. No diagnostic/test/workload overlaps.
- Preserve W1r13–r17 and timing failures; no capacity/Completed/activation claim
  from a diagnostic or partial test. V22/V23 dependencies remain pending.

## Approval boundary

R9 kept original cross-owner head order. This proposal changes that order on
alternate attempts, so it is a new selection method, not reapproval of R6–R9.
Plan§5 requires “ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md prohibits coding a
method different from the approved plan before approval. Requirements, trading
rules and financial gates are unchanged. Owner explicitly approved this method before implementation. Existing approved repairs and refactor remain valid.


## Experiment evidence — 2026-10-28

Implemented/reviewed with253affected safety tests and enabled26composition
tests passing; frozen60s scenario passed43.4648s. W1r18 completed all3planned
risk scenarios, then Failed/Partial on a later owner60s cycle at172.5measured
seconds (1626completed/312cycles). FullW1notpassed; W2W3notrun. Experiment
option disabled back toR8 after diagnosis, disabled26tests/static/types/import
checks passed. Source-freshness errors observed in a later diagnostic do not
prove the exception behind the earlier delayedSELL. No retry/freshness protocol
was altered. Complete history/limitations and final source in
[M5](evidence/m5-final-candidate.md#r10-final-experiment-checkpoint--2026-10-28).
