# FENCE-03 — owner-authorized refactor and affected validation

สถานะ: **Scoped refactor/validation Passed**,2026-11-16.
Owner instructed refactor the code after scopedreviewAPPROVED;refactor scope recorded
before edits in [amendment](../../publisher-fence-failure-evidence-plan.md).
[Sanitized summary](fence03-refactor-summary.json).

Replaced the publication-selection conditional expression with an explicit guarded
assignment. The callback is still called once at capturestart;identity check and tick
freeze occur at the same point. Existing error/cancel/association/retention/phase order,
readonlySQL,timeout/row limits and close/join/dispose behavior unchanged.

Moved the pre-existing query-result double from the older sampler transition test to
that testmodule's shared QueryResult and reused it in the new failure tests,removing
two identical copies. No new fixtureframework/helpermodule,testcase/assertion change,
financial/domain/API/session/risk/Live behavior or infrastructure change.

Affected validation ran automatically:all80targetedcasesPassed in21.929s including
realPGreadonly/blocker/timeout/connectionreturn,combinedclockrollback/commit/guard,
failure identity/transition/privacy/overflow/cancel/retention andownedcleanup regressions.
Scopedthree-file Ruff/format/mypy andwhitespacePassed. Independentmaintenance connection
confirmsownedtestDBabsent,0connections/0advisorylocks. Rawprivate artifacts retained at
validation-artifacts/f17-fence03-refactor-tests-20261116/;do not publish wholeconfig.

No workload,shortcampaign,4h,Git,CI ormerge. Historicalstall cause remainsunproven;
currentpolicy stillstops the sampler on error andmayallowpublisher/workload to continue
untilfinalizationmarksIncomplete. Refactor does not add orpromiseearlyworkloadabort.
No priorIncomplete/poolFailed was regraded;REBUILD20-04Passed is its owncandidate/offline
proof,not a newinstrumentedW3 result. F17notCompleted/Release/dependencies remain.

The authorizedrefactor andimpactedvalidation checkpoint is complete. Next proposed
scope:prepare the W3 execution/readiness plan,explicitly deciding the response to lost
observer evidence/timecost before anylongrun. Suchplan/anyruntimechange andone4hcampaign
need the applicable approvals/review gates;none is started orauthorized by this receipt.
