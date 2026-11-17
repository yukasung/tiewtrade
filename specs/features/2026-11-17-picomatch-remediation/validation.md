# Picomatch dependency remediation — Validation

สถานะ: Approved — owner approved plan/validation on 2026-11-17
วันที่: 2026-11-17
Requirements: [Approved](requirements.md); implementation: [plan.md](plan.md)

No implementation/probe/install/campaign has started. Drafting checks only.

| ID | Requirement | Required evidence / acceptance | Level | Status |
|---|---|---|---|---|
| PV-01 | PR-1 | Exact candidate/manifest/lock/config/advisory/registry identities; all installed occurrences and paths identified, including optional/dev/transitive; capture errors block assessment | Feature | Not Run |
| PV-02 | PR-1/5 | Caller-to-pattern-to-input mapping covers build/test/dev server/plugins and release output; server.host=true considered; uncertain/external input paths explicitly unresolved; dev=true alone never qualifies as safe | Feature | Not Run |
| PV-03 | PR-4 | Official-derived bounded child probes with original and authorized candidate when available, benign expected matches, exact versions/inputs; ≤5probes,2s per child/256MiB/sequential,≤60s stage, parent kill/join proof; only scratch child resources; non-repro/timeout not conflated with global safety | Feature | Not Run |
| PV-04 | PR-2 | Official published patched compatible version and integrity/advisory evidence before edits; semantic lock diff only required dependency edges; no unrelated upgrades or implicit source substitution | Feature | Pending Safe Fix |
| PV-05 | PR-2/5 | Node22 clean frozen npm ci succeeds, installed versions correct, lock hash unchanged after install; API/schema/backend/trading/session unchanged | Feature | Pending Safe Fix |
| PV-06 | PR-4/5 | Relevant tooling/regression tests, frontend lint/typecheck/build and disposable loopback build/dev smoke pass; actual bundle inclusion/exclusion evidenced; no owner/Live mutation | Feature | Pending Safe Fix |
| PV-07 | PR-3 | Original pinned OSV covers both lockfiles completely; no unresolved High/Critical/Unknown; targeted advisory/aliases resolved by valid remediation; errors/missing inventory block; no scanner suppression/version falsification | Feature | Not Run — known baseline Blocked |
| PV-08 | PR-3/6 | Readable sanitized evidence, bounded resource cleanup, honest historical failures and uncertainties; no exception without exact owner review; final diff scope reviewed, applicable source review/refactor gates honored | Feature | Not Run |
| PV-09 | PR-3/6 | All required CI checks pass on final committed candidate, current main/expected head verified before merge; local results never replace CI | Feature | Not Run |
| PV-10 | PR-3/6 | Postmerge CI and Security pass on merge SHA; if newly updated advisory blocks, record Failed and stop/report; never certify Completed from merge alone | Release | Not Run |
| PV-11 | PR-5/6 | F17 Paper proof reuse mapped to dependency-only scope; V18 original100-account and V19/V20 dependencies retain true status; no workload repetition unless concrete affected proof requires it | Batch | Pending Full Validation — record applicable proof mapping at final checkpoint |

## No-fix checkpoint

If no supported patched release is available, PV-04–10 remain pending/blocked rather
than being waived. Report investigation evidence and concrete options; the safe fix
selection may require an owner decision. Successful reachability/probe results alone
do not make PV-07 Passed. Do not open an artificial vulnerability exception.

## Draft validation

Check document consistency, relative links and whitespace only before approval. Tests,
source edits, dependency installs and timed probes await approved plan/validation.

## Investigation checkpoint — 2026-11-17

- PV-01 Passed for locked inventory/hash/integrity and current official metadata.
- PV-02 Partial: static caller/config provenance mapped; complete plugin/transitive and
  release bundle verification unresolved. No unreachability claim.
- PV-03 Passed for bounded baseline probe execution/cleanup only:2benign expected,
  3advisory-derived stalls timed out and were killed/joined;6.185s total. Candidate
  comparison Pending Safe Fix; this is not remediation acceptance.
