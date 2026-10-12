# F-11 pre-merge coverage audit - 2026-10-12

Historical audit snapshot. A–D were subsequently implemented after NC-38 approval;
see [current evidence](ad-validation-report.md) and [baseline crosswalk](baseline-coverage-crosswalk.md).

This audit reconciles the approved R2 criteria, existing tests and recorded results.
It does not amend acceptance thresholds or treat old test counts as new runs.
No production change, new test execution, commit, merge or release is part of it.
N4 re-review was APPROVED in the conversation after its seven-case correction.

## Scope and evidence

Reviewed `requirements.md`, baseline V-1..18 in `validation.md`, PV-1..10 in
`performance-plan.md`, R2-1..12/L/F/N/S/G/D/C in `performance-plan-v2.md`, and
the phase-9 registry in `specs/roadmap.md`. Test paths below start at `backend/tests/`.
Test presence alone is not used to close a criterion.

Recorded execution evidence checked includes source-lock 179+16 tests,
post-update D4/L/F/G/API 213 tests, Compose/D6 89 tests, F1-F6 241 tests,
N4 correction 7 tests, and the historical full-backend result (2,324 passed,
one skip covered separately on the host). Counts overlap and must not be summed.

## Items whose remaining partial status was stale or solely aggregate

| Criterion | Reconciled status | Evidence and limits |
|---|---|---|
| R2-5 | Functional passed; G7/load deferred | G1-G6 corrected container/shutdown/ACL evidence, claims/publication atomicity, S retry budget and N4 corrected deadline/window/crash cases. No claim that full 30-series resource acceptance passed. |
| R2-6 | Passed | Actual-role/source/DDL/PUBLIC tests, rollout replay/downgrade and missing-grant matrix plus new read-only `premerge-security-catalog.json`: 35 related functions, all 28 SECURITY DEFINER functions pin search_path to pg_catalog,public and deny PUBLIC EXECUTE; API/market-data/builder cannot CREATE in public. This verifies the installed isolated test schema, not production deployment. |
| R2-8 | Cold-miss correctness passed; capacity deferred | `api/test_prepared_indicators.py::test_missing_ready_never_builds_or_writes_demand` asserts 503, Retry-After, zero generations/demand; N4 asserts no GET DML/partial responses. R2-1's complete scheduler lifecycle remains separate and open. C2/C6 historical failures remain failures. |
| R2-11 | Structural correctness passed; sustained resource acceptance deferred | Codec oversized-payload rejection; `test_staging.py::test_dense_scan_releases_previous_rows_before_next_fetch` uses weak references and a 1,000-row peak; full M1 sparse scan checks 527 checkpoints; prepared API prefix test asserts total <=1,999 and per-fetch <=1,000; maintenance checks GC batch <=1,000 and publication safety. `storage-pressure-fix-tests.xml` is a 55.131s finite pressure test, not continuous-load certification. |
| R2-D2 | Functional passed; production inventory remains a release check | Actual two-image processes, common test keys, cross-replica routing/parity/restart/rejection in `d2-current-image-tests.xml`; later D3/D4/Compose lifecycles provide follow-up evidence. Production key distribution is not certified by fixture keys. |
| R2-D3 | Functional passed; capacity deferred | `d3-aged-seed-tests.xml` / `d3-aged-seed-evidence.json`: actual same-series cursor seed crosses 365-day cutoff while still within grace and original cursor/generation lifetimes; both compatible cleanup processes preserve it and continuation parity. D1/D5/D7 supply old-writer/drain/restart controls. |
| R2-G7 | Logical prerequisites passed; full-load acceptance deferred | G1-G6, S1-S4, F4/F5 and N4 cover logical ownership/retry/fairness/deadline accounting. Two-replica 30-series capacity is not closed. |
| R2-D7 | Compose functional passed; aggregate/release dependencies remain | `d47-combined-review.md`, `d57-compose-tests.xml` and evidence: actual Compose stop/drain/start, compatible rolling replacement, inventory negatives. F1-F6/N4 are no longer missing prerequisites; open R2/baseline functional checks and capacity/release remain. |
| R2-N4 | Functional review approved; load deferred | `n4-review-fixed-tests.xml` seven passing cases and JSON traces isolate 119/120/121s deadline from GC and prove live M1 window coalescing. |

