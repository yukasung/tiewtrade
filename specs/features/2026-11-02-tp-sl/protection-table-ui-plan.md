# F-17 — Compact protection table UI amendment

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-08; plan/validation และ implementation ตามขอบเขตนี้ได้รับอนุมัติแล้ว**
วันที่: 2026-11-08 (Asia/Bangkok)
Parent: requirements.md RQ-03/11/12, manual-acceptance-fix-proposal.md MR-03.

## Scope and acceptance intent

Adopt Binance Spot's compact open/history presentation, using this project's
admin template. Keep TiewTrade Paper protection semantics: these are app-monitored
TP/SL, not exchange-native OCO. No changes to trigger, MARKET exit, quantity,
allocation, retries, authorization, API/database, pagination or source readiness.
Do not merge protection rows with actual orders or imply an exit already exists.

## Reuse and implementation plan

- Reuse frontend/src/components/ui/{Table,Tabs,Modal,Badge,Button,Alert}.tsx,
  MarketValue/MarketTime, OrderStatus and protectionText translations.
- Follow frontend/src/PaperOrderList.tsx for table/tab layout and accessibility;
  source template references/admin-template/src/components/tables/BasicTables/
  BasicTableOne.tsx and references/admin-template/src/pages/UiElements/Tabs.tsx.
  Confirm the matching table source before implementation; no new styling system.
- Change frontend/src/ProtectionPanel.tsx and protectionMessages.ts only as needed;
  adapt existing affected tests/browser selectors. Reuse current create/edit form,
  useProtectionAttempt journal, expected revisions, pending/unknown/error handling.
- Two tabs: current protections/issues (default) and protection history.
  Only CLOSED/CANCELED go to history. FAILED, conflicted and unknown states stay
  visible in current/issues; never hide unprotected quantity as completed history.
- Each row: pair, snapshot time (not creation time), state, allocated quantity,
  covered quantity, TP, SL and actions. Use shared table spacing, horizontal overflow
  on narrow screens and the existing focus/keyboard patterns.
- Residual/nonverified coverage and failure/unready indications remain visible
  compactly in their row; do not bury all risk information behind Details.
- Details opens the shared Modal with existing step residual warning, full failure/
  conflict/readiness message and linked exit identity/state/filled quantity. Resolve
  the selected row from current query data by id; do not preserve stale financial
  row snapshots as business truth. Close safely if selected row disappears/scope
  changes; edit/submit retains original concurrency/idempotency guards.
- Keep create action in the panel header. Edit/cancel available only under existing
  gates; no actionable edit/cancel controls for CLOSED/CANCELED history rows.
- Distinct empty current/history messages; explicit unavailable/loading/errors.
  History still readable when trading gates are off. No CSS per-page overrides.
- Thai/English via protectionText, no JS financial calculation or raw precision loss.

## Targeted validation — Feature

1. Existing owner/episode/base filtering, allocation/coverage/residual truth and
   pending/unknown/rejected recovery behavior retained.
2. Current/history partition: ARMED/WAITING_ENTRY/ARMING/EXITING/FAILED/unknown,
   conflict visible; CLOSED/CANCELED history only, correct empty states.
3. Details shows residual/null coverage/exit state accurately, updates on refreshed
   data, closes on missing row/scope; focus entry/trap/Escape/return via existing
   Modal. Hidden history cannot leave mutation controls acting on the wrong row.
4. Create/edit/cancel keep exact string payload, expected_revision, attempt identity
   and disabled-state rules; no mutation merely from tab/details navigation.
5. Browser isolated fixture light/dark + desktop/narrow: readable table/header,
   horizontal scroll contained, warnings visible, keyboard and details modal.
   Do not induce faults or submit orders on owner's real local account.
6. Run affected component/browser cases and scoped lint/typecheck. Retain previous
   unchanged backend financial/concurrency proof, owner STOP/replace/cancel proof.
   This UI change does require new affected rendering proof; do not reuse old
   screenshot acceptance. No long workload/full regression required by layout alone.

## Budget, gates and final state

Expected implementation/targeted validation about20–40minutes, no timed trading
campaign, no Live execution. Owner manual gates remain off; no owner data reset.
Stop on spec conflict or repeated-failure rule. Record initial failures honestly.
After implementation report checkpoint; owner-requested review/refactor/Git gates
remain. No commit/push/merge or F17 Completed claim from this plan approval.

Next: owner approval of this concrete plan/validation, then implement continuously
through targeted checks and report the UI checkpoint. No UI source changed for
this new layout proposal yet.

Implementation note: isolated rendering exposed selected shared Tabs using native
button background. Restore bg-transparent on all shared tab buttons per the
existing TabWithUnderline template; retain focus/selection semantics. Residual
row uses short translated warnings; full wording stays in Details. Pair/status
and quantities precede the verbose snapshot column to prioritize small screens.


## Implementation checkpoint

UI source and scoped checks complete; see
[evidence](evidence/manual-acceptance-fix/table-ui/checkpoint.md).
Historical approval-wait text above is superseded by the owner approval in the
header. Next final UI review requires owner command; current local runtime is
stopped/Docker unavailable, not a claimed owner-browser deployment.
