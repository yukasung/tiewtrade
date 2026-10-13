# F-11 — Performance round 3: sparse LEGACY gap fast path

สถานะ: **Approved** — เจ้าของอนุมัติเมื่อ 2026-10-13.
วันที่: 2026-10-13
Branch: feature/f-12-candlestick-chart

This amendment changes only the implementation of the existing LEGACY full scan.
All approved F-11 requirements, numerical rules, rollout gates and validation remain
in force. It does not activate PREPARED mode or change trading behavior.

## Measured problem

The fixed read-only snapshot used by the chart's slow BTC/USDT 1m request contained
5,845 stored candles in a 525,599-slot calculation range. A single instrumented read
took 7.870049s and attributed 4.361351s to `IndicatorStream.feed_batch`, 1.678560s to
the canonical digest, 0.613779s to DB execution and 0.173266s to row decoding.

There were 519,754 missing slots. cProfile recorded almost 5 million `_Average`
constructions because every RESET recreates empty numeric state, including repeated
RESET events after the stream is already empty. These measurements are diagnostic
observations on the development environment, not workload acceptance results.

## Selected implementation

### Stage 1 — exact all-RESET fast path

- Add an internal fast path to `core/money/indicator_batch.py` after the existing
  batch identity, order, type, unit and price validation. It applies only when every
  input in the bounded batch is `RESET`.
- The fast path returns the same empty averages, `previous=None`, `accepted_count=0`
  and `last_open=inputs[-1].open_at` as the current transition. It emits `(None,) * 8`
  for exactly the requested output indices and keeps the existing batch limit of 16.
- `IndicatorStream.feed_batch` continues to own GAP metadata, seed, blocked,
  unconfirmed and refresh-dependency resets. No caller may jump time, omit a slot or
  construct financial state outside `core.money`.
- Mixed ACCEPT/HOLD/RESET batches continue through the existing transition. No formula,
  rounding, Money/Quantity/Scalar representation, seed, gap, refresh or finality rule
  changes.

### Stage 2 — conditional canonical missing-record batching

Run the same read-only fixture after Stage 1. Implement Stage 2 only if the median of
three uninstrumented reads remains above 4.0s on the same machine and database snapshot.

- Add a bounded `IndicatorDigest` operation that feeds consecutive missing records in
  batches of at most the existing 1,000-slot reader window. The byte stream supplied
  to SHA-256 must be identical to calling the current `_record([timestamp, "MISSING"])`
  once per slot, including timestamp precision, separators, ASCII encoding and newline.
- Retain deadline/disconnect checks and `asyncio.sleep(0)` at least as often as the
  existing 16-slot scheduling boundary. Batching digest bytes must not create a longer
  synchronous CPU slice or a buffer above the existing reader window.
- Present rows still use the current canonical Money/Quantity strings and record shape.
  Dataset revision, cursor invalidation and prepared/full-scan parity cannot change.

Stage 2 is a permitted fallback within this amendment, not a requirement to modify the
digest when Stage 1 already meets the target.

## Files in scope

- `backend/src/tiewtrade/core/money/indicator_batch.py`
- `backend/src/tiewtrade/infra/market_data/indicator_reader.py` only if Stage 2 is needed
- focused tests under `backend/tests/core/` and
  `backend/tests/infra/market_data/test_indicator_reader.py`
- F-11/F-12 evidence documents for the final measurements

No API schema, migration, database role, admission limit, frontend retry policy,
prepared generation, builder, order, balance, position or exchange code is in scope.

ผล Stage 1 และ Stage 2 ยังสูงกว่าเป้าหมาย 4.0s เล็กน้อย; ขอบเขตเพิ่มที่เสนอจาก
ผลวัดอยู่ใน [stream-gap-amendment.md](stream-gap-amendment.md) และยังต้องอนุมัติ
ก่อนแก้ `core/indicators.py` หรือเพิ่ม core entry point.

## Validation amendment

1. Compare the fast path against the existing transition for batch sizes 1, 2 and 16,
   every valid output-index subset used by tests, an already-empty state and a populated
   state. Assert complete `IndicatorBatchResult` equality.
2. Cover mixed RESET/ACCEPT/HOLD batches, repeated gaps, a correction before seed,
   UNCONFIRMED/refresh-required state and the first accepted candle after a long gap.
   These cases must remain on, or equal, the existing path as applicable.
3. Run the independent indicator oracle/parity tests selected for the changed core,
   reader digest tests at fetch sizes 16/64/1,000, snapshot/concurrent-writer revision
   tests and the API LEGACY page/cursor tests. Any changed numerical or digest value is
   a failure.
4. For Stage 2, compare the exact digest byte stream and final SHA-256 against the
   current scalar serializer for leading, middle and trailing gaps, timezone-aware
   boundaries, present rows and a full 525,600-slot sparse fixture.
5. Measure three uninstrumented read-only runs on the same snapshot before and after.
   Stage 1 is accepted for the reported local latency issue when the post-change median
   is at most 4.0s and at most 60% of the 7.870049s baseline. Report all three samples;
   do not claim a general SLA or capacity result from them.
6. Repeat the initial chart load and 1h→1m switch smoke. Record candle-first time,
   indicator-ready time, admission refusals and API compute time separately. The chart
   must keep exact coherent handoff behavior and must not show indicators from provisional
   candles.
7. Run targeted Ruff, format check, strict mypy and affected tests after the final code.
   Do not run the full suite or deferred workload/soak merely for this development fix.
   Existing release-checkpoint capacity gates and failed/partial evidence remain pending.

## Stop conditions and rollback

- Stop and request a new amendment if the target requires changing the 16-slot numeric
  batch, admission concurrency, calculation bounds, seed history, canonical revision,
  formula, deadline, prepared rollout or resource limits.
- Revert the fast path if any exact parity, revision, snapshot, deadline or cancellation
  check fails. The existing scalar transition remains the reference behavior.
- No automated validation may place a live order.
