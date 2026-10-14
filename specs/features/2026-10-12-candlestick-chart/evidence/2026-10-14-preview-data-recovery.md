# Local chart preview data recovery — 2026-10-14

The reported BTC/USDT 15m chart combined a real price near 83,000 with
`open=100.000000000000000001, high=101, low=99, close=100, volume=1`.
This exact signature belongs to `tests/infra/market_data/test_chart_preview.py`.
Integration fixtures had contaminated the shared development database.

Removed 45 preview rows matching all five fixture values in one transaction.
No historical candles, account data, orders, or balances were deleted.
No application code or price-scale workaround was needed for this incident.

Read-only verification after cleanup:

- Remaining matching preview rows: 0; matching historical candles: 0.
- BTC/USDT 15m history: 96 candles within the preceding day, lows/highs
  between 82,972.74 and 84,168 USDT.
- Live 15m preview advanced from 83,678.69 to 83,691.08 USDT;
  last observed receipt: 2026-10-14 04:09:51 UTC.
- Frontend `/chart` and API `/health` both returned HTTP 200.

Browser rendering was not directly verified. Reload the page to discard any
fixture candle retained in client memory. Other timeframes' backfill completion
and the existing full-validation criteria remain unverified by these checks.
No test suite or build was run for this data-only repair.

Subsequent destructive integration tests must use a disposable, isolated database,
never the database serving the development UI.

## Follow-up: actual browser and API verification

After the report of a single live 1h candle, read-only inspection found that the
worker had now completed the 1h history window (1,001 stored rows including the
current candle; 96 within the latest four days). 4h and 1d backfill remained pending.

A fresh Chromium session registered a disposable local smoke account through the
normal signup UI and loaded `/chart` without mocked endpoints or database fixtures.
Both `/market-data/candles` and `/market-data/chart/history` returned HTTP 200 and
1,000 historical candles for 1h; candle-only coverage was PRESENT. The live endpoint
returned one current candle. Visual inspection confirmed the historical chart and
current candle render together, with no browser page errors.

Screenshot: [real 1h recovery](2026-10-14-real-1h-recovery.png).
An already-open tab holding the earlier incomplete snapshot may need a reload.
This verifies current 1h behavior, not completion of the other backfill queues.
