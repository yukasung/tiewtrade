# Base refresh checkpoint - 2026-11-08

Main advanced with chart 3m support (PR #60, 8d3007e) while the first candidate's CI was
running. Candidate cf2b5b1 passed PR/push/Security CI but became BEHIND under strict branch
protection. Refreshed the branch via merge 55b7937; no conflicts or additional runtime
changes were introduced. The PR diff against the new main remains prices removal only.

Inspected automatic merges in candlestick-chart.spec.ts and CandlestickChartPanel.test.tsx:
retired-route assertions and the new 3m cases coexist, without losing either coverage.
Read the approved 3m requirements. No new business/architecture decision or requirement
change was necessary. Backend and generated API types have no diff against main.

Affected validation:
- ESLint on the two automatically merged test files: passed.
- Frontend TypeScript: passed.
- CandlestickChartPanel + chart-candleTimeline: 29 tests passed.
- Real PostgreSQL/Redis chart E2E: five flows passed in 28.8s, including navigation,
  retired bookmarks, recovery, login/series switching and native 3m BTC/ETH history/live.
  [Log](base-refresh-chart-20261108.log).
- git diff --check: passed.

Used disposable PostgreSQL 16/Redis 7, guarded database
`tiewtrade_e2e_prices_refresh_20261108`, unchanged chart config/default loop and migrations
through 0066. Task containers removed afterwards. No Live orders were sent.

Existing price-service/refactor evidence remains applicable: its runtime, test and
contracts were unchanged by the refresh. The affected chart evidence is replaced by
this run; historical results remain retained. Local gates V-01..08 remain satisfied.
Required CI V-09 must pass on the refreshed published SHA; the old SHA's green CI does
not substitute for it. No PR merge authorized or performed.
