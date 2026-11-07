# 3m implementation checkpoint — 2026-11-07

Result: **Review findings addressed; authorized refactor and affected validation passed; required CI/Release pending**.
Branch feature/f-12-3m; uncommitted changes on base f15596d. No commit/push/merge.
Implementation follows approved plan/validation until the source-maintenance conflict.
The owner runtime database and API/frontend processes were not changed by this task.

## Implemented scope

- Core M3=180s, native REST bound, chart selector/timeline and generated contracts.
- Draft migration0066 extends schedule/TF constraints, dynamic catalog9TF readiness,
  count bound9 and shared scheduler indexing. Uses prior checked DDL helpers.
- Isolated DB regression cases: SQL/Python schedules, exact amounts, invalid duration/
  unknownTF, guarded downgrade, concurrent insert/downgrade,18-series seed/selection.
- Frontend tests/native3m recorded stream cases and isolated browser fixture extension.
- Future capacity/evaluator metadata9/18; preserve per-series cadence and thresholds,
  five existing fault series and raw-probe denominator. No workload campaign run.

## Historical checks before NC-3M-01 A (failures retained)

| Check | Actual result |
|---|---|
| Empty-source migration trial |0065→0066→0065→0066 passed before later counter/guard changes; not proof of populated-source support |
| Initial core/venue/newDB selection |233passed/2failed/9fixture errors,13.56s; new core test used wrong wrapper signature and DB fixture import/source readiness was missing; corrected later |
| Second selection |106passed/19failed,14.79s; newDB cases and corrected core test passed; failures were profile fixtures/evaluator retaining old16/8 shape; later corrected |
| Third selection |129passed/2failed,28.46s; profiles/rollout/scheduler/newDB selected cases passed except populated-source preservation and catalog lifecycle readiness count guard |
| Catalog counter follow-up |added missing ready_timeframe_count≤9 check in0066; rerun on previously migrated test DB still failed because that DB had prior constraint. Fresh-run launcher then failed import before pytest; fix is not yet certified on a newly migrated schema |
| Frontend regression |50tests/5files passed1.54s: panel, timeline, chartAPI/data/pages controllers |
| TypeScript |passed after contract/UI changes |
| Ruff/format |20affected Python files passed scoped checks after final formatting |
| mypy |18affected backend Python files passed at recorded scoped invocation; final affected recheck of3later-edited test/helper files also passed |
| Scoped frontend ESLint |6changed UI/test/E2E files passed |
| Browser attempt1 |setupFailed: temporary config outside package caused named-export loading errors; no tests ran |
| Browser attempt2 |1testFailed: F12_FIXTURE_REJECTED during seed-3m, before native3m browser assertions. No network/order flow success claim |

Raw logs are retained locally outside the repository in /tmp/tiewtrade-chart3m-*.log.
Private environment files are outside the repository and contain credentials; do not
publish them. Counts above overlap: do not add them as a unique-test total. No full
regression/current-candidate required CI or release capacity proof exists yet.

## Historical blocker before approval A

Populated-source test installs actual source protection plus old-TF READY generations,
heads, checkpoints and source guard metadata, then attempts the migration roundtrip.
Constraint DDL raises SOURCE_MAINTENANCE_SCOPE_REQUIRED and rolls back. Existing
begin_indicator_source_maintenance changes epoch/journal state and expires/removes
derived generation/head state, contrary to current P2.5 preservation assertions.
The draft migration currently fails closed; it does not disable triggers, fabricate
scope or silently invalidate data. See [proposed A/B amendment](../source-maintenance-amendment.md).

The V3-04 failure is current. Earlier empty-DB passes do not override it. Browser
failure is separate and remains open; no repeated full campaign was launched.
Next: owner chooses A (existing maintenance + explicit derived rebuild contract)
or B (new metadata-only protocol proposal). Update specs first, then resume P2 and
only affected checks. Owner runtime0065/working chart/signup remain unchanged.

## Approved A implementation and replacement checks

Owner “อนุมัติ A” on2026-11-07; requirements/plan/validation amended before code.
Migration0066 reuses begin_indicator_source_maintenance, after table locks and IDLE
writer check. Downgrade checks3m inventory before maintenance can remove heads.
No trigger bypass, new maintenance protocol or source/business-value conversion.

