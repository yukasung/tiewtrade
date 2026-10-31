# F18-R16 — Batched standalone monitor read snapshot

สถานะ: Approved — owner approved R16 on 2026-10-28

## Evidence and scope

R15 failed its bounded comparison and was rolled back to blocking/default20.
Metadata-only risk-process profiling found distributed SQL round-trip cost;
no CPU throttling or OOM was observed. It does not establish a capacity pass.
The stopped W1r23 database has100 READY evaluations, all replay_pending=false;
there is no evidence to exempt those owners from the existing SLA.
Removing the duplicate private replay owner-lock acquisition passed30 safety
tests; the public wrapper still holds the lock through replay/error handling.

Current standalone monitoring separately reads owner/setting, replay state,
boundaries, verified frames and authoritative position snapshot while holding
the same owner lock. This proposal reduces those database round trips, without
changing the replay algorithm or moving financial arithmetic into SQL.

## Proposed method

1. Only the standalone monitor uses a batched read, after the existing blocking
   owner lock is acquired in a prior statement. Preserve role verification,
   RLS, timeout settings, four active transactions, default20-owner scan,
   fairness cursor and20ms sleep. No reads before lock acquisition.
2. One PostgreSQL statement captures the owner/wallet/setting, owner replay
   state and committed publication watermark, ordered next21 financial markers,
   and a bounded frame page through that captured watermark (at most100 new
   frames plus the current cursor frame when needed). Read the exact current
   F14 position activity/projections and completeness proof in the same snapshot.
   No unbounded history payload or cross-owner state is returned.
3. Extract and reuse existing decoders and validation from
   `risk_limits/storage.py::read_monitor_owner`, `prices.py::read_frames` and
   `positions/storage.py::read_position_snapshot`. Preserve fresh SQL frame
   checksum/contiguity checks and every position completeness/revision check.
   Financial numeric values remain native exact numerics or explicit strings
   decoded through Money/Quantity; never JSON floating-point financial values.
4. Feed the captured inputs into the existing chronological replay, including
   marker before/after checks, every intermediate price, transient breach and
   pause transitions. Keep frame budget100/boundary budget20. Financial facts
   needed for FILL/CORRECTION/reconstruction still use existing readers.
   Missing/corrupt input follows existing unavailable handling, never a shortcut
   to READY. Initialization continues through the existing path.
5. Preserve the final database clock read, original evaluation/cursor/ack writes,
   audit/stop handling and transaction commit/rollback. R14 permits later price
   publications to be consumed next round. Owner-locked financial state cannot
   change during this transaction. No shared cache of owner data or readiness.
6. Financial writers, reset, request intake and API retain their existing read
   and fencing paths. Reuse the same replay function; do not fork financial
   logic into a separate optimized implementation.

## Verification and rollback

Before measuring: prove equivalence for ready/pending/uninitialized owners,
missing/corrupt frame, projection gap/revision mismatch, transient breach/pause,
multiple financial boundaries, correction and episode change, rollback and
cross-owner RLS. Retain captured-watermark concurrency, full financial-fence,
R6 API tail and R13 intake tests. Run affected lint/types and scope review.

Then one sequential same-clone bounded comparison with unchanged actors and
resources. Record SQL-call reduction and every-owner progress/SLA, including
failures. Only demonstrated improvement justifies native W1. W2/W3 follow W1
pass; no new diagnostic may overlap tests/workloads. Keep all CPU/RAM/pools,
workers, rates,60s deadlines,1s SLA and financial gates unchanged.

If equivalence fails or throughput/readiness regresses, restore the existing
standalone read path and retain failed evidence. This proposal does not promise
SLA success or authorize relaxing acceptance criteria or production admission.

## Approval boundary

This introduces a new combined standalone read snapshot after R14, rather than
merely removing a redundant call. `plan.md:301` requires “ขอ plan amendment
ก่อนเปลี่ยนวิธี”; AGENTS.md requires approval before implementing a changed
method. R6–R15 approvals remain valid; no implementation of R16 before approval.

## Experiment outcome — Failed / rolled back (2026-10-28)

Safety92tests passed, but same-clone probe7029late/max2.657488s did not
demonstrate benefit. Restored original reader per rollback terms; experimental
source/evidence retained. Rollback34tests/mypy235 passed. This approval remains
history; the batched standalone reader is inactive. See M5 evidence.

## Re-evaluation with approved R15/R17 — 2026-10-28

The standalone R16 experiment remains Failed. Re-test its exact read method with
R15 nonblocking acquisition and R17 decoding reuse after that combination reduced
late fraction/max relative to R17 alone. Same proof checks/resources/rollback
apply;34combined safety tests passed. No acceptance claim from this re-evaluation.
