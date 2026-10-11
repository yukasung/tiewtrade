# G1–G6 — Evidence after the four harness review fixes

Date: 2026-10-11

Result: **All four fixes implemented; targeted verification passed. Ready for re-review.**

- [Container/lease tests](container-tests.xml): **20 passed**, 269.233s;
  G1: 15 barriers, G4: 4 faults, G3: 1 actual 151.000-second pause.
- [Shutdown/ACL/lock-order regression](regression-tests.xml): **24 passed**, 11.115s.
- Both runs have **0 failures, errors and skips**: **44 passed** in total.
- Ruff check/format on the four changed Python files and mypy src/tests (338 files)
  passed; git diff --check passed.
- After teardown, isolated DB control is LEGACY/PENDING, slot IDLE, builder sessions 0.
- G3 resumed mutation attempts: 0; checkpoint/head rows unchanged; generation stayed
  STAGING until verified REAPED. No capacity/load/soak run was performed.

This directory contains new evidence; the earlier 223-test artifacts remain
historical results and are not overwritten or counted as new executions.

## Review findings addressed

1. **Stale identity during active ownership (G4).** Each of the four real faults
   still uses a container owner, a real contender, and verified container stop/reap.
   The successor is now driven by the test process through the real pinned writer,
   claim, source scan and publication functions. While its slot is RUNNING and its
   generation is STAGING, all five old-identity calls run on the successor's actual
   physical writer session. Thus rejection cannot be attributed just to an IDLE
   slot, absent advisory lock or caller PID mismatch. Slot, all jobs, generations,
   checkpoint payloads and heads remain identical after each rejected call.
   Positive controls then heartbeat and publish READY using the current identity
   on that same session. No replacement/stub ownership function is used.

2. **No expired-owner writes after resume (G3).** The probe records attempted and
   committed checkpoints plus attempted/completed READY and numeric publication.
   After the actual 151-second pause, the test requires none of those events in
   the resumed portion of the trace. It compares complete checkpoint/head rows
   and generation fields with their pre-pause snapshots. Safe cleanup may only
   leave STAGING or expire it; READY/FAILED_NUMERIC and other metadata changes are
   rejected. Comparison happens before operator reap or successor work, so those
   legitimate later writes cannot obscure an expired-owner mutation.

3. **Observe real unlock and contend during cleanup (G1/G2).** G1 adds the source
   cleanup barrier to all three series/formula cases (15 cases total), with a real
   second container returning LOCK_BUSY while the source snapshot is still open.
   SQL events record the actual unlock statement and assert source-close precedes
   it, followed by writer cleanup completion. G2's six exit classes use a separate
   contender engine during source and writer cleanup, inspect pg_locks before and
   after the real cleanup, observe actual unlock SQL, and verify pool reuse.
   The G2 SQL observer records unsafe attempts for assertions outside run_attempt;
   it does not throw an instrumentation exception that production could swallow.
   Owner-pool checkout peak remains two (one for no-job); the separate contender
   represents another worker, not extra connections in the owner's pool.

4. **Complete mutation privilege coverage (G6).** All three runtime roles check
   table INSERT/UPDATE/DELETE/TRUNCATE and any column-level INSERT/UPDATE grants.
   Every indicator table additionally receives actual zero-row INSERT, UPDATE and
   DELETE probes, which must return 42501. Statements use constants and WHERE
   false, so accidental privileges cannot cause data changes. TRUNCATE is checked
   through PostgreSQL's effective privilege function without executing it.
   Existing complete function allowlist, PUBLIC EXECUTE and privileged-helper
   denial checks remain in place.

## Reproduction and scope

Use the isolated test PostgreSQL on 55433 and Redis on 56379, with the existing
runtime-role test URLs. From `backend`, set `TIEWTRADE_GLOBAL_EVIDENCE_DIR` to this
directory and explicitly run `tests/services/indicator_builder/profile_global_handoff.py`.
The profile includes the 151-second pause; it is not part of ordinary pytest
discovery. The original global-slot report documents Docker/network prerequisites.

`g1-*.json` and `g4-*.json` contain fixed-harness traces; `g3-real-pause.json` contains
the new pause/mutation evidence. Snapshot equality is asserted in the test without
persisting private claim tokens or full checkpoint payloads to these reports.

These changes affect tests/instrumentation and validation evidence only. They do
not alter production logic, migrations, grants or approved requirements. G7 and
capacity/load/soak remain deferred to phase 9; S/D and other open gates are not
closed by these fixes. Network-partition teardown still cleans only the recorded
severed source session after owned containers stop, as described in the original
report; this is not a claim of immediate production TCP-session cleanup.
