# F-12 — Faster timeframe switching

สถานะ: **Approved** — owner approved the approach on 2026-10-13 for initial load and timeframe changes.
The concrete implementation amendment in plan.md/validation.md was also approved on 2026-10-13.

## Observed evidence

One browser session switched from default BTC/USDT 1h to 1m on localhost.
Timing captured at browser route interception using performance.now; the API request
was forwarded using Playwright route.fetch. These are individual observations, not
benchmarks or latency guarantees.

| TF | Delay before history request | Request duration | HTTP | Candles |
|---|---:|---:|---:|---:|
| 1h | 2200ms | 433ms | 200 | 1000 |
| 1m | 2052ms | 7869ms | 200 | 999 |

Both responses had generation_id=null. The 1m calculation window was
2025-10-13T09:36:00Z to 2026-10-13T09:35:00Z.
No busy retry occurred in this sample.

The LEGACY branch in services/api/indicator_read_controller.py calls
infra/market_data/indicator_reader.py:read_indicators, which scans calculation
windows, updates the dependency digest, and feeds indicator state before returning
the selected output. Returning fewer output rows alone does not remove that work.
Frontend useChartData additionally waits 2s before the history request for reader cleanup.

## Proposed behavior for approval

- Show recent OHLC candles as soon as a bounded candle-only read completes.
- Continue loading the existing coherent history/indicator bundle separately.
- Show indicators only after the existing consistency checks pass.
- When that bundle is ready, atomically replace the provisional historical candles
  with its own candles and indicator data. Never combine an independently fetched
  history with indicators from a different snapshot.
- Preserve live-preview identity/finality rules, exact text values, user viewport,
  session isolation, cancellation and existing retry/admission limits.
- Explicitly indicate that indicators are still loading while provisional candles
  are shown. Empty/failed candle reads must have a visible state.

## Required design work after scope approval

Assess reuse of the existing authenticated F-09 candle reader/API, its coverage and
status contract, and its resource/admission limits. Document whether reuse is sufficient
or a bounded candle-only endpoint is necessary before implementation. Define atomic
handoff and tests for corrections, switching TF, stale responses and failed history.
Update RQ-7 and plan section 5/validation with the approved provisional display policy.

This proposal does not activate PREPARED mode or shorten indicator seed/dependency
windows. PREPARED rollout remains subject to its existing release gates.
