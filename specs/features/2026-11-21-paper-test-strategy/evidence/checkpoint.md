# Paper Test Entry — Local implementation / review checkpoint

2026-11-21, branch `feature/paper-test-entry`, worktree `../TiewTrade-paper-test-entry`.
Baseline local F-21 snapshot e811800a2ea50ed618965fd4156c038b39921a14. Working-tree candidate,
not a published SHA. Original F-21 branch, WIP/index, preview15121/API18021 preserved.

**Implementation and targeted local checks done; owner acceptance and required CI pending.**
No merge/publication or production/Live activation. Batch/Release: Pending Full Validation.

## What changed

- Distinct gated strategy `paper-green-atr-test`: CLOSED green candle, selected timeframe,
  ATR14, user quote budget, one occupied/pending entry at a time. No RSI/EMA filter.
- Reuses F-21 source/lease/candle/entry/exit fences and F-17 financial/protection writer.
  TP/SL are first actual fill ±3×signal ATR, with approved TP tick floor and exact SL.
  Later fills change quantity only; invalid actual levels retain fill and use BOT failure/STOP.
- Migration0075 adds owner-scoped append-only configuration and first-fill metadata with
  FORCE RLS, scope FKs, narrow grants and a once-only resolution trigger. Advisory key lock
  serializes configuration idempotency across the two distinct strategy tables.
- API/UI use strict typed test config, explicit server/worker opt-in, immutable run pin and
  existing Start/Stop/journal controls. No max-entry input for test strategy. Live refused.
- CI includes a separate owned DB/ports E2E step; default production composition stays closed.

## Tests and static checks

| Evidence | Result / scope |
|---|---|
| [Pure](pure-final.log) |66 passed: RSI regression plus test entry/config/levels/property cases. Later [next-candle](next-candle.log) rechecks4 changed terminal/re-entry cases.|
| [Regression](regression.log) |46 passed: basket accounting, decision atomicity, indicator inputs and ordinary F-17 protection lifecycle.|
| [Safety](safety.log) |68 passed: commit fences, STOP/source/risk/catalog/lease changes, exit races, recovery/feature gates; includes8 first-fill test integration cases.|
| [Late fill](late-fill.log) |10 passed: late fill/cancel, crossed bracket, unknown exits and acknowledgement-loss replay in shared F-17 path.|
| [Migration](migration.log) |4 passed: new/old schema roundtrip, narrow grants, downgrade history refusal and restored FORCE RLS.|
| [API](api-final.log) |12 passed: config/gate/owner/idempotency/strict inputs/Live refusal plus old RSI contract.|
| [Registration fault](registration.log) |1 passed: failure after anchor registration rolls back anchor, entries, links, decision, command and run revision; retry succeeds.|
| [Restart/replay](restart.log) |2 passed: actual fill transaction rollback/retry, concurrent claim replay, immutable anchor/RLS/grants, separate interpreter+DB pool reconstructs test strategy and original106/94 levels.|
| [Engine gate](engine-gate.log) |1 passed: persisted test run cannot execute when test worker opt-in is absent; system STOP requested, no order.|
| [UI](ui-final.log) |26 passed: existing panel cases plus strategy selection, strict payload and journal remount.|
| [Browser](browser.log) |2 passed in4min: actual API Start→future real CLOSED green→BUY→TP or SL→SELL→zero position/reservations→Stop, plus reload/pin. Controlled public-source fixtures, not actual Binance pricing.|
| [Ruff](ruff.log), [mypy](mypy.log), [imports](imports.log) |Passed,291 checked Python source files;7 architecture contracts kept.|
| [ESLint](eslint.log), [types](types.log), [build](build.log) |Passed; generated OpenAPI/types synchronized. Existing Vite bundle-size warning retained.|

Distinct test scopes:208 backend cases,26 UI cases,2 browser cases (236 total), excluding
repeat checks. This counts passed tests, not branch coverage or every possible race permutation.
`git diff --check` passed. DB tests use guarded owned scratch databases and runtime DB roles;
no mock substitutes for financial ledger/locking evidence and no Live orders.

