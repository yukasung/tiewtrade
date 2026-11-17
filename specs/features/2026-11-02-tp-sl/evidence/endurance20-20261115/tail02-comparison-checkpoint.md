# NC-F17-TAIL-02 — Query correction and comparison checkpoint

สถานะ: **Local checks/comparison complete — stop for owner-directed review**
Owner approved implementation and one comparison. No4h, Git, CI or opening action.

## Implemented scope

profile_workload.py now shares TAIL_CURSOR_SQL/read_input_cursor between the two
existing reads in wait_for_input_recovery and drain_final_tail. A correlated scalar
max over all visible keys replaces the one-to-many grouped join. Each read is still
one SQL statement; READY, empty-history zero, missing/invisible activity failure,
all-pair/generation/INPUT/REBASE maximum, task/session/gate behavior and the total60s
deadline are retained. No source/publisher or financial calculation change.

profile_tail_reads.py binds the shared SQL, reader and both callers. Comparison
control is the normalized old query extracted from immutable b0d5580 and matched
to the recorded TAIL-01 SQL digest. The --compare arm follows the approved fixed
order; the original43-observation mode remains available and historical results
are unchanged. test_tail_reads.py's drift/mixed-history assertions updated;
test_tail_query_equivalence.py adds real-PG state/absence/snapshot comparisons.

## Local validation

123targeted tests Passed in24.93s, no skips: old/new READY/UNKNOWN/CONFLICTED,
0/1/many keys, missing/invisible activity, append committed during a held snapshot,
fresh subsequent read, diagnostic safety, final-tail/parent-poll/prior review
regressions. The strengthened mixed-pair/generation/INPUT/REBASE equivalence
assertion then1Passed in4.84s (overlaps the123; not124unique cases).
Scoped Ruff/format/mypy and whitespace Passed for all4affected harness/test paths.
Private logs attempt-1794731748596574000.log and attempt-1794731851844294000.log
remain in validation-artifacts/f17-clock-recovery-tests-20261115/.

## One comparison campaign

Total1217.443057s (20m17.443s), seed1085.873239s, measurement7.678821s. One preflight
Passed7/7. Same20synthetic episodes/2890260keys and60decoded samples for every arm;
all86observations returned with identical expected values, financial snapshot
unchanged, candidate unchanged. Pool5+10 and gate4 retained.

| Arm | Reads | Wall seconds | Mean query ms |
|---|---:|---:|---:|
| Old serial |20|3.794991|185.715|
| New serial |20|2.019414|98.202|
| Old concurrent |20|0.814253|129.545|
| New concurrent |20|0.439358|81.362|

Old plans3/3: external-merge Sort over144513rows, temp-read461/temp-written463blocks
per read, execution123.663–129.355ms. New plans3/3: no Sort and zero temporary I/O,
execution65.701–69.762ms. New plan still scans144513visible keys; no index-only or
constant-time claim. Fixed arm order/cache effects retained, no sample dropped.
This is observed improvement on a quiescent analyzed fixture, not a randomized
causal percentage or proof of the original4h contention/60s drain acceptance.

[Summary](tail02-comparison-summary.json), [source receipt](tail02-source-bridge.json).
Raw runner/launcher/schema/source/diff/config,43-per-arm reads/plans and gate
observations are retained privately at validation-artifacts/f17-tail02-20261115/.
Normal owned-DB cleanup succeeded; independent DB absence,0connections/0locks.
No Redis created; owner PostgreSQL/Redis running/restart0, PostgreSQL healthy.
Backend production, migrations and frontend unchanged. All older results retained.

## Review focus and publication blocker

Review equivalence across all dimensions/RLS, single-statement snapshot semantics,
unchanged deadline and gate, actual runtime SQL binding, and comparison limits.
There is a concrete portability issue to resolve before publication: baseline_sql
uses git show b0d5580 at runtime, while ci.yml's backend job uses default shallow
checkout (the config job alone fetches full history). Current new equivalence/mixed
history tests call baseline_sql, so a checkout without that object will fail before
running their assertions. Local validation used full history; it is not requiredCI.
Recommended correction during the review/fix gate: package the already verified
immutable old SELECT as a small fixture with provenance and the same normalized
digest, test mismatch/missing controls fail closed, and use it without depending on
ancestor availability. Do not expand workflow checkout/network behavior merely for
this diagnostic. No new query/fixture/workload experiment is needed for that change;
retain comparison evidence with an explicit control-retrieval source bridge.

The plan requires stopping after this comparison; this issue is reported rather
than silently changing the pinned candidate afterward. Not ready for publication
or merge. Next is owner `review code`, then scoped fixes/refactor authorization and
affected validation. A new4h replacement requires separate authorization after
those gates. Both4hIncomplete grades and finalfinancial/rebuild/Release/opening/
bot/notification/Live dependencies remain pending; F17 not Completed.
