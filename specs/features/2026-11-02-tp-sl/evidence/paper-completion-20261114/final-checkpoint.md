# Paper internal20 — final local checkpoint, 2026-11-15

สถานะ: **Local internal checkpoint complete under R4; final publication/release gates pending.**
Source: main `98152fa` plus uncommitted task diff in `validation/f17-paper-completion-20261114`.
Authority: owner requested continuous completion and engineering criteria adjustment after >2 failures.
[Approved amendment/history](../../paper-timing-acceptance-amendment-20261114.md),
[validated summary](final-internal-checkpoint-summary.json), [source reuse map](source-reuse-map.json).

## Actual results

| Check | Scope | Result |
|---|---|---|
| Controlled TP/SL | 20 accounts / 400 baseline orders | Passed20/20; maximum trigger start544.278ms; exact financial effects Passed |
| SMOKE | 600 commands / 5min | Passed; p95/p99252.525/412.615ms |
| W1 | 3600commands / 30min, authenticated HTTP | Passed; p95/p99285.161/450.931ms;20/20 monetary oracles and20 rebuilds Passed |
| Original W2 benchmark | 12000commands / nominal10s^-1 | **Failed retained**:1645.305s>1260s, p95508.348ms>500ms and4unproven pool cancellations; financial/snapshot/rebuild facts Passed |
| R4 local burst5 | 6000commands /5s^-1 /20min | Passed;1205.726s measured; p95/p99221.671/329.159ms;20/20 monetary oracles, snapshots/rebuilds and strict pool contract Passed |
| Overflow | 4097book inputs | Passed; no economic change, all20 owners reconciled |
| Short W3 | 3000commands /30min /7scheduled faults | Passed; p95/p99176.256/262.801ms; all7fault observations RECOVERED; final financial/global invariants Passed |
| W4 | Actual dump/restore into new DB | Passed; canonical data and RLS/grants match; source unchanged; expired claim recovered; receipt identity/exact retry Passed; duplicate exit fill0 |

All engine samples and original benchmarks retained. Normal internal processing
ceiling500ms/2s and source/snapshot/replay/TP-SL/STOP/financial requirements were not
relaxed. New burst changes only offered load/counts (6000/5s^-1, same20min and amounts)
and is explicitly NOT the old12000/10s^-1 benchmark. Both 100-account W1 failures
and the old20-account burst failure remain Failed. No retrospective passing grade.

W3 snapshots620/620, p95/p9964.002/193.422ms;20 final rebuilds, maximum7.055s.
RSS stable-window growth -2.414% (original20% upper bound retained). Seven injected
fault windows:3owned-worker restarts,2owned connection churns,2dedicated Redis pauses.
This records the approved short-run fault/end reconciliation checks; it is not a
new claim of 4h endurance,100-account recovery or multi-API-instance load coverage.

W4 contains20wallets/21episodes including reset/correction/partial/cancel evidence,
plus pending intake, armed/exiting/closed/retry protection states. Real restored
owner RLS, exact receipt retry and no duplicate exit effect verified.

## Changes and relevant verification

Production: reuse complete wallet accounting without unrelated reset-readiness
work; reuse a fully validated position snapshot's version under the owner financial
lock while rereading actual held/reserved quantities. Default API/reset reads retain
full validation. No money/quantity/fee/risk/strategy/Live rule changes or migrations.

The public price reader alone uses a read-only execution-options facade over the
same pool; authenticated WS session refresh retains its original writable engine.
0.5s deadline/query limits unchanged. Test observer separates only actual expired
read-only public-reader cancellation (single cancellation, known code scope, no08
SQLstate) from resource errors. Unknown/external/financial/disconnect/leak failures
remain failures. Actual new timed parent reports:0resource errors and0expected read
deadline cancellations; the exception path was proven with blocked real PG reads.

Relevant proof:191retained financial safety cases; R4 facade group168Passed and
2initialSkipped; followup86Passed/no skips resolves those2dedicated-Redis guards and
adds cancellation/null-context/diagnostic-option checks. Groups overlap; no inflated
combined count. Real WS/session/HTTP/pool tests Passed; initial bad import and overly
broad readonly implementation failures retained in amendment history. First failed
unit logs were overwritten, not reconstructed; successful replacement logs retained.
Scoped Ruff/format/mypy7files Passed. Final whitespace/content checks Passed.

Current burst/overflow/W3/W4 code inventories1017/1017 match final source. Explicit
reuse mapping for earlier controlled20/SMOKE/W1 proves all backend production code
outside API app composition unchanged; affected app changes have actual readonly/
WS/session/HTTP proof. Other changes are new profile/observer or unsupported
release-diagnostics rejection; legacy valid configurations and financial code unchanged.

## Cleanup and remaining gates

Every manifest-owned source/restore DB showed0connections/0advisory locks and was
dropped normally. Dedicated Redis ownership label verified, stopped normally and
removed. No images/volumes or owner service/process stopped; no owner-account or
Live command issued. Two other restored-prefix DBs had no ownership evidence in
this task and were left untouched; no claim that every DB with that prefix is ours.

Still pending: review/refactor/publication gates for this uncommitted source,
required CI on the final candidate, owner/opening gates, original100-account and4h
Release validation, F17V19bot/notification andV20Live dependencies. **Not F17Completed,
not public/Live readiness, not a product-enforced20-user or5s^-1 limit.**

Next: review the consolidated source/evidence diff before publication. No further
local workload rerun is justified without an affected dependency/new finding; the
current local checkpoint is complete. Git/deploy/owner financial actions retain
their existing authorization gates. Raw campaigns are under the worktree's
`validation-artifacts/f17-paper-20261114/`; do not stage raw dumps/tokens/large traces.
