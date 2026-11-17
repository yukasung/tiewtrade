# OBS-05 one W3-prefix campaign — 2026-11-17

สถานะ: **Incomplete — PoolEvidenceIncomplete; stop/report**

## Refactor and checks

Owner-authorized M1 refactor extracted receipt writing from task/resource cleanup,
without changing behavior. 40 affected tests and Ruff/format/mypy passed. Earlier
170 targeted/real-PG tests remain valid for unchanged transaction/locking behavior.
No production source changes were made in this refactor.

## Campaign result

- Original preflight passed once before fixture creation. Source/config/migrations,
  fault schedule and runner were pinned; source/bindings unchanged at completion.
- Total 2558.486967s (42m38.49s), measurement 2400.002313s. Original W3 target remains
  14400s; planned 28200 commands were not claimed complete.
- Offered 4734, admitted/completed 4733, rejected 0; fills 1893, cancels 946,
  replays 947, completed cycles 946. Offered/admitted gap remains partial/unknown;
  cancellation alone is not rollback proof. No replacement commands were sent.
- First WORKER_RESTART at offset 1800s recovered in 32.989054s. Later faults Not Run.
- Scheduled observations 40/40 RETURNED and task joined/completed. Lifecycle median
  27.351ms/max 182.031ms, max lateness 3.035ms. Before/during/after actual restart:
  30/1/9 samples, respective maxima 182.031/19.646/51.405ms. Full phase metrics and
  cold/reused figures are in the summary; no outliers omitted.
- Natural sampler NO_TRIGGER: zero observations/errors, monitor and loop-lag task
  joined. Loop-lag maximum 237.864ms (aggregate, not per-query attribution).
- Publications: 24053 RETURNED, one CancelledError during planned shutdown. Independent
  witness retained book owner/generation and committed cursor 24053 before cleanup.
  No WriterLeaseLost or clock recovery event recorded.
- Full final-tail/financial invariants/positions/replay/resource acceptance Not Run.
  This diagnostic cannot establish full W3 acceptance or close F-17.

## Remaining blocker

Parent pool contract failed: ENGINE `final_disposal_checked_out=1`, although its final
`checked_out=0`; configuration matches, resource error list empty. All 40 worker pool
receipts passed. `diagnostic_errors=[PoolEvidenceIncomplete]` is preserved.
This is evidence of outstanding borrowing at dispose, not proof of a permanent leak;
no claim is made yet about which task retained it or why. Do not waive the criterion.

Independent post-cleanup audit: database and owned Redis absent, zero DB connections/
locks, all 40 worker PID receipts inactive. Cleanup success does not erase the earlier
pool return violation. No prefix cleanup exception receipt was produced.

## Interpretation / next proposal

The earlier timeout did not recur during this 40-minute prefix including restart;
that does not prove the root cause fixed or four-hour endurance passed. Timings include
fixture, driver and scheduling; session exit is not server-only commit latency.

Recommend next investigating parent ENGINE borrowing during planned cutoff with a
small isolated reproduction and borrow/return/dispose timeline, before another long run.
Retain current result and require zero outstanding borrows before disposal; no criterion
change or automatic retry. This campaign consumed the approved one run. Stop here under
observer-w3-prefix-plan.md: “หลังหนึ่งcampaignหยุดพร้อมหลักฐาน/ข้อเสนอ”.
No further source changes, four-hour test, commit/push/CI/merge in this checkpoint.

Raw receipts: `validation-artifacts/f17-w3-obs05-20261117/`.
See [machine summary](obs05-result-summary.json) and [refactor checks](obs05-m1-refactor.md).
