# D6 partial-grant activation failure — 2026-10-12

Status: **Original failure corrected — NC-36 Closed (2026-10-12)**.

Owner instructed the fix. Migration 0023 now checks required runtime grants.
The original 1-failed XML below is retained as history; corrected grant regression
passed 80 tests, followed by the combined Compose/rollout suite (89 passed).
See `d47-combined-review.md` for final scope and evidence.

High: `backend/migrations/versions/0023_indicator_rollout.py`,
`transition_indicator_rollout`, non-PAUSED policy predicate, does not verify
required runtime grants. R2-D6 requires half-installed grants to prevent PREPARED.

Reproduction on isolated PostgreSQL port 55433:

1. Reuse existing source-proof/prepared fixtures and 30 synthetic READY heads.
   These heads test only the transition predicate, not capacity or HTTP parity.
2. In a rollback-only transaction, revoke SELECT on `indicator_ready_generations`
   from `tiewtrade_api`. Verify `has_table_privilege` is false.
3. Invoke the real migrator transition PREPARING to PREPARED.
4. Expected fail closed; actual result is **APPLIED**, with a new epoch.

The API cannot read the required READY view despite successful activation.
The production CLI's immutable-image capability and evidence checks do not inspect
these live DB grants; a valid historical evidence bundle cannot establish them.
This reproduction directly tests SQL, not a fabricated production evidence bundle.

Recommended fix: validate required runtime privileges before allowing PREPARED,
preserve mode/epoch on rejection, and retain the existing ability to PAUSE when
configuration is broken. Add negative controls for partial grants plus a restored
grants positive control; then continue D5–D7 and review D4–D7 together.
No requirement change or relaxation is proposed.

Evidence: `d6-partial-grant-tests.xml` (**1 failed**, no skip/xfail).
Regression: `backend/tests/infra/indicators/profile_partial_install.py`.
Ruff check/format passed. Transaction rollback restored SELECT; teardown verified
mode LEGACY and slot IDLE. No production code or application database was changed.

AGENTS.md explicitly says to stop and ask when code conflicts with specs.
D5/D7 remain incomplete; no combined D4–D7 approval is claimed.
