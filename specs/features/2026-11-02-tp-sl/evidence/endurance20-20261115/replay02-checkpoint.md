# REPLAY-02 — duplicate market decoder elimination

สถานะ: **Scoped implementation/safety/comparison complete; awaiting owner review**
2026-11-16,owner requested ทำต่อ;[pre-source amendment](../../replay-decoder-improvement-plan.md).
F17 remains notCompleted. No approved numerical criterion was relaxed.

## Change / behavioral proof

Only production storage._decode_checked changed: payload lacking source_market
reuses its already decoded immutable market; explicit source still decoded separately.
Reuse StoredExecutionInput only when market/source are the same object. No rawdict
value-equality shortcut (True and1 can compare equal but have different validity).
Retain outercanonicaldigest,source digest,domainvalidation,rebase/source equivalence,
rowprovenance,metadata and SimulationProfile checks. No SQL/queryorder/pagecursor,
RLS,sessionstorage,Money/Quantity math,financialformula,lease,retry/schema/API change.
Per-row immutable object reuse is transient,not a cross-request/process businesscache.
The query's diskSort and sampler failure-envelope remain separate pending work.

30new focused tests:8BOOK/TRADE × missing/explicit equal source × dict/stringpayload;
2actualconsumer REBASE;20negative malformed/redigested outer/source/provenance/
profile/metadata/boolean/null/decisioncontent cases. Known returnrecord equality and
originalcodec invocation count1missing/2explicit are checked. Explicitbool1 source
still rejected even though it equalsTrue in Python. No integrity check bypassed.

Combined52targeted cases Passed on fresh owned migratedDB,15.457s total inclsetup/
cleanup:30newdecoder +8existing test_evidence +14read/lifecycle regressions. Existing
suite covers concurrent duplicatecopy,actualRLS/privileges/immutablepayload/rebase/
rollback/read behavior. Log validation-artifacts/f17-replay02-20261116/safety/pytest.log.
Scoped2-file Ruff/format/mypy Passed; whitespacePassed. Test import/format adjustments
only after initial30case unit run; final52case combined run used final semanticcode.
No architectureimports changed in production. An initial backend-relative test command
from repo root collectedno tests(exit4); corrected command thenpassed. No test skipped.

## One bounded microbenchmark

Freeze pre-edit storage source/hash before changing production. Compare old
_decode_checked compiled from frozen source with currentfunction and same unchanged
dependencies on1000fixed valid BOOK rows (stringJSONpayload),60s outerbudget.
Fixed fourarmscontrol/candidate/candidate/control;4000decodes,all SavedExecutionInput
outputs exactlyequal. No IO/DB/ordercommands during measurement. Actual rawarms:

| arm | decoder | seconds /1000 |
|---|---|---|
|1|control|0.387683458|
|2|candidate|0.234667709|
|3|candidate|0.216554208|
|4|control|0.343372250|

Total1.271742s incloutput equality checks;sourceunchanged. All arm timings retained,
no slow samples trimmed. These few microbenchmark arms do not establish statistical
confidence,whole-reader/W3performance acceptance,or that historicalowner14 now fits60s.
No new96000read/20owner workload/4h run and no claim of historicalrootcause fixed.

Preparation initially stopped at candidate pin before measurement because its output
subdirectory was missing. Preserve benchmark-preparation-incomplete.json with0measured
decodes; create directory under delegatedharnessauthority,then perform the single
four-arm comparison. No completed comparison was discarded/replaced.

## Provenance / cleanup / checkpoint

Rawprivate artifacts validation-artifacts/f17-replay02-20261116/ include frozencontrol,
controlbinding,bothcandidate/runner hashes,allarmtimings and safety/cleanup receipts.
Independent maintenanceDB check confirms ownedtestDB absent,0connections/0advisorylocks.
No retainedresources,forcedrop,owner/Live orders,service stop ornewinfrastructure.
Originalrunner/results and all Failed/Incomplete grades remain immutable.

Scoped implementation/targetedvalidation/comparison finished. Next is owner-directed
code review of this productiondecoder change,then fixes/refactor if instructed.
Do not automaticallyreview/refactor/start anothercampaign or publish. F17pending
finalfinancial/global/rebuild20/resource/100accountRelease and otherdependencies
remain; this microbenchmark cannot close them. No Git/CI actions in this scope.