## Concrete remaining non-deferred work

These are missing or incompletely mapped acceptance evidence, not newly discovered
production defects. Keep the listed rows Partial until the evidence is supplied.
No long load/soak run is needed for the functional cases below.

| Work package | Criteria | What remains and what can be reused |
|---|---|---|
| A: API lifecycle and failure boundaries | R2-1, R2-4, R2-10 | R2-1: one trace from genuinely empty derived state through real scheduler dispatch/publication to GET 200; existing READY fixtures call `run_attempt` directly and cold-miss tests stop at 503. R2-4: exact first-request age 600s -1us/equal/+1us and independently observable token/generation expiry; the current 601s test and response-expiry test accepting 401 or 409 do not prove these distinctions. Retention/oldest-seed and all-TF alignment already have evidence. R2-10: tie DB/Redis failure and HTTP cancel/disconnect, cleanup/slot release, cache/session behavior to the indicator request path; worker outage/G4 and serialization tests already cover their own layers. Reuse prepared API fixtures, `http_clock`, D3 seed evidence, existing admission/session helpers and cancellation tests. |
| B: Source identity proof | R2-3 | R2-3: source ABA/rollback, delayed writer, outside-U, journal floor, root/leaf/upsert/cleanup and read/publication races are evidenced by L and publication/staging/API suites. Still need explicit old/new source-identity move proof assertions (pair/timeframe/open_at as applicable); current source tests mutate values/metadata, not identity. Reuse source/journal and publication tests. R2-6 is now closed separately using the installed catalog audit above. |
| C: Exact prepared-fixture prerequisite | R2-7 | Existing `capacity-c1-v2/r2-7-coverage.json` records **525,599**, not 525,600 slots. The full-M1 staging test has 527 checkpoints but empty source; it cannot substitute for the dense prepared fixture. Prepare/check exact aligned bounds, row/slot inventory and digest separately from the deferred cold1/warm5 resource measurement. Do not promote the old result to Passed. |
| D: Baseline traceability and final gates | RQ/V/PV; R2-12 | Produce the explicit RQ-1..15 / V-1..18 / PV-1..10 crosswalk and retain their unchanged functional obligations. In particular V-17/PV-9 refresh-to-indicator flow cannot be signed off solely from separate F-09 ingestion and indicator tests. R2-7 supersedes only the documented V-15/PV-6 full-build measurement; it does not waive API admission/session/cleanup correctness. Historical full/backend/frontend results remain evidence; final current-tree checks and remote CI are separate pre-merge work, not completed by this audit. |

The four packages group related verification, not four individual tests or a
guarantee that there will be no findings. Requirements/architecture changes still
require the normal owner decision; none were proposed by this evidence audit.

## Deferred and release work remains visible

Phase 9 retains C2/C3/C5, full C4/C6, G7, sustained GC/resource pressure and the
capacity-dependent parts of F4/F5/N4/D7. The exact R2-7 fixture is still missing;
the registry permits short fixture/correctness work during development and does
not convert the old 525,599-slot run into acceptance.

Production image/key/inventory checks remain release obligations, separate from
test-environment functional evidence. F-11 stays In Progress; this audit does not
authorize Development Complete, merge, PREPARED activation or real-money use.

Next recommended implementation package: **A**, followed by **B**, **C**, and the
baseline/final crosswalk in **D**. Preserve historical failures and avoid rerunning
load/soak merely to refresh this document.

## Follow-up during A-D implementation

Package A exposed an actual code/spec mismatch, not just missing evidence:
`api-disconnect-review.md` / NC-38. Its new regression fails because an ASGI
disconnect does not stop the reader. R2-10 is now Failed functional; production
correction awaited the owner decision required by AGENTS.md at that point.
The owner subsequently approved it; current corrected results are linked above.
