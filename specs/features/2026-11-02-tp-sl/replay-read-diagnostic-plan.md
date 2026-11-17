# NC-F17-REPLAY-01 — bounded production evidence-reader diagnosis

สถานะ: **Approved under owner engineering delegation2026-11-14; owner instructed เริ่มทำ2026-11-16**
Amendment to existing F17 validation/branch; no new product behavior or acceptance.

## Problem, evidence, alternatives and decision before source

FENCE-02 completed14400s/28200commands, but replay14 hit its unchanged60s budget
inside read_execution_inputs after29queries/94777rows.13earlier replays each read
~95–96krecords,about50–60s. Fixture was normally cleaned; physical historicalplan,
waits and payload distribution cannot be reconstructed. Sampler also recorded one
TimeoutError without a failure-stage/timestamp, so no blocker can be inferred.

A second4h run would repeat expensive setup without isolating replay cost. A timeout
increase weakens an approved criterion and is not authorized. Choose one bounded
synthetic reader diagnostic: isolate original SQL/result/decoder work on valid~96k
records, under same owner ENGINE/RLS and original4096page limit. No SQL rewrite,
index/schema change, altered lease, retries, trading commands or financial rules.
Do not claim synthetic reader timing explains the exact historical timeout.

## Requirements / implementation and reuse

Reuse profile_tail_reads.seed_history/verify_owner, seed_owners, production
read_execution_inputs/_decode and user_session, existing isolated migrated database
factory, source pinning,financial_state and environment_preflight. Add one harness
module with task-isolated measurement: original reader and decoder invoked once,
perpage SQL+driver result time and decoder time, count/cursor/role/session spans.
No query text/parameters/URL/secrets in output. Task context and temporary wrappers
must restore on success/error/cancellation; retain partial pages on error.

Small real-PG tests cover exact enumeration, owner isolation, unchangedfinancialstate,
original-once decoder error and restoration, cancellation and no ambient tracing.
No mock replaces fixture/RLS proof. Existing sampler safety evidence retained;
read its failure policy/source, but do not change sampler/publisher in this scope.

After targeted tests/static checks: one120s/7sample preflight before diagnostic
fixture, one fresh owned migratedDB,2synthetic owners (secondempty RLSnegative),
seed96000valid evidence records for owner1 using existing bounded500batch helper.
Record explicit fixture ANALYZE only for generated evidence keys/input tables.
One full4096-page enumeration with60s limit (same upperbound as owner replay),
then if returned2SELECT-only EXPLAIN ANALYZE BUFFERS JSON for first/late page under
same owner role/RLS,each10s statement timeout. Never repeat failed enumeration.
Max15min inclpreflight/seed/cleanup; expected5–10min runtime after development/tests.
StopIncomplete on safety/preflight/seed/read/evidence failure, preserve partialdata.
This isolates reader path,not fullfinancialposition/history replay or W3acceptance.

Pin candidate/config/migrations/copiedrunner beforepreflight; sourceunchanged proof.
Only ownedDB normaldrop afterdispose/join/0connections+advisorylocks; noRedisneeded,
no owner/Live data or service stop/reset/prune. Retain resource if cleanup notsafe.
Do not change financial checks or historicalgrades to obtain a pass.

## Validation and checkpoint

Feature: new wrapper count/task isolation/error/cancel/restoration and actualPG
RLS/financial-no-write/knowncursor proof; scopedRuff/format/mypy/whitespace.
Batch diagnostic: one described run,allpages retained,posthoc timing reported without
latency exclusions. Record actualcounts/planlimits/candidate/cleanup and caveats.
Release: previousW3Incomplete and F17pendingfinancial/rebuild/100account/otherdeps
unchanged. No4h rerun, productionfix,timeoutrelaxation,Git/CI in this scope.
Stop/report after diagnostic; next optimization requires evidence-backed amendment
and normal owner review/refactor gates. Do not claim historicalrootcause fixed.

## Execution checkpoint2026-11-16

[Diagnostic complete](evidence/endurance20-20261115/replay01-checkpoint.md),one run,
202.625s total/36.707s reader,96000decoded/25pages;SQLdriver8.659s,decode27.638s.
Firstpage externalmerge sort beforeLimit observed; not historicalrootcause proof.
4targeted tests/scopedstatic Passed. Sourceunchanged,independentDBabsent/0conn/locks.
No productionfix/samplerchange/new4h/Git/CI. Stop/report; historicalF17Incompletekept.

## Review corrections M1/M2 — authorized2026-11-16 before source

Owner requested แก้ไข after scoped review. Two Medium findings were reproduced
without a workload: retainedrunner final source-hash exception skipped cleanup;
partialreceipt OSError replaced the originalreadTimeoutError. These are lifecycle/
evidence defects,not financialreader defects or changes to acceptance.

Use existing exception-preservation patterns (profile_commit_observation.py,
profile_publisher_lease_load.py add_note) in two replay-specific helpers in
profile_replay_reads.py. Partial-save failure must retain original exception identity,
record secondary stage/type and make resultIncomplete. Finalization must attempt
sourcecheck,ownership-checked cleanup and finalsave independently, preserving the
firsterror/cancellation and marking source/cleanup/save failuresIncomplete. Never
forcecleanup ordrop without ownership; retain database identity on cleanup failure.