-14/14 isolated actual-DB tests passed (approved-a-tests.log): actual0065 populated
  upgrade and guarded roundtrip, oldTF candles/source changes/jobs/checkpoints preserved,
  expected EXPIRED generations/removed heads/new source epoch, unchanged function ACL/
  owners/security/search_path and schema roundtrip; injected post-DDL failure rolls back
  state/schema; claimed writer blocks migration and old source fence fails after upgrade;
 18-series seed/fairness/idempotency and concurrent3m insert/downgrade guards.
-310 fresh-schema tests passed (fresh-regression.log): catalog lifecycle on0066,
  source guards/proof/fences, multi-writer claims, rollout, realtime/core/history/native mapping.
-113 native REST/feed, preview and candleAPI tests passed (api-regression.log).
  The same selection had39 chartAPI setup errors due to missing test Redis URL.
  With isolated test Redis configured, reran only chartAPI on fresh0066:39/39 passed
  (chart-api-regression.log). No assertions, policy, timeout or production settings changed.
-Browser native3m passed1/1 in12.6s (browser-third.log); BTC/ETH history/live180s,
  exact OHLCV, reload and no order/mode requests. Seed fixture first loads recent100slots,
  then bounded regular rounds fill exactly1000/series; production4-fetch budget unchanged.
-Browser shared-fixture regressions passed3/3 in20.1s (browser-regression.log):
  original chart/keyboard, module navigation/cancel, preview→REST confirmation.
-Ruff/check and format20affected Python files passed from backend working directory;
  mypy updated DB test passed. Prior18-file +3-file mypy, frontend50tests, TS and ESLint
  remain valid for unchanged runtime code. Migration/evidence scripts are outside the
  project's mypy src/tests targets; an extra exploratory invocation surfaced SQLAlchemy
  untyped-scalar inference/unreachable diagnostics there, not a project gate pass claim.

These selections overlap; do not sum as unique test coverage. Earlier Failed/Incomplete
results above remain attached to their earlier candidate/environment. Test-only servers
15139/18039 stopped after tests. Owner runtime/schema0065 untouched. No live orders,
full regression/current-candidate CI or Release campaign. No commit/push/merge.

Reviewer focus: shared SQL9TF mapping/readiness, source maintenance effects and writer
fencing, safe downgrade inventory, and native3m lifecycle. Runtime indicator readiness
may be temporarily unavailable until derived rebuild after eventual activation.
Next: await owner `review code` before starting review. Refactor needs a later explicit
instruction per AGENTS. Local activation remains after review/refactor/Feature gates.

## Candidate source hashes (uncommitted, base f15596d)

