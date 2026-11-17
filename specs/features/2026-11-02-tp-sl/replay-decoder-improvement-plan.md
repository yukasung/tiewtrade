# NC-F17-REPLAY-02 — eliminate duplicate decoding of the same stored market

สถานะ: **Approved under engineering delegation2026-11-14; owner instructed ทำต่อ2026-11-16**
Existing F17 validation amendment/branch; no product or acceptance change.

## Evidence, alternatives and pre-source decision

REPLAY-01 valid96000-record fixture spent27.638s in decoder vs8.659s SQL+driver;
production _decode_checked decodes payload.market twice when source_market is absent.
_prepare_execution_input intentionally omits source_market whenever decision/source
market are identical. The decoder creates a second equivalent immutable MarketInput
and StoredExecutionInput,although the first object was already validated.

Choose smallest safe production change: reuse decoded market only when the separate
source_market field is absent; explicit source_market,including malformed/null/equal
values,still goes through its original decoder. Reuse the already constructed source
record when source_market is the market object. Keep BOTH outer/source digest checks,
rebase equivalence,provenance,metadata and SimulationProfile validation unchanged.
No rawpayload equality shortcut,cache,new rounding,Money/Quantity replacement,retry,
lease/timeout/session/schema/API change. Immutable per-row reuse is not business or
session caching; stateless/multi-instance persistence architecture unchanged.

Query plan also spilled sort beforeLimit, but movingLimit beforejoins changes the
proof surface for RLS/equal-input generation/REBASE boundaries. Leave query unchanged
in this amendment; no speculative query rewrite or skipping decoded evidence. This
reduces one measured duplicate cost without claiming it fixes historical60s failure.
Sampler failure-envelope and query work remain separate pending scopes.

## Reuse / implementation

Only storage._decode_checked plus focused execution_market tests. Reuse codec
input_from_payload,metadata codec,_source_digest,source_record and existing evidence/
real-PG tests. Frozen pre-change storage source/hash retained privately BEFORE edits
for a bounded comparison; never change prior runner/results or test against Git-only
ancestors. No golden code dependency in published tests.

Known valid BOOK/TRADE and actual consumer REBASE,explicit equal source,dict/string
payload; assert exact returned SavedExecutionInput against independently constructed
record. Assert1market decode when omitted,2when explicit. Negative cases must still
reject outerdigest/source/provenance/metadata/profile/rebase/sourceinvalid evidence,
including payload with recomputed outerdigest to reach deeperguards. Existing
read/RLS/append/immutability/rollback/duplicate identity regressions use a fresh
owned migrated database,not shared owner/testdata. Preserve all money/order rules.

## Validation / checkpoint

Feature: new targetedmatrix plus existing test_evidence and read-observer regressions;
scopedRuff/format/mypy/whitespace. Existing SQL/RLS unchanged but realPG suite retained.
After safety checks,one bounded microbenchmark only:1000fixed valid BOOK rows,
four fixed arms control/candidate/candidate/control,all results compared for equality;
4000decodes total,cap60s,expecteda fewseconds after preparation. Use frozen oldfunction
with same dependencies and currentfunction,no financial commands/DB/workload/4h.
Retain all arm timings;no slow-sample exclusions or claims of performanceacceptance.
This is per-row decoder microbenchmark,not representative20owner workload timing.
Release: all originalIncomplete/fullfinancial/rebuild/resource/100account gates remain.
After scoped implementation/tests/comparison report and stop for owner review;
noautomatic review/refactor/newcampaign/4h/Git/CI in this scope.

Preparationnote: benchmark source pin stopped before measurement because its output
subdirectory was not created. Preserve PreparationIncomplete/0measureddecodes;
create that private output directory before pinning under delegated harness authority,
then execute the originally authorized single four-arm comparison(no priorarmran).
No workload/4h or criterion change.

## Executioncheckpoint2026-11-16

[Scoped implementation/tests/comparison complete](evidence/endurance20-20261115/replay02-checkpoint.md),
52targetedcases/scopedstaticPassed. Equaloutputs for all4000microbenchmarkdecodes;
sourceunchanged,cleanupindependentlyverified. Originalgradeskept,F17notCompleted.
Stopforownerreview;no automaticreview/refactor/productionqueryfix/4h/Git/CI.

## Owner review/refactor checkpoint2026-11-16 — before source

Owner-directed scoped review found no findings; testedsource hashes matched reviewed
candidate. Owner then requested refactor the code. Productiondecoder is already
small and clear; keep its exact reviewed bytes/behavior. Refactor only new TRADE
testrecord helper: replace nested duplicate record construction with one named
intermediate,then recompute its unchanged source digest. No new helper abstractions,
changed assertions,testmatrix,recordvalues,SQL or financialbehavior.

Immediately run30affected decoder cases/scoped2-file static and whitespace; retain
8evidence/14observer lifecycle cases and microbenchmark on byte-identical production.
Record sourcebridge/currenttesthash; no benchmark/workload/4h/Git/CI repetition.

Refactor executioncheckpoint: [production byte-identical,30affected cases/static Passed](evidence/endurance20-20261115/replay02-refactor.md).
Onlyfixtureconstruction readability changed;22unaffected proofs retained. Scopedwork
complete,no newbenchmark/campaign/4h/Git/CI. Nextrepresentativerebuildscope needs
ownerstart;F17pendingacceptance/historicalgradesunchanged.
