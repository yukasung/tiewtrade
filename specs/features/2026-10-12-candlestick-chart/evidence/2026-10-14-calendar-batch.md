# Calendar history batch verification — 2026-10-14

## Change

Approved amendment replaces single-candle weekly/monthly requests with oldest-first
`startTime` + native-slot `limit` (maximum 1,000), omitting `endTime`. Fixed intervals
retain explicit time bounds. The adapter rejects oversized, unordered, duplicate,
unaligned and out-of-window responses. Existing CandlePage validation, Money and
Quantity parsing, ingestion claims, transactions, retry and rate limits are reused.
No frontend, schema, order, balance or strategy changes.

## Targeted checks

- Adapter: 64 tests passed in an ephemeral Linux container, using mocked HTTP and
  existing saved public fixtures. Includes 1/2/3/1,000 slots, caller-limit capping,
  single-slot compatibility, malformed/duplicate/reversed/outside data, fixed
  timeframe requests and transport/rate-limit behavior.
- Ingestion: 53 tests passed on isolated `tiewtrade_history_test`, then four batch
  size cases (two existing + two new) and four new sparse/reserved-slot cases passed.
  Total 59 distinct ingestion cases; covers recent/deep progress, restart, rollback,
  fencing, retry caps and shared four-request budget. No fixtures wrote to dev DB.
- Scoped Ruff and adapter mypy passed. Diff whitespace check passed.
- Local market-data image rebuilt and worker restarted. No extra worker, manual
  candle insertion, rate-limit override, frontend rebuild or live order.

## Runtime evidence

Before the change BTC had 27 weekly and 27 monthly rows; later, immediately before
the new worker processed these series, each had 31. After the first batch pass,
weekly increased to 102 and monthly to 60. The queue remained PENDING without a
failure code while older gaps awaited their normal scheduler turns.

At **17:32:04 Asia/Bangkok** the real authenticated page API returned:

| BTC timeframe | rows | first open UTC | latest open UTC | gaps |
| --- | ---: | --- | --- | ---: |
| 1w | 479 | 2017-08-14 | 2026-10-12 | 0 |
| 1M | 111 | 2017-08-01 | 2026-10-01 | 0 |

Counts and earliest bounds match the public source probe. Normal browser signup
and the running frontend/API were used, without mocked auth/data or DB fixtures.
Both timeframe switches displayed continuous charts; no browser JavaScript errors.
The weekly initial viewport still shows the latest viewport, with older candles
loaded for navigation; the display was not forcibly zoomed to all 479 candles.

- [API progression and browser errors](2026-10-14-calendar-batch.json)
- [Weekly screenshot](2026-10-14-calendar-batch-1w.png)
- [Monthly screenshot](2026-10-14-calendar-batch-1M.png)

Other pairs use the same adapter. At the subsequent DB check, monthly DOGE/SOL/XRP
and weekly SOL/XRP had reached full slot counts; ETH and weekly DOGE still had
queued gaps. Their backfill continues under the unchanged shared scheduler.
Do not equate PENDING queue state with missing rows: the completion transition
and outstanding refresh work are processed on later scheduler turns.

Existing full-suite/workload acceptance remains **Pending Full Validation**.
This targeted run is not a release approval.
