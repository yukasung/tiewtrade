# NC-F19-20 BOOK readiness/clock diagnostic — Not Reproduced

Owner approved `approve NC-F19-20` on2026-11-02. The scoped harness implementation,
targeted checks and one diagnostic are complete. **Not Reproduced, acceptance_result=false**;
this does not pass W1/V-20 or establish a production/environment fix.

## Change and checks

- `profile_book_clock.py` wraps the existing `BookState.require_ready` only inside the
  child test publisher. Original arguments/return/exception remain; only an existing
  SourceUnavailableError records the exact caller DB clock, received/verified/source
  timestamps, existing comparison flags and input/generation/process identities.
- No financial values, SQL parameters, arbitrary error messages or credentials in trace.
  Failure output bounded32; write/cap errors mark incomplete and fail the diagnostic.
  Patches restore on exception/cancellation. Child close rejects missing/incomplete,
  unused observation or nonzero process exit. No SQL observer/extra connection/process.
- `--book-clock-diagnostic-seconds 60` requires parent W1/F19_SET5/child exclusively.
  It reuses the existing diagnostic cutoff and never creates acceptance success.
  The copied launcher guard allows the one named NC20 DB and checks all actual roles.
  The original NC19 guard artifact was preserved byte-for-byte (hash verified).
- **94 Linux tests passed, zero skips,10.044s**, including original publisher/control/IPC
  regressions and real child publication/restart/cleanup with the observer enabled.
  Controlled future received/verified/source, stale and not-ready cases preserve outcomes
  and identify exact flags; exception identity, redaction, cap/write errors, restoration,
  incomplete child close and CLI exclusivity covered. JUnit: `nc20-checks.xml`.
- Ruff/check, format/check and mypy passed on six changed Python files. Source/runtime
  did not change after checks. Production code, financial calculations, database schema,
  API, authorization, freshness/leases/timeouts and pool/resource bounds unchanged.
  Existing NC19 safety evidence remains applicable; no full suite rerun.

## One execution

Run `nc20-r1`,09:59:52–10:04:01 Bangkok on2026-11-02, exit0/no OOM. Frozen tested source:
`aa3fcb7009f53678ebe8b9b8765966a49b302ed29740f7df7270ffe094650cc8`.

- Fresh `tiewtrade_f18_release_set5_nc20_source_r1`: all nine actual role connections
  matched; public schema empty before migration; schema0062 and users/commands/settings/
  price frames all0 before seed. Safe role/freshness proofs and exact command retained.
- Same100core owners x baseline20, ten Paper workers, monitor4/request1/stop2/scan3,
  target10commands/s, child5Hz, same CPU/RAM/VM limits and NC17 barrier configuration.
  The heavier source SQL/backend observer was disabled.
- Setup181.451s: baseline20/20, dedicated LOSS_LIMIT partial/stop/RESET/opening-blocked,
  and manual/BOT resting setup completed. Observation cutoff targeted60s; the recorded
  elapsed value is60.600486s. This is a diagnostic, not a600s acceptance window.
- Observer **1203 calls across setup and observation,0 failure records**; closed/complete,
  original guard never raised in these calls. No publisher-failure.json/failure.json.
  Original diagnostic.json records OBSERVATION_COMPLETE and acceptance_result=false.
-3599 source receipts: no adjacent wall-time or monotonic reversal observed in this
  journal. This does not prove global clock stability between samples, or resolve the
  prior r3 wall-time reversal/failure. **The exact r3 failing guard arguments remain missing.**

The observer reports failure-recording time0ns because that path did not execute.
Wrapper dispatch/counter overhead is unmeasured; do not claim zero overhead or subtract
an estimate from latency. The active child observer import/scope is also part of this
candidate; no controlled overhead-free comparison was run.

## Partial workload, safety and cleanup

Counters527offered,485admitted/completed,0rejected,186fills,93cancels,103replays,78cycles.
In-flight work is cancelled at the diagnostic cutoff; counters are not a full conservation
oracle. Scheduled RESET0/100, Not Exercised. One queued-manual preparation journal record
exists; no completed full stop schedule. One-shot/partial barrier and later work were
outside the observed window, Not Exercised, **not Passed**. No SLA verdict was evaluated.

All13pool files finalized with checked_out0; remaining DB connections0. Partial snapshot:
194FILL events, duplicate/null execution identities0, negative positions/reservations0,
terminal command rejections0; one breach event with exactly one matching audit.
Reused `get_wallet`/Money to inspect103wallets:0missing/negative balances. This does not
replace the full financial/PnL/conservation oracle. Fourteen connection termination/
CancelledError warnings are retained, not hidden by the successful cleanup snapshot.

73original run files hashed, DB dump18,051,985bytes+SHA256 retained, along with launcher,
source/resource/fresh-DB inventories, JUnit, observer summary and saved analysis/query
scripts under `validation-artifacts/f19-set5-20261101/` (`nc20-analysis/summary.json`).
Task PostgreSQL/Redis stopped with data retained; unrelated containers unchanged.

## Stop and next step

The approved plan requires stop on no reproduction. No repeated diagnostic, replacement
W1, W2/W3/W4, production/environment edit, commit/push or deployment followed this run.
V-20 remains **Failed / Pending Full Validation**; V-21..24 remain Pending Dependency.
Prior r3 Failed and NC17 Failed SLA evidence are preserved.

Recommended next scope: read-only host/Docker VM clock configuration and existing-log
review (about10–20min), before selecting a fix or another workload. Current evidence
supports a clock/freshness hypothesis but does not identify a synchronization cause or
prove the original guard condition. Await owner direction for that scope; do not choose
future-time tolerance, relaxed thresholds or another timed run from this non-reproduction.