## Review and refactor

Reviewed this branch's entire source/config/schema/test diff and relevant callers, F-21
entry/exit/recovery dependencies and F-17 fill/trigger/late-fill transaction paths. Checked
requirements/plan, auth/CSRF/RLS, financial precision, state recovery, concurrency, idempotency,
Paper isolation and deployment defaults. Persistent authority lives in PostgreSQL; immutable
registry constants/browser recovery journal are not account/session/business authority.

Refactored nested bracket serialization, duplicate configuration reads and an unnecessary join;
extracted shared candle fixture without changing RSI assertions. Used existing UI components and
React checklist from `vercel:react-best-practices`. No remaining material code finding identified
within this review scope. This local review does not replace owner acceptance or required CI.

Earlier failures retained: browser R1 incorrect control URL (404), R2 wrong harness runtime
attribute (AttributeError); R3 passed2/2 after harness corrections. Fault test initially expected
raw SQLAlchemy error rather than translated domain NotPermittedError; corrected expectation,
DB rejection kept. UI mock initially did not wait for catalogue and did not return pending receipt;
corrected then26/26 passed. No safety assertion removed or threshold relaxed.

## Remaining gates / observations

- V13/V15 Partial: owner must inspect actual desktop/mobile, light/dark, locale and keyboard
  behavior. [TP entry](screenshots/paper-test-TP-entry.png), [TP closed](screenshots/paper-test-TP-closed.png),
  [SL entry](screenshots/paper-test-SL-entry.png), [SL closed](screenshots/paper-test-SL-closed.png)
  are automated desktop fixture captures, not owner acceptance. Reload captures can show other
  panels still loading; they do not prove chart rendering or real-market display correctness.
- V16 Not Run: CI configuration prepared, no final published candidate/required CI run yet.
  Owner acceptance is required before publication/merge under this feature's approved plan.
- Browser risk monitor logged DATABASE_TIMEOUT deferrals and retried until both flows completed.
  Preserve this observation; no performance/scalability or production-market claim from this fixture.
- Existing F-21 implementation is an unmerged local baseline. This branch's checks do not approve
  unrelated F-21/UI WIP or replace its own owner/CI gates.
- V17/V18 Pending Full Validation. No leverage/margin/liquidation changes or tests claimed.

**Next:** owner visual acceptance of the feature; after acceptance, assemble final candidate and
run required CI, then evaluate remaining Feature gates before publication/merge. Do not merge
or call the feature Completed while these gates are pending.

## Local preview follow-up

After owner's report that the strategy was unavailable, corrected15121/API18021 to serve
this worktree and opted in both API and the compatible bot worker in the local acceptance
composition. Applied0075 additively on the owned preview DB; preserved existing accounts,
RSI run history and zero positions. No application source change or order/start/resume.
Authenticated catalogue returned both identities, stopped run had replacement proof and no
pending request (selector unlocked); served frontend contains new option. Current owner
Chrome interaction not inspected because CUA host unavailable. Reload the existing URL:
http://127.0.0.1:15121/paper/trade. This supersedes the earlier statement that preview still
uses the original worktree; original F-21 source/index remain preserved. Owner/CI gates pending.

## Approved CLOSED-only diagnostic follow-up

After owner's approval and proceed instruction, corrected misleading readiness reporting:
UNCONFIRMED now yields BOT_CANDLE_UNCONFIRMED and a short waiting-for-confirmed-close
message in compact/full status. Same rejection/source/strategy/execution rules retained.
Readiness mapping is shared within the component; no loading flash or stale RUNNING notice.
See finality-reason.log4 passed, finality-pg.log3 passed, finality-ui.log33 passed and
finality-{mypy,ruff,lint,types}.log. These replace affected diagnostic evidence only;
no unrelated whole-feature campaign repeated. Authenticated preview status verified
PAUSED/BOT_CANDLE_UNCONFIRMED/positions0. Real-market entry remains blocked, owner/CI pending.
