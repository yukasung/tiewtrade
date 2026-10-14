# Calendar history batch retrieval

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-14

## Problem and evidence — 2026-10-14

BTC weekly and monthly history each contained only 27 canonical candles during
inspection. Both demands remained PENDING, with discovered history starts in
August 2017. Forty series share the bounded worker budget. The current adapter
allows only one weekly/monthly candle per request.

Read-only public API probes to `https://api.binance.th/api/v1/klines` used
`symbol=BTCUSDT&startTime=1501545600000&limit=1000`, without `endTime`:

| interval | rows | first open (milliseconds) | last open (milliseconds) |
| --- | ---: | ---: | ---: |
| 1w | 479 | 1502668800000 | 1791763200000 |
| 1M | 111 | 1501545600000 | 1790812800000 |

This does not invalidate the recorded seven-day rejection when both time bounds
are supplied. It establishes an alternative request shape for calendar history.
No credentials, order requests, database writes or code changes were involved.

## Requirements and plan amendment

- Preserve the approved requirement to retrieve all available native weekly and
  monthly history. Do not aggregate daily candles or fabricate missing slots.
- Supersede the one-slot calendar restriction in plan.md: request native `1w`/`1M`
  with `startTime` and a bounded `limit`, omitting `endTime`. Keep fixed-timeframe
  requests unchanged.
- Reuse `BinanceThCandles.fetch_candles`, native slot helpers, CandlePage validation,
  existing ingestion claims, transactions and recent/deep cursors. Permit up to
  1,000 calendar slots; derive the upstream limit from the logical requested window
  and caller limit. Validate ordering, duplicates, alignment, identity and bounds;
  never persist observations outside the requested window.
- Retain four-request round budget, scheduler spacing, shared rate limiter,
  Retry-After, retry cap, lease fencing and independent historical progress.
- Existing one-slot in-flight requests must complete safely before new batches.
  Partial/empty source responses remain subject to existing gap repair; do not
  mark incomplete history complete merely because a request succeeded.
- Rebuild/restart only the affected local worker after targeted verification.
  Let normal fenced ingestion fill existing demands; no direct candle inserts.

## Validation

- Adapter tests: native week/month requests omit endTime, use correct start/limit,
  respect logical window and 1,000 cap, and reject malformed/duplicate/out-of-window
  data; unchanged fixed-timeframe request and failure handling regressions.
- Ingestion tests: multi-slot recent/deep progress, resume existing one-slot work,
  sparse response gap repair, restart/fencing/rollback and exact request budgets.
- Test only in an isolated database; scoped lint/type checks on affected code.
- Runtime read-only evidence for BTC weekly/monthly: compare stored native slots
  against source-discovered bounds, report real gaps and queue progression, and
  confirm API/chart can display the populated history.
- Preserve pending full regression/workload validation; no live orders.

Owner approval covers this requirements-preserving plan/validation amendment and
supersedes the prior single-slot calendar fetch prescription. Implementation and
verification evidence: [calendar batch results](evidence/2026-10-14-calendar-batch.md).
