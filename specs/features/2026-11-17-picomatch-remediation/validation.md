# Picomatch release checks
สถานะ: Approved — combined validation
- Feature: verified installed bytes, normal/frozen/relocated installs, 12 actual build callers,
  709 frontend tests, build and asset smoke passed locally. LP04 passed its 24-case matrix.
- Feature: 66 security tests passed with 4 opt-in tests skipped. Real pinned OSV covered
  464 identities, found the expected High and retained four Medium. After the exact owner
  decision the High was excepted and zero findings blocked. See [receipt](evidence/remaining-integrated/approved-sbom-result.json).
- Feature: fresh frozen install with Docker dependency-layer inputs produced the approved
  parser. Docker daemon unavailable for a full local image build.
- Feature and Release: required PR checks and postmerge checks pending at publication.
- F-17 remains Pending Full Validation. Earlier prototype failures and partial trials remain
  recorded in the local investigation worktree. Publication includes scoped summaries.


## Publication results reconciled — 2026-11-18

PR #77 merged at `06107d0`. Its postmerge Security passed, while CI failed at F-12
chart fixture seeding. Preserve that historical Failed result; diagnostics PR #78 then
merged at `c243d13`, where [CI](https://github.com/yukasung/tiewtrade/actions/runs/44336322663)
and [Security](https://github.com/yukasung/tiewtrade/actions/runs/44336322562) Passed.
The chart failure did not recur in that run; its historical cause remains unproven.
The exact approved artifact-bound exception and its retirement/reassessment conditions
remain unchanged. This closes publication monitoring through the follow-up candidate,
not F-17 Full Validation or general regex safety for other callers/options.


## Exact withdrawn-advisory verification — owner approved 2026-11-18

PR #79 first candidate `f78b456` failed Security dependencies with
`TRUSTED_SOURCE_ADVISORY_COVERAGE_UNPROVEN`. GitHub and OSV had withdrawn the exact
advisory at 2026-11-18T15:38:56Z; the old guard still required an active High forever.
Owner approved the [concrete amendment](withdrawn-advisory-coverage-amendment.md) before code.

Feature checks: 26 targeted tests Passed; all 79 security tests completed successfully
(75 Passed, 4 existing opt-in Skipped). New nine test methods exercise exact identity,
fresh requests, missing/malformed/future/unwithdrawn evidence, package/range mismatch,
query inconsistency, HTTP/timeout/oversize/duplicate JSON and unchanged blocking of other
High/Critical/Unknown findings. Original active-advisory and offline fail-closed paths
remain tested. Five-file Ruff/format and strict mypy with explicit package bases Passed.
[Actual pinned OSV scan](evidence/remaining-integrated/withdrawn-advisory-scan.json):
464 identities, 4 Medium, 0 blocked/unknown, no exception used; online withdrawal
evidence verified during the scan. Both lock hashes and exact LP04 bytes unchanged.

Development history retained: one new test initially expected Unknown in the blocked
counter instead of needs_triage; assertion corrected to require policy refusal through
the existing counters. A test-edit SyntaxError and mypy module-mapping/type annotation
issues were corrected before the final checks. No policy threshold/assertion was weakened.
Review found no remaining correctness/security findings; no source refactor beyond the
scoped helper reuse is needed. Final required CI and postmerge remain mandatory.
