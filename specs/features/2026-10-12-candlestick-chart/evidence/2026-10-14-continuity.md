# Candle continuity checkpoint — 2026-10-14

Approved scope: [continuity amendment](../candle-continuity-amendment.md).

## Cause and correction

REST lagged by several minutes while persistence and live response retained only
two observations. The chart also waited for `history_end` (null until REST recovery)
before reading history again and discarded previously observed preview candles.

- Persistence retains at most 120 observations/series; the live response stays at two.
- Candle pages read canonical rows and bounded stream overlay in one repeatable-read
  snapshot. Canonical settlement takes precedence; ended/old-epoch preview is UNCONFIRMED.
  Missing observations remain gaps. Canonical storage and indicator inputs are unchanged.
- Frontend retains at most 120 received observations, isolated by user/series,
  and refreshes once per observed native boundary even when `history_end` is null.
- Time comparisons use timestamps, not lexical ISO strings.
- Browser inspection also caught automatic pagination on programmatic time-range changes.
  Only pointer/wheel navigation now triggers page loading, preventing initial auto-pan/zoom.

## Verification

- Isolated PostgreSQL `tiewtrade_history_test`: nine preview/overlay tests passed across
  the affected runs. Includes 40-series × 120-row cap, rollback/fencing, epoch takeover,
  old-event rejection and delayed REST overlay for 1m/1w/1M with a deliberately missing
  observation; corrected REST replaces stream without changing the canonical reader.
- Seven page API/auth/bounds tests passed with isolated Redis and PostgreSQL.
- Frontend: 26 affected hook/page/component tests passed across the final runs;
  includes eight native boundaries with null recovery, 122 observations capped at 120,
  TF clearing, late-response cancellation, 429, 401, exact values and user-only pagination.
- Scoped Ruff/mypy, frontend TypeScript/ESLint and diff whitespace checks passed.
- No full suite, live orders or development DB fixture writes.

## Real data

Browser watched BTC/USDT 1m for 130 seconds across the 12:36 and 12:37 Bangkok
boundaries, then reloaded. The former 12:29–12:33 gap was repaired by the existing
REST worker during this window. At 12:37:50 the latest page had no gaps and included
continuous 12:26–12:37 rows. No indicator/proof requests or JavaScript errors.

[Response evidence](2026-10-14-continuity-browser.json) records the initially missing
old slots and their subsequent repair; it is not an assertion that all three months
or every market series has finished backfill.

API, market-data and frontend were rebuilt/restarted. No migration was required.
Final browser smoke after the pagination correction: cold reload returned 1,000
BTC/USDT 1m rows with zero gaps, no unintended `before` requests and no JavaScript
errors. The [final screenshot](2026-10-14-continuity.png) shows the normal recent
viewport with continuous candles, rather than the erroneous two-bar zoom.
Existing release/full validation remains pending. Outages beyond the bounded buffer,
or native observations never received, still require REST backfill and remain gaps.
