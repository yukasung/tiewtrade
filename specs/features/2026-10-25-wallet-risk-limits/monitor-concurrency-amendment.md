# F18-R18 — Eight bounded monitor transactions within existing CPU/RAM

สถานะ: Approved — owner approved R18 on 2026-10-28

## Evidence and current candidate

R17 deterministic public decoding passed78 unique affected tests and achieved
30041hits/3683misses in its first comparison. Paper transaction median improved
102.42→81.45ms, but monitor SLA did not pass. Approved-method combinations were
tested separately; their original failures remain in M5 evidence.

The best observed combination uses the original blocking100ms owner lock,
R15's100-hint/four-slot sweep, R16's captured read snapshot and R17's decode reuse.
Its comparison still failed3249/58947 acknowledged price inputs (~5.51%), with
max2.327136s.86owners without lock timeout also had late inputs (max1.5495s).
Thus another lock retry alone is not supported as a sufficient explanation.
Observed scan-to-scan rounds had median.5875s and max1.3293s, with only about
30–60ms at the final tail. No ready-input SLA exemption has been introduced.

A transaction-phase diagnostic measured checkout/begin median1.55ms/p959.87ms,
body17.42ms/48.65ms, and commit-or-rollback/release2.05ms/12.10ms. These are
separate distributions, not additive per-transaction measurements. Risk CPU in
the earlier combined probe averaged about.785 of its1CPU quota with one throttle
period; PostgreSQL had substantial headroom under its4CPU ceiling. Increasing
concurrency may overlap I/O, but may instead saturate CPU or worsen contention.

Equivalent setup SQL batching did not help (max5.575732s) and was rolled back,
including its shared session-helper changes. It is not part of this proposal.

## Proposed bounded experiment

1. Increase only standalone monitor in-flight owner transactions from4 to8.
   Set its ENGINE pool_size=8, max_overflow=0; retain pool_timeout=.1s. Warm the
   same eight slots before measurement. Reuse the existing bounded scheduler,
   semaphore, RLS session and replay functions rather than introducing another
   worker process or a second replay algorithm.
2. Keep scanner page100, fairness cursor, one attempt per candidate per sweep,
   blocking owner lock100ms, statement timeout700ms, normal20ms sleep, and
   frame/boundary budgets100/20. Financial/API fences and native retry schedules
   remain unchanged. Do not combine this experiment with a new retry method.
3. Preserve request pool1, stop pool2 and scan pool3, and their existing loops.
   CPU/RAM remain API/Paper3CPU/1536MiB plus risk1CPU/512MiB (aggregate4CPU/2GiB),
   PostgreSQL4CPU/3GiB and Redis1CPU/256MiB. Keep10 Paper processes and one risk
   process. This DOES add four possible monitor database connections; it is not
   described as an unchanged pool budget. PostgreSQL currently has max_connections
   200; verify actual aggregate connection use and pool failures under load.
4. No money/quantity/PnL/risk arithmetic, source freshness, workload rate/duration,
   60s cycle deadline,1s evaluation SLA, admission gate or acceptance criterion
   changes. No automated Live orders.

## Reuse, tests and acceptance

Reuse `services/engine/risk_limit.py::run_risk_monitor_round`, the pool factory
and warming in `risk_limit_main.py`, the real scheduler barrier/fairness tests,
and the existing matching/concurrency/stop tests. Keep the concurrency bound in
one explicit runtime configuration shared by pool sizing and scheduler wiring.
Direct-call defaults may remain4 for existing callers; only the approved runtime
opts into8 and reports that actual composition in its manifest.

Prove eight transactions can be active and a ninth waits; same-owner processing
still serializes through the financial lock. Verify role isolation, rollback,
transient breach, duplicate stop prevention, and request/stop progress while
monitor slots are occupied. Run affected static checks and review before load.

Then run one sequential same-clone comparison with cache/owner progress, every
input SLA, CPU throttling, memory, connection counts and pool failures recorded.
No overlapping diagnostics/tests. If fairness, safety or contention worsens,
restore pool/concurrency4 and retain failed evidence. Improvement is not a pass:
native W1, then W2/W3, final regression/review and remaining validation are still
required before any completion or activation claim. If this does not provide
enough headroom, do not silently increase CPU, memory or connections again.

## Approval boundary

R15/R16 explicitly retain four monitor slots/pool4. Changing that ceiling is a
new concurrency/pool allocation method, outside R17's decode-only approval.
`plan.md:301` requires “ขอ plan amendment ก่อนเปลี่ยนวิธี”; AGENTS.md requires
approval before implementing a changed method. Existing R6–R17 approvals remain
valid; Owner approved R18 before implementation.

## Experiment outcome — 2026-10-28

Approved experiment executed; safety32passed, both bounded SLA comparisons failed.
Native comparison did not establish stable headroom. Runtime restored to4slots;
bounded explicit8-slot API/tests retained but normal runtime does not opt in.
Rollback12passed/static checks passed. Details and limitations in
`evidence/m5-final-candidate.md`. Further capacity changes need a new amendment.
