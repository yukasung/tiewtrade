# F-17 Set-4 recovery and publisher diagnostic — 2026-11-06

Latest local campaign: **internal W1/W2/overflow/shortW3/integratedW4 Passed**, see
[2026-11-07 aggregate receipt](internal-pilot-local-checkpoint-20261107.md) for scope
and remaining candidate/opening/Release gates.

Original recovery checkpoint: **Recovery/safety complete; one diagnostic Incomplete / cycle Failed**.

The original `/tmp/tiewtrade-paper-set4-20261106` directory disappeared while its
worktree registration and uncommitted branch reference remained. The owner confirmed
no known move/backup. Reconstructed file edits from the existing session record on
base `98ff2f840fe08dc46ab5eb9976f17bdf32b062b1`, in the durable sibling workspace
`TiewTrade-paper-set4-recovery`; the original development workspace was not changed.
No historical shell/DB/workload command was replayed. Recovery used file patches,
file-only transforms and the pinned Ruff formatter. Original raw workload artifacts
are unavailable; recovered historical prose is not replacement raw evidence.
Original scratch PostgreSQL databases remain. No commit, push or merge was performed.

Revalidated recovery: fresh0065 migration, **303 tests passed in70.52s**, all28
recovered Python files type-checked. Ruff/format passed after restoring one test's
formatting. The source archive and recovery-operation records are outside the worktree
in `../f17-recovery-records-20261106`, including a pre-instrumentation archive/digests.
The raw new checks are copied here; environment credential files are excluded.

The owner-approved follow-up changes only `profile_pool_timing.py`,
`profile_diagnostics.py` and their existing tests. Before measurement, only selected
publisher/acquisition transactions gain detailed timing. Default worker activation,
production source, SQL, leases, pool and financial rules remain unchanged. Timing
separates connection acquisition (including pre-ping/connect), queries, body and
transaction finalization (commit/rollback plus cleanup); it is not server-only timing.
Fingerprints and UUID/tick identities are retained, without SQL/bind/error text.
The100000 transaction and64 per-transaction query limits fail on truncation.

Follow-up validation: **78 unique affected cases passed** (77 in the first run,
the corrected opt-in fixture then passed with its default regression; the initial
fixture failure is retained). Scoped Ruff/format/mypy passed on4 files;7 import
contracts kept. Financial/recovery tests from the recovered303-case suite remain
valid because no production source changed afterward.

One unchanged authorized diagnostic ran on the database in `campaign.json`:
100 owners ×20 baseline orders,600 measured cycles /3000 commands,20 workers,
R8 claim1, V2 coordination, per-book heartbeat, parent poll4, final-tail drain,
10 commands/s and1200s total cap. The old60s/p95/p99/financial/resource criteria
remain. `candidate-sha256.json` pins source/lock/config; `campaign-result.json` and
`cleanup.json` report execution and cleanup. This diagnostic cannot certify W1–W4,
HTTP/snapshot/integrated restore, required CI or F-17 Release dependencies.


## Result and limits

The run exited1 after **566.039s**, within the1200s cap. Baseline2000/2000 completed.
Measurement stopped132.005s into the planned300s when one positive cycle exceeded
60s (60.002306s). Offered1017, admitted1015, completed917, rejected0, completed
cycles145/600; planned commands3000. No complete financial/final-tail/resource
acceptance result was reached. Counters are observations, not a zero-violation proof.

The failed cycle spent0.167439s in submit_order/submit_cancel calls,37.001056s in
wait_command and22.757371s in wait_status. Its134 polling attempts spent25.768762s
waiting for the parent gate;139 owner transactions totaled2.376915s, including
0.674451s acquiring connections. These intervals overlap the wait phases and must
not be added again to the60s total. The final wait was for FILLED after the command
already reported success. Post-stop dispatch rows were TERMINAL, but that later
snapshot cannot prove timely visibility before the deadline. An optional expanded
owner read was rejected by existing API-role column grants; no privileges changed
and no expanded snapshot is claimed.

Worker processing from2326 samples fully inside the partial measurement interval:
**p95=470.510ms, p99=841.634ms**, against unchanged250ms/1000ms targets. The14064
setup-plus-partial samples havep95=344.670ms, p99=738.045ms; they are a different
population. Neither is a completed acceptance run. Measured dispatch observations
record8110 gate calls,2330 acquired/5780 busy and2331 successful claims; acquired
coordinator holds totaled84.811s across workers. This is evidence of substantial
coordination/processing/polling work, not proof of one causal bottleneck or permission
to change scheduling, permits or deadlines.

Publisher acquisition/publication2172 transactions retained detailed query timing
without truncation:2171 committed, one canceled during shutdown. Maximum transaction
2.771s, maximum connection-acquisition0.380s, body2.612s and finalization0.406s.
These maxima are from different transactions and must not be summed. The publisher
lease-loss failure from the preceding run **did not reproduce**; it is not proven
fixed or causally explained. `publisher-analysis.json` maps known fingerprints to
source locations without SQL/parameter content.

All20 workers stopped with no nonzero exit reported. All21 pool reports finalized
with0 checkouts;41 transaction/dispatch streams CLOSED and untruncated; parent
poll permits0; database connections/advisory locks0. No campaign processes remain.
All839 pinned source/lock/config hashes stayed unchanged. The original retained
NC11 database's0065 function body exactly matches the reconstructed migration.
Two additional recovered scanner-read tests passed on their own fresh database;
recovery validation is303+2 tests, plus the overlapping78-case instrumentation scope.

## Checkpoint and next step

The authorized recovery/instrumentation/one-run scope is complete. No production
source changed during the follow-up, and no additional diagnostic, W1, commit, push
or merge was run. V18 remains Partial/Failed; later integrated workload/HTTP/rebuild/
restore and candidate CI remain pending. V19/V20 still require their existing
bot/notification/Live dependencies. F-17 cannot be marked Completed.

Next recommended work is a bounded runtime-fix plan for command-to-fill progress:
use the retained cycle/worker/gate traces to choose a specific change that reduces
queue/processing/polling delay while preserving financial, owner, retry and scheduling
contracts. Review the concrete change before another timed campaign; do not repeat
this diagnostic or increase60s/250ms thresholds. This recommendation is not approval
for a new runtime protocol or another experiment.
