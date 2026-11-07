NC12 §21 V3 short W3 — Incomplete after observer resource alarms,2026-11-07.
Stopped the owned campaign after connection churn exposed invalid retired-pool
observations, saving the remaining planned runtime. Total596.076s includes preflight/
fixture/cleanup;30min measurement was not completed.755HTTP records and160snapshot
records retained; no full financial/oracle/fault/endurance acceptance is claimed.
Only initial restart and connection-churn faults had begun; remaining faults/W4 not run.

Parent observer recorded9PoolCapacityViolation and4PoolDisappearedBeforeReturn.
Raw snapshots show disposed ENGINE pool native checkedout=-1/-4 while independent
checkout/checkin event counts changed3→1→0. Installed SQLAlchemy QueuePool.dispose
sets _overflow=-size, and checkedout computes size-checkedin+overflow; late returns
can therefore make the retired pool's native counter negative. This is not an
actual negative/over-capacity connection count. Retired MARKET_DATA pool weakref
was collected while event count1 was still pending; its event count later reached0
before final shutdown. All registered loans returned in final parent proof; cleanup
0connections/0advisory locks and candidate/runner unchanged. Retain raw Incomplete/
CancelledError and original resource flags, not retrospective Passed.

The existing real-DB generation test disposed only after its borrow was returned;
it missed held loans across churn. This evidence identifies an observer accounting
defect, not a justification to waive lost-borrow/capacity safety or claim30min passed.
Evidence:retired-pool-observations.json, parent pool streams/summary, campaign log.

Next: proposed§22 fixes only retired-generation measurement semantics, adds real-DB
held-loan/GC regressions, then one replacement V3 W3 if approved and checks pass.
No source fix/new run after the failed gate. W1§16/W2§20/overflow§20 remain Passed;
4h Release remains Pending Full Validation and F17 remains open.
