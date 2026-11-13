# Test mapping — Paper Spot bot panel

วันที่: 2026-11-13
Source base: 4a9b46a; uncommitted feature candidate (see checkpoint for final results).

| Before | After | Retained proof |
|---|---|---|
| PaperTradePage NEW BUY form tests | NEW SELL modal tests; legacy BUY journal remains supported | write before POST, duplicate clicks, UNKNOWN/key/scope, terminal handling, storage failure |
| ManualOrderForm variants | Original tests retained plus fixed SELL test | MARKET/LIMIT payload strings, default Live behavior, protection gate |
| ManualOrderSession | Unchanged | owner/session journal cleanup; not claimed as pre-POST proof |
| No direct useManualAttempt tests | Hook harness sends actual production hook | pre-POST persistence, storage failure POST0, duplicate send POST1, reload/manual retry same body/key, wrong owner |
| Manual E2E BUY setup | postFixtureOrder via authenticated API; refresh discovery | real DB cash/fills/reservation/cancel/reset unchanged |
| Legacy BUY loss/DB-disconnect/reset fault | seedLegacyBuy journal then real UI retry | legacy key/payload preserved; server fault/rollback/duplicate prevention still asserted; seed is not pre-POST proof |
| Storage denial E2E | actual SELL modal submit | production write failure blocks transmission |
| Protection entry BUY / bracket | authenticated API setup, same amounts/prices | actual bracket/exit/cash/reservation/failure/fee assertions unchanged |
| Protected SELL | actual SELL modal, same selected allocations/revisions | reductions and canceled-sale residuals unchanged |
| Risk BUY setup / blocked BUY | authenticated API and real server rejection | same prices/cash/risk baseline/stop rules; no fake BUY UI |
| Risk bounded SELL | actual SELL modal | bounded reduction when opening is blocked |
| Navigation draft/submit geometry | bot budget / disabled Start | real candles, timeframe, resize/draft, internal scroll, no writes, Live remains disabled |

New UI matrix covers four widths × two languages × two themes; component/page checks cover
loading/error/scope reset and late old-owner responses. Settings/menu/SELL modal focus checks
use fixtures and never issue owner-account orders. Only tests changed for API setup; no production
fixture endpoint, trading rule, timeout or financial expected amount was changed.

All screenshot output moved from historical tracked feature evidence into private test-results
for the touched dedicated suites; prior evidence is not overwritten.
