# F15 publisher heartbeat and R8 latency diagnosis

สถานะ: **Approved A — implementation, first diagnostic and one replacement**
วันที่: 2026-11-06

## Owner decision

Owner approved option A: add an explicit standalone, test-only heartbeat option, verify
its safety, and run one bounded R8 diagnostic defined below. Stop to report the
diagnostic before proposing a performance fix or another full W1. This proposal
does not authorize production changes, a full W1 retry, W2/W3, or Git publication.

Option B: retain the existing publisher unchanged and run the same bounded R8
diagnostic with heartbeat disabled. This isolates existing runtime timings but
leaves its known heartbeat/price-update coupling in place. It cannot validate a
heartbeat fix or guarantee reproduction of the late publisher failure.

## Evidence and limits

The approved R8 trial prepared the full2000-order baseline and reached2021cycles,
then failed `WriterLeaseLost` during price renewal after1378.654s including setup.
The last persisted price receipt is04:59:40.393791UTC; feed lease ends
04:59:45.530089UTC; publisher failure host timestamp is04:59:46.760245UTC.
This is consistent with renewal lateness. The exact locked row/DB time, guard,
pool wait and query/commit durations at failure were not recorded; expiry is
not claimed as an independently captured exact guard result.

In `profile_workload.py::publish_market`, book renewal happens each tick while
price renewal occurs only when `update_price` is true. Under measured10Hz target,
that branch occurs once in10ticks; ten slow ticks need not take one second.

Existing46015processing samples have p95=0.571253s versus the unchanged0.250s bound.
All20workers individually have observed p95 above0.250s (range0.546463–0.603312s).
These records have no pool/SQL/commit split, include the original full worker
recording scope and come from an incomplete run. They do not prove a warm-phase
acceptance result or identify a safe production optimization.

Evidence: [Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md),
[failure analysis](../2026-11-02-tp-sl/evidence/batch-20261106/r8-w1-failure-analysis.json),
[per-worker timing analysis](../2026-11-02-tp-sl/evidence/batch-20261106/r8-w1-worker-latency-analysis.json).

## A — scoped heartbeat implementation

Reuse the existing `infra/market_data/realtime_storage.py::renew_writer`; do not
change that function, lease duration, generation/owner checks, publication fence,
readiness policy, database roles/grants or transaction boundaries.

1. Add `--publisher-heartbeat-per-book` to the standalone parent CLI, default off.
   Forward an optional default-false keyword through `market_publisher` to
   `publish_market`. Other callers, including F18 publisher/restore, retain the
   original default and do not opt in implicitly.
2. In the existing transaction, preserve book-renewal and book-publication ordering.
   After `publish_input`, call `renew_writer` once when either this option is on
   or `update_price` is true. Then run the unchanged price-update branch only when
   `update_price` is true. Do not renew twice on a price-update tick.
3. A heartbeat changes writer liveness only. It must not write price observations,
   timestamps, trade IDs, revisions, reconciliation state or readiness flags.
   Stored price freshness continues to age normally. Keep price-update cadence,
   book cadence, payloads, financial math, command identities and liquidity unchanged.
4. An expired/stolen lease still raises and rolls back that transaction. Propagate
   the original failure through supervision. No reacquisition, retry, new generation,
   longer TTL, silent error suppression, separate heartbeat task/process or new pool.
5. Record `publisher_heartbeat_per_book` and the actual runtime in the manifest.
   R8+heartbeat uses `F15_STANDALONE_R8_HEARTBEAT_V1`; heartbeat off retains the
   approved `F15_STANDALONE_R8_OPTIN_V1` identifier. Keep the fixture/capability
   version/digest unchanged. Require R8 for this new standalone option so no
   unspecified runtime combination is introduced.

Extra renewals add SQL and may worsen contention. This is a test-harness liveness
proposal, not a performance fix or proof that the17-minute failure is resolved.
Pauses longer than the unchanged5s lease may still fail, as they should.

## Reuse for the bounded diagnosis

- `execution_market/profile_diagnostics.py::observe_workload/parent_observations/observe_worker`
  for explicit observation, cleanup, failure propagation and non-acceptance output.
- `risk_limits/profile_pool_timing.py::TransactionTrace/operation_scope/sample_database`
  for existing180s measured window, fixed SQL hashes, pool timing and read-only
  activity samples. Label the original `publish_market` call as a publisher phase
  using the existing context wrapper; do not add diagnostic SQL to its transaction.
