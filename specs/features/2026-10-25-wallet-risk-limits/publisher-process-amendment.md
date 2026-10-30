# F18-R31 — isolate fixture publication from the command-driver event loop

สถานะ: Approved — owner replied “approve” on 2026-10-29
วันที่: 2026-10-29

## Evidence and single hypothesis

The ONE approved backend/loop diagnostic is `r30-source-waits-20261029` under the
existing artifact root; full evidence/candidate hash is in
[evidence/m5-final-candidate.md](evidence/m5-final-candidate.md).
100owners×20orders, R10+R22, monitor4 and existing allocation remained unchanged.
Price committed158fresh observations/pair and book268inputs in60s:2.633Hz/4.467Hz,
below10Hz. Completed price cycles averaged373.248ms.

The independent read-only observer collected2465samples. Correlation retained
5ms boundary guards, backend PID and query-start/state-change timestamps. It found
actual advisory-lock waits AND client-side waiting: BOOKcycle3076ROLE_CHECK took
106.486ms, with its backend already idle-in-transaction/ClientRead at a sample
95.13ms before client completion. PRICEcycle3201PRICE_WRITE took72.603ms and had
post-start idle observations while the publisher heartbeat was delayed89.57ms.
124non-fence query intervals had a post-start idle observation. This is evidence
of a client-resumption component, not proof that all latency is CPU scheduling.
Heartbeat lag p9535.682ms/max131.547ms; observer roundtrip p950.005690s.
Parent CPU2.966/3cores and533/574throttled periods corroborate pressure but are not
per-query latency. Some SQL intervals have no sample and must remain unexplained.

**Hypothesis:** sharing the publisher event loop with API/command-cycle orchestration
adds avoidable client-resumption delay across many sequential awaits. A dedicated
publisher process within the SAME parent cgroup may reduce that component. It will
still share the3CPU quota with API/Paper; this proposal does not solve or eliminate
financial advisory-lock waiting, guarantee10Hz, or guarantee acceptance.

## One proposed change and reuse

Move the existing supervised BOOK/PRICE tasks into ONE fixture-only child process;
retain both serial source loops and their native storage calls. Reuse:
- `tests/infra/risk_limits/profile_workload.py`: Fixture.publish, _publish_books,
  _publish_prices, source_receipt and existing fault/scenario/control semantics.
- `tests/infra/execution_market/profile_workload.py`: acquire_sources,
  publish_market(update_price=False), worker environment/PID/supervision patterns.
- Native `realtime_storage`/`order_book_storage` calls unchanged; no SQL batching,
  cache, lease/fence/role/catalog-check deletion or financial schema/API change.
- Existing SourceTimeline/PID/heartbeat/wait observer, commit receipt formats,
  phase journal, pool/resource inventory and final drain checks.

Extract only the publisher state needed for those loops rather than instantiate a
second complete Fixture (which would duplicate unrelated engines/output writers).
The child owns the source leases, price cursor/identities and MARKET_DATA pool;
the parent retains MARKET_DATA access needed by overflow/recovery. Split the existing
15-connection MARKET_DATA ceiling into publisher3 (pool3/overflow0) and parent12
(pool5/overflow7), rather than duplicating15 in each process. Both inline baseline
and child candidate use this SAME split, so process placement is the comparison
variable. No engine/connection crosses process boundaries. Diagnostic observer
connection remains explicitly counted on both comparison configurations. Include
this pool partition in the approved method change and test exhaustion/cleanup.

Add a bounded local IPC control/receipt channel. Versioned controls cover price,
ask quantity, finish_partial, price-suspension deadline, measurement start and stop.
Preserve ordering with acknowledgement before dependent scenario actions; no
scenario may proceed against an unacknowledged value. Use existing Money/Quantity
serialization, never float conversions or new financial rounding. Relative fault
windows retain their original start/deadline, not IPC-delivery time. Command
results, source commit IDs/timestamps, readiness and last-frame statistics remain
available to the parent. Preserve every commit receipt; bounded-channel overflow
must backpressure/fail explicitly, never drop/coalesce a frame or fabricate10Hz.
Classify receipts by original commit timestamp and phase boundaries, not arrival.

