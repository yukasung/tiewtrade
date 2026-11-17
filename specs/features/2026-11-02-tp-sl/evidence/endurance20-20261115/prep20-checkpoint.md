# NC-F17-PREP20-01 — preparation capacity checkpoint

สถานะ: **Passed — scoped preparation check only** (2026-11-16).
[Approved scope](../../fixture-preparation-capacity-plan.md) · [Sanitized summary](prep20-summary.json).

## Result

One approved campaign completed in **182.374 seconds**, including the 120-second
preflight, migration, fixture, verification and normal cleanup. Economic preparation
itself took **54.254 seconds**, including wallet/baseline/worker setup. All 400 baseline
orders were prepared. The additional 600 commands were offered, admitted and completed:
240 fills, 120 cancels, 120 replays, 120 cycles; zero rejected commands.

All 20 original financial owner oracles passed, including cash, reservations, held
quantity and cost. Global checks passed: 760 orders, 240 fills, 120 cancels, 400 expected
pending baseline dispatches; zero unlinked fills, invalid reservations/positions,
wrong-mode records or duplicate fill effects. Final input lag was 3 (original bound 20).
The committed public-source journal contains 522 records. No financial rule was changed.

Twenty separate owned worker processes exited normally. The fixed parent and twenty
worker pool reports all passed the original capacity/return/disposal checks. Eleven
resource samples observed peak process RSS 80,805,888 bytes, peak connections 64,
zero lock waits, and database growth 35,430,400 bytes. Last active connection sample 57
is not a post-disposal measurement; the pool receipts and independent cleanup check
provide that proof. This short run does not prove long-term RSS/connection stability.

## Safety and candidate binding

82 affected tests passed on an isolated real PostgreSQL database, including an actual
20-process small fixture, financial/source/replay checks, isolation, partial startup,
cancellation, ambiguous commit, evidence IO and pool negatives. Scoped five-file
Ruff, formatting, mypy and whitespace checks passed. The earlier 72-passed/1-failed
safety attempt remains preserved: accidentally selecting the integrated acceptance
profile correctly triggered RISK_SOURCE_UNAVAILABLE. The correction uses the existing
F15 AllowPaperPolicy only within the guarded fixture worker entry point; the ordinary
worker and integrated TransactionalRiskPolicy remain unchanged.

Source, configuration, schema, copied runner and journal were pinned before execution;
source comparison at finish passed. HEAD alone is not the tested candidate: the retained
working-tree diff and source inventory hashes in the summary bind the uncommitted code.
Raw evidence is retained locally at validation-artifacts/f17-prep20-20261116/; private
configuration/runner material must not be published wholesale.

## Scope limits

This is unthrottled economic-fixture preparation, not authenticated HTTP/admission/risk
acceptance, fixed-five-minute D20, 96,000-input history, full 20-owner rebuild or W3.
The 10 Hz fixture publisher refreshes price on every book tick through the existing
publish_market default; it is not the integrated W3 one-Hz price-refresh schedule.
Consequently this proves fixture capacity only, not equivalent W3 performance.
Do not extrapolate the 54-second total linearly to predict 282-cycle/history duration:
setup is included and query cost can grow with history. The 60-second full-rebuild
criterion and all prior Failed/Incomplete grades remain unchanged.

## Cleanup and next checkpoint

Normal cleanup removed only the owned database. An independent maintenance connection
confirmed database absent, zero connections and zero advisory locks; no owned worker
PIDs remain. Existing PostgreSQL is healthy/restart 0 and Redis running/restart 0.
No new Redis, force drop, other-service stop, owner-account or Live commands occurred.

The single approved campaign scope is complete and ends here. No full-history run,
four-hour run, commit/push, CI or merge was performed. Next: owner-requested code review
of the preparation harness, then any authorized fixes/refactor and a bounded plan for
the representative full rebuild. REBUILD20-01 setup Incomplete and all four earlier W3
Incomplete results remain; F-17 is not Completed and its remaining release dependencies
are unchanged.