- `risk_limits/profile_dispatch_timing.py::traced_worker` and
  `profile_resources.py::worker_pool_evidence` for worker phases/claims/pools.
- `profile_workload.py`'s existing SMOKE phase, baseline setup, scheduling, oracle,
  publisher supervision, drain and shutdown. Do not copy its financial workflow.
- Existing lease-expiry/row-lock/generation tests in
  `tests/infra/market_data/test_realtime_storage.py`, supervision and opt-in/config
  tests in `tests/infra/execution_market/`, and shared R8 safety tests.

Extend the observer's explicit phase allowlist to include SMOKE. Keep the default
non-diagnostic path unchanged. Retain existing trace bounds (180s,100000transaction
rows per process, existing query-hash bounds); lost/truncated evidence is an
incomplete diagnostic, never silently sampled away to claim success.

## Approved diagnostic envelope — not W1 acceptance

One fresh schema0064 database; verify all8role URLs and actual databases before
load. Use100owners,20baseline orders each,20workers, scan20/claim1, existing20ms
tick,10commands/s, and6positive cycles per owner through existing SMOKE scheduling.
This is3000commands/600cycles, nominal300s measured plus original drain/cleanup.
The first180measured seconds have the existing transaction/activity traces.
No deliberate faults or extra load phases. Instrumented timing cannot be used as
an uninstrumented before/after speedup or full W1 pass.

Approved argv after targeted checks:

```text
python -m tests.infra.execution_market.profile_workload
  --phase SMOKE --owners 100 --baseline-orders 20 --cycles-per-owner 6
  --rate 10 --workers 20 --r8-claim-budget --diagnostics
  --publisher-heartbeat-per-book --output <new-evidence-directory>
```

For option B only, omit `--publisher-heartbeat-per-book`. Announce approximately
10–15minutes including baseline and cleanup before starting. Preserve the original
60s cycle bound, complete6-cycle oracle and processing/resource thresholds; a
failure stays Failed/Partial. Always write `acceptance_result=false`, even if all
smoke assertions pass. The owner approved this diagnostic envelope. It does
not replace or shorten any approved W1/W2/W3/W4 criterion.

Do not use a shorter diagnostic to claim the late publisher failure reproduced or
resolved. Its purpose is to expose pool/query/worker/source timing under the same
owner count, resting-order load and command rate before another expensive trial.

## Required checks and decision gates

1. Targeted tests before the diagnostic (estimated1–3minutes):
   - Default path retains its original renewal calls and F18/restore callers.
   - Enabled book-only tick renews liveness without changing any price fact or
     its freshness; price-update tick renews exactly once and writes once.
   - Real PostgreSQL expired/stolen generation and expiry-after-lock-wait cases
     still fail closed. Controlled expiry test does not require a long load run.
   - Failed renewal rolls back new book/price work; supervision propagates the
     original error, joins tasks and retains pending commands for inspection.
   - CLI/manifest/defaults and R8 constraint agree; worker configuration and
     credential filtering remain unchanged across restart/recovery.
   - SMOKE observers are non-accepting, respect bounds, restore patches/listeners
     and close pools on success/failure/cancellation; no payloads or secrets logged.
   - Reuse unaffected financial/claim/reset/retry evidence; rerun relevant safety
     cases if the touched publisher path affects them. Relevant Ruff/format/mypy.
2. Review the scoped harness diff; no source optimization outside this plan.
3. Run exactly one diagnostic above, then stop and report:
   - Original failure or completed diagnostic, workload counts and financial checks.
   - Publisher and worker pool wait, connection-held duration and SQL-hash totals,
     grouped by processing/claim/poll/publisher phases. Client SQL duration includes
     possible server/network/lock waits. Do not label residual time as commit time
     without separate evidence or sum overlapping process durations as wall time.
   - Mark uncaptured late phases, missing role metadata, interrupted queries,
     truncated evidence and cleanup warnings explicitly; report resource headroom.
4. Use that evidence to propose the smallest justified latency change, if needed.
   Any production/performance change, new runtime amendment, further diagnostic or
   full W1 needs a concrete reviewed plan and the owner's next decision. Do not
   automatically start W1 because the smoke/heartbeat tests pass.

