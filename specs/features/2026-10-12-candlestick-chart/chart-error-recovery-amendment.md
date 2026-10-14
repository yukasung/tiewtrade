# Chart recovery after history admission failure

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-14

## Evidence

- API logs show `/market-data/chart/history` returning 429 while candle-only and
  live endpoints return 200.
- `frontend/src/chart/useChartData.ts` cancels every query beneath the episode key
  when any terminal history error occurs. A fast 429 can therefore cancel the
  initial candle/live responses before they reach the renderer.
- The UI removed manual retry; reset is disabled without candles and its approved
  contract explicitly forbids API calls. Waiting for cooldown alone cannot recover.

## Proposed requirements and plan

- For a terminal history admission failure, stop history/proof retries and subsequent
  automatic polling, but let already-started, bounded candle-only/live reads finish.
  Do not launch additional requests to bypass a rate limit.
- Authentication failures, series changes, logout, hidden/offline transitions and
  unmount continue to cancel affected work. Old-series responses must remain isolated.
- Render available candle data without claiming verified freshness or consistency.
- Add a shared admin-template Button labelled `ลองใหม่` inside the error state only.
  Reuse the existing retry action and monotonic Retry-After cooldown. Keep the existing
  `รีเซ็ตกราฟ` viewport-only behavior unchanged.
- Preserve server admission limits, financial precision and all trading behavior.

This explicitly amends the terminal-error cancellation scope and the approved
removal of manual retry controls in plan.md; it does not authorize unrestricted polling.

## Targeted validation

- Fast history 429 followed by delayed valid candle/live responses still renders
  those responses; no automatic requests follow the terminal error.
- Retry stays disabled until Retry-After expires, including wall-clock changes;
  one manual action starts one new episode.
- Switching TF or unmounting cancels outstanding responses; 401 follows auth flow.
- Successful charts keep their existing reset behavior and controls.
- Run affected hook/component tests, scoped ESLint and frontend type-check;
  rebuild/restart frontend and verify the 4h failure/recovery path in a browser.
- Do not run destructive integration tests against the development database.

## Verification — 2026-10-14

- Targeted hook, component and read-episode tests: 59 passed. Existing series-change,
  cancellation and backward-wall-clock cooldown regressions remain green.
- Frontend type-check and scoped ESLint passed.
- Frontend image rebuilt and container restarted without restarting backend services.
- Chromium smoke against the served frontend with browser-only mocked responses:
  switched to 4h; immediate history 429 followed by delayed candle/live responses
  displayed OHLC and mounted seven chart canvases; retry disabled during cooldown,
  enabled after expiry, then issued exactly one new history request. No page errors.
- This smoke verifies the browser failure/recovery path, not real exchange history
  completeness. No mock data was written to the database, no orders were sent,
  and no full test suite was run.
