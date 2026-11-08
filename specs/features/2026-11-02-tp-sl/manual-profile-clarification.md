# F-17 — MF-13 account-type clarification

สถานะ: **Approved A — เจ้าของตอบ “อนุมัติ A” วันที่ 2026-11-08; ไม่เปลี่ยนสิทธิ์เทรดหรือผล manual เดิม**
วันที่: 2026-11-08 (Asia/Bangkok)
Scope: correction to the approved manual-acceptance-fix plan §5 / MF-13 only.

## Concrete blocker

**Resolved — owner approved option A on 2026-11-08:** use the
account-compatible validation mapping below. F19 business authorization is already
specified and is not reopened by this proposal.

Post-refactor local readiness confirmed one MANUAL trading preference. Existing
F19 requirements RQ-03 and its approved amendments retain MANUAL opening after user
cutoff and explicitly do not add MANUAL resume. `infra/trading_stops/views.py`
requires account_use == BOT for resume_ready; engine/kill_switch.py independently
requires the same before applying resume. Source and F19 requirements agree.

The F17 manual plan says the owner performs STOP→resume before Paper TP/SL checks,
but that expectation cannot pass on this owner's MANUAL account. Do not bypass the
gate, switch this financially active account to BOT, or reset its positions.
No owner STOP/resume/TP-SL replacement action was sent by the agent.

## A — recommended: map manual validation to the existing account contract

- Keep the owner's MANUAL account and all trading rules unchanged.
- Owner checks Paper STOP and durable receipt/completion through the real UI/API/
  worker. Same-key retry of an uncertain receipt must not add an intent.
- Verify resume is unavailable for this MANUAL account, as required; do not count
  that expected refusal as an implementation failure or claim a manual resume passed.
- Reuse the scoped passing BOT resume proof: fresh-DB immediate stop/completion,
  audit rollback/restart and snapshot-gated resume, plus16STOP component regressions
  including STOP→resume→STOP and stale-storage recovery. Keep fixture scope explicit.
- Owner then chooses any TP/SL repair/order actions through UI under the original
  MANUAL-after-cutoff and risk gates. Existing FAILED groups are never re-armed or
  modified automatically. Agent does not choose prices/quantities or send BUY/SELL.
- Update MF-13 to record MANUAL STOP, expected MANUAL resume refusal, retained BOT
  resume proof, TP/SL results and cleanup separately. One owner manual replacement
  round only; Failed/Incomplete stops without automatic retry. Release gates remain.

This reuses valid proof and changes the manual test mapping, not the product's
authorization rule. Requires owner approval because the original MF-13 wording was
approved; the original manual Failed result remains unchanged.

## B — add a separate BOT browser fixture before returning to owner manual checks

Keep MANUAL account/rules unchanged. Prepare a scoped proposal for a fresh isolated
BOT test-account browser STOP→resume→STOP scenario, with no strategy or Live orders,
then return to MANUAL-compatible owner checks. Define its harness, test budget and
cleanup before execution; this option does not itself authorize a campaign or
changing the owner's account. Requires additional setup beyond option A.

## Current safe state

Refactored candidate is serving local, with API, frontend and all three Paper
workers from the same worktree. Market feeds recovered and risk reached READY;
financial/protection fact digests matched the pre-restart snapshot across8selected
tables/views of data. After finding this profile mismatch, publication/financial/
admission/protection are all off again. Stop authority remains explicitly enabled
in the compatible API so the reduction path is available. No Git publication,
production opening, Live activation or F17 Completed claim.

Next: owner performs one MANUAL STOP round through the UI. Record durable receipt,
completion and expected unavailable resume before any owner-selected TP/SL action.
All four gates remain off until the staged readiness procedure is satisfied.
Option B was not selected. No manual replacement result is claimed by approval.