## Acceptance and retained state

W1 remains Failed/Partial; W2/W3 remain Not Run; W4 Passed0064 is reused only where
its schema/fixture/recovery path is unchanged. NC-SET4-01 integrated coverage is
still open. No change to0.250s/1s processing limits,60s cycle/drain bounds, original
load/duration, financial oracles, Money/Quantity, owner locks, CAS, FIFO, lease
fencing, idempotency, Paper/Live isolation or business requirements is proposed.
Owner approval authorized the scoped harness implementation, targeted checks and
exactly one diagnostic above. It does not authorize any Git publication, full W1
retry or subsequent performance change. Implementation and that trial are complete;
the trial is Incomplete for the reason below, not a validation pass.

## Outcome and scoped observer repair — 2026-11-06

Heartbeat/config/safety implementation passed89targeted tests and relevant static
checks. The single diagnostic prepared2000baseline orders, then existing worker
observers raised3JSONDecodeErrors while activating from a partly written
`dispatch-trace-control.json`. Those exceptions reached claim handling and perturbed
the workload. The diagnostic was stopped via SIGINT to its exact parent, joining
workers and disposing engines through existing cleanup. Whole time440.559s;
captured transaction span100.142s, not the planned300s/180s observation envelope.

All21trace streams closed untruncated and all21pool reports finalized empty.
Post-stop no worker remained, only the read-only observer DB session; zero duplicate
fill effects/unlinked fills/negative reservations/positions/non-Paper activity.
No final counters/resources/full financial oracle was written after cancellation.
Original DB, logs, worker metrics, source hashes and partial traces are preserved.
No p95 optimization or historical lease-failure resolution is inferred from this
perturbed run. See the [Batch ledger](../2026-11-02-tp-sl/evidence/batch-20261106/README.md).

Within the authorized observer implementation scope, the control writer now uses
`publish_trace_control`: write the identical JSON to a temporary file in the same
directory and atomically replace the final path, reusing the existing runtime-PID
publication pattern. Strict readers/row bounds are unchanged; no parse-error
suppression, command retry, business/session state or shared helper rewrite.
Interrupted writes propagate without exposing a partial final control file.

Two deterministic regression cases force real Recorder/TransactionTrace readers
into the create-before-content interval; success/failure publication is safe.
Eight affected regression/integration cases passed, plus Ruff/format/scoped mypy.
Unchanged heartbeat/financial/fencing checks reuse the previous89-test evidence.
This metadata repair did not authorize or start a second diagnostic.

## Replacement diagnostic — Approved A 2026-11-06

Owner selected A in the latest instruction, superseding the earlier B stop choice.
No workload ran between those choices. This authorizes exactly one replacement
of the same diagnostic after the
observer metadata fix. Use a fresh database/output, verify all8role URLs/schema
and empty data, freeze final sources, and keep the exact100×20/6cycles/10commands/s/
20workers/R8/heartbeat/SMOKE/180s trace parameters above. Nominal300s measured,
approximately10–15minutes total. Keep the first attempt Incomplete; do not erase,
reset, retry its NEW commands, reuse its partially traded baseline, or label this
as a new full W1 acceptance run. Stop/report after the replacement, even on another
observer error. No performance changes, further runs or Git publication included.

Option B: stop workload experiments here, retaining heartbeat/metadata fixes and
all Failed/Incomplete/Pending results. No replacement or other workload is run.

NC-SET4-04 is closed by this explicit latest A decision. The original trial remains
Incomplete. Approval covers only this replacement with the same envelope and a
stop/report afterward; no performance fix, full W1, W2/W3 or Git publication.

### Replacement result — 2026-11-06

One authorized replacement finished in715.169s including setup/cleanup, measured
319.447s. All3000commands/600cycles and100owner financial oracles passed. Diagnostic
result remains Failed: p95processing469.526ms >250ms, input_lag22 >20. No control
JSON/lease/worker errors or cycle timeouts. All21streams/pools finalized, no workers
remain. The first180s trace and exact SQL-hash mapping identify DB round trips as
the dominant observed processing component, not a proven specific optimization.
See Batch evidence for client-timing/lag-tail limitations. Both trials and all
original W1 failures remain. This authorization is consumed; stop/report before
any new plan implementation, performance change, further run or Git publication.
