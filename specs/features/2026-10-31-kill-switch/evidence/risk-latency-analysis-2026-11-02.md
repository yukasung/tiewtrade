# NC17 risk latency — analysis of existing evidence

สถานะ: **Analysis recorded 2026-11-02 — root cause not yet established**

Scope authorized: inspect NC17 evidence/evaluator and prepare a separately approved
NC-F19-18 if attribution is insufficient. No production/harness behavior was changed,
no services started, no new tests/workload/W1 run. Original Failed verdict is retained.

## Evidence and independent reconstruction

Candidate source hash:
`dfd4cce5d4702afcb6dfee1e80347b6783bf035be0e1480201ede9ac1ec17a13`.
Raw evidence is `validation-artifacts/f19-set5-20261101/nc17-w1-r1/`.
Derived audit is `validation-artifacts/f19-set5-20261101/risk-latency-audit-20261102/`.

`audit.py` independently builds increasing acknowledged frontiers per owner and
binary-searches the first qualifying non-pending acknowledgement for each input.
It does not invoke `sla_summary` or overwrite its output. The full set of late
(owner/kind/input/ready/observed) identities matches all original1302 records;
expected918703, hard misses3, failed owner quotas56 also match. SHA256 of all21
raw files used by the audit is unchanged before/after analysis.

- All11 acknowledgement streams are timestamp-ordered; measured input duplicates0,
  price cursor-order errors0, unacknowledged0, clock errors0. All stored acknowledgements
  have pending=false; absence of a pending record is not evidence that no rollback occurred.
- Measured price frames9162 ×100 owners plus2503 core financial boundaries =918703.
  Nominal load contributes902475 samples,1293 late/3 hard; drain contributes16228,
  9 late/0 hard. There are no setup-time measured samples by ready timestamp.
  This documents the existing measured-flag convention; it creates no new exemption.
  Excluding drain would not eliminate the load-period failures.
- The1302 late samples group into213 distinct owner/observed-time acknowledgements,
  **not213 proven transaction IDs**.1239 samples/201 groups first qualify in risk worker
  telemetry;63 samples/12 groups first qualify in paper worker telemetry. All are price
  inputs; there are no late financial-boundary samples in the supplied evidence.
- `telemetry()` records only after successful transaction context exit and checks final
  cursor/boundary/pending state before commit to handle savepoint rollback. Existing
  NC17 regression includes pending-replay and savepoint-rollback checks. Its timestamp
  remains a post-commit client observation, not an exact server commit timestamp.
  Historical acknowledgements lack transaction identity; restored xmin/commit times
  cannot recover the original commit times.

## Failure timelines

| Window from load start | Evidence | Limits of inference |
|---|---|---|
| +50..65s |360 late samples/55owners;11 PostgreSQL configured owner-advisory-lock timeouts;47 overlapping cycles; no RESET offered/completed in this window;45–47 sampled connections and sampled lock waits0 | Planned queued preparation+50/STOP+60 belongs to other owners. Stop journal lacks actual timestamps. Coarse resource samples do not rule out short lock waits. |
| +240..270s |426 late samples/77owners;25 owner-advisory-lock timeouts;76 overlapping cycles;58 RESET journal records overlap;45–50 sampled connections and sampled lock waits0 | RESET overlap is correlation. Existing logs cannot attribute each wait to a request, round or lock holder. |

Hard-limit input3069/3070/3071 for owner
`3baa7030-605b-4b29-a2fe-ef1d1da5fc47` committed ready at16:34:12.308923 UTC.
Previous acknowledgement cursor3068 was observed16:34:12.263526; next cursor3143
at16:34:17.343621, boundary473 unchanged. The acknowledgement gap is5.080095s;
input latency5.034698s. Owner cycle0 ran at+38.004..45.293s, cycle1 starts+87.996s;
this owner has no core cycle overlapping the hard-miss window. Its RESET is offered
at+257.630s. Open baseline orders still permit paper-worker activity while a user is idle.

NC17 barrier READY is16:35:11.702327, well after the hard miss. Its consumed input is1325
after captured book1323; it cannot cause the earlier miss. This does not exclude other
stop/harness activity or shared-resource contention as contributors.

Read-only Docker log inspection16:34:08..16:37:55 UTC finds137 lock-timeout errors.
All corresponding statement families match configured `lock_risk_owner` advisory-lock
acquisition. The derived log files retain timestamp/PID/classification/hash only, never
SQL/messages/parameters. Four backend PIDs recur in the hard window, but the old
acknowledgements do not map those PIDs to owner/round. No actor assignment is inferred
merely because the monitor pool also has four connections.

## Hypotheses and decision

| Hypothesis | Classification | Evidence / missing information |
|---|---|---|
| Duplicate inputs, unordered stream merge or omitted worker stream creates these misses | ตัดออกแล้วสำหรับ supplied trace | Independent earliest-ack reconstruction matches; all11 streams ordered, duplicate0. |
| Pending/savepoint statement execution was used as a successful acknowledgement | ไม่พบหลักฐานรองรับ; producer safeguards reviewed | Final-state read and post-commit emission are present and regression-covered; raw logs alone cannot prove every historical transaction lifecycle. |
| NC17 one-shot barrier caused hard5s miss | ตัดออกแล้ว | Hard miss occurs before barrier; owner identities differ. |
| Owner advisory-lock contention occurred during slow windows | ยืนยันแล้ว |137 whitelisted PostgreSQL lock-timeout errors, including11/25 in the two selected windows. |
| Repeated owner-lock deferral plus full-page scheduling causes the5s gap | หลักฐานไม่พอ; leading hypothesis | Monitor selects≤100 with semaphore4 and awaits the page before next round; no owner/round/queue/attempt spans or backend mapping in old trace. |
| Snapshot SQL, replay/serialization, pool queue or event-loop delay dominates tail | หลักฐานไม่พอ | Per-stage timings and commit observation delay absent. Paper p95 does not isolate owner-lock hold duration. |
| Client observation delay changes the hard/service verdict | หลักฐานไม่พอ | Exact transaction IDs/server commit times absent; never subtract an estimated delay. |

**Decision: do not choose a production fix yet.** There is concrete lock contention,
but not an attributable latency budget that identifies which code change removes
the service tail safely. No evaluator defect has been established and no verdict is
regraded. Submit NC-F19-18 for one bounded risk-stage diagnostic, with separate approval
before instrumentation/run. Preserve F19 quotas/hard bounds, and no W1 rerun.

## Reproduce the analysis

Run with the existing backend Python3.12 environment (no new dependencies):

```sh
backend/.venv/bin/python validation-artifacts/f19-set5-20261101/risk-latency-audit-20261102/audit.py
backend/.venv/bin/python validation-artifacts/f19-set5-20261101/risk-latency-audit-20261102/server_logs.py
```

The second command reads the retained stopped task PostgreSQL container logs only.
Outputs include summary, source hashes, late groups/samples, window inputs/acks/resources/
RESETs/planned stops and redacted server-lock classification. Docker-log attribution
remains limited if container logs are later removed. No API/schema/runtime changes,
commit/push, CI or Live activity occurred in this analysis checkpoint.
