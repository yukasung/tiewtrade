# F-17 — one D20 replacement with backend identity at cleanup

สถานะ: **Approved A — เจ้าของตอบ approve วันที่ 2026-11-09; cleanup identity/tests, D20หนึ่งรอบ→W4หนึ่งรอบเมื่อผ่าน แล้วหยุดรายงาน**
วันที่:2026-11-09 Asia/Bangkok
Evidence: [single cleanup diagnostic](evidence/remaining-paper-20261109/cleanup/analysis.md).

Diagnostic without load closed every connection and did not reproduce the D20
one-backend observation. No production fix or cleanup exception is justified.
Retain original D20 Incomplete and all its measured results.

Recommended A scope:

1. Extend only the current D20 runner's existing final read-only cleanup SELECT
   to record the target backend PID/role/state/backend_type/transaction-open and
   timestamp alongside the existing connection/lock counts. One SQL snapshot;
   no SQL text/credentials/session values and no samples during measurement.
   Preserve count0/locks0 acceptance, original classification and no retry/wait.
   Record a distinct after-process-exit observation on postgres DB, outside target,
   without using that later result to override cleanup acceptance.
2. Targeted tests: empty target accepted, one target backend still blocks, identity
   rows/count agree, malformed/missing evidence not Passed, query only generated
   fixture target and allowlisted fields. Scoped Ruff/format/mypy. No production,
   money, pool, timeout, sampler, rate or profile change. Preserve old artifacts.
3. Reuse controlled20 Passing proof because diagnostic/cleanup-only harness changes
   do not touch its domain/runtime. Pin all source/config/schema/runner identities
   and owner-confirmed window. Run one fresh-DB D20 (SMOKE internal diagnostic
   intake),20owners/400baseline/600commands,300s,book≥3000, original20min total cap,
   engine500ms/2s pilot acceptance and250ms/1s target, exact economic/resource rules.
4. If D20 **campaign** passes, run one fresh-source/fresh-target W4 per approved§23,
   actual current schema and pending-request/exit/exact-retry/security/restore proof.
   Estimated D2010–15min + W45–10min after environment ready, plus about10–15min
   preparation/checks. Each phase retains existing preflight and cleanup. Any
   Failed/Incomplete stops before next phase; no auto-rerun or criterion waiver.
5. Stop/report after this sequence. No B/W1/W2/overflow/W3, owner trading/gate action,
   commit/push/PR/merge/deploy/Live order. Passing does not complete F17 or replace
   original100-account/4h and bot/notification/Live obligations.

This scope is not authorized by the no-order diagnostic, which explicitly stopped
before further D20/W4. Owner can instead stop and retain the current Incomplete.

## Execution complete — 2026-11-09

[Checkpoint](evidence/remaining-paper-20261109/identity-replacement-checkpoint.md):22targeted tests/scoped static checks Passed. One fresh D20 replacement Passed600commands/300s/3000inputs, p95/p99=95.948/128.225ms, financial/pool and one-shot cleanup0/0; candidate unchanged. One conditional integrated W4 Passed, source unchanged, restore/recovery/security equality and cleanup0/0. Current campaign databases removed normally. Original Incomplete/unknown cause retained, no threshold/production fix. Scope complete; no B/Live/owner actions/Git. Next owner review of scoped harness before Git publication; other validation gates remain pending.
