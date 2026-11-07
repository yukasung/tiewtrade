# Exact extension remote checkpoint — 2026-11-07

Head12e62040d00f2797a7c192b50bd1d81c8edb3d68, draft PR59.
Security42367203731 **Passed7/7**. Complete history/tree scanned; stage timing:
60.9405s history,1.2913s history mapping,7.5867s export,50.2232s tree,6.0626s tree
mapping (126.104s total stages). The unchanged15min deadline is met. All CodeQL,
dependency, policy and aggregate checks passed. This closes the previous secret
timeout/exact-identity blocker for this head; old failures remain unchanged.

PR CI42367203737 **Failed5/6jobs passed**: main backend pytest4759passed/2failed/
31deselected in997.24s; later isolated steps Not Run. Push CI42367198109 failed
the same2cases (4759passed/2failed/31deselected in796.31s). E2E, frontend, API,
containers and PostgreSQL config passed in both. Backend static checks passed.

Failures: missing backend PLATFORM_BOOTSTRAP URL in all-role checkpoint preflight,
and NoResultFound for the first coordinated financial wrapper scenario's required
projection. The latter still needs controlled isolated-input verification; do not
claim its exact queue cause proven from this log alone.

No new fix/retry after this third non-passing published recovery CI round. See
[two-file proposal](../../remaining-ci-fixtures-plan.md). Existing Security approval
and exact data remain valid; no exception expansion or acceptance relaxation.
No merge/deploy/F17 completion. Next: owner chooses the proposed checkpoint before
the next fix/test/publication round; do not create documentation-only remote CI.
