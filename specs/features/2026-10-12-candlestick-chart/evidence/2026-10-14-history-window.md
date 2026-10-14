# History-window implementation checkpoint — 2026-10-14

Scope: RQ-37..42 / P-H1..4 / V-H1..8. Owner approved requirements and the
plan/validation amendment in conversation. This is a development checkpoint,
not evidence that every series has completed backfill.

## Implemented

- Authenticated `/market-data/candles/pages`: server UTC three-calendar-month
  display bounds for 1m–1d, at most 1,000 slots, 200-slot overlap between pages.
- Native weekly/monthly source-bound discovery and migration 0028. Discovered
  history can create historical monthly partitions; indicator seed remains unchanged.
- Chart pan loads older/newer pages, preserves the visible time range, rejects
  obsolete responses and limits concurrent page reads to one. LRU cache: five
  pages plus the latest-page metadata/reference. Reset returns to the current view.
- Discovery consumes the existing four-attempt round budget; retries remain bounded.

## Evidence

- Calendar bounds: 4 tests passed (calendar clamp/leap year/aligned boundary).
- Ingestion: 49 tests passed on `tiewtrade_history_test`, including inserting
  discovered August 2017 monthly history through the partition-provisioning path.
  Seven tests initially lacked API-role environment configuration; those seven
  passed after setting the isolated API URL. No development DB fixture seeding.
- Auth/page bounds API: 7 tests passed on isolated DB/Redis.
- Frontend paging and chart: 25 tests passed, including cancellation, dedup,
  cooldown and eviction/refetch. Earlier affected useChartData tests: 19 passed.
- Scoped Ruff/mypy and frontend TypeScript/ESLint passed.
- Binance TH candle adapter: 48 tests passed in an ephemeral Linux container,
  including empty/malformed discovery responses. Windows execution was blocked
  by the existing network guard intercepting the event-loop socketpair; the guard
  was retained and the tests were moved to Linux.
- Local migration 0028 applied; API, market-data and frontend restarted.
- Browser: 1h page returned 1,000 rows; 1d returned 63 rows within the requested
  three-month boundary; switching to 1m produced no JavaScript page errors.
- Browser pan crossed the initial 1,000-slot window: successive responses contained
  995, 256 and 0 rows, with older bounds advancing correctly. The empty page is a
  genuine missing-data/backfill condition, not a successful complete-history result.
  Screenshot: `2026-10-14-history-pagination.png`.

## Remaining validation

- V-H1/H2/H3: verify complete retained data for every pair/timeframe after backfill;
  automated bounds/pagination do not establish three months of available candles.
- V-H3/H7: exercise wide zoom, sparse/empty pages, return navigation and anchor
  stability across many pages; browser smoke alone is partial evidence.
- V-H5: dedicated discovery crash/takeover and downgrade validation remains pending.
- V-H8 and existing V-17: **Pending Full Validation** at release checkpoint.
- No full suite, performance endurance run or live trading orders in this checkpoint.
