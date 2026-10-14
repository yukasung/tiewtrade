# Recent history before deep backfill

สถานะ: **Approved** — เจ้าของอนุมัติ 2026-10-14

## Confirmed problem

BTC 4h ingestion has reached June 2026 and 1d December 2025, while the chart
displays October 2026. Both demands are progressing without a failure code.
Ascending backfill leaves the initial viewport without historical candles.
Separately, running API/worker images still supported only six timeframes; the
already-approved native week/month code must be deployed against migration 0026.

## Proposed requirements and implementation

- Prioritize missing candles in the latest 100 native slots within the existing
  demand/retention window before ascending deep backfill. This matches the chart's
  current initial viewport; do not shorten the required full history window.
- Reuse `_next_fetch_window`, claim/fetch identity, fencing, source limits and
  transactional writes. Finish an already-reserved fetch before reprioritizing.
- Keep the deep-backfill cursor separate from recent-priority progress: recent
  writes must not advance the historical cursor over unfilled history.
- Bound the recent-priority pass per leased window so newly arriving candles cannot
  indefinitely starve deep history. Persist its progress if needed; any added state
  requires a migration with coverage for existing queued demands.
- Preserve four-request round budget, scheduler spacing, source Retry-After and
  retry budgets. No additional parallel workers or direct unfenced inserts.
- Keep incomplete history classified as incomplete. Indicator warm-up/consistency
  and financial precision contracts do not change. No live order requests.

## Validation

- Cold 4h/1d/1w/1M demands fetch their latest viewport before deep history.
- Existing in-flight fetch, restart, lease takeover, rollback and duplicate work
  preserve fencing and resume safely; historical gaps remain discoverable.
- Calendar month/week boundaries, retention cutoffs, and seven-day source request
  caps remain correct. Test exact request count and retry/backoff bounds.
- Prove deep-history progress while the current candle advances.
- Run targeted core/ingestion/storage tests in an isolated database, lint/typecheck,
  and browser checks using actual API data for each affected timeframe.
- Full regression/workload validation retains its existing release checkpoint.

Approval applies to these requirements, plan and validation together. This changes
the backfill scheduling policy; it is not implemented by the existing UI error fix.

## Implementation and verification — 2026-10-14

- Migration 0027 adds `recent_cursor`, `recent_end`, `fetch_recent`. Existing reserved
  fetches retain identity and retry count. The recent pass moves backward from a
  fixed lease horizon, in source-sized chunks; deep history retains its own cursor.
- Windows already within 100 slots use their existing forward traversal, except
  monthly windows, which start at the newest month because the source permits only
  one month per request. Existing source gaps remain eligible for bounded repair.
- Ingestion regression: 47 cases passed on disposable `tiewtrade_recent_test`.
  Extended rollback coverage subsequently passed for both deep and recent progress
  (48 distinct cases overall). No test wrote to the UI database.
- Scoped Ruff and mypy passed. Migration downgrade correctly refused an outstanding
  recent fetch; after clearing only the isolated test demands, downgrade/upgrade passed.
- Applied migration 0027 and rebuilt/restarted the market-data worker locally.
  API/frontend code did not change in this amendment.
- Real API/browser smoke (normal signup, no route mocks) returned 200 for candle
  reads on 4h, 1d, 1w and 1M, with no browser page errors. Initial observation:
  4h had 42 recent candles, 1d seven; week/month had fetched the current slot and
  were still waiting for subsequent scheduler turns to fill preceding slots.
- This is not full-history completion. Full regression/workload remains
  **Pending Full Validation** at the established release checkpoint.

Follow-up at 04:35 UTC: real BTC history increased to 84 recent 4h candles,
14 daily candles, two weekly candles (October 5/12), and two monthly candles
(September/October). A second real browser check confirmed the preceding week/month
was returned and rendered. Screenshots are in `evidence/2026-10-14-priority-*.png`.
The frozen-horizon test also passed with a live weekly demand extension. Database
privilege checks confirmed API cannot update recent progress, while the worker can.
Backfill continues under the original four-request/30-second scheduler budget;
the full 100-slot recent window and deep history are not yet complete for all series.
