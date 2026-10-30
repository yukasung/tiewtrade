# F18-R11 — one bounded probe after source publication resumes

สถานะ: **Approved** — เจ้าของอนุมัติ R11 ใน conversation 2026-10-28
วันที่: 2026-10-28

## Evidence and limits

The owner authorized retry tracing before choosing another repair. Application
source remains R8, both R9/R10 runtime flags false. Observational helpers are
outside the repository; no financial/source/retry rule was changed.

Real-role minimal reproduction (`controlled-sell-retry/result.json`) used an
actual funded Paper wallet, native SELL, ordinary claims/rollback/defer and
unchanged SourceUnavailable handling. Execution-book verification was deliberately
paused; the writer lease and latest-trade prices remained healthy through normal
public APIs. Fresh verified books resumed7.018s after the first failure.

| Observed outcome | Result |
|---|---:|
| Persisted defer after failures1/2/3 |0.978s /4.986s /29.987s|
| SELL success |36.555s|
| Elapsed after verified-book publication resumed |29.454s|
| Order headers for that command |1|
| Additional SELL fill / cash / held change |none|

This proves that existing backoff can retain a pending SELL long after source
publication resumes. It is a controlled reproduction, **not proof of the exact
exception for W1r18's39.86sSELL**, and not capacity/SLA acceptance. Broad tracing
and fresh W1 replays stopped before the relevant SELL; all failed/aborted logs
remain. The original delayed SELL's historical exception was not logged and
cannot be recovered from claim_revision alone.

The trace also observed source ages crossing1s during reads/processing and slow
publisher operations. Those observations do not isolate a single publisher or
host cause. This proposal addresses the demonstrated post-resumption scheduling
wait; it does not claim to solve producer throughput/freshness failures.

## Proposed method

1. Optional Paper source-resumption mode, defaultfalse including standaloneF15.
   Introduce no worker, extra phase, automatic in-transaction retry, network call,
   changed price rule, input skip/coalescing or financial calculation. Keep
   10Paper+1risk,4CPU/2GiB,pools,tick,20hints/1successfulclaim perphase and all
   original rates/deadlines/SLA/resource/financial gates.
2. Preserve normal1s/5s/30s/5m backoff exactly. Only the existing
   `except SourceUnavailableError` branch may mark a source wait, in the same
   fenced CAS transaction that defers the claim after its processing rollback.
   Generic DB errors, financial conflicts, lost claims and unknown errors do not
   acquire a new source-wait marker. No message-string classification.
3. Add only reconstructible nonfinancial dispatch metadata in0057:
   `source_wait_since` timestamp, `source_wait_revision` matching the failed
   claim_revision, `source_resume_used` boolean and `source_resume_claim` boolean.
   No monetary/source payload is copied. ENGINE writes; SCAN reads only required
   status/version fields and narrow public market publication metadata.
4. A future scheduled NEW may receive **at most one extra probe per failure
   streak** when both its execution book verification and last-trade quote
   publication have advanced after source_wait_since. Use the canonical pair,
   existing ready/connected/generation/lease/future-time sanity metadata as
   hints; do not invent a replacement freshness threshold. These hints are
   not proof of current tradability. Full execution/reference/risk gates run
   unchanged after claim, including1s book freshness and existing F10 rules.
   Missing/unknown metadata, due owner CANCEL or unknown owner hint suppresses
   the optional probe and retains ordinary dispatch.
5. Version-bind the wait marker: waiting PENDING state, attempts>0,
   source_wait_revision=claim_revision, unused guard, original future due time
   and original owner/pair/command identities must still match. Source-aware
   scans rank eligible probes using their failed-at time for owner ordering,
   while retaining the actual next_attempt_at for CAS. Return at most20hints.
   When the mode is off, legacy/R9/R10 queries/default behavior stay unchanged.
6. ENGINE rechecks canonical NEW identity/pair, source publication progress,
   wait revision, original due and unused guard under the existing owner lock.
   The successful claim atomically consumes the guard. Increment claim_revision
   and use a new claim token normally; **do not increment attempts for the
   extra probe**. Count it as that phase's one successful claim. An early head
   is claimed directly, not substituted through an R9 anchor whose original
   next_attempt_at is still in the future.
