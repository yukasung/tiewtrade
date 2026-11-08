# F17 publication E2E correction — 2026-11-08

Owner approved Option A in publication-e2e-empty-state-proposal.md before edit.
Only protections.spec.ts:321 changed, to the exact current emptyActivity text.
Production code and all financial/no-SELL assertions unchanged.

- ab9c57a replacement [Security](https://github.com/yukasung/tiewtrade/actions/runs/42461978478): Passed all jobs.
- ab9c57a [CI](https://github.com/yukasung/tiewtrade/actions/runs/42461978437):
  browser Failed: F17 six Passed, one Failed obsolete empty-text assertion.
  F16 seven Passed; main browser20 and catalog2 Passed. Later risk E2E skipped.
  Backend still running at preparation; no successful full CI claim.
- Targeted real-DB browser: one Passed (11.8s), including rejected standalone
  request, reload, 9900 cash, exact BTC held/reserved/protection/available and
  all orders BUY assertions. Existing test-policy override retained.
- Isolated database: tiewtrade_e2e_f17empty20261108, distinct from owner DB.
  Screenshot alongside is test data. Prior screenshot preserved.
- Scoped ESLint/typecheck and git diff --check Passed. Temporary venv link removed.

Normal commit/push and one further required CI round approved; results pending
until observed on final candidate. No merge, Live order, owner mutation or F17
Completed claim. Existing Batch/Release dependencies remain pending.
