# F-11 — Sparse stream gap-path amendment

สถานะ: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13.
วันที่: 2026-10-13
Branch: feature/f-12-candlestick-chart

## Evidence after approved v3 work

The all-RESET transition fast path reduced the three-run median from the measured
7.870049s baseline to 5.036063s. Conditional canonical missing-record batching then
produced 4.435306s, and eliminating duplicate RESET validation work produced 4.267635s.
The final observed median is 54.2% of baseline and preserves the scalar digest revision
and all 1,000 indicator points, but it remains above the approved 4.0s local target.

Post-change cProfile still attributes the largest cumulative cost to
`IndicatorStream.feed_batch`. It validates and materializes `IndicatorBatchInput` and
metadata for every missing slot before reaching the exact all-RESET fast path in
`core.money`. Removing that work inside the reader would construct financial state
outside `core.money`, which the approved v3 plan forbids.

## Proposed extension

- Add a bounded public `reset_indicator_batch` operation in
  `core/money/indicator_batch.py` and export it through `core/money/__init__.py`.
  It accepts the validated current state, a tuple of 1..16 consecutive aware open
  times and output indices. It returns the exact state and null outputs produced by
  `advance_indicator_batch` for equivalent RESET inputs.
- Keep all identity, timeframe, ordering, output-index and state validation inside
  `core.money`. The operation cannot accept prices or perform ACCEPT/HOLD transitions.
- In `core/indicators.py`, after the existing slot identity/time validation, detect an
  all-gap batch and call `reset_indicator_batch` directly. Build GAP points and
  refresh-dependency results only for selected output indices; reset seed, blocked,
  unconfirmed and refresh dependency exactly as the existing loop does.
- Keep the current generic path for every mixed or non-gap batch. Keep the 16-slot
  bound, deadline/cancellation cadence, full calculation range and canonical digest.
- Make the existing all-RESET path in `advance_indicator_batch` delegate to the same
  reset implementation so there is one source of transition behavior.

Files added to the approved v3 scope:

- `backend/src/tiewtrade/core/indicators.py`
- `backend/src/tiewtrade/core/money/__init__.py`
- corresponding focused tests in `backend/tests/core/`

## Validation

1. Assert complete result equality between `reset_indicator_batch` and
   `advance_indicator_batch` for empty and mature states, sizes 1/2/16 and empty,
   first-only, sparse and all output-index selections.
2. Reject malformed state, naive/unordered/non-consecutive times, wrong tuple/type,
   bool indices and more than 16 slots without mutating the stream.
3. Compare `IndicatorStream.feed_batch` gap points, seed, finality, statuses,
   dependencies and exported checkpoint state against the pre-fast-path expected values;
   include refresh-blocked state, repeated gaps and the first accepted candle afterward.
4. Re-run the affected core/oracle, reader digest/snapshot and LEGACY API tests. Any
   numerical, status, revision, point or cursor difference is a failure.
5. Repeat three read-only runs on one snapshot. The median must meet both approved v3
   targets: at most 4.0s and at most 60% of the 7.870049s baseline. Record every sample.
6. Then build/restart only the API and run the initial chart plus 1h→1m browser smoke,
   separating admission refusals from compute time. No full load/soak or live order.

## Stop conditions

Stop for another amendment rather than changing formulas, rounding, Money/Quantity,
seed history, canonical revision, admission concurrency, deadline, calculation bounds,
PREPARED rollout or resource limits. Existing release-checkpoint capacity findings
remain Failed/Partial/Pending as recorded.

## Implementation result — 2026-10-13

Implemented the approved bounded reset operation and the `IndicatorStream` all-gap
dispatch. The generic path still handles every mixed/ACCEPT/HOLD batch. The canonical
digest continues to cover all 525,599 calculation slots and the reader still yields
and checks its deadline at each 16-slot slice.

Three uninstrumented read-only runs in one repeatable-read snapshot took 3.568926s,
3.508940s and 3.554133s. Median 3.554133s is 45.2% of the 7.870049s baseline, passing
both approved local targets. Every run returned the same revision and 1,000 identical
indicator points. A separate full sparse comparison against the scalar digest path
also produced identical revision and points.

Validation evidence:

- focused core/digest tests: 36 passed;
- isolated migrated PostgreSQL reader/snapshot integration tests: 5 passed; the
  disposable `tiewtrade_gap_test` database was dropped afterward;
- Ruff check/format, strict mypy over 371 files and all 7 import contracts passed;
- API image `sha256:f0add4466c1cfe5ffcf6b52367b78d830b97714784e406e8ffb482a7c63308d3`
  built and the API-only restart became healthy;
- real browser smoke: chart visible in 420ms, initial 1h history request 363ms,
  1m history request 3.749s and switch indicator-ready in 5.799s; no busy response,
  blank chart or JavaScript page error was observed.

These are targeted development measurements, not release workload/capacity evidence.
No full suite, soak, PREPARED activation or live order was run.
