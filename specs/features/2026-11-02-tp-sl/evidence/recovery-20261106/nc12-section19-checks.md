NC12 §19 completed,2026-11-07. Test-only OwnedPools resource-error provenance
now includes UTC/monotonic timestamps, pid, engine/current-pool identity/generation,
role/capacity/configured-readonly, task id/cancellation count and bounded project
coroutine file/function/line locations. It never captures task names, SQL/binds,
URLs, payloads, locals or exception text. Unknown task/deadline stays unknown. Pool
identity is labelled current-engine-pool or original-registration fallback; after
churn this is not proof of the invalidated connection's original pool. Details are
bounded to16 with omitted count; all errors remain counted. No extra SQL queries.

Real-DB short regressions distinguish an explicit read-only query deadline from an
explicitly cancelled ENGINE query, preserve TimeoutError/CancelledError, show loans
returned and hooks restored, and prove neither secret binds nor task names appear.
Existing disconnect simulation, leaked-borrow, lifecycle/generation/classification
cases still pass. No financial state/session storage or production change.
Final affected suite82passed14.38s; scoped Ruff/format/mypy passed2files. Existing
production safety evidence remains valid; production hashes unchanged from§18.
Evidence: nc12-section19-final-targeted.xml/.log and nc12-section19-final-mypy.log.

Limitation: these controlled regressions do not identify the4historical W2 query
cancellations; the old artifact lacks source identity/time. Active cancellations
still fail under current acceptance; no warning waiver or retrospective Passed.
No workload/campaign was run. §18 V2 W2 remains Failed, W1 remains Passed; overflow/
W3/fullW4 and F17 acceptance remain pending. §19 stop/report checkpoint reached.
