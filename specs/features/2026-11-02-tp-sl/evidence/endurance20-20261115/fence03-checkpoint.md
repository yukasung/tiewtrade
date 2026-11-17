# NC-F17-FENCE-03 — observer/failure-cleanup readiness checkpoint

สถานะ: **Scoped implementation and safety checks Passed; awaiting owner code review**.
2026-11-16. [Engineering scope recorded before source](../../publisher-fence-failure-evidence-plan.md) ·
[Sanitized summary](fence03-summary.json).

## Readiness finding and scoped change

Owner instructed ทำต่อ after REBUILD20-04 offlineproofPassed. Readiness inspection found
that historical FENCE-02 sampler TimeoutError1/0snapshots still had only an errorcount,
not failuretime/capturephase/completedviews/statementassociation. The four-attempt review
requires that bounded envelope before another observedW3 proposal. This directly
related harness change used delegated engineering authority; no new business/risk rule.

FenceObservation.sample now retains one firstfailed observation in addition to existing
64successful snapshots/counters. It freezes publisherPID/stage/statementstart and the
actual optional publicationtick only when the same statement belongs to the captured
trace. It records monotoniccapture/phase timings,hostUTCfailed_at,dbclock when read,
lastcompletedphase,activity/locks intervals/counts and completed allowlistedviews.
Null counts mean unread/unknown,not zero rows. Overflowrecords observedcount but does
notretain an oversized view;it remains an explicit failed observation. Conservative
association marks completed/overlapped/unconfirmed statements without naming a guessed
blocker. Views remain non-atomic;phase elapsed is client-observed,not pure server time.

Original readonlySQL/settings/queryorder,128activity/8192lock limits,1sobservation,
500msstatement/200mslock timeouts,≥1strigger,atmost4Hz,enginepoolinventory and monitor
stop-on-firsterror unchanged. Primary error/cancellation propagates;onlyerrorclass,
never exceptionmessage/SQLtext/parameters/cookies/tokens/userfinancialrows is saved.
Cancellation counting/shutdown policy is unchanged;partialcancel context is diagnostic,
not a successfulsample or a new acceptance waiver. Existing shieldedclose/join/dispose
behavior and finalizer's Incomplete behavior remain. No production/sourceguard/lease/
clock/retry/financial/session change and no newinfra. Bounded in-memorydiagnostic data
is not application session/persistent business storage.

## Targeted validation

Final80casesPassed in20.010s on freshowned PostgreSQL. Includes28new failure-envelope
cases plus existing fence/loadobserver regressions:checkout/settings/dbclock/activity/
locks/sessionexit failures,statementtransition/frozenidentity/firstfailure retention,
cancellation,unknownidentity,overflowlimits and privateerror-message exclusion.
RealPG samplerquery timeout retained activityphase,stopped afteronefailure,returned
connection andallowed subsequentREAD ONLY read;realshared-holder/exclusive-waiter and
actualpublisher/combinedCLOCK01rollback+guard/commit proofs passed too. Repeatedcancel/
join-before-dispose/finalIO-primarypreservation/poolinventory/defaultoptions retained
and checked by the affected suites. No mock substituted for DBtransaction/blocker proof.
Initial76casecheckpoint retained;expandedcancellation/missingidentity matrix produced
final80. Two-file Ruff/format/mypy and whitespace Passed. Independent maintenance check
confirmedtestDBabsent/0connections/0advisorylocks. No timedload/campaign orGit/CI/merge.
Private logs validation-artifacts/f17-fence03-tests[-r2]-20261116/ remain local.

## Remaining readiness limits / next gate

The new envelope improves attribution if sampling fails;it does not prevent another
samplingtimeout or prove the historical9.848s publisher stall fixed. No historical
blocker identity can be reconstructed retroactively. Existingpolicy stops the sampler
on error while publisher maycontinue;overallIncomplete is enforced by finalization.
This change does not introduce an earlyworkloadabort or claim one exists. Any future
long-run plan must state that behavior/timecost and whether an engineering change to
fail-fast diagnostic orchestration is required before execution;no silent policy change.

Next ownercode review of this source change,then authorizedfindings/refactor/affected
validation. Only then prepare an explicitly approvedW3 execution scope with candidate/
helperbinding,originalfaultprofile/14400smeasurement,completefinancial/positions/tail/
resources/pools/cleanup and instrumented result limits. No fourhourrun was started or
authorized here. OfflineREBUILD20-04Passed remains scopedvalid;FENCE-02/allolderW3Incomplete
remain unchanged. F17notCompleted and100accountRelease/bot/notification/Live pending.
