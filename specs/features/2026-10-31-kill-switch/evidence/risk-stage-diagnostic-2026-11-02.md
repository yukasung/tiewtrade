# NC-F19-18 — risk-stage diagnostic

สถานะ: **Observation complete / Non-acceptance — 2026-11-02**

Owner approved `approve NC-F19-18`. Harness-only stage/transaction/commit observers
were implemented and checked; no production/API/schema/resource/threshold change.
Targeted regression116 passed/30.788s, frozen Linux38 passed/22.555s, zero skips.
Ruff/format and mypy on affected modules passed, including after the report-only
correction described below. No commit/push/CI or Live activity.

## Run and coverage

One diagnostic only: fresh DB `tiewtrade_f18_release_set5_nc18_r1`, NC17 barrier,
core100×20baseline,10commands/s,10paper workers/monitor4,child5Hz, original pools,
PG4CPU/3GiB, VM3043373056bytes/8CPUs, uncapped runner. Candidate based on2322d86:
runtime hash `03e4bb431cc77fafbcf55ce9f457446a10f8790707a061a341a7a3a0a0ce29b4`.
Frozen source `/tmp/tiewtrade-set5-nc18-candidate-20261102` is retained.

Runner00:25:30.514982→00:32:56.940775 Bangkok on2026-11-02 (~7m26s), exit0/no runner OOM.
Setup141.511s; observation300.392s with W1 profile duration still600s. Manifest and
diagnostic declare `acceptance_result=false`. Dedicated LOSS→RESET/opening blocked
and scheduled one-shot/stop/resume complete.100 scheduled RESETs APPLIED by cutoff.

Counters at deliberate cutoff:2972offered/2954admitted+completed/0rejected,582completed
cycles. In-flight/remaining cycles were cancelled/joined, not successful acceptance.
552 sampled ready inputs remain unacknowledged at shutdown. This does not establish
their eventual latency and cannot be presented as W1 SLA coverage.

All13 observer streams CLOSED without truncation:22547 owner spans/234 measured rounds,
32086 risk-process transactions,24920 commit-proof records; collector row count exactly
matches proof totals.23648 proofs VERIFIED;1272 UNKNOWN due writer-xmin/current-XID
mismatch. No mismatch was accepted by guessing parent/subtransaction identity.
Some paper paths use savepoints; old/probe evidence does not prove a parent/sub-XID
mapping, so UNKNOWN remains.23,648 verified client delays are nonnegative.

## What the trace establishes

Offline analysis samples451280 nominal-window inputs:933 observed>3s,0observed>5s,
155 late acknowledgement groups.915late samples first qualify in risk telemetry,
18in paper telemetry.150 risk-monitor groups have linked span/round/transaction budgets.
Stage trace is not available for every paper or non-monitor risk transaction.

**A measured sufficient cause of real3s SLA misses is the100-owner page queued behind
4 semaphore slots plus waiting for the entire round before reselection.** It is not
necessary to assume slow SQL or inaccurate client timestamps for the example below.

Owner `5b96062b-c9a0-4e22-abf1-ed2500c05495`, attempt10129/round106:

| Component | Seconds |
|---|---:|
| Input ready→successful selection |0.188206|
| Selection→queue entry |0.011604|
| Semaphore wait |**3.161157**|
| Pool acquisition |0.013317|
| Owner lock |0.000890|
| Snapshot |0.012062|
| Replay including nested persistence |0.010731|
| Final-state verification |0.002690|
| Server commit→client observation |0.000940|
| Residual/session setup/other transaction work |~0.011032|

Ready17:29:57.976861 UTC→observed17:30:01.389490; client latency3.412629s,
verified server latency3.411689s. Round106 selects100, concurrency4, completes after
~3.24s.8 linked late groups have semaphore wait alone≥3s. This establishes a scheduling
queue violation in the instrumented workload, not merely correlation with lock logs.

Across150 linked groups, their oldest-input budgets total493.633s;481.189s (97.48%)
is before successful selection or waiting for a semaphore. These are overlapping
per-group latency budgets, **not CPU seconds**, and preselection includes prior failed
attempts.6 groups have same-owner lock timeout between input-ready and acknowledgement.

Example of deferral amplification: owner `15a46812-b269-4b61-a771-8ad870723874`,
round106 attempt10060 queues17:29:58.176407, receives slot17:30:00.063900, then
owner-lock timeout ends17:30:00.204112. It is next selected in107 at17:30:01.421627,
commits at17:30:01.466498; oldest input server latency4.513804s. A100ms lock failure
alone cannot explain this delay; queue/whole-round retry scheduling materially extends it.

Another owner has no same-owner timeout, commits near the end of195, is not selected
in196, then is selected in197 and records4.296651s server latency. The trace does not
distinguish whether196 omission is eligibility-at-snapshot or page LIMIT; it does show
no opportunity for reconsideration before the round barrier completes.

PostgreSQL logs show170 lock-timeout events during the measured interval;168 match
recorded risk transactions by backend PID/time (SQLSTATE55P03).2 remain unlinked.
No claim is made that every timeout or old NC17 hard miss has the same blocking writer.

## Measurement and overhead limits

- 148 of152 server-verified late groups remain>3s using actual commit time.4 groups/12
  samples cross3s only at client observation;3groups/18samples have UNKNOWN proof.
  No original NC17 verdict is regraded and no estimated delay is subtracted.
- Verified observation delay p50/p95/p99/max=0.004984/0.019768/0.042491/0.149723s.
- Observer risk-process flush time totals11.519s over setup+measurement; maximum
  observed event-loop delay0.094352s. These are process aggregates, not a controlled
  observer-free comparison; they cannot be assigned to a particular late input.
- The old NC17 hard5s violation did **not** reproduce. This run establishes actual3s
  queue misses; it does not prove that every old miss is explained or that a fix passes W1.
- Diagnostic JSON inherited the60s diagnostic field `scheduled_resets_not_exercised=true`.
  It is inaccurate for this300s run: raw reset journal proves100OFFERED/100APPLIED.
  Original artifact remains immutable. Corrected only future report metadata to use
  real progress/counters; no workload, deadline, stage or evaluator behavior changed,
  and no diagnostic rerun was performed for this reporting correction.
- Two asyncpg connection-termination CancelledError warnings occur at deliberate cutoff.
  All observer/pool files finalize, checked_out0 and database connections0 afterwards;
  no warning is hidden or interpreted as an acceptance pass.

Safety snapshot: duplicate fill execution0, duplicate RECORD position execution0,
negative reservations0 and negative position quantity/cost0. These are partial-run
checks, not full PnL/conservation acceptance. Task PG/Redis stopped with data retained.

## Artifacts and next checkpoint

`validation-artifacts/f19-set5-20261101/`: `nc18-r1/`, `nc18-analysis/analyze.py` and
derived latency budgets/coverage/server-log linkage/closure/safety records; candidate
and resource inventory; test XML/logs; container outcome;52,678,912-byte DB dump+SHA256.
`nc18-command.json` preserves image/command/network/candidate and env-file path only;
`nc18-analysis/raw-sha256.json` fingerprints the raw files. Reproduce analysis with:

```sh
backend/.venv/bin/python validation-artifacts/f19-set5-20261101/nc18-analysis/analyze.py
```

Recommend NC-F19-19: bounded rolling admission to available monitor slots, using the
same owner evaluation transaction and fairness cursor. Its production scope, invariants,
tests and rollback are proposed in plan.md; separate owner approval is required before
production edits or W1. No further diagnostic/W1/W2/W3/W4 was started. V-20 remains
Failed/Pending Full Validation; dependency gates remain unchanged.
