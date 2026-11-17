# NC-F17-FENCE-01 — continuous engineering follow-up checkpoint

สถานะ: **Passed diagnostic — historical failure not reproduced; F17 notCompleted**

Owner requested “ทำแบบต่อเนื่อง” after the captured9.848s price-fence interval.
[Recorded engineering amendment](../../publisher-fence-observation-plan.md) before
source: bounded read-only blocker evidence, original trading/lease/fence rules.
No production source, schema, locks, role grants, public API or financial logic changed.
Static review confirmed F18 shared/exclusive ordering and MVCC book reads, but did
not establish a deadlock/holder from the historical client spans. No speculative
lease extension, reacquisition or trading-rule change was made.

## Implementation / safety proof

Added an opt-in fence sampler alongside lease observer, restricted to original20
SMOKE and rejected without lease observer/with other disallowed profiles/options.
Actual driver backend PID is captured without an extra SQL query. A single task
checks active statement duration and samples only at >=1s, at most4Hz. Queries are
readonly on the same guarded isolated DB with500ms statement/200ms lock/1s observation
bounds. Capture only PG timestamps/PID/role/state/wait events/blocking PIDs/lock
identities. No query text, parameters, sessions, cookies or user financial rows.
Retention64snapshots; activity128/lock8192bounds fail incomplete rather than silently
truncate. Only final/error disk flush. Monitor/query/IO error preserves primary and
partial evidence, prevents complete grade. Monitor is joined before owned disposal.

One additional declared ADMIN_OBSERVER(default5/10) pool is required only with the
explicit fence flag; one sampler task/connection at a time. Tracker and aggregate
validator use the same trusted exact inventory. Original parent/worker pool rules
remain mandatory. LEASE-only/default paths unchanged. Transient test counters/buffers
are diagnostics, not application sessions or persistent business source of truth.

111distinct affected cases Passed incrementally:
-54/28.12s: initial9fence +18load +27fixed-case/IO/rollback regressions;
-61/11.35s: updated10fence +51owned-pool/default/negative/caller regressions;
-9/8.96s: real full monitor integration +8lease-witness paths (4additional fence-on).
Logs `validation-artifacts/f17-clock-recovery-tests-20261115/` attempts
1794756855097069000,1794756934556567000,1794757008340455000. No skips.
Controlled real-PG shared holder/exclusive waiter verified actual blocking PIDs and
Lock wait event. READ ONLY rejected an attempted fixture write with SQLSTATE25006.
Live monitor test observed the blocker then publisher committed once after normal
holder release. No test lease/backdating/financial command or guard was substituted.
Cancellation/unknown commit/pool disposal/default behavior retained. Scoped9-file
Ruff/format/mypy and whitespace Passed. No full regression/CI claim.

## One diagnostic result

One120s/7sample preflight Passed before fixtures, then one fresh20owner/400baseline
order SMOKE with600commands at2/s and existing workers/claim/poll/final-tail rules.
**Passed**, total472.652305s (7min53s), measured302.800946s against300s target.
600offered/admitted/completed,0rejected;120cycles,240fills,120cancels,120replays.
20/20owner balance/reservation/held/cost oracles and global invariants Passed.
3028measured book inputs >=3000required. Final-tail drain2.058s. Original base/resource
and aggregate pool checks Passed across parent+20workers,0aggregate errors.

Publisher3115RETURNED/0failed. Slowest whole publication1.456718s (stats); recorded
inner trace tick2737 1.456421s, price-renew stage1.097079s across multiple SQL calls.
The longest individual retained SQL call was0.901022s; slowest16retention floor was
0.429484s, so all publications exceeding1s were retained. No individual SQL reached
the sampler's1s trigger: **0blocker samples**,0sampler errors,task joined. This is
consistent with configured trigger, not proof that no short lock contention occurred.
Engine transaction p95/p99183.913/369.764ms,10260samples, current/original targets
Passed; end-to-end is separately retained in summary. No slow samples were excluded.

These are diagnostic measurements with explicit instrumentation overhead. There is
no blocker identity from this workload because the target stall did not recur.
Do not claim the historical lease problem is fixed or this replaces4h acceptance.
SMOKE position snapshot/rebuild NotRun; full financial/rebuild/Release remain pending.

## Cleanup and source binding

Source/config/migrations/copied runner pinned before preflight, unchanged at end.
Dedicated DB/labelled Redis removed normally; independently verified DB absent,
0connections/0advisory locks and Redis absent. Owner PostgreSQL healthy/owner Redis
running, restart0both. No retained resources, owner/Live orders or service changes.
Raw evidence `validation-artifacts/f17-fence01-20261115/` contains private local
configuration; do not publish wholesale. [Sanitized summary/source hashes](fence01-summary.json).

## Checkpoint

Continuous follow-up completed through implementation, safety/static verification,
one short campaign and independent cleanup. No second campaign, production fix,
4h/Git/CI action. Keep all original Incomplete grades and F17 notCompleted with
financial/rebuild/Release/opening/bot/notification/Live dependencies. Next is scoped
review of this new observer before a separately approved long-run observation or
other evidence-led correction. No requirement/lease relaxation justified here.
