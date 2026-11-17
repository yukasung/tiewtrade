# W4-CURRENT01 — current-candidate restore, 2026-11-17

สถานะ: Incomplete — one authorized attempt finished; no automatic rerun.

## Result

- Preflight Passed: all seven samples across120s; no fixture before it passed.
- Current1046-file inventory still matches AWAKE01; no production/shared harness changes.
- Total157.256s (2m37s), including preflight and owned cleanup; bound1200s.
- Actual pg_dump/pg_restore completed; backup1,831,704bytes.
- Stopped with SourceUnavailableError in profile_internal_restore.py:585,
  recover_legacy_claims → process_claimed_order → order_book_storage.read_inputs:359.
- Control flow reached recovery only after replay_restored_domain returned, but aggregate
  canonical/RLS/evidence-count/economic assertions and result serialization occur AFTER
  recovery. Their final values were not recorded; do not claim these gates Passed.
- Integrated F16/F17 recovery did not start. Current W4 remains outstanding.

## Evidence and interpretation

Read-only pg_restore --file=- inspection of the retained local dump (no new database)
found ready=true, generation18, last_input_id89, verified_at14:46:47.697814UTC and
lease_until14:46:52.696873UTC. failure.json records14:46:52.722949UTC,
26.076ms after the copied lease expired. Verify readiness observer has0checks; build57.
The legacy recovery callback does not start a publisher before reading restored market
inputs. This supports stale restored market readiness at recovery. The exact state and
DB timestamp AT the rejecting guard were not captured, so do not assert which guard
branch fired or treat exception-write time as the exact query time.

No evidence here establishes a financial discrepancy or a failure of W3. Preserve the
successful four-hour W3 and all historical Failed/Incomplete results. Do not relax lease,
book freshness, rollback, exact-once or financial checks to make this test pass.

## Cleanup

Both manifest/creation-owned databases had0connections/0advisory locks and were dropped
normally. Independent check: both absent,0connections; labeled owned Redis absent.
Owned native sleep assertion released. Other services and unrelated sleep assertions
untouched. No Live/owner trades, force drop, production edits, Git or CI.

## Next step

Prepare a narrow harness amendment for restored-market readiness before legacy recovery,
using existing publisher/recovery patterns. Prove correct target DB, source unchanged,
original guard/freshness and no extra economic effects with targeted real-DB tests.
Review/refactor only affected changes, then one replacement W4 under its recorded scope.
Do not repeat four hours merely because this restore fixture failed. Publication remains
a later checkpoint; F-17 remains Pending Full Validation, notCompleted.

Artifacts: `validation-artifacts/f17-w4-current01-20261117/`; private raw dump and runner
remain local. Sanitized structured receipt: [w4-current01-summary.json](w4-current01-summary.json).
