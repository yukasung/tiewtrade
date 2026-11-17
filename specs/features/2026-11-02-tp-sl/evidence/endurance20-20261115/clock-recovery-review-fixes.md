# NC-F17-CLOCK-01 review corrections — 2026-11-15

สถานะ: Review findings corrected; awaiting owner refactor instruction.

Owner instructed “แก้ไข” for the prior review's two Medium and one Low findings.
This is a harness-only correction to approved steps B–C, not a four-hour result.

## Corrections

- R1 Medium: after confirmed root rollback, retain the exact guard exception and
  exit the authorized session normally. Rethrow only outside that session. This
  exposes internal close failures through the existing normal-exit policy instead
  of allowing the shared error path to suppress them. No shared session change.
  The rolled-back attempt has no committed timestamp; no retry on close failure.
- R2 Medium: check the retry's renewed source pair, generation, owner and expected
  next input ID while its transaction holds the source lock, before publication or
  price writes. Changed identity fails before writing; post-commit checks remain.
  Apply this only to the additional attempt, not later ordinary publications.
- R3 Low: ignore inherited recovery context in foreign tasks at publish_market
  entry, before new_attempt or abort can mutate parent evidence. Root orchestration
  still accesses its controller to manage the original measurement window.

Three new real-PG regressions verify an internal engine-context exit failure after
rollback, a separate publisher committing the expected input before retry, and a
foreign child failing while the parent's recovery is in flight. They prove no
extra publication and intact parent evidence/recovery. Existing real-PG financial
invariance, root rollback/lock release and unknown-commit tests remain covered.
Commit-reply fixtures now distinguish the clean exit of a rolled-back session
from an actual commit reply; assertions about accepted effects/retry caps remain.

## Validation and retained failures

- Initial recovery module: 58 Passed / 4 Failed in 12.08s. The new source identity
  check initially also affected later ordinary ticks; fixed its retry-only scope.
  Two old commit-reply fixtures needed to distinguish rollback from commit exit.
- Those four cases plus readiness/heartbeat/internal-profile/campaign regressions:
  101 Passed in 7.77s, no skips.
- Three new regressions, the original real-PG successful recovery/financial check,
  failure timeline/cycle budget/prior review regressions: 56 Passed in 6.10s,
  no skips. The recovery module's 62 unique cases are covered incrementally;
  overlapping runs are not additional unique cases.
- Ruff check, format check and mypy Passed for all five affected harness/test files.
- Parent test databases removed normally after each run. No owner/Live operation.

Private logs retained in validation-artifacts/f17-clock-recovery-tests-20261115/:
attempt-1794711308704759000.log (initial failures),
attempt-1794711345320552000.log (101 Passed),
attempt-1794711375304948000.log (56 Passed).

[New source receipt](clock-recovery-review-fixes-source-bridge.json) supersedes the
implementation fingerprint for this correction; the historical receipt remains.
Production/backend schema/frontend unchanged against b0d5580. No new API, session,
financial calculation, retry limit, guard, timeout or acceptance threshold.

Original four-hour run remains Incomplete. OS/VM clock mechanism remains unproven;
one-event recovery does not ensure a future endurance pass. No four-hour run, CI,
commit, push or merge performed. F17 remains Pending Full Validation, not Completed.
Next: obtain the required separate `refactor the code` instruction; after authorized
refactor run affected validation, then seek plan step D execution authorization.
