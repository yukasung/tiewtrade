# PR63 — F19 browser recovery contract alignment

สถานะ: **Approved A — owner approved test correction, targeted checks, commit/push and one CI round on 2026-11-08**
Date: 2026-11-08 Asia/Bangkok
Candidate: 19434bca450c5fe6cd6a12e6fd741dbd2bfa6659

## Evidence / diagnosis

[CI](https://github.com/yukasung/tiewtrade/actions/runs/42462612331) passed browser
main20, catalog2, F16 seven and F17 seven. Risk/F19 suite: five passed, one failed
at frontend/e2e/risk-limits.spec.ts:253, expecting the old idempotency key after
reload. [Security](https://github.com/yukasung/tiewtrade/actions/runs/42462612306)
passed. Backend is still running; do not claim full CI passed.

The existing test commits STOP, aborts its response, reloads, then clicks plain
STOP. Approved review correction intentionally resolves a persisted key by GET
on remount; a found receipt retires the old hint. A subsequent explicit normal
STOP creates a fresh cutoff. Test currently mistakes this for UNKNOWN retry.
KillSwitchControls.tsx separates these paths. Existing component tests cover
found REQUEST_PENDING/APPLIED, exact missing receipt, failed lookup, no automatic
POST and fresh MANUAL cutoff. Browser proof must preserve both contracts.

## Proposed scoped correction

Only frontend/e2e/risk-limits.spec.ts and associated evidence/docs:

1. Keep real dropped-response STOP and assert explicit retry **before reload**
   uses the committed key, returns200 with the same request/generation and never
   creates another economic effect. Use the actual retry accessible label.
2. Exercise another dropped-response STOP followed by reload. Observe the real
   by-key GET receipt, assert it references the lost-response identity, no
   automatic POST, and journal retirement. An explicit normal STOP must then use
   a new key/request and advance generation exactly once. Keep generation
   assertions relative to the last known receipt.
3. Retain after-cutoff order, STOP completion and summary, Paper/Live isolation,
   Live-unavailable proof, focus/escape, locale/mobile and unexpected-error
   assertions. Do not remove same-key protection to make the test pass.
4. Reuse existing tests/fixtures; no production code, financial rules, API,
   security exceptions, infrastructure or Live-execution change.

Run the corrected case on an isolated fresh DB, the19 existing STOP component
cases, scoped ESLint/typecheck (about2–4min). If all pass, normal commit/push and
one required CI round (about20–25min), then stop/report. Preserve all prior failed
results. No merge or F17 Completed claim. Any behavior contradicting approved
receipt/idempotency rules is a new blocker, not permission to weaken assertions.

Approval needed because the latest instruction permits only one further CI
round, now used. AGENTS.md requires honoring the checkpoint scope. No edit to
this test or production source has been made for this proposal.
