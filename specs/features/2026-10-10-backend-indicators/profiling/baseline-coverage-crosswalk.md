# F-11 baseline crosswalk — 2026-10-12

This is package D's explicit coverage inventory. R2 does not waive RQ, V or PV
functional requirements. A test module name proves only the cases it contains.
Paths below are relative to `backend/tests/`. Prior results remain historical;
current execution results are recorded in `ad-validation-report.md`.

## Requirements

| Requirement | Evidence | Coverage |
|---|---|---|
| RQ-1 | `gates/test_gates.py`, architecture contracts, core purity checks | Core stays independent of I/O/time; NC-38 corrections stay in HTTP service and infra cleanup. |
| RQ-2 | core/catalog matrices, numeric-window all-timeframe tests, API validation | Fixed catalog and supported formula/timeframe restrictions. |
| RQ-3 | `infra/market_data/test_indicator_reader.py`, prepared API lifecycle | Reads F-09 committed candles; normal tests use FakeVenue, never live orders. |
| RQ-4 | codec/cursor fixtures, canonical digest and DB parity | Source, pair, timeframe, bounds, seed and formula identity are preserved. |
| RQ-5 | `test_checkpoint_parity.py`, full-scan reader parity, overlapping pages | Shared seed/history, including warm-up and gaps. |
| RQ-6 | `core/test_indicator_arithmetic.py`, purity gates | Existing Money/Quantity/Scalar arithmetic; no new financial rules. |
| RQ-7 | arithmetic golden examples and independent integer oracle | Formula, rounding, zero division and first usable points. |
| RQ-8 | core gap/warm-up tests, checkpoint parity | Missing data remains a status, not invented candles or zero values. |
| RQ-9 | core refresh/finality tests; real F-09 refresh/rebuild lifecycle | Pre-end fetch blocks dependent values; successful refresh keeps UNCONFIRMED. |
| RQ-10 | API schema/response tests, unchanged OpenAPI/generated types | Exact numeric text and units; no frontend formula added. |
| RQ-11 | route inventory/auth/secret canary; API outage/session test | Auth retained, read does not renew session, recovery has no secret output. |
| RQ-12 | actual-role source/claims/rollout tests and catalog audit | No grants/schema change in NC-38; API transaction remains read-only. |
| RQ-13 | independent oracle/checkpoint/full-scan tests | Numerical and pagination evidence, not self-comparison alone. |
| RQ-14 | prepared continuation faults, snapshot races, source identity moves | Changed or unprovable source returns 409 without rows. |
| RQ-15 | bounded-prefix/weak-reference tests, N1–N3, exact fixture | Structural bounds evidenced; full resource certification remains phase 9. |

## Baseline validation

| Criterion | Evidence | Status / limits |
|---|---|---|
| V-1 | catalog, core/API input matrices | Functional evidence present. |
| V-2 | independent arithmetic golden/oracle tests | Functional evidence present. |
| V-3 | hostile decimal-context and batch tests | Functional evidence present. |
| V-4 | checkpoint/full-scan overlap parity | Functional evidence present. |
| V-5 | strict codec/cursor identity and digest tests | Functional evidence present. |
| V-6 | core finality/end/fetch boundaries; N1–N3 | Functional evidence present. |
| V-7 | refresh-blocked checkpoint states; F-09 HTTP refresh/rebuild | Backend state and committed refresh path evidenced. |
| V-8 | UNCONFIRMED taint tests and refreshed HTTP output | Functional evidence present. |
| V-9 | gaps/seed/retention tests and D3 aged seed | Functional evidence present. |
| V-10 | source/snapshot/publication races; prepared continuation tests | Functional evidence present. |
| V-11 | cursor signature/session/identity/expiry tests | New expiry cases isolate token versus generation at entry and response completion. |
| V-12 | input/output boundary matrices, N1–N3, bounded suffix reads | Structural correctness evidenced; no capacity claim. |
| V-13 | batched DB reader parity and snapshot races | Functional evidence present. |
| V-14 | actual read-only snapshot, grants/RLS, route/auth/canary tests | Session non-renewal additionally checked through outage and recovery. |
| V-15 | admission tests, serialization boundaries, NC-38 disconnect/query cleanup | Functional evidence expanded; cold/warm/RSS/lag acceptance remains deferred. |
| V-16 | current static/frontend/OpenAPI checks; full regression | See current results and external CI limit in report. |
| V-17 | empty-derived scheduler → HTTP → F-09 refresh → rebuild lifecycle | Real endpoint/worker/scheduler flow plus 23 consumer cases including HTTP elapsed time and exact/over-60s rejection (`ad-review-fixes-tests.xml`); active-lease duplicate POST and expired-target HTTP cases. Ready for re-review; no production frontend claim. |
| V-18 | crypto cursor/key tests, mixed-replica D2, exact expiry boundaries | Backend token evidence present; consumer restart policy additionally tested by the V-17 reference harness. |

## Performance amendment

| Criterion | Evidence | Status / limits |
|---|---|---|
| PV-1 | batch oracle and DB fetch-size/digest parity | Functional evidence present. |
| PV-2 | arithmetic boundaries, codec/state invariants, numeric-window failures | Functional evidence present. |
| PV-3 | canonical digest fixtures, source mutation/metadata tests | Identity-move commit/rollback adds explicit old/new-scope proof. |
| PV-4 | bounded batches/slices, staging weak references, suffix <=1,999 | Structural evidence; sustained lag/resource acceptance deferred. |
| PV-5 | separate-process capacity instrumentation | Method exists; current fixture check is not an RSS benchmark. |
| PV-6 | exact dense fixture and independent digest | Fixture prerequisite passes; approved R2-7 capacity replacement remains phase 9. |
| PV-7 | constant fixture plus changing/fractional independent oracle | Correctness fixtures present; not a new full-size performance result. |
| PV-8 | source/API snapshot races and NC-38 real-query cancellation/pool reuse | Functional evidence expanded; this is not continuous-load certification. |
| PV-9 | parity gap/refresh states, D3 retention, F-09 refresh/rebuild | Functional evidence includes V-17 consumer matrix and real refresh flow; not waived by R2-7. |
| PV-10 | current local static/frontend/backend results | Remote CI/release approval remains separate; no push was authorized. |

The V-17/PV-9 consumer matrix remains a non-deferred requirement; its new evidence
is in `ad-consumer-tests.xml`. Phase 9 covers only the explicitly approved
load/soak/capacity items. This inventory does not
authorize Development Complete, Completed, merge, or production PREPARED mode.
