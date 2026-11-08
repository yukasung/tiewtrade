# Remove prices page — implementation checkpoint

วันที่: 2026-11-07 (Asia/Bangkok)
สถานะล่าสุด: **Reviewed / V-03 Passed on combined candidate 2026-11-08**

Latest: [refactor checkpoint](refactor-checkpoint-20261108.md) — local gates passed, required CI pending; the earlier blocker narrative below is historical.

Latest: [review follow-up](review-followup.md) records the owner-authorized fixes and bounded
baseline/clock diagnosis. The initial-checkpoint narrative below is historical.
Branch: `feature/remove-prices-page`
Base: `f15596df0b1ced53107964a8ed9bb657fda9d336` (`origin/main` fetched before implementation)
Candidate: uncommitted working tree; no commit/push/PR/merge authorized or performed.

## Approval and scope

Owner approved requirements, then explicitly approved plan/validation and source/test implementation.
The earlier review's first two items described pending implementation at the spec checkpoint,
not regressions introduced by a runtime diff. Implementation is now present; no new code review
has been started after the Ready for Code Review notification.

Removed the prices route/menu, panel/hook/client/messages/CSS and obsolete panel-only tests.
Unknown-route fallback handles `/prices` through existing auth/history behavior, preserving queries
and the chart-disabled state. Removed obsolete chart translation references; F-12 still fixes its
chart locale to Thai as required by the approved F-12 amendment.

Kept backend price ingestion, API/WS, generated contracts, financial/trading logic, shared auth and
PostgreSQL sessions. No new persistent process memory, infrastructure dependency, migration,
production flag change, exchange connection or Live order was introduced.

Reworked realtime-price E2E into a test-only authenticated GET/native WebSocket consumer.
Preserved exact price/catalog/timestamps, READY→STALE→outage alert→recovery,
frame-limit rejection 1008, disconnect/reconnect and logout-all revocation 4401/HTTP 401.
Updated chart navigation/history tests and replaced the retired panel read with a price API read.
The workflow-document finding was fixed narrowly in AGENTS.md/testing.md on the new base;
other workflow rewrites in the original worktree were not copied over.

## Results

| Check | Result |
|---|---|
| Frontend six targeted suites | **Passed, 65 tests**: five suites 40 passed on the combined run; final CandlestickChartPanel rerun 25 passed |
| Backend API/WS tests | **Passed, 9 tests across runs**: initial 8 passed; authorization deadline case initially failed at 0.727s against <0.6s, then passed in isolation; no safety threshold changed |
| Full frontend ESLint | Passed; final changed-test ESLint passed after subsequent test-only edits |
| TypeScript | Passed on final test/source candidate |
| Vite production build | Passed, 216 modules, 6.51s; non-blocking >500kB shared bundle warning retained (621.43kB uncompressed JS) |
| Price-service E2E | **Passed, 1 flow, 21.2s** — [log](price-service.log) |
| Chart/navigation E2E | **3 passed / 1 failed, 29.3s** — [initial run](chart-initial.log) |
| Failed chart recovery isolated diagnostic | Failed — [second run](chart-recovery-diagnostic.log) |
| Final chart recovery diagnostic | Failed — [third run](chart-recovery-final.log), all probe responses HTTP 504 / CHART_DEADLINE_EXCEEDED; retries stopped |
| References/contract/source scope | No retired UI imports or automatic price GET/WS in runtime; backend, OpenAPI/generated types, lockfiles/configuration unchanged |
| Diff whitespace | Passed |
| Review / required CI | Not Run; awaiting owner commands |

Initial frontend failures came from new tests incorrectly assuming an unused disclaimer was rendered
and that changing the i18n instance changed the explicitly Thai chart locale. Corrected those test
assumptions to the approved F-12 contract; kept translated-message and removal assertions.
An initial local E2E startup attempt hit Node's TypeScript-under-node_modules restriction for a
throwaway config, before starting tests. Moved the temporary config outside node_modules; no
application configuration or dependency changes were made.

## Recovery blocker and stop condition

The existing `live snapshots recover after disconnect without indicator reads` flow cannot get
READY after `fixture("preview")`: `/market-data/chart/live` returns HTTP 504 with
`CHART_DEADLINE_EXCEEDED`. It failed in the combined run and two isolated diagnostic runs.
No timeout, freshness rule, assertion or acceptance threshold was relaxed.

Backend chart runtime and the fixture are unchanged by this work. A read-only direct `read_live`
diagnostic on the same disposable DB completed in 0.076s with one preview and recovered=True;
DB/host clocks differed by about 0.073s. These observations do not establish why the HTTP path
times out and do not prove the failure exists on an unmodified baseline.

Stopped after three failed executions. V-03 stays Partial/Failed and blocks Feature acceptance/merge.
Owner choices before any further attempt:

1. Recommended: authorize a bounded baseline comparison on unchanged main and trace the
   HTTP live-read boundary in the isolated environment. This distinguishes an existing runtime/
   harness issue from a regression without changing financial or freshness rules.
2. Keep this checkpoint pending and handle chart recovery separately; V-03 remains blocked.
   Any backend/fixture source fix beyond this plan needs scope review before implementation.

## Browser observations

Passed flows cover old bookmarks after login/reload, retained query string, desktop/mobile menu
absence, keyboard activation/focus, TH/EN account navigation, no automatic price requests/sockets,
navigation history, password login, pair/timeframe switching and real latest-price API data.
Chart recovery itself is not claimed to pass. Screenshots show the retained chart loading/error
states and are evidence of navigation/removal only, not a healthy live-candle feed:

- [Thai desktop](removed-prices-th-1440.png), [Thai mobile](removed-prices-th-375.png)
- [English account navigation desktop](removed-prices-en-1440.png), [mobile](removed-prices-en-375.png)

Historical F-10/F-12 evidence was not overwritten. New screenshots use Playwright output paths
and copies in this feature's evidence directory.

## Environment and next step

Implementation lives in the isolated `TiewTrade-remove-prices` worktree. The original worktree's
source and existing localhost:5173/8000 dev processes were left intact. Price E2E used temporary
ports 18175/18013; chart E2E used its existing 18174/18012 configuration. Both used a new
PostgreSQL 16/Redis 7 pair (removed after validation) and a guarded `tiewtrade_e2e_prices_20261107` database, never dev/live data.

Next: wait for `review code` for this implementation and an owner decision on the bounded recovery
investigation. Refactor requires its own decision after review; no automatic fourth diagnostic,
commit/push/merge, or claim of Completed.
