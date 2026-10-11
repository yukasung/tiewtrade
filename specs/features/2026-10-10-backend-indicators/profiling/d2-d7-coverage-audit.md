# F-11 D2–D7 coverage audit — 2026-10-11

Source of truth: approved `performance-plan-v2.md` R2-D2–D7 and
`rollout-runbook.md`. This audit does not amend their acceptance criteria.
Long capacity/soak remains phase 9; functional release checks are not deferred.

## D2 current-image verification

Reused `backend/tests/services/indicator_builder/profile_mixed_replicas.py`.
Rebuilt the prepared test image from the current working tree using the repository
Dockerfile. Preserved the compatibility image. Both APIs execute image-contained
code without source mounts and use the isolated PostgreSQL/Redis services.

Docker `.Id` values selected by the harness:

- Compatibility: `sha256:b96ed3cf5c213a887bb5e631958498938f861384a620505425a7d747449d3302`.
- Current: `sha256:b7ae3fd6193e00fb323587c2dc220ba6eacd5bf2f9e5057119fcac6e14d672cf`.

The API environment is constructed explicitly in `Replicas.start`, with the same
public test cursor-key configuration (current key ID `1`) for both images.
No application secrets, cookies, MACs or cursor values are recorded here.
This establishes test deployment compatibility, not production key distribution.

The continuous lifecycle checks both routing directions, seeded random routing,
full-scan row/cursor parity, restart/replay, valid v1 rejection, tampering,
cross-session use, format spoofing, expiry, retired key IDs and old rollout epochs.
It also executes existing D3/D4/D5 checks; that does not complete their missing
clauses listed below. The fixture has 30 READY series but only one dense series;
it is not capacity evidence.

Result: **1 continuous lifecycle passed, 0 failures/errors/skips, 91.449 seconds**,
recorded in `d2-current-image-tests.xml`. This refreshes D2 functional evidence
against the current test image; it is not six separate passed gates. Teardown
confirmed slot IDLE and zero API/auth/builder sessions on the isolated test DB.

## Remaining work, tied to concrete clauses

| Gate | Existing evidence | Remaining short verification |
|---|---|---|
| D2 | Real two-image API lifecycle and shared test key configuration; current-image rerun recorded separately | Actual release image/keyring inventory remains an operator deployment check. Do not certify production activation from public-test-key results. |
| D3 | Approved D1 covers pre-strict S0/S1, legacy writer rejection, drain and compatible restart; mixed-image cleanup preserves a grace row | Add cursor issuance **before** cleanup and continuation **after** cleanup for the same series with a real seed dependency. Current cleanup helper inserts DOGE/1m probes, cleans them, then starts BTC/4h pagination; this does not prove preservation of a cursor's seed during cleanup. Assert cutoff/seed preservation after each replica's cleanup. |
| D4 | HTTP request/source-snapshot/cleanup barriers, PAUSED status and old-epoch rejection | Add real active build overlap with activate/rollback, observed stop/join before flip, and tie no-post-cutoff issuance/no-GET-DML assertions to the transition trace. Existing G/S worker evidence is supporting coverage, not this combined rehearsal. |
| D5 | Fresh/older cursor rejection on both replicas, session expiry, DB cutoff/replay, actual migration downgrade before/at/after support boundary | Complete application/schema/key/grace retirement sequence with reader drain and legacy routing/restart gate. Existing helper tests retirement eligibility; it does not perform the whole release retirement. Boundary correctness can use a controlled clock; it does not require a six-hour wall-clock wait. |
| D6 | Runtime transition denial, graph/replay/CAS, cancellation, atomic proof installation, real lost-response recovery | Add explicit partial-install faults: missing trigger/grant/control and unsupported control codec, with unchanged mode/epoch and operator inspect/resume assertions. Invalid generation codec coverage is not a substitute for unsupported control protocol/codec. |
| D7 | Actual Docker stop/start/restart and missing/offline inventory rejection | Run isolated Compose stop/drain/start rehearsal using immutable inventory and non-secret key configuration IDs. Existing `docker run` containers carry Compose labels but are not a Compose release rehearsal. Recheck relevant functional regressions after that sequence; full capacity remains phase 9. |

Follow-up: D3 same-series seed/cleanup/pagination implemented and passed one
continuous lifecycle in 125.024 seconds; review then identified the seed must
actually cross the ordinary cutoff. That correction passed in 102.331 seconds
with a controlled cleanup/API clock; see `d3-same-series-report.md`.
The D3 gap above describes the pre-fix audit.

D4 follow-up (2026-10-12): actual CPU builds now block both activation and pause;
worker exit/runtime drain precede the successful SQL transition. HTTP cutoff,
PAUSED payload-read/write observations and unchanged derived rows are recorded.
New lifecycle plus rollout/barrier regression: **52 passed in 91.981 seconds**.
See `d4-active-build-report.md` for evidence and scope limits. The D4 row above
is the original gap; this functional implementation is ready for review.
Next: review D4, then complete D5 retirement sequence. Production orchestration
capacity evidence and the D7 release rehearsal remain separate gates.
Reuse the current lifecycle fixtures, independent full-scan reference and existing
cleanup binaries; do not introduce another trading or retention rule.

F-11 remains In Progress. No production code, application deployment, approved
requirement, or acceptance threshold was changed by this audit.


Follow-up 2026-10-12: owner authorized completion of D5–D7 before combined review.
NC-36 missing-grant activation was reproduced and corrected with owner approval.
The Compose/retirement and grant-fault work above is now implemented; 89 combined
tests passed in 117.997s. See `d47-combined-review.md` for current evidence,
post-update regression and remaining aggregate release/capacity dependencies.
The original gap table is historical, not a current assertion that these harnesses
are missing.
