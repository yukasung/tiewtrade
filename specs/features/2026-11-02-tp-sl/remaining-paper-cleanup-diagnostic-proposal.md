# F-17 — identify the connection observed at D20 cleanup

สถานะ: **Approved A — เจ้าของสั่งเริ่มทำ วันที่ 2026-11-09; หนึ่ง lifecycle diagnostic ไม่มีคำสั่งเทรด แล้วหยุดรายงาน ไม่รวม D20/W4 rerun**
วันที่:2026-11-09 Asia/Bangkok
ฐานหลักฐาน:[approved A checkpoint](evidence/remaining-paper-20261109/checkpoint.md).

## Problem and bounded objective

D20 workload completed600commands and financial/performance assertions passed,
but aggregate campaign is Incomplete: final cleanup saw1connection. All parent/
worker pool reports passed. After processes exited the connection disappeared;
fixture dropped normally. Original backend PID/role/state was not captured, so
there is no proven attribution or basis to waive cleanup/change its criterion.

**Recommended A:** use one new isolated empty local database, no BUY/SELL/order/
protection requests and no20worker workload. Reuse existing require_empty_database,
manifest-engine disposal, resource-observer/pool shutdown and launcher-cleanup
paths to collect a bounded lifecycle timeline. Record timestamp, backend PID,
role/state/backend_type, connection opened/returned/disposed and process-exit state;
no SQL text, parameters, URLs, session tokens or owner identifiers. Test only
current harness shutdown paths; no production code/config or threshold changes.

Prepare targeted observer/isolation/cancellation tests and scoped static checks
before one diagnostic run. Instrument only test harness; observe via separately
identified read-only admin connection to postgres DB so its backend cannot count
as a connection to the generated target. Keep current pool sizes/timeouts and
cleanup criterion0connections/0locks. Retain one-shot cleanup outcome; a later
sample may explain server shutdown timing but cannot replace that outcome or
make the old D20 Passed. Missing observations are Incomplete, not waived.

Budget after preparation: about5–10min, hard diagnostic observation limit5min;
report preparation estimate before timing if it needs more than15–30min. No
wait-until-pass loop, financial fixture or extra full regression. One diagnostic
only, then stop/report and propose an evidence-based fix if any. A confirmed
production issue or specification gap requires separate approved scope before fix.

Cleanup only this generated diagnostic database after proving no active work;
do not force-stop shared services/backends or touch owner DB/volumes. Preserve all
A artifacts and results. No D20 replacement, W4, B, gate opening, Git publication,
merge/deploy/Live authorization is included. Owner can instead stop here and retain
Incomplete without a new experiment.

Reason to request approval: [approved A](remaining-paper-validation-plan.md) §5
limits each phase to one attempt and stops on failure; AGENTS.md requires honoring
approved stop points. Latest instruction approved that scope, not an additional
lifecycle diagnostic or another D20 campaign.

## Preparation — 2026-11-09

Added no-order diagnostic with separate read-only postgres observer, allowlisted PID/state/event timeline, actual empty guard/intake/resource sampler/owned-pool shutdown paths, fixed post-cleanup observations. Targeted observer-isolation and actual-parent interruption/error/cancellation tests5passed; scoped Ruff/format/mypy Passed. No production changes or criterion relaxation. One diagnostic proceeds after these checks; old Incomplete unchanged.

## Execution complete — 2026-11-09

[One diagnostic](evidence/remaining-paper-20261109/cleanup/analysis.md) finished15.576s with unchanged source,13parent pools Passed, zero connections at immediate cleanup and all fixed post samples/process exit. Original D20 symptom not reproduced; attribution remains unknown. Generated source removed normally. No production fix/criteria waiver or D20/W4 rerun. Scope complete. Next owner decision: [one replacement D20 with identity evidence](remaining-paper-d20-identity-proposal.md); not automatic execution.
