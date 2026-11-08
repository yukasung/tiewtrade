# Wallet timeout injection correction — 2026-11-08

Owner instructed เริ่มทำ for publication-wallet-timeout-proposal.md, authorizing
this scoped test repair, checks, normal commit/push and one replacement CI round.

Only backend/tests/infra/paper_wallet/test_recovery.py changes executable code:
- Existing50ms cancellation window is armed after the real ledger INSERT returns.
- A separate5s outer watchdog bounds setup and is outside pytest.raises; it cannot
  count as successful injected timeout. Assert inner timeout expired and reached.
- Cancel parameter, exact episode/ledger/closure/result/audit rollback checks and
  same-command recovery success remain unchanged. No production/migration/API or
  financial/session-storage/transaction behavior change.

Checks on isolated real PostgreSQL tiewtrade_e2e_wallettimeout20261108:
- Existing cancel and timeout parameterizations:2 Passed (1.00s).
- Same timeout test with100ms delay before worker entry:1 Passed (0.72s), proving
  preparation longer than50ms does not prevent the intended post-write injection.
  Diagnostic runner alongside reproduces that delay using existing fixture hooks.
- Ruff check/format and scoped mypy with current src path: Passed.
  Initial mypy invocation lacked local source path; corrected environment and
  explicit Optional narrowing before final successful check. No checks disabled.
- Diff check Passed. Prior failure on577593a retained, not reclassified as pass.
- Test database dropped after zero-connection check; owner database untouched.

Financial proofs and browser42/Security Passed on577593a remain historical.
Replacement required CI on the next SHA is Pending until observed. No merge,
Live order, owner-account action, criterion relaxation or F17 Completed claim.
