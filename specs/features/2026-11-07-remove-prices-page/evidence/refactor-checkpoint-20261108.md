# Prices removal — post-review refactor checkpoint

วันที่: 2026-11-08 (Asia/Bangkok)
Branch: feature/remove-prices-page
Base: 1237bf6f1e2146fff6c68d01094e4fbb96ebd8c3
Candidate: uncommitted prices-removal diff; frontend diff SHA256:
b890d6d0837796bb8535991bbe86ed89c5659099de0acbdc59c33efece3864da

Owner explicitly requested `refactor the code` for this feature after combined-candidate
validation closed the Medium recovery finding. The Low stale route-list finding was already fixed.

## Refactor

Extracted latestStreamStatus(page) in frontend/e2e/realtime-prices.spec.ts so outage and
recovery polling share the same paired readiness/alert_due read. Assertions keep the same
expected values and timeout settings; the helper uses the API field name directly.
No runtime source or other test flow was changed in this refactor.
Checked that both paired assertions still read one stream snapshot and preserve optional
missing-row behavior. No new finding from these edits.

## Validation immediately after refactor

- Changed-file ESLint passed.
- Frontend TypeScript check passed.
- Real producer → PostgreSQL/Redis → authenticated GET/browser WS E2E passed in 19.3s:
  [log](refactor-price-service-20261108.log). Includes exact price/catalog/timestamps,
  READY/STALE/outage alert/recovery, oversized frame 1008, reconnect and revoke 4401/HTTP 401.
- git diff --check and authored document links passed.
- Prior combined chart E2E 4 passed in 22.6s remains applicable: chart runtime/tests,
  default-loop config and backend dependencies were not changed.
- Prior unit/session/auth/static/build/backend contract evidence remains applicable
  for the same reason. No full regression was needed for this test-only refactor.

Docker daemon was initially stopped and earlier /tmp runner/config were absent. Started
Docker and recreated temporary external config/runner. Used disposable PostgreSQL 16/Redis 7,
guarded database tiewtrade_e2e_prices_refactor_20261108, ports 18013/18175, and readiness
checks before migration. Task containers were removed after the run. No production data,
exchange requests or Live orders were used.

V-01..V-08 local gates are satisfied; V-09 required CI remains Not Run. No commit/push/PR
or merge was performed for prices removal. Next: owner-authorized commit/push/PR, then
required CI on the final candidate. Merge requires its own command. Not Completed/merge-ready.

## Publication authorization

Owner authorized commit/push/PR and CI tracking on 2026-11-08. Merge still requires a separate command.
Published evidence copies normalize trailing whitespace only; output content/results are preserved.