- `backend/migrations/versions/0066_three_minute_timeframe.py`: `b8eec531659f7849e81a390ea1445c172ff078aeec0ac63f34c7026805540553`
- `backend/openapi.json`: `6eca9565f838bfeda441a66759d1281c96d34731ed8d92a7b4e873a7b3fa56c6`
- `backend/src/tiewtrade/core/timeframes.py`: `d5389ad5766ac854082e48bd4e86bad96728abf4c65ceb6f75617a8b6e7033d2`
- `backend/src/tiewtrade/venues/binance_th/candles.py`: `0e750d156cce8487eec14441b9a5ecc996728acdd68b4b0a7fc228566f8936ca`
- `backend/tests/core/test_chart_history_bounds.py`: `dca559768ab85cfca68892e490b79c27e8fe690498c363825a1f9b300c9d03cc`
- `backend/tests/core/test_market_data.py`: `86c050e2de84a670625621ff4ed1a3c274f46a54b3b25df378cdc7973e59b180`
- `backend/tests/e2e_candle_runner.py`: `14a310ae4b58dadb842f2c4036b9a810839b377f21080e516781a69b94db1b36`
- `backend/tests/infra/indicators/test_rollout.py`: `aa2d55478b76d581fbe8b2b7d88a40eef2303c9a43465fe293398f1cb8d6dbb6`
- `backend/tests/services/indicator_builder/profile_capacity_gates.py`: `2b4966391f1af45bd7aa3b6bb4b3653ccd9decf69da3a2a91944f3ae0bb21217`
- `backend/tests/services/indicator_builder/profile_capacity_s5.py`: `cc7bb40cbd9479ce12ed3e7975c5c8f17c1f91cc5cb92f5f37f9de0128a9dd94`
- `backend/tests/services/indicator_builder/profile_capacity_steady.py`: `94314519abcc409557e0da3cd220736a5c87da36dbad457724264248e2349594`
- `backend/tests/services/indicator_builder/profile_first_release.py`: `88b5c8ab7691dec740de19b123e5817f661614b2582a86f10d54dc10d822fc8c`
- `backend/tests/services/indicator_builder/test_capacity_smoke.py`: `2d0fe5d4aab5d7ec07da8c1165d5e4027803dddde5940d00d775408a0029c818`
- `backend/tests/services/indicator_builder/test_profile_capacity_gates.py`: `c8ed69eab1fbb9dde559c8a5215cf5758840543d74e1fe5819bf45959ad5991d`
- `backend/tests/services/indicator_builder/test_profile_capacity_s5.py`: `def6254118dae8fff10c8e6c6cd947a1451098b90d24d54d819b3cb666f48515`
- `backend/tests/services/indicator_builder/test_profile_capacity_scope.py`: `5dcc505054e3e68f2f4dfe4f70fde5ed5faaad05c835000a81bef4593db09a85`
- `backend/tests/services/market_data/profile_chart_workload.py`: `01dab3519d5a727e183392ca0d4ff8cb6240a130d6de9a6afbd46ebe93b725a9`
- `backend/tests/services/market_data/test_candle_realtime.py`: `82e46531b37c402718c39e67f1b9487ff7af74ada577fe49d229acd9bbc636e6`
- `backend/tests/services/market_data/test_three_minute_timeframe.py`: `b96001d7802929fadc036889a2d1eb944bd68883a351173bdf8811f668fc3314`
- `backend/tests/venues/binance_th/test_candle_stream_mapping.py`: `1b62749f75939a91bdc4483da8912427b2bdee6a911e381ca37711a1a2e44601`
- `frontend/e2e/candlestick-chart.spec.ts`: `a7f2a20c3f601b0235cf3dc677d1904ea09cbbfc035141febb8ff838ae5f1042`
- `frontend/e2e/chart-workload.workload.ts`: `ad5b7b98e39cff22a7fceb790172fe8474212508b721bb5ac96ec31d67226021`
- `frontend/src/CandlestickChartPanel.tsx`: `96ff73e0006fa79eaa63d3a0c71a0362cf1edc0460e950af7aa8fdad3d0c2f5c`
- `frontend/src/api-types.ts`: `3191f1748c985ed50bc7a4026bafb06168e2b48256f6914f3bf91b28e75c9250`
- `frontend/src/chart/candleTimeline.ts`: `d49e6219c746bbf8ec8877f39b7b3ea2bbb35155f1c64fff2e96330467d4e940`
- `frontend/tests/CandlestickChartPanel.test.tsx`: `7c7b4753624eba0dc042826b5690a5b40fe028bf3e1fdd35d7329bea4c159c22`
- `frontend/tests/chart-candleTimeline.test.ts`: `62345b91232daf7ecb9148419ad710445f90c4c152ff7752dd88b78bf6365b72`
- `specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py`: `f5deeaf0e90e597ab4b0df8ffe6c6d07e02916fb4a7ea5f5e0df34dfc67a3555`

## Review findings M1/M2 fixes — 2026-11-07

Owner `review code` found two Medium validation gaps; owner `เริ่มทำ` authorized fixes.
No runtime/business logic or migration was changed in this correction.

- M1 addressed: native3m BTC/ETH fixtures now use distinct exact OHLC values, separate
  from H1. Browser test waits for real browser candle-page and live responses for the
  selected series, checks base/timeframe/180s/open values, verifies the distinct rendered
  open and absence of stale H1/BTC values, and retains no-order-mutation checks.
  There are no independent page.request live probes in this test anymore.
- M2 addressed: actual0065 claims serve15 or16 old-series jobs before upgrade, leaving
  durable cursor14 or15 plus nonzero last-served/attempt history. Migration preserves
  complete slot/job state. Seeding adds exactly2 new jobs; actual-role claims first finish
  the unserved current round, then cover all18 series in the next round without duplicates,
  proving ring wrap and new slots with no cursor reset.

Checks and retained failures:
- First expanded DB selection:14passed/2failed. The new test setup used clock_timestamp()
  per row for deadlines, so they were not equal and priority ordering dominated the ring.
  Corrected only fixture to statement_timestamp(), ensuring a common deadline.
