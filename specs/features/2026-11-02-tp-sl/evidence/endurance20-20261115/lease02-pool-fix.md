# LEASE-02 review and aggregate-pool correction

สถานะ: **Fixed — affected tests Passed; await owner refactor instruction**

Owner instructed “เริ่มทำ” after the next step to review the observer and correct
aggregate inventory validation. Review confirmed the documented hardcoded inventory
mismatch: a properly declared and disposed diagnostic witness pool was rejected by
the independent aggregate validator. No production/trading/lease-policy correction
was inferred from the short workload; its historical lease cause remains unproven.

Before source changes, [the amendment](../../publisher-lease-load-diagnostic-plan.md#owner-started-review-and-aggregate-pool-correction)
recorded the correction and bounds. `parent_configuration` now selects an exact
trusted inventory from an explicit boolean flag, defaultFalse. Tracker and aggregate
validator both use it, and workload.run passes the same validated opt-in option to
both. No permission is inferred from report-supplied expected_configuration. The
original13parent pools and all worker pools remain mandatory. Only one exact
MARKET_DATA(size1,overflow0) witness pool is accepted in opt-in mode; other inventory,
capacity, return/disposal/error/sample rules unchanged. No existing result regraded.

Validation: **68Passed/12.72s**, no skips, comprising the affected pool suite and
18lease-load observer regressions.14new cases cover normal/default acceptance,
opt-in acceptance, unexpected/missing/duplicate/wrong-capacity witness, missing
original pool, outstanding borrow, missing disposal, extra worker pool, untrusted
self-declared inventory, and actual workload.run tracker/aggregate wiring with both
flag values. Caller tests use real owned-pool lifecycle reports with a stubbed
workload, not a timed campaign or financial acceptance substitute. Existing real-PG
observer tests retain original-once, rollback/independent witness, cancellation and
ambiguous commit proof. Scoped Ruff/format/mypy on3changed files and whitespace
Passed. Isolated parent test DB removed normally.

[Source bridge and receipt](lease02-pool-fix-summary.json): only owned-pool helper/
validator, workload caller and pool tests changed relative to the diagnostic
candidate. Observer/production/workload publication functions/migrations/config and
other pinned files unchanged. The original LEASE-02 campaign remains **Incomplete**
on its original candidate, and no new workload/diagnostic/4h/Git/CI action occurred.
F17 remains notCompleted with earlier4hIncomplete/finalfinancial/rebuild/Release/
opening/bot/notification/Live dependencies unchanged.

Next: await owner's `refactor the code` instruction per AGENTS review-fix gate.
A replacement timed diagnostic is not authorized by this correction.
