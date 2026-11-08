# F-17 — Single navigation row / shared activity table

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-08; plan/validation และ implementation ตามขอบเขตนี้ได้รับอนุมัติแล้ว**
วันที่: 2026-11-08 (Asia/Bangkok)
Supersedes navigation/table composition only in unified-trading-activity-ui-plan.md.
Requirements direction: owner explicitly requested a single row matching the supplied Binance UI.

## Concrete result

- One toolbar: Open Orders | Order History, with Protect held assets aligned right
  in the same flex row on desktop. No Normal orders / TP-SL second tab row or
  separate protection heading/toolbar. Narrow screens scroll the tab group and
  wrap only as required to keep controls readable and accessible.
- One shared table in each view, containing normal orders and protection records.
  Normal orders and protections use explicitly distinct record keys/kind labels.
  Each protection is one monitored-condition row, not two invented exchange orders.
  Show TP/SL trigger prices in a conditions column. Never claim sent/filled before
  the existing actual exit proof. Actual sell orders remain distinct real orders.
- Shared columns: pair, type/side, state, quantity/coverage, price or conditions,
  snapshot/available time and actions. Existing remaining/reserved/filled facts
  remain visible in the row or read-only details, with server strings and shared
  MarketValue/MarketTime. Label snapshot time as snapshot, not creation time.
- Protect held assets retains existing selected-pair/scope/gates and form. Edit/
  cancel and details route by record type and original target identity/revision.
  Do not create synthetic order IDs or send mutations on view changes.
- For consistent table scope, list all returned PAPER records in the current
  wallet/episode (normal orders already do this). Protection edits/details use the
  selected row's base/quote rather than the chart's current base. Global create
  action still uses chart selection. Do not add new pair filtering controls.
- Open view includes unfinished normal orders and current protection records,
  including FAILED/unknown/conflicts. Nonconflicted CLOSED/CANCELED protection
  records are history. Financial meaning and pending/unknown recovery unchanged.
- Coverage/residual/failed/source-unready warnings stay visible compactly. Pending
  requests remain recoverable even when a different tab or symbol is selected.
  Do not show confirmed empty until both sources have loaded completely; retain
  normal-order Load more/paging and protection loading/error indications.

## Reuse / implementation

Reuse PaperTradePage activity state, PaperOrderList query/paging/order actions,
ProtectionPanel journal/forms/details and protections.ts display classifiers.
Extract only the row/detail rendering necessary to compose the shared table; no
new generic data-grid engine, transport, monetary calculation, query/cache/session
store or dependencies. Use components/ui/{Tabs,Table,Button,Modal,Badge,Alert},
MarketValue/MarketTime and current translations. Source template:
references/admin-template/src/components/ui/tabs/TabWithUnderline.tsx and
components/tables/BasicTables/BasicTableOne.tsx. Update only affected frontend,
tests and feature evidence. Keep recovery hooks mounted and scoped to owner,
retain immutable payload/attempt identity across navigation, and close stale
local dialogs on true owner/wallet/episode changes. No backend/API/schema changes.

## Feature validation

1. Exactly one activity tablist/toolbar, no second category tab row or duplicate
   table/card; mixed normal/protection rows and history partition correct.
2. All returned current-episode PAPER rows are represented, including protections
   for a different chart symbol. Edit/details/cancel use that row's correct symbol,
   target, expected revision and scope; global create uses selected chart symbol.
3. Preserve exact normal-order paging, cancellation, reserved/filled/remaining facts
   and protection coverage/residual/exit facts. Incomplete/error data cannot be
   represented as a confirmed empty list or protected quantity.
4. TP/SL visibly identified as monitored conditions until an actual exit exists;
   no fabricated TP/SL orders, duplicated commands or order-completion claims.
5. View changes do not POST, change recovery key/payload, reset unknown outcomes or
   let stale/hidden forms submit. Original mutation gates and history read-only.
6. Targeted component/session/journal tests, scoped lint/types, browser Thai/English
   light/dark desktop/mobile, table overflow, keyboard navigation, modal Escape/
   trap/return focus and warnings. Synthetic browser reads are not financial E2E.
7. Keep prior unchanged backend/owner proof scoped; no new timed trading/manual
   campaign or Live order. Record source identity, results and remaining gates.

## Boundaries

Keep local database and trading gates unchanged. No automatic owner orders,
position changes, account changes, reset or service interruption. Preserve all
existing uncommitted work. No commit/push/merge without explicit owner command.
After scoped implementation/checks, report checkpoint and await owner review.
F17 Release/dependency gates remain pending. Approval of this amendment authorizes
implementation through that checkpoint; no repeated approval for implementation
substeps. No source change for this correction before plan/validation approval.


## Implementation checkpoint

Approved scope implemented; [evidence](evidence/manual-acceptance-fix/single-row-ui/checkpoint.md).
ProtectionPanel renamed to PaperTradingActivity to reflect mixed record ownership;
existing order query/row extracted from PaperOrderList without query contract change.
56distinct scoped tests and8isolated browser scenarios passed, final lint/types
passed. Earlier approval-wait statements are superseded by approved header.
Next owner-commanded final UI review; no new trading campaign or Git publication.
