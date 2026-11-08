# MF-13 owner STOP observation — 2026-11-08

Owner reported pressing STOP. Read-only DB evidence: two PAPER/USER STOP requests
at04:04:34.746722Z and04:04:41.006772Z, revisions1and2, distinct idempotency keys.
Each has exactly one APPLIED result and one stop job. Both target sets complete,
target/pending/failed counts0/0/0. Current USER cause is active on revision2.
No duplicate stored key; this alone does not prove one-click/one-intent behavior.
Need owner confirmation whether there were two explicit clicks before accepting
that aspect. No automatic retry or fresh STOP was sent by agent.
MANUAL account means resume_ready false under unchanged F19 predicate; owner UI
confirmation still pending. All four gates remain off. TP/SL replacement Not Run.
Original Failed retained; MF-13 is partial observation, not Passed or Completed.

## Owner confirmations

Owner confirmed two explicit STOP clicks, explaining the two distinct requests;
no duplicate intent is inferred from their count. Each request has one applied
result/job as recorded above. Same-key uncertain retry proof remains scoped to the
retained automated regressions; no such failure was induced in the owner browser.
Owner screenshot confirms Paper stop summary: stopped, pending0, failed0; no
snapshot targets; BTC/USDT held0.00263736. Resume button disabled. This is the
expected MANUAL authorization result under approved option A, not a passing BOT
resume or evidence that holdings were liquidated. The generic reconciliation
message does not by itself establish a reconciliation failure or its completion.
MANUAL STOP/completion and expected unavailable resume are observed; owner TP/SL
UI replacement and cleanup remain pending. Do not mark all MF-13 Passed.
Next: inspect current owner TP/SL panel before any owner-selected repair/order.

## Staged local manual readiness after STOP confirmation

Owner screenshot showed risk unavailable and protection inputs hidden while all
four gates were deliberately off. Enabled publication only; evaluation became
READY, not latched, not replay pending; watermark3631→3665. Checked zero unresolved
order commands and only two historical FAILED protection groups. Enabled financial
then admission/protection under approved local manual procedure, after retained
compatible-writer proof and actual owner STOP completion. All four flags now true
for the owner manual round only. Existing USER stop is not resumed; MANUAL follows
its existing post-cutoff authorization. No FAILED group was rearmed and agent sent
no BUY/SELL/protection mutation. Owner must refresh and inspect TP/SL panel below
the orders list (separate scroll area). New manual action/result still pending;
cleanup will follow the approved procedure, checking unresolved work first.

## Owner TP/SL read-only screenshots

Owner UI shows two existing unprotected groups: allocation0.00131868BTC each,
covered0BTC, step residual0.00000868BTC. First TP76500/SL75000, second TP76000/SL75000.
The red generic failure message is visible; do not interpret this as a new failed
replacement without a new command/result. Historical FAILED groups were explicitly
not auto-rearmed by deployment. Owner replacement/repair has not been requested.
Screenshots also expose low-contrast warning heading/body on a pale alert in dark
mode. Record as a UI validation concern, not a passing visual-accessibility check;
no unrelated shared-style change was made during this observation.
Next safe owner step is opening the existing group's Edit dialog for inspection,
without saving or choosing new financial values on the owner's behalf.

## Owner replacement observation

Owner opened Edit with existing allocation0.00131868BTC, TP76500 and SL75000,
then provided a resulting screenshot showing ARMED/เฝ้าราคา, covered0.00131BTC,
residual0.00000868BTC. DB confirms one group ARMED revision4 with no failure,
allocation/acquired0.00131868, disposed/extra_exit0. Other group remains historical
FAILED. No new Paper order command since staged activation at inspection time.
This supports owner-selected replacement/partial-coverage display; it does not
prove a live-price trigger/exit or fix the observed alert contrast issue.
Cleanup is pending because one protection is now active: do not disable protection
or its worker silently. Owner must choose whether to keep it watching or explicitly
cancel protection through UI before the approved final gate shutdown. No position
sale or cancellation was submitted by agent. MF-13 remains Partial, not Passed.

## Owner cancellation and final cleanup

Owner screenshot shows CANCELED with allocation/covered/residual0. DB confirms one
CANCEL APPLIED revision5 after REPLACE APPLIED revision4, no failure. Canceled
group retains acquired0.00131868 and disposed0; other historical FAILED allocation
remains0.00131868. Exit rows0 and new order commands0 during the manual interval.
No active protection states, pending protection requests or pending order commands
were present. Shut down admission→financial→publication, then protection, with an
in-transaction unresolved-work guard. Readback confirms all four flags false.
No BTC was sold or wallet reset. Existing FAILED history/holdings remain explicit.
Owner manual STOP, expected MANUAL resume refusal, replacement/partial coverage,
and cancellation/cleanup are verified in scope. Visual warning contrast remains
an open validation issue; do not mark MF-13 wholly Passed. No trigger/exit at real
prices was claimed; retained controlled proofs remain separately scoped.
Next: resolve the observed warning contrast within approved UI scope, verify only
affected rendering, then required CI on owner-authorized published candidate.
F17 Release dependencies remain pending; no commit/push/merge occurred.
