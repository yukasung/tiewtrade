# W2 existing-evidence throughput analysis — 2026-11-07

Owner approved analysis of existing evidence only. No production/harness edits,
new tests, workload, migration, retry, threshold or service changes in this turn.
The only database access was read-only repeatable-read aggregation on the existing
isolated W1/W2 databases, with15s client/10s statement bounds. No credentials/payloads
were exported. Relevant current source hashes matched the campaign candidate.

## Findings

- W2 offered/admitted/completed12000 commands in963.571s; allowance660s. Effective
  cohort completion12.454commands/s. W1 passed3600commands in1800.965s at2/s.
- Each owner must finish a five-command cycle before its next cycle. W2 plans an
  owner cycle every5s (20owners ×5commands /20commands/s), but observed consecutive
  cycle starts average7.971s,p95=9.700s. All20owners have600HTTP records/120cycles;
  replay keys/command IDs match the preceding LIMIT operation. This explains how
  delayed cycles stretch total duration; it does not identify one expensive query.
- POST→acknowledgement mean:BUY121.5ms,LIMIT115.5ms,CANCEL64.7ms,SELL114.0ms.
  Ack→HttpIntake return mean:roughly290–300ms for non-replays. This includes250ms
  result polling and identity reads, and is NOT exact bridge execution duration.
- Mean gap after HttpIntake return until the next HTTP call:BUY2.248s,LIMIT0.967s,
  CANCEL0.844s. Source shows these within-cycle gaps wait for command/result and
  expected projection status. SELL→nextBUY2.285s also includes possible cycle pacing;
  it must not be attributed wholly to worker processing. Replay gap≈0.1ms.
- The cycle core (firstBUY start→lastSELL HttpIntake return) averages5.694s,
  already above the5s planned interval. It excludes finalSELL result/status wait,
  so is a lower bound on the complete cycle, not a complete execution metric.
- Poll gate acquisition mean≈0.7–0.8ms,p95≤2.5ms across measurement kinds. Held
  time means10–26ms. There is no evidence the4-permit queue is the dominant delay.
  These are concurrent operation sums, not additive elapsed time on a global path.
- Durable bridge completed_at−request recorded_at means81–142ms,p95≤254ms.
  All9600unique requests had bridge attempts=1;2400HTTP replay calls reuse requests.
  No pre-financial inbox retry amplification was found in these final rows.
- Command-result timestamp−request recorded_at means924–964ms,p95≈1.36–1.39s,
  versus265–332ms in W1. WARNING:command result completed_at defaults to now(),
  the transaction-start time; these are stored timestamp differences, not actual
  commit/processing-end measurements, and exclude separately observable fill waits.
- Engine transaction p95=364ms/p99=492ms passed the pilot ceiling but engine metric
  excludes full queue/wait/projection progression. Passing it does not certify20/s.
- Financial, position, resource and pool-return checks passed; no observer error.
  This does not exclude sub-sample transient contention or identify a slow statement.

## Scope of confidence and recommendation

Confirmed: W2's closed-loop cycle cannot maintain the intended5s owner schedule;
substantial delay remains after HTTP intake/bridge. Poll permit waits and bridge
retries do not explain the dominant observed delay. W1/W2 differ in workload, so
these observations are not an A/B test or a maximum-capacity certification.

Unresolved: exact division among worker scan/selection/coordinator hold/busy backoff,
claim transaction, processing, and projection/fill visibility. The runtime uses a
nonblocking coordinator plus250ms busy backoff and one successful claim per phase;
this is a candidate to measure, not a proven bottleneck. No dispatch/transaction
phase traces were enabled in the failed W2, so an exact SQL/lock fix is not justified.

Recommend one opt-in bounded worker-phase observation using the existing
risk_limits/profile_dispatch_timing.py::traced_worker/Recorder. Capture aggregate
scan/gate/selection/claim/process timings, explicit busy/acquired/skipped counts,
and active/pending/cancel work. Do not increase pool sizes/poll permits, change
worker count/coordination/backoff, relax throughput, or bypass safety based on this
analysis. Proposed§17 describes a concrete diagnostic scope requiring approval.

## Reproduction inputs/method

- offline-timing-summary.json for W1 and W2: group HTTP rows by owner, sort started,
  validate each five-command sequence via replay key/command identity, subtract
  existing monotonic timestamps. Poll rows filtered phase=measurement. Quantiles
  use nearest-rank ceil(q*n)−1; sums across owners overlap in wall time.
- offline-durable-timestamps.json for W1 and W2: read-only request/result/dispatch/
  command-result join, grouped NEW BUY/LIMIT SELL/MARKET SELL/CANCEL. Only numeric
  timing/count/attempt summaries saved. Request replay calls are intentionally not
  counted as newly durable requests. Timestamp caveat retained in JSON artifacts.
- Source:profile_workload.py cycle/run_scheduled_cycles;profile_http.py request;
  profile_parent_poll.py permit;services/engine/paper_order.py andmanual_order.py.

W2 remains Failed. Overflow/W3/fullW4 remain Not Run. No automatic new campaign.
