# F18-R17 — Bounded immutable execution-input decoding reuse

สถานะ: Approved — owner approved R17 on 2026-10-28

## Evidence

R16 passed92 affected safety tests but its comparison failed7029late inputs,
max2.657488s. It was rolled back, including unused helpers. Rollback34tests,
mypy235sourcefiles and lint passed. No native W1 was repeated on that failure.

The subsequent same-budget metadata diagnostic measured PostgreSQL at about
1.14 CPU with zero additional quota throttling, while the API/Paper group used
about2.71 CPU of its3CPU ceiling and was throttled344 of429 periods. This proves
pressure in that group, not that it alone explains every SLA miss. Risk retains
its existing1CPU/512MiB allocation; no resource increase is proposed.

One Paper worker was then profiled with cProfile (diagnostic, not acceptance).
It made7713 constraints_from_payload calls (3.464s cumulative) and2808
input_from_payload calls (1.514s cumulative). These timings include profiler
overhead and nested calls; they must not be added as independent CPU savings.
Public execution inputs are read/decoded repeatedly for different owners.
No monetary validation, rounding or Money/Quantity implementation will change.

## Proposed implementation

1. In `infra/market_data/order_book_storage.py::read_inputs`, retain the fresh
   statement snapshot of execution state and bounded buffer rows on EVERY call.
   Preserve readiness, lease/freshness, retained-window/gap, order/identity,
   pair, generation and stored-digest checks in their existing order.
2. Read public payload/capability JSON as exact text. Extract the existing pure
   input/metadata decoding and canonical digest calculation into a bounded
   `lru_cache(maxsize=256)` helper keyed by BOTH complete payload and capability
   texts. Reuse `input_from_payload`, `metadata_from_payload`, `input_payload`
   and `metadata_payload` unchanged. Return only their deeply immutable values
   and the derived canonical digest. No user identity or mutable owner state.
3. A cache hit may reuse deterministic decoding/canonicalization of identical
   bytes. It must still compare the derived digest against the freshly read row
   digest, and compare the immutable identity against fresh row identity and
   current generation. A changed payload/capability gets a different key; a
   missing row, changed digest, stale lease or new generation cannot be hidden.
   Failed decoding is not cached. Never key only by input_id or claimed digest.
4. Reuse the existing immutable public-frame decoding pattern in
   `risk_limits/prices.py`; do not cache orders, checkpoints, balances, positions,
   owner books, evaluations, authorization, readiness or current source state.
   Keep all existing financial/catalog/owner/publication fences and transaction
   boundaries. No change to matching, quantity, fee, PnL or risk calculations.
5. No schema, worker, pool, scheduling, retry, source rate, resource allocation,
   retention, duration,60s deadline or1s SLA change. Production admission stays
   gated. Cache is per process and bounded within existing memory limits.

## Verification and comparison

After warming the cache, verify fresh-read rejection for missing row, corrupt
payload, corrupt capability, changed digest/identity, generation rollover,
lease expiry and unavailable source. Confirm same decoded values and unchanged
fills/projections across cached and uncached reads; assert cached graph is
immutable and eviction cannot affect results. Keep actual-DB matching/recovery,
financial fencing and quantity/precision tests. Run affected lint/types/review.

Only after those pass, run one sequential same-clone comparison, documenting
cache hits/misses, owner progress, input SLA and parent CPU throttling. No overlap
with other tests/diagnostics. Improvement must be measured, not inferred from
call counts. If CPU/progress/readiness worsens or safety differs, remove the cache
and retain failed evidence. Only sufficient evidence justifies full native W1;
W2/W3 remain dependent on W1 passing. No threshold relaxation is authorized.

## Approval boundary

This extends decoding reuse from already-approved immutable risk price frames
to the F15 public execution-input reader. It is outside R16's standalone read
snapshot and changes an approved source-reading method. `plan.md:301` requires
“ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md prohibits implementing that change
first. R6–R16 approvals remain valid history. Owner approved R17 before implementation.
