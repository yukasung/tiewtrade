# Endurance20 publication checkpoint — 2026-11-17

สถานะ: Approved continuation — owner instructed เริ่มทำ after W4 READY02 Passed.

Publish the accumulated, previously reviewed/refactored endurance harness amendments,
production replay reader corrections and sanitized evidence in this existing feature
branch. Preserve original requirements and Pending Full Validation. User delegates
publication/merge under AGENTS.md once applicable Feature gates and final required CI
pass. Older execution-only no-Git boundaries ended at their reported checkpoints.

Inventory tracked diff plus untracked source/test/fixture/spec evidence; exclude all
validation-artifacts, private launchers, dumps and credentials. Preserve historical
Failed/Incomplete records. Reconcile final proof: AWAKE01 W3, representative20 rebuild,
READY02 W4; W4-only callback change does not invalidate W3. Run accumulated targeted
backend tests on a fresh owned DB, Ruff/format/mypy on affected Python, check evidence
for secrets/private raw data, then final diff check and candidate publication. No full
four-hour rerun. Required CI provides final combined regression proof. Monitor candidate
through merge and postmerge, analyze failures within delegated scope; retain explicit
safety/three-failure stop rules and owner-review requirement for security exceptions.
No activation/Live, new release waiver or completed F17 claim. No new feature scope.

## Candidate1 CI correction — 2026-11-17

4bcbad3 backend stopped at full mypy before tests: existing profile_diagnostics dynamic
kwargs became ambiguous after _run gained callbacks; READY02 test imported internal
aliases not explicitly exported. Delegated fix: explicit conditional _run call preserving
absence of parent_runtime when disabled, direct os/profile_workload imports in test.
No runtime algorithm, assertion or acceptance change. Check affected diagnostic/readiness
tests and full configured mypy to cover import/re-export rules omitted by scoped silent
checks, then publish replacement. Security/frontend/contracts/container already Passed;
final candidate still must get fresh required CI. No workload rerun is indicated.

Correction validation: full configured mypy727files Passed;52diagnostic/readiness tests
Passed on owned migrated PostgreSQL with cleanup, Ruff/format Passed. A first local
invocation referenced a nonexistent test filename; a subsequent invocation omitted DB
environment and produced configuration errors. Both invalid invocations retained as
local diagnostics, not acceptance failures; final run used the existing isolated runner.
No financial/runtime behavior changes or workload repeats. Candidate2 may publish.

## Candidate2 CI test-fixture correction — 2026-11-17

6b2b883 Security/E2E/frontend/contracts/container Passed. Backend full regression:
5641Passed/7Failed. Six legacy fake argparse namespaces omit observer_w3_prefix and
raise before the intended failure/cleanup assertion. One preflight-failure unit case
attempts local-named Docker schema capture before reaching its mocked preflight.
Delegated correction: default flagFalse in that shared fake namespace; stub only schema
capture in that preflight-failure case while delegating other capture calls. Keep real-DB
fixture, seed-not-called/result/duplicate-output assertions and all safety checks. No
production or workload behavior change. Run both modules with actual isolated DB,
Ruff/format/mypy, publish candidate3 and monitor once; third same-gate failure must stop
for review per AGENTS.md. Historical candidate failures retained.

Candidate3 local validation: both affected modules Passed on a fresh owned PostgreSQL
DB, cleanup removed with0connections; Ruff/format/mypyPassed for2testfiles. No source
runtime changes; existing W3/W4 and candidate2 production proofs remain applicable.

## Candidate3 stop and proposed next scope — 2026-11-17

f6f1dcd backend failed full mypy before tests: test_tail_reads.py refers to unexported
profile_tail_reads.campaign (lines241/248), causing no-any-return at246 as well.
Scoped follow-imports=silent again omitted the imported-module export rule; it was
insufficient and should not have been used as replacement for configured full mypy.
Three candidate failures reached: STOP under AGENTS.md การทำงานให้เร็ว before another
candidate. PR76 remains unmerged; no acceptance/security criterion relaxation.

Recommended optionA: import remaining_paper_campaign directly in test_tail_reads and
patch that same module's capture; no assertion/runtime change. Run55affected tests on
isolated migrated DB plus Ruff/format and full configured727-file mypy before push.
Then one replacement required CI candidate, merge/postmerge only if all gates pass.
AlternativeB: retain current PR/blocker and defer publication. No production change,
workload rerun or four-hour rerun needed. Owner decision pending; no patch yet.

Owner approved optionA: direct import correction, targeted tests, full configured mypy,
then one new CI candidate through merge/postmerge when all gates pass. Record before
editing; no assertion, production or acceptance change.

OptionA checks Passed before push:55targeted tests on owned migrated DB with cleanup,
Ruff/format and full backend-configured mypy727files. Diff is direct import and same
module patch target only. Original assertions and production inventory unchanged.

## Merge and postmerge new security blocker

PR76 merged d3c9eae after all required checks Passed on2e51d01. Postmerge dependencies
reportsHigh1 in picomatch4.0.7; advisory updated between scans, npm latest4.0.7 with no
patched version listed. Lockfiles unchanged. See evidence/endurance20-20261115/
publication-postmerge-blocker.md. Do not reclassify oldPassed, override gate, rerun
scanner to seek different result or publish another candidate under current scope.
Monitor existing main CI; then report unresolved blocker and proposed next scope.
