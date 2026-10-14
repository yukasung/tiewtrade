# F-12 local preview — 2026-10-12

This is development-preview evidence, not complete F-12 acceptance. The owner
authorized updating the local containers after discovering that the running
frontend and API did not contain F-12.

## Local environment

- UI: http://localhost:5173/; chart mounts after authentication.
- Opt-in configuration: [compose.chart.dev.yaml](../../../../compose.chart.dev.yaml).
  Base Compose still leaves the chart disabled. API host port is 18000 because
  Windows reserves a range containing 8000; the frontend proxy still uses api:8000.
- Start: `docker compose --env-file config/postgres.env -f compose.yaml -f compose.chart.dev.yaml up --no-build -d --wait --wait-timeout 60`.
- API, market-data, migrator and frontend images rebuilt from this working tree.
  [Snapshot](chart-enable-snapshot.json) records input hashes, Git baseline and
  running image IDs; it includes uncommitted inputs and is not a merged revision.
- Development DB backed up with `pg_dump -Fc` before upgrading. Backup is outside
  the repository at `%TEMP%/tiewtrade-before-f12-20261012-201648.dump`.
- Market-data drained before migration; existing idempotent event-trigger
  bootstrap applied, then the migrator upgraded development DB from 0014 to 0024.
- Indicator rollout remains LEGACY. No PREPARED activation or order submission.
- Local checks: UI and proxied health HTTP 200; chart component HTTP 200;
  frontend/API chart flags enabled; library 5.0.9 installed.
- Actual DB: both preview tables allow API SELECT and deny API writes.
  Feed connected/bootstrapped with no failure code; preview rows observed within
  the 60-row bound. This observation is not workload/soak evidence.

## Checks

| Check | Environment / command | Result |
|---|---|---|
| Chart API, preview fencing, proof, candle parser and shared trade transport | Linux Python 3.12, disposable tiewtrade_f12_test; run_backend.py pytest with the six selected modules | [49 passed](chart-enable-linux.xml) |
| Migration roundtrip, actual roles and gates | Linux Python 3.12, disposable tiewtrade_f12_test; run_backend.py pytest tests/infra/db/test_migrations.py tests/infra/db/test_roles.py tests/gates/test_gates.py | [60 passed](chart-enable-gates.xml) |
| Frontend types and read episode | Built Linux frontend image, Node 22.23.3: npm run typecheck; npm test -- tests/chart-readEpisode.test.ts | Exit 0; 9 passed |
| Final types and affected E2E/config lint | Node 22.23.3: tsc --noEmit; eslint e2e/candlestick-chart.spec.ts playwright.chart.config.ts | Exit 0 |
| Browser recovery, source mutation, gap and logout | Node 22.23.3 / Chromium, disposable tiewtrade_e2e_f12; run_browser.py NODE22 --reporter=list,junit | [2 passed, 1 failed](chart-enable-browser.xml); layout assertion failure described below |
| Browser layout after assertion correction | Same environment: run_browser.py NODE22 --grep "actual chart panes" --reporter=list,junit | [1 passed](chart-enable-layout.xml), [chart screenshot](chart-browser.png) |

The final browser results cover all three existing stories across two commands;
the latter changed only the layout assertion in the first story. They do not
constitute a single all-green run or the six minimum flows required by validation.
The browser fixture uses real API/PG and controlled FakeVenue ingestion, never
the development database or real orders.

Earlier diagnostic results are retained, not counted as acceptance:

- [Windows focused run](chart-enable-focused.xml): 34 passed, 15 setup errors.
  The network guard intercepts socketpair while Windows creates its event loop.
  The same selected modules subsequently passed on Linux.
- Initial browser run: 2 passed, 1 gap-selection failure. Scrolling/moving the
  pointer to the previous-candle button selected a different candle via crosshair.
  The test now verifies the initial latest selection and activates the button
  with Enter. Its focused rerun passed; the subsequent file run also passed it.
- Subsequent browser run: layout assertion raced the chart ResizeObserver after
  viewport resize. It now polls the same no-horizontal-overflow condition instead
  of checking it immediately. Its focused rerun passed at 375/768/1440 widths.
- Dedicated browser launcher starts Vite with the selected Node executable and
  forwards CLI arguments for focused checks and artifact reporters.

## Remaining acceptance

Each partially covered criterion still needs its remaining cases. In particular,
V-17 workload in both modes, the remaining required E2E flows, complete V-18
regression/build/generated-contract/CI/review and owner manual acceptance remain
open. No full repository suite was run during this local-preview step, and no
feature is marked Completed. Earlier full-suite artifacts are not automatically
valid for this snapshot.

Flow verification followed the local-browser guidance in
[vercel:verification](C:/Users/User/.codex/plugins/cache/openai-curated-remote/vercel/0.54.1/skills/verification/SKILL.md).
