# D4 active build and rollout barrier evidence

Date: 2026-10-11. Scope: approved R2-D4 functional build/HTTP boundary coverage.
No production code, grants, thresholds or activation evidence rules changed.

`profile_active_rollout.py` reuses real 30-series READY lifecycle preparation,
the existing mixed-image API fixtures and the existing instrumented container
worker. In one continuous scenario it exercises PREPARING→PREPARED and
PREPARED→PAUSED, each while an actual synchronous indicator CPU batch is held.

For each transition the harness checks:

- The worker has emitted `cpu_start` and its slot is RUNNING.
- The real migrator SQL transition returns NOT_DRAINED; the entire control row
  and slot remain unchanged. This is a worker barrier, not a fake claimed row.
- After release, the actual attempt reaches READY. Source/CPU/writer close order
  is asserted; `Probes.finish` confirms the container exited successfully.
- API processes are stopped, host pools disposed, and PostgreSQL reports zero
  API/market-data/builder sessions with the slot IDLE before the transition.
- Only then does the SQL transition apply and change the rollout epoch.

During the PREPARED build a real API request obtains a v2 cursor. Its epoch
matches the pre-pause control state and its issue time does not exceed the DB's
recorded pause cutoff. After restarting both API processes in PAUSED, first-page
requests return 503 and that cursor returns 409 on both images.

The API fixture's optional D4 SQL observer records only statement category and
boolean payload/write flags, never parameters, SQL text, credentials or cursors.
The PREPARED request is a positive control that must show payload reads. PAUSED
requests must show neither payload reads (including prepared views and candles)
nor non-session DML, and full derived-row snapshots must remain unchanged.
Authentication session renewal is permitted and is not counted as indicator DML.
Observation is enabled only by a test-container file; the D3 clock stays disabled.

## Limits and companion evidence

- Positive PREPARED activation uses the actual restricted SQL helper on the
  isolated fixture, as in the existing lifecycle tests. It does **not** claim to
  pass the production orchestration CLI's capacity/evidence bundle gate and
  does not fabricate such a bundle.
- Worker containers use the established probe image plus read-only current
  workspace mount. APIs use immutable image code. This is functional evidence,
  not the D7 Compose release-image rehearsal.
- Existing `profile_rollout_barriers.py` supplies actual source/cleanup
  transaction barriers and downgrade/cutoff cases; the prior mixed lifecycle
  supplies the observed in-flight HTTP relation-lock barrier. These are separate
  scenarios, not a claim that all four activities overlap in one transaction.
- Thirty sparse lifecycle series do not constitute the phase-9 capacity workload.
  No wall-clock load/soak or long pause was run for this change.

Final run: **52 passed, 0 failures/errors/skips, 91.981 seconds** (new lifecycle
plus existing rollout/barrier regression). Ruff/check-format and mypy (341 files)
passed. Teardown verified slot IDLE and zero API/auth/builder DB sessions.

Artifacts: `d4-active-build-tests.xml`, `d4-active-build-evidence.json`.
The evidence contains worker traces, host join/drain/transition observations,
DB epochs/cutoff and sanitized SQL/HTTP observations. Host and container
monotonic timestamps are not compared to each other.

Ready for review after passing the recorded run. F-11 remains In Progress;
D5–D7 and phase-9 acceptance are not closed by this harness.