- Reran only the2 affected cursor cases:2/2 passed (review-cursor-tests.log). Existing14
  migration/constraint/guard cases passed in the expanded run and remain valid.
- Strengthened browser3m:1/1 passed16.5s. Shared fixture regression:3/3 passed22.3s.
- Scoped Ruff/format3files, mypy2testfiles, frontend ESLint and TypeScript passed.
- git diff --check passed. Existing production/API/core results remain valid.

All review findings addressed within their scope; no runtime activation, commit/push,
CI or Release campaign occurred. Owner runtime stays0065. Next await explicit
`refactor the code` per AGENTS; required CI/full validation and local activation remain
subject to existing gates. No fresh whole-feature review was started automatically.

Changed files at this correction (hashes supersede earlier entries only for these files):
- `backend/tests/e2e_candle_runner.py`: `ef864785682f6685dcee14c0ea714af2f8837cafd8e84d72bff754ab218e8c94`
- `backend/tests/services/market_data/test_three_minute_timeframe.py`: `55e1d8de25561d9b52777a3fb65f19b4439b3a4948d1d1e6db2d4df4f47a581e`
- `frontend/e2e/candlestick-chart.spec.ts`: `70da771c2272e25d2b8ef9d0aa8f6eacbe2b9d48e6f8555df82e02fec89e3af0`
- `specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py`: `d20d01cc9f7390249b1abfe467edb11198f540b0257e60d76cdd7d4c9e974a76`

## Authorized refactor and validation checkpoint — 2026-11-07

Owner requested `refactor the code`. Scoped changes only:
- Explicit per-series price fixtures and named OHLC fields replace nested ternaries.
- Browser test reuses CandlePage/ChartLive API types and existing response waits;
  removes the duplicate request log/assertions. Series selection, exact amounts,
 180s duration, stale-value rejection and no-order checks are unchanged.
- Cursor test reuses its job snapshot query and names the series-index mapping,
  retaining migration state preservation, current/next rounds and all18-series coverage.
- No production, SQL migration, formulas, permissions, timeouts, retry or business logic changed.

Affected validation ran immediately after refactor:
- Populated cursor migration/fairness cases:2/2 passed (refactor-cursor-tests.log).
- Native3m browser flow:1/1 passed18.5s (refactor-browser.log).
- Shared-fixture browser regressions:3/3 passed20.3s (refactor-browser-regression.log).
- Scoped Ruff and format3files, mypy2testfiles, frontend ESLint and TypeScript passed;
  git diff --check passed. Other recorded runtime/migration/API/UI evidence remains valid.

No extra confidence-only full suite or Release campaign. Required CI/full regression
must still run on the final PR candidate before merge; no commit/push/PR is authorized
in this refactor command. Release V3-10A/B remains Not Run / Pending Full Validation.
Owner app/schema0065 untouched. Test servers stopped normally; generated legacy
screenshot retained privately and original evidence restored. No commit/push/merge.
Next requires owner Git instruction to commit/push/open PR, then follow required CI.
Local activation remains after Feature gates; no Completed/release claim.

Refactored file hashes (supersede earlier hashes only for these files):
- `backend/tests/e2e_candle_runner.py`: `058e981ba3008504a4ff278a0ecfee21faf90e06071cc8d6a47614a29a627a01`
- `backend/tests/services/market_data/test_three_minute_timeframe.py`: `880881442262d7a8ed7e27125375a92686e47c4fa5e07660f5ac3ca575c75ba1`
- `frontend/e2e/candlestick-chart.spec.ts`: `318efe0e347efbaab3166099e3b8a6662df24d445dcaa0ea016a2889e17b63f7`
- `specs/features/2026-10-12-candlestick-chart/evidence/browser_fixture.py`: `e39fb95b9b5d9ec011b3236a0bd19c8bca82e3ab9edae44aa8a9f175f296f003`

## Git / CI checkpoint opened — 2026-11-07

Owner `เริ่มทำ` authorized the proposed commit/push/PR step after refactor.
Branch is based on current origin/main f15596d; no merge authorization inferred.
Implementation/review/fixes/refactor and affected validation receipts are included
in this candidate. Required CI will be followed on its exact PR head SHA and reported
with run links; do not create a documentation-only CI recording loop. Local activation
remains gated by Feature checks; Release profiles remain Pending Full Validation.
