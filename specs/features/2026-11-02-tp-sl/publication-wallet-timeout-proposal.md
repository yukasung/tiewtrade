# PR63 — final CI blocker: wallet timeout injection

สถานะ: **Approved — owner instructed เริ่มทำ on 2026-11-08: scoped test correction, targeted real-DB checks, commit/push and one replacement CI round**
Date: 2026-11-08 Asia/Bangkok
Final published head: 577593a326f41ae49f36ffe58ce7cb69747736c9
PR: https://github.com/yukasung/tiewtrade/pull/63

## Observed final results

- [Security42463638267](https://github.com/yukasung/tiewtrade/actions/runs/42463638267): Passed all jobs.
- [CI42463638317](https://github.com/yukasung/tiewtrade/actions/runs/42463638317): Failed backend pytest.
- Browser42 Passed: main20, catalog2, F16seven, F17seven, wallet/risk/F19six.
- Frontend/static/API-contract/config/container checks Passed.
- Backend static/import checks Passed. Pytest4820 Passed, one Failed,
  31deselected, fivewarnings (935.42s). Subsequent isolated integration/migration/
  fresh-global-state steps Skipped, not Passed on this SHA.
- Failure: backend/tests/infra/paper_wallet/test_recovery.py:282,
  test_reset_interruption_rolls_back_and_same_command_recovers[timeout].
  The50ms timeout elapsed before the injected post-ledger-write barrier was
  reached, so reached.is_set() was False. Later rollback/recovery assertions were
  not reached. This evidence does not establish financial corruption or prove
  there is no production defect.
- This wallet test and wallet production package have no diff against base
  e6b32bb. Backend passed on previous candidates f5b3449, ab9c57a and19434bc;
  those results cannot replace failed required CI on the final SHA.

## Approved correction scope

Make timeout injection deterministic in this one existing safety test. Start a
bounded setup wait to reach the real post-ledger-write barrier before arming the
same50ms interruption window. Reuse asyncio timeout/events and local test patterns;
keep a separate bounded outer watchdog, cancellation propagation and cleanup.
Retain every exact rollback, episode/ledger/audit/result count and same-command
recovery assertion. Do not increase the financial deadline, remove the reached
assertion, modify wallet production, or retry failures to declare a pass.

Reuse approved F13 wallet plan and validation V-6/V-9 (wallet reset cancellation/timeout rollback and same-command recovery), plus F17 publication safety gates. Run both
cancel/timeout parameterizations on isolated real PostgreSQL, relevant scoped
static checks; if those pass, normal commit/push and one replacement required CI
round (about20–25min). Stop on further failure, no merge or F17 Completed claim.
Owner approval authorizes this scoped dependency test repair and one replacement CI round. Production wallet code and financial criteria remain unchanged. Reuse asyncio.Timeout.reschedule (backend/tests/infra/risk_limits/profile_timing.py), local post-write Event barriers and 5-second test watchdog conventions. Arm the same 50ms timeout only after the ledger write, assert that this inner timeout expired, and keep the outer setup watchdog outside the expected TimeoutError assertion so setup failure cannot count as successful injection.