7. Cap the probe lease at min(normal30s lease, original next_attempt_at), so a
   crashed/lost-ack early probe cannot lease the job beyond its ordinary retry
   time. Keep the original next_attempt_at. A failed probe preserves that due
   time and failure count, clears its active probe kind but leaves the used
   guard consumed. It must not accelerate the command to5m, reset the failure
   streak, add another early probe or postpone its original retry schedule.
   If the lease expires, existing token/revision fencing rolls back stale work
   and the ordinary claim becomes eligible as before.
8. A healthy committed result/checkpoint/covered-pair reschedule resets the
   failure streak and its new metadata atomically. Source failures/defer/crash/
   rollback/ack loss must not clear the consumed guard. Wait revision prevents
   an old marker from authorizing a new claim. Old workers without this marker
   continue ordinary backoff; mixed-version execution may conservatively miss
   an optional probe, never manufacture one from an unknown/currently claimed
   request. Default-off queries continue working on0056; disable before downgrade.
9. No order is accepted or filled by the resumption hint. Ownership/episode,
   manual-use policy, stop/latch/reset, catalogue/constraints, cash/positions/
   reservations, FIFO/eligible_at, financial publication fence and immutable
   execution identity stay authoritative. Pending orders may execute earlier
   when the original full checks pass; this is the intended timing effect,
   not a guarantee of identical historical fill timestamps/prices.
10. Reuse existing due/claim/CAS/defer/finish functions, R9 recovery guards and
    source validators. No new scheduling framework or second financial path.
    Source-aware behavior must be explicit in runtime/harness/manifests. After
    affected safety passes, candidate qualification may reuse the already
    approved R10 alternation plus this mode: R10 is not being approved again.
    Production NEW activation remains closed until all required gates pass.
11. Run controlled comparison first: same7s verification gap, source resumption
    triggers one guarded probe without waiting for the old30s timer. If it does
    not help or regresses safety/fairness/resource use, disable toR8, preserve
    results and make no further method change without an approved amendment.
    Only after safety/progress proof run fresh uninstrumentedW1; W2→W3 only if
    fullW1passes. This proposal does not authorize increasing resources or
    relaxing any gate to obtain acceptance.

## Required validation

- Real PostgreSQL source-unavailable SELL with unchanged price/book rules,
  original persisted schedule and attempts; new-publication probe completes
  once, exact reservations/held/cash/fill/identity oracles and no duplicate order.
- Probe rejected/SourceUnavailable/generic DB failure, expired/very short lease,
  concurrent workers, rollback, commit-ack loss, crash before/after claim,
  stale wait revision/due, closed episode, stop/reset while waiting, unsupported
  or removed pair; a failed probe preserves the original normal retry time.
- No new book/price publication, only one feed progresses, invalid lease or
  generation, stale/corrupt input, unknown hint, due CANCEL, bounded reduction
  and normal other-owner progress. At most one successful claim perphase.
- Old/new writer overlap,0056default-off compatibility,0057up/down, narrow SCAN
  permissions (no amounts/payload/secrets/writes), restore of pending waits and
  consumed guards; financial/audit/baseline history unchanged.
- Targeted dependencies and static checks first; full regression when actual
  common-code impact requires it. Reuse unchanged evidence honestly. Recheck
  affected restore/grants on0057. No concurrent diagnostic/test/workload jobs.
- All acceptance gates unchanged:100×20,book/price10Hz,commands10/100/10/s,
  W1/W2/W3 600/300/1800s,owner60s,p95≤250ms,p99≤1s,everyREADYrisk evaluation≤1s,
  financial/source/resource/fault gates. Preserve all Failed/Partial history.

## Approval boundary

This adds an early claim outside the original scheduled backoff, so it is a
new retry method, not ordinary tracing or reapproval of R6–R10. F15plan239 says
“retries ใช้ backoff เดิม 1s/5s/30s/5m”; F18plan301 requires
“ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md79 forbids implementation differing
from the approved plan before approval. Owner approved this method on 2026-10-28 before implementation.
Requirements/business/financial rules remain unchanged.