- PV-04 Blocked: no official published patched version available (latest4.0.7).
- PV-05/06 Pending Safe Fix; no install/build/smoke or dependency edits performed.
- PV-07 Blocked: retained main scanner findingHigh; not rerun seeking another verdict.
- PV-08 Investigation evidence/cleanup Passed; final remediation review remains pending.
- PV-09/10 Not Run for this task; F17 parent PR/main CI evidence retained separately.
- PV-11 Pending Full Validation: dependency-only scope does not alter financial/workload
  source, so no4h repetition; F17V18/V19/V20 remain pending as declared.

Evidence: [reachability](evidence/reachability.md), [structured results](evidence/investigation-summary.json),
[cleanup](evidence/cleanup.json). Historical statuses preserved; no Completed claim.

## LP-01 bounded prototype outcome

LP-01 provenance/version/license/one-file scope verified. LP-02 remainsPartial: linear
scan implemented but lexical quote/bracket interaction unproven and semantic changes
intentional. LP-03 matrixFailed19/20 (case4original expected false vs actualtrue); no
correction or retry, original failure retained. All20processesjoined/no timeout, total
1.526s. LP-04 Pending Owner Review; LP-05 Blocked/no install or exception. PV-07 remains
Blocked. See [checkpoint](evidence/lp01/checkpoint.md); no final Security/F17 acceptance.

## LP-02 finding correction checkpoint — 2026-11-18

Duplicate lexer replaced with parser token metadata; original baseline oracle corrected;
runner nonzero failures/overall deadline/cancellation cleanup implemented. Final5runner
controls,Ruff/format/mypy2files andJSsyntaxPassed. LP02rawmatrixFailed0/20 at bootstrap
argv parsing before matcher load; effective matching proofIncomplete. Argv fixed and
harmless CLI regressionPassed; no hostile matrix rerun. All20childrenjoined/scratch
removed. [Checkpoint](evidence/lp02/checkpoint.md). LP01Failed19/20 retained. Await owner
refactor/one-replacement decision; no stageB/exception/Git/CI or F17Completed.

## LP02R1 replacement — 2026-11-18

Owner authorized refactor+one replacement thenstop. [Checkpoint](evidence/lp02r1/checkpoint.md):
20/20frozen matrixPassed1.598s incl quote/class/innerbracket/POSIX/nobracket cases;
5runner methods/Ruff/format/mypy2files/JSsyntaxPassed. Exact LP02patch unchanged;
20childrenjoined/independentPIDsabsent/scratchremoved. LP01/LP02 failures retained.
LP01provenance and LP03scoped replacement evidencePassed; LP02general security/semantic
proof remainsPartial, LP04Pending OwnerReview, LP05/ PV07Blocked. No application or
Security policy change, full acceptance or F17Completed implied. Await review code.

## LP03 corrections — 2026-11-18

[Checkpoint](evidence/lp03/checkpoint.md): actual top-level alternative flag replaces use
of original conditions counter; cancellation test uses atomic readiness and owned-group
cleanup even before PID.6runner controls/Ruff/format/mypy2files/JSsyntaxPassed. One9case
targeted matrixPassed, allchildrenjoined/independentPIDsabsent/scratchremoved. Original
failures and LP02R1Passed retained within scope. App/lock/config/registry unchanged.
Await owner refactor decision. No complete-library/security acceptance or F17Completed.

## LP03refactor checkpoint — 2026-11-18

[Refactor receipt](evidence/lp03refactor/checkpoint.md): duplicate cancellation fixture
cleanup branches consolidated with same ownership checks; descriptive private helper.
Parserpatch/runner/child/matrix/license byte-identical, prior9/9matching proof reused.
6affectedrunner methods/Ruff/format/mypyPassed. No hostile rerun or application change.
Owner code review andstageB/security gates remainpending; no F17Completed.