On normal stop, finish/ack in-flight publications and all evidence before final
risk drain. On child/IPC failure, fail workload and join/terminate sources safely;
no silent child restart or duplicate writer. Recovery/restart generation and
price-gap semantics stay as approved. Include child PID/RSS/CPU/connections in
existing complete resource inventory; do not hide its usage in an external host
process. Keep10Paper+1risk workers; this adds one test-fixture process only.

## Unchanged constraints and rollback

Aggregate app4CPU/2GiB: API/Paper group3CPU1536MiB, risk1CPU512MiB, monitor4.
Same PostgreSQL/Redis,100×20, source10Hz, R25–R29, deadlines/fault schedule,
financial safety, freshness/authentication, minimum windows and no Live orders.
No CPU pinning/priority increase or allocation change in this experiment.
Switch between original inline and child publisher for a controlled comparison;
no other variable may change. Do not enable the child path for acceptance until
its targeted safety/supervision tests and source-load gate pass.

## Tests and one controlled comparison

Before any timing trial: control ordering/ack and timeout; no simultaneous duplicate
writer; monotonic IDs and full receipts; publication fence/lease-loss rollback;
transient breach and latch; unchanged partial fills/quantities; price-gap recovery;
child death/channel saturation; graceful stop with committed tail; final baseline
readiness; no orphan/PID/connection leak; affected lint/types/architecture checks.

Then freeze one implementation containing both modes and identical instrumentation.
Run one inline baseline and one child candidate sequentially with100×20 and the
same bounded60s W2 input plan/resources; current differing instrumentation results
are NOT substituted as the before sample. Stop if a safety failure or invalid
measurement prevents comparison; do not rerun hoping to pass. Judge source commit
cadence, client idle-to-return intervals, heartbeat lag and command/stop progress,
not just averages. If evidence does not support the hypothesis, keep failed results
and restore inline mode; no automatic second tuning experiment.

Estimate after approval: implementation/targeted checks25–40min, two sequential
setup+60s sets8–12min, analysis5–10min (~38–62min, not a completion promise).
Announce revised estimate before overruns. This is a bounded alternative to more
unfocused tracing. W1–W4 remain a later checkpoint, not part of this trial.
Any publisher-path change invalidates source-dependent W1–W3 evidence; historical
W1 is retained but is not certification of the changed load path. W4/regression
reuse is determined by actual dependencies. F18 remains Pending Full Validation.

## Approval boundary

R12 explicitly specifies the existing event loop and “No new process, worker,
connection-pool limit or resource allocation.” R31 changes only the process/event-
loop part of that method. plan.md requires “ขอ plan amendment ก่อนเปลี่ยนวิธี” and
AGENTS.md forbids implementing a different method before approval. Owner approved this specific process/pool-partition experiment on 2026-10-29.
Prior approvals remain valid.

## Approved execution exception after baseline setup failure — owner approved 2026-10-29

The first R31 inline baseline failed during setup at14:32:17.905UTC with native
`SourceUnavailableError` in book publication, before MEASURED_WINDOW. Its captured
setup bucket includes a1.033938s DB_CLOCK roundtrip. Both CPU throttling and host
paging were present; attribution is incomplete. No child workload was launched,
no automatic retry occurred, and the original stop rule was honored. Tests/static
passed; the process hypothesis itself remains untested.

Propose ONE child-only60s diagnostic on the already-frozen candidate
77cd04dd9be4477279b444d096e4571b525fc18dcf055b8f8b2039a301a31c10,
using the prepared empty child database and same resources/instrumentation/load.
Do NOT rerun inline. This changes the paired-comparison execution rule only; no
code, financial rule, freshness, rate, SLA or allocation change. Because there is
no valid same-window baseline, report child feasibility/source-load gate results
only; make no speedup/causality claim. Stop on setup/source/safety failure, preserve
unfinished inputs and cleanup evidence. If the60s window completes, inspect every
source commitment, query/loop observation, control/stop progress and errors; never
call it W1/W2 acceptance. No further workload or tuning follows automatically.
Estimate6–10min including setup/60s/analysis. Owner approved this exception on
2026-10-29 after the paired trial stopped. Prior R31 implementation approval remains
valid. Keep inline default and child diagnostic-only, with F18 Pending Full Validation.
