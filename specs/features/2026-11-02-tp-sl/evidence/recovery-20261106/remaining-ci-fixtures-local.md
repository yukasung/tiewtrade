# Approved remaining CI fixtures — local checkpoint,2026-11-07

Owner approved Option A of remaining-ci-fixtures-plan.md before this fix/retry
cycle. Only the two specified executable/config lines changed:
- Backend CI now supplies PLATFORM_BOOTSTRAP URL using the existing disposable
  E2E/bootstrap credential pattern and backend database. No new role/grant/service.
- The financial-oracle wrapper uses the existing fresh DB fixture. Every original
  scenario/fault/oracle assertion and the1-successful-claim budget is unchanged.

51targeted cases passed together in27.22s:10coordinated financial oracles plus
claim regressions and actual-role checkpoint preflight. This proves the controlled
scenarios pass on isolated input; it does not reconstruct the earlier CI-selected
owner/claim. Historical NoResultFound and missing-config failures stay unchanged.
Ruff/format/Linux mypy passed the affected test module. Pinned actionlint passed the
CI workflow; backend bootstrap role URL equals the existing E2E role configuration
with only database name changed. Evidence:remaining-ci-fixtures-targeted.log/.xml,
remaining-ci-fixtures-mypy.log and remaining-ci-fixtures-actionlint.log.

Full pinned history/tree scan must pass before the one authorized combined push/CI
round. Keep existing immutable exception approvals, coverage and15-minute security
budget; no new exception, skip/xfail, production rule, timeout or assertion change.
No trading workload, merge/deploy/Live or F17 completion. Required CI must run all
later isolated backend steps too; local targeted proof is not remote CI.
