# Implementation checkpoint — 2026-11-13

สถานะ: Ready for Code Review — implementation/local validation passed; review/required CI pending
Branch: `feature/paper-spot-bot-panel`; dependency/base: `4a9b46a`.
Uncommitted frontend candidate fingerprint (SHA-256 prefix): `f7ca45e56085`.
No commit/push/merge or owner-preview switch performed.

## Changes

- PaperBotPanel: sole Grid Close System choice, exact balance display, local text budget,
  disabled Start, shared template controls and Thai/English messages. No bot endpoint or strategy.
- PaperTradePage preserves recovery/discovery/risk/protections/cancel; draft scope is
  owner/wallet/episode/pair. Late old-owner data is not displayed.
- Approved RQ-13 provides a separate SELL-only modal below the chart. ManualOrderForm
  keeps default Live behavior and existing MARKET/LIMIT, protection and submission rules.
- Browser BUY setup uses authenticated fixture API; SELL remains real UI. Legacy BUY recovery
  seed is explicitly not pre-POST evidence; direct production hook tests cover that boundary.
- STOP regression locators now open Settings/account navigation before accessing controls.
  Assertions for money, isolation, request keys, stop generations and completion remain intact.

## Local validation

Targeted unit suites passed: PaperBotPanel, PaperTradePage (33), ManualOrderForm (6),
useManualAttempt (3), ManualOrderSession, PaperTradingActivity, KillSwitchControls,
AccountSession. Existing results reused for unaffected cases. Final old-owner test rerun:
1 passed, 32 deliberately filtered; 1.05s. No failed test hidden by this filter.

| Browser campaign | Result | Duration | Evidence under frontend/test-results/bot-runtime/ |
|---|---|---|---|
| manual-orders | 7 passed | 45.1s | manual-round1.log / manual-round1-results |
| protections | 7 passed | 54.6s | protections-round1.log / protections-round1-results |
| risk/risk-key and remaining cases | 4 passed, 2 STOP cases initially failed | 2.2m | risk-round1.log / risk-round1-results |
| Paper/Live STOP recovery | 1 passed; Platform Owner blocked by reused fixture DB | 14.2s | risk-round2.log / risk-round2-results |
| Platform Owner on empty isolated DB | 1 passed | 22.4s | risk-owner-clean.log / risk-owner-clean-results |
| bot matrix + real chart/layout/timeframe | 2 passed | 12.6s | ui-round2.log / ui-round2-results |
| expanded menu/Settings/SELL focus + 16 UI combinations | 1 passed | 8.8s | ui-focus.log / ui-focus-results |

Final distinct dedicated financial/regression browser cases: 20 passed (7+7+6).
UI matrix: 375/768/1280/1440 × Thai/English × light/dark. Real chart test retained
actual timeframe/reset, resizing, scrolling and no mutation checks. Geometry fixtures are
not used to claim financial correctness. Screenshots/traces/logs remain private and ignored.

Commands: `npx vitest run` with the suites above; dedicated Playwright configs
`playwright.manual-orders.config.ts`, `playwright.protections.config.ts`,
`playwright.risk-limits.config.ts`; isolated UI config in `test-results/bot-runtime/`.
After failures, reran only affected cases using `--grep` (F-19, Platform Owner, Paper bot panel).
Private runner changes CI fixture DB URLs/ports only; production API on separate 8019/UI5189
for UI checks and existing dedicated safety configs for their fixtures.

Static checks: frontend lint/typecheck/build passed; final changed-file ESLint/typecheck
passed after test edits; final owner-isolation test lint passed. Build retains existing
large-chunk warning (>500 kB). No generated API/schema/dependency/backend files changed.

## Failed/invalid attempts retained

- Initial page tests expected removed manual controls; adapted locators/flows and passed.
- Refresh test initially asserted before query notification; now awaits actual state.
- UI round1: heading ambiguity (panel + Alert) and obsolete Start scroll expectation;
  fixed level-2 heading selector and explicit internal scroll proof; round2 passed.
- Risk round1: Live STOP expected outside Settings, admin link expected without dropdown;
  corrected navigation-only assertions, financial assertions unchanged.
- Risk round2 Platform Owner: reused fixture contained an owner from round1. Clean separate
  DB passed; no production behavior or singleton constraint altered.
- Test-only async-act lint errors corrected; final isolated test and lint passed.
- Wrong-cwd tool commands did not edit files or constitute successful checks.

## Isolation and cleanup

Used only disposable databases named `tiewtrade_e2e_botpanel_20261113` with optional
`_manual`, `_protections`, `_risk`, `_risk_owner` suffixes. After campaigns all had zero
connections; all five were dropped normally (no force). No owner database, containers,
volumes or owner processes stopped. Test servers exited. No Live orders sent.

## Outstanding and next step

V10 pending: owner-directed code review, fixes/refactor if requested, then final candidate
required CI on publication authorization. Owner visual acceptance Not Run; local preview
still uses its original worktree. Navigation dependency has its own pending workflow.
No new Batch/Release workload required by this UI-only diff; existing F-17/F-20/F-21 gates
and statuses unchanged. Bot remains unavailable; this does not complete strategy features.
Reviewer should focus on owner/scope isolation, SELL-only payloads and recovery outside modal.
Next: owner sends `review code`; do not begin review/refactor or publish automatically.