Preserve original executed runner/hash/result immutable. Prepare a separate corrected
private runner copy that calls the tested helpers; retain exactold/new diff/hash as
review evidence,not a replacement execution receipt. No campaign or4h rerun. Test
hashfail/IO/cancel/cleanupfail/source drift/finalsavefail/success and firstexception
identity,plus binding correctedrunner's partial andterminal finally to helpers.
Retain4unchanged observer/RLS tests and originaldiagnostic grade; scopedstatic only.
After fixes report and ask for owner refactor instruction per AGENTS; no Git/CI.

M1/M2 executioncheckpoint: [fixes and14targeted checks](evidence/endurance20-20261115/replay01-review-fixes.md)
Passed,scopedstaticPassed. Correctedprivate runner finally bodies exercised underfault,
not a campaign. Originalrunner/grade unchanged. Await ownerrefactor instruction.

## Owner-authorized M1/M2 refactor2026-11-16 — before source

Keep scope at two reviewed helpers/new tests: cache secondary exception type once,
normalize the strict source-check boolean once, name cleanup result explicitly,
consolidate repeated test imports. Preserve public signatures, callback order,
exceptionidentity/notes/reportshape,cleanupownership and error/cancel behavior.
Run10affected lifecycle tests plus scoped2-file static and correctedrunner binding;
retain4unchanged real-PG observer/RLS proofs. No new campaign/4h/Git/CI authorized
or required for this behavior-preserving cleanup; historicalgrades unchanged.

Refactor checkpoint: [10affected tests/scopedstatic/binding Passed](evidence/endurance20-20261115/replay01-review-refactor.md),
4unchanged realPGproofs retained. Same behavior,no campaign/Git/CI. This scopecomplete;
next optimization requires ownerstart; F17historicalgrades/pendingacceptance retained.

## REPLAY-03 — CUT-01 size/criterion review, before execution (2026-11-17)

สถานะ: Approved within delegated engineering diagnosis; owner instructed เริ่มทำ
following the proposal to investigate replay before considering a criterion change.

CUT01 completed4h/28200commands but first replay exceeded60s after111161 returned
rows/33queries. Publichead144364. Prior offline rebuild proof used96000records/owner,
so its timing does not cover this volume. No exact historical query plan/payload/waits
remain after normal cleanup. Do not infer count mismatch proves criterion invalid.

Reuse corrected REPLAY01 runner and current ReplayReadObserver/production reader.
One synthetic144364-record reader enumeration,2owners (secondempty for RLSnegative),
page4096 and unchanged60s including session; bounded500record seed helper. Full
financial position replay is NOT reproduced. Same original SQL/decoder/data guards.
If enumeration succeeds, first/late-page read-only EXPLAIN ANALYZE BUFFERS under
original10s statement bounds; no query optimization or rerun of a failed enumeration.
Compare prior96000 evidence cautiously: decoder/candidate/host differ; do not label
cross-run timing changes causal or use synthetic timing for W3 acceptance.

Pin currentcandidate/schema/config/runner and exact copied helperhash before one
120s preflight. Fresh ownedDB; noRedis/Live/owner commands. Reuse corrected partial
IO/finalization helpers and M1 cleanup/269test evidence where unchanged. Syntax/AST
bindings must prove only runidentity/head/latecursor and stronger helperbinding differ.
Budget900s inclcleanup,expected5–10min. Ifpreflightfails stop; no waiting/retry.
Onecampaign then report whether evidence supports query work or a proposed criterion
review. All correctness/financial/60s criteria and priorFailed/Incomplete remain.
No4h/sourceoptimization/commit/push/CI/merge in this scope.

### REPLAY-03 criterion review — 2026-11-17

[Evidence](evidence/endurance20-20261115/replay03-criterion-review.md): Incomplete at
initial preflight service check; Docker socket unavailable. No fixture/reader/EXPLAIN
ran. Original60s and all safety criteria unchanged. Historical96000-record rebuild
proof does not cover144364publicinputs automatically; no criterion-change conclusion.
Stop before retry; next bounded diagnosis requires Docker availability.

### REPLAY-03 replacement after Docker startup — 2026-11-17

Owner reports Docker opened after explicit request to resume the short reader diagnosis.
Original attempt remains Incomplete/no fixture. Start only existing PostgreSQL and test
Redis dependencies (both exited), preserving data/volumes. One replacement with fresh
output identity and identical144364/4096/60s/900s scope; preflight once, no workload retry.
No production/query/criterion change. Stop/report after result or readiness failure.

### REPLAY-03 replacement result — 2026-11-17

[Evidence](evidence/endurance20-20261115/replay03-r2-result.md): diagnosticComplete,
144364records/37pages in55.346s;SQLdriver20.312s/decode34.372s. First-pageplan
joins144364 then external-sort208128KiB beforeLIMIT4096. RLS/no-write/source/cleanup
Passed;total245.796s. Keep60s;next propose exact-equivalent bounded-key query diagnosis
before criteria relaxation. Nooptimization/4h/Git;W3Incomplete/F17Pending unchanged.
