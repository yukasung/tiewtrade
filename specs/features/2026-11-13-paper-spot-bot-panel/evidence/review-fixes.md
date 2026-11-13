# Code-review fixes — 2026-11-13

สถานะ: Findings R1–R3 fixed and targeted validation passed; awaiting owner refactor instruction.
Base `4a9b46a`; branch `feature/paper-spot-bot-panel`; frontend fingerprint prefix `ff13cf81d9fe`.
Supersedes previous implementation fingerprint for changed files only. No commit/push/merge.

| Finding | Fix | Proof |
|---|---|---|
| R1 Medium: long SELL modal inaccessible | Opt-in scrollable shared Modal, enabled only for SELL; viewport-bounded internal scroll | Real browser 10 protections at 375/768/1440 ×480: dialog fully inside viewport, quantity/first+last allocation/submit accessible, heading reachable at scroll0; Escape restores focus/scroll |
| R2 Medium: missing new SELL browser recovery | Real SELL modal submit, intercept verifies persisted journal before forwarding POST, drop ACK, reload, explicit retry | Same exact key/body/request/order; no autoPOST; real DB command count stays1, fill quantity1, wallet unchanged on second drive |
| R3 Medium: weak safety assertions | Reject BUY with exact503/RISK_PRICE_UNAVAILABLE and503/RISK_SOURCE_UNAVAILABLE; discovery failure explicitly attempts SELL form submit | Real risk test passed with bounded SELL/correction balances intact; page test verifies disabled SELL, POST0 and no journal |

## Checks

- ESLint for all changed source/tests: passed. Final test edits lint/typecheck passed.
- Vitest PaperTradePage/ManualOrderForm/KillSwitchControls/PaperTradingActivity: **73 passed**,2.85s.
- Production build: passed1.13s; existing >500kB bundle warning remains.
- Browser new SELL recovery: **1 passed**,12.5s (`fix-manual2.log`).
- Browser risk outage/cache: **1 passed**,21.6s (`fix-risk.log`); transient DATABASE_TIMEOUT monitor messages occurred, assertions passed without relaxed criteria.
- Browser16 locale/theme/width combinations plus long-dialog short-screen checks: **1 passed**,10.0s (`fix-ui3.log`).
- git diff --check passed. Existing unaffected evidence remains valid; no full workload needed.
- React checklist: stable Modal focus callback, opt-in default preserves other consumers,
  no added request/session/global business state, no financial arithmetic or backend changes.

Logs/traces remain private under `frontend/test-results/bot-runtime/`.
Historical failures retained: fix-manual compared changing snapshot timestamp; corrected to immutable
identities plus exact request body/key. DB `commands` is stored row count (not newly executed count),
so replay must remain1. fix-ui hit breakpoint selector race; fixed expected-breakpoint locator.
fix-ui2 nearest-edge scroll left a fraction of a CSS pixel beyond dialog; explicit center scrolling
now proves full access using the original strict bounds, no tolerance/timeout increase.

All four disposable databases (`_fix_manual`, `_fix_manual2`, `_fix_risk`, `_fix_ui` suffixes)
had zero connections and were dropped normally. Owner DB/runtime/preview untouched; no Live orders.

## Next checkpoint

Await owner `refactor the code` instruction per AGENTS.md, then impacted final validation.
Required CI/publication still pending. No change to F-17/F-20/F-21 status or trading rules.
