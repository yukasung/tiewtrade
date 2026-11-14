# Failure-only cycle timeline — 2026-11-14

Status: Diagnostic complete; original100 acceptance remains Failed. No W1 started.
[Machine receipt](failure-timeline-summary.json). Owner instructed starting this
investigation after three failed acceptance attempts. This is one bounded
observation, not a fourth acceptance attempt and not an automatic retry allowance.

## Implementation and checks

Harness-only opt-in failure_timeline for original100 SMOKE; default/profile/worker
and production untouched by this amendment. Reuses existing32phase cycle observer,
records32query fingerprint aggregates/16recent query timings in memory per active
cycle, discards completed cycles; no SQL text/parameters/error messages/row values.
Failure captures bounded existing worker metric tails and existing ENGINE_SCAN
queue reader after workers stop. No full SQL/dispatch trace or additional sampler.
Actual60s budget, nested timeout/external cancellation semantics and original
exceptions retained. Errors saving diagnostic receipt do not mask workload error.

Initial isolated suite98Passed/6Failed: old mocked Namespaces lacked new flag.
Changed optional selector read to defaultFalse; corrected33casesPassed. With four
new malformed-timing/receipt-error cases,108unique affected tests Passed overall,
including realDB scanner/worker observations. Final16focused cases/static4files
Passed. Mypy source resolution explicitly MYPYPATH=src. No assertions weakened.

## Observation

Preflight7/7Passed; source unchanged.671.267stotal includingpreflight/cleanup,
within1200s. FailedCycleBudgetExceededError;1161offered/admitted,1061completed,
175cycles,414fills,205cancels,221replays,0rejected,workerfailures0. Full final
financial/snapshot oracleNotRun. No accepted financial/performance conclusion.

One expired owner cycle(number1) captured without phase/query truncation:
- market BUY submit/wait:20.120s (receipt9.520s + FILLED10.549s).
- resting LIMIT submit/wait:9.869s (receipt9.715s, ACCEPTED0.102s).
- exact replay submit:0.015s; cancel submit0.060s.
- cancel receipt9.584s, CANCELED0.231s.
- market SELL submit/wait until expiry:20.089s (receipt9.284s + FILLED10.769s).

203parentqueries cumulative0.450s,slowest19.856ms.149parentpollattempts for this
cycle spent22.127s cumulative at gate and2.246s holding permits; single wait max
0.784s. Existing intentional250ms polling sleeps are additional time. These nested
phase/query/poll durations overlap; do not sum them as independent totals.
This proves cumulative multi-step latency, not one60s query or semaphore stall.

After workers stopped all four selected commands were TERMINAL, including last
SELL dispatch next_attempt_at56.7ms after cycle deadline (not itself a fill time).
Snapshot had2126PENDING across100owners and814TERMINAL. Public sources remained
READY at post-stop snapshot; this cannot prove readiness for every earlier tick.
All20worker metric tails captured; their last transaction completions range7.131s
before to1.364s after deadline. Partial2731processing samples p95/p99=390.616/
552.613ms; diagnostic-only, not acceptance, and no improvement claimed.

## Interpretation and next scope

The60s criterion fails from accumulated receipt/fill observation waits under100
owners. Evidence does not yet isolate worker scheduling/processing from parent
observation delay; query durations here cover parent queries only. Worker timing
samples are transactions, not a complete command-to-commit timeline. No proof yet
justifies pool expansion, semaphore changes, admission priority or a longer timer.

Next recommended engineering scope: correlate committed admission/fill timestamps
with first parent read for the same command/order, and inspect existing coordinated
selection fairness/backlog progression. Start with deterministic scheduler/polling
fixtures and existing evidence; propose the smallest supported correction with
safety/idempotency/concurrency tests before any acceptance rerun. Do not alter
money/risk/source-freshness rules, omit baseline orders or lower original100 SLA.
Stop/report after this authorized observation. No production edit/publication/merge
or additional timed campaign authorized by this receipt. V18Partial/Failed and
V19/V20 dependencies remain. F17 is not Completed.

## Evidence limits / cleanup

Raw evidence is preserved. The historical diagnostic-only receipt incorrectly
labels baseline_publisher_timing=true from configuration, while full tracing was
actually disabled (trace_seconds=0, no transaction traces). Corrected this metadata
selector after observation and16focused tests Passed; no timed rerun required for
this metadata-only correction. Historical file/hash retained, not rewritten.

Cleanup0connections/0advisorylocks; fixture DB dropped normally. Exact-label local
Redis is stopped/removed separately; owner PostgreSQL/Redis/app and gates unchanged.
No commit/push/merge. This closes the authorized diagnostic checkpoint only.

Final cleanup confirmed: exact-label dedicated Redis stopped normally and removed;
zero completion-prefixed DBs remain. Owner PostgreSQL and Redis remain running.
