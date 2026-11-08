# F-17 — Unified order / TP-SL activity UI

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-08; อนุมัติ plan/validation และ implementation ตามขอบเขตนี้**
วันที่: 2026-11-08 (Asia/Bangkok)
Parent: requirements.md RQ-03/11/12, manual-acceptance-fix-proposal.md MR-03.
Supersedes only the separate panel/tab layout in protection-table-ui-plan.md after approval.

## Requested result / boundaries

One activity area below the chart. Top tabs Open Orders / Order History; each has
Normal orders / TP-SL subtabs. Remove the separate TP-SL card below the orders.
This is presentation grouping only: protection records are never combined with
actual order records or labeled exchange-native OCO. No Futures Positions tab,
Reduce Only switch, separate synthetic TP/SL orders, new trigger rules or new APIs.
Use an explicit app-monitoring label before an exit exists. Actual linked exit
remains the original order, accessible through protection details without creating
an additional command or double-counting holdings/allocations.

Current TP-SL includes WAITING_ENTRY/ARMING/ARMED/EXITING/FAILED/unknown and conflicts.
History includes only nonconflicted CLOSED/CANCELED. FAILED is not completed
history. Warnings must remain discoverable when the normal-order subtab is active:
show a persistent attention indicator / summary above the tab panels for failed,
conflicted, nonverified or residual protection scope; link to current TP-SL view.
Distinguish unavailable/incomplete queries from confirmed empty data. Do not reduce
coverage warnings or make a tab count look complete before all pages are read.

## Reuse / concrete implementation

- frontend/src/PaperTradePage.tsx owns OPEN/HISTORY and ORDERS/PROTECTIONS view state
  for the existing trade-workspace-orders area; no new generic tab framework.
- Existing PaperOrderList.tsx and ProtectionPanel.tsx accept the controlled view
  rather than creating independent navigation bars. Reuse tables, edit/create/
  cancellation handlers and existing protection details; remove the standalone
  ComponentCard/header in this composition. No duplicate legacy presentation.
- Keep both data/recovery components mounted within the current owner/episode scope
  while hiding the inactive view, so navigation does not discard unknown attempts,
  create a fresh idempotency identity or restart recovery. Retain the existing
  page-visibility/polling rules; no new query/cache/session ownership.
- Close a form/details dialog when navigating away, with valid focus restoration;
  do not clear its durable mutation journal. Reset view-local selections on actual
  owner/episode/base changes without clearing unresolved attempts or receipts.
- Reuse components/ui/{Tabs,Table,Modal,Button,Badge,Alert}.tsx and MarketValue,
  MarketTime, OrderStatus, manualOrderMessages/protectionMessages. Follow
  references/admin-template/src/components/ui/tabs/TabWithUnderline.tsx and
  components/tables/BasicTables/BasicTableOne.tsx. Shared patterns remain the visual
  authority; no Binance asset copying or new style system.
- Put Protect held assets action in the TP-SL toolbar, preserving original disabled
  gates. Retain the bracket inputs in the new-order form. History is read-only.
- Normal orders retain paging, all-pair/episode filtering, order status and cancel
  semantics; TP-SL retains existing base/episode scope, protected/allocated exact
  string amounts, explicit trigger prices, residual and linked-exit facts.
- Scoped updates to CandlestickChartPanel.css only if needed for this same toolbar/
  overflow layout; use existing tokens. Translations Thai/English, semantic tab
  labels/controls, independent tablist keyboard traversal and visible focus.

## Feature validation

1. One common activity area, no duplicate TP-SL card/tab bars. Correct OPEN/HISTORY
   × ORDERS/PROTECTIONS routing and empty/loading/error states; never call an
   incomplete page empty. Retain normal-order pagination and cancellation tests.
2. Protection states partition as above; important attention remains visible from
   normal/history tabs; selecting it opens current TP-SL. No synthetic order IDs,
   no false exchange-sent or position-closed state, no duplicate exit representation.
3. Switching tabs sends no POST, preserves unknown attempt key/request and pending
   recovery. Edit/create/cancel keep exact payloads/revision and all old safety
   gates. Owner/base/episode changes cannot target a stale row or dialog.
4. Current covered/residual/null coverage and linked exit data remain server strings;
   details updates on refresh and remains accurate in both current/history views.
5. Keyboard arrows/Home/End, Tab, Escape and focus return through nested tabs and
   forms/details; no hidden focused dialogs or duplicate DOM ids/labels.
6. Browser isolated fixture on both themes, Thai/English and desktop375/1440 widths:
   contained table overflow, visible warnings, readable headers/actions. No owner
   account orders, new manual campaign or Live execution.
7. Run affected PaperOrderList/ProtectionPanel/PaperTradePage/form/recovery tests,
   scoped lint/types and browser checks. Adapt affected existing E2E navigation.
   Real-DB end-to-end rerun only where a changed mutation/data contract warrants it;
   do not claim a fixture rendering check as actual financial integration proof.
   Retain backend and prior owner STOP/replace/cancel proof in its original scope.

## Execution and stop boundaries

Estimated implementation + targeted validation30–45minutes, no timed trading load.
Keep existing local database and publication/financial/admission/protection gates
unchanged (last verified off). No service reset, new infrastructure, account-type
change, position cleanup or automatic trade. Existing source edits preserved.
No commit/push/PR/merge without owner instruction. After implementation report the
UI checkpoint and await owner review command; this is a scoped F17 UI amendment,
not a new whole-feature Ready for Code Review / Completed announcement.
Stop on contradiction, material scope change or existing repeated-failure rule.
Final review/CI and F17 Batch/Release dependencies remain pending.

Next: owner approves this plan/validation; then implement continuously through
scoped tests and read-only local UI checks. No UI source changed in this proposal.


## Implementation checkpoint

Approved scope implemented; [checkpoint and validation evidence](evidence/manual-acceptance-fix/unified-ui/checkpoint.md).
52distinct scoped component/session/journal cases and8isolated browser scenarios
passed; final lint/types passed. Approval-wait statement above is historical and
superseded by the approved header. Next: owner-commanded UI review.
