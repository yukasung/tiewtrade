# D4–D7 implementation and combined review — 2026-10-12

Scope: the approved functional D4–D7 work, including NC-36 (owner instructed
the grant fix on 2026-10-12). Capacity/soak remains phase 9. This report is not
a production activation bundle or a claim that F-11 is complete.

## Implementation and evidence

- D6: migration 0023 checks effective SELECT/EXECUTE privileges required by the
  API, market-data and builder roles before non-PAUSED transitions. Missing
  privileges return POLICY_UNSUPPORTED without changing mode/epoch. PAUSE remains
  available when configuration is broken. Runtime function signatures reuse their
  owning migrations. No runtime grants or money/trading behavior were changed.
- The per-grant fault matrix revokes each privilege, confirms it is absent,
  checks unchanged control state, proves PAUSE works, restores the privilege,
  activates and replays without another epoch change. An independent catalog
  inventory checks the manifest is complete. Trigger/control/codec/protocol fault
  cases also fail closed. The original independently specified API-view regression
  now passes; its previous failure XML remains historical evidence.
- D5/D7: real Compose project with two APIs and real one-shot F-09 cleanup / builder
  GC commands, isolated PostgreSQL/Redis and immutable image IDs. It exercises
  stop/drain/start, then compatible rolling replacement (old and new APIs overlap).
  Existing v2 rows and cursor identity agree across replacement. Each sidecar must
  exit zero. No live venue requests or application containers are used.
- Real inventory/capability checks reject omitted containers and an offline legacy
  F-09 container. Real orchestration pauses after drain. A committed missing API
  grant blocks PAUSED→PREPARING; operator inspection observes unchanged state;
  repaired grants plus exact pause replay preserve the epoch.
- Retirement rejects an unelapsed support window and an active API DB reader.
  Actual Alembic downgrade is rejected in both cases. After the fixture ages the
  DB cutoff past six hours and readers drain, retirement check succeeds and
  migrations downgrade to 0014 without deleting the candle rows. Only then are
  the API cursor-key configuration and compatibility images retired. The approved
  pre-F11 binary returns 403 for its unclassified indicator route (D1 baseline).
  A real 365-days-plus-3-hours candle survives compatible cleanup, then legacy
  cleanup removes it after retirement. Head schema/proof is restored for teardown.

Final Compose + D6/rollout/barrier run: **89 passed, 0 failures/errors/skips,
117.997 seconds**. Artifacts: `d57-compose-tests.xml`, `d57-compose-evidence.json`.
Earlier grant-fix regression: `d6-grants-fixed-tests.xml`, 80 passed in 9.908s.

## Review checks

Reviewed migration policy/lock order and replay, effective privilege inventory,
source proof, API routing, retirement checks and downgrade sequence against
requirements, plan, performance-plan-v2 D4–D7 and rollout-runbook. Inspected
changed files directly (feature files are still untracked), plus git diff and
related existing rollout/API/worker/migration code.

NC-36 High is corrected. The privilege predicate adds no row locks or runtime
write permission; existing guard→control→slot order, atomic rejection, bounded
orchestration, retry/fence rules and PAUSE exception remain intact. Migration
0023 is unreleased: existing test DBs must reinstall it via 0022→head; an ordinary
upgrade-head on an already installed 0023 does not apply this source edit.

The harness uses actual HTTP/DB/container boundaries, checks process exit and
runtime-session drain, records image/control identities without keys/cursors,
and cleans up only its unique Compose project. It does not send orders, compute
balances/PnL/margin or change exchange retry behavior.

## Limits and remaining gates

- D4 positive activation still uses the restricted SQL helper with a real prepared
  fixture, not a fabricated capacity bundle. D4 API/source/build/cleanup barriers
  are complementary scenarios; see `d4-active-build-report.md`.
- D7 Compose writers are finite cleanup/GC commands. Full launcher/worker lifetime
  remains covered by the existing G/L/worker tests and D4 active CPU build case.
- Test keys are public fixture keys. Actual production inventory, distribution of
  the verification keyring, external/offline restart paths and owner-reviewed
  capacity evidence remain operator/release gates. Labels record non-secret
  configuration IDs; they are not a proof of arbitrary production configuration.
- The support-window fixture ages DB cutoff; it does not wait six wall-clock hours.
  Before/at/after boundary tests remain in the companion rollout-barrier suite.
- Post-update L/F/G-related regressions do not close unrelated outstanding F1–F6/N4
  acceptance clauses or full capacity. D7 aggregate release acceptance remains
  partial until its dependencies pass. No zero-downtime claim is made.
- Failed prototype runs exposed test assumptions (time-varying response metadata,
  legacy route status and proof restoration on teardown); these were corrected
  against existing contracts. No production requirement was weakened.

## Final verification and review result

Post-update regression: **213 passed, 0 failures/errors/skips, 165.597 seconds**
(`d47-post-update-regression.xml`). Includes the actual D4 CPU/HTTP lifecycle on
current images (`d4-reviewed-evidence.json`), source/maintenance lock matrix,
claims/fences, complete runtime function ACLs, global lock/shutdown ordering,
worker error/retry paths, manual recovery/GC and prepared API routing.

Ruff check/format passed on all four changed Python files; mypy passed 344 files;
all seven architecture contracts passed. git diff --check passed. One existing
FastAPI/Starlette test-client deprecation warning was emitted, with no test failure.
Teardown confirmed revision 0023, mode LEGACY, slot IDLE, restored API SELECT,
zero API/auth/market-data/builder DB sessions and no rehearsal Compose containers.

No unresolved Critical/High/Medium/Low findings in this scoped implementation
review. NC-36 is fixed and its negative/positive controls pass. Functional
D4–D7 harness work is approved; aggregate D7/F-11 production acceptance remains
subject to the explicitly listed outstanding dependencies. This is not approval
to commit, push, merge, enable PREPARED in production or mark F-11 Completed.

APPROVED

