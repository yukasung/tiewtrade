# Unified trading activity UI checkpoint

Date:2026-11-08 Asia/Bangkok. Owner approved unified-trading-activity-ui-plan.md.
Base remains e6b32bb with existing uncommitted F17 work preserved; see source hashes.

## Implemented

PaperTradePage owns OPEN/HISTORY and ORDERS/PROTECTIONS navigation within one
existing activity area. Removed standalone TP-SL card and its independent tabs.
Normal order query/table/paging and protection recovery/form/table/details reused.
Both recovery/data components stay mounted across activity navigation; hidden view
has no actionable visible controls. New owner/base/wallet/episode scope resets
view-local selection, while the durable owner request journal stays intact.
Protection dialogs close on view/active/scope change; details derives latest rows.
Persistent attention summary links to current protections from any activity tab.
FAILED/unknown/conflicted records remain current; only nonconflicted CLOSED/
CANCELED are history. Unknown recovery/error notices remain visible when hidden.
Display classifiers shared in protections.ts; no financial arithmetic added.
Condition label distinguishes app-monitored records from actual linked sell orders.
No fake TP/SL leg/order IDs, exchange-native OCO or Futures features were added.
Scoped CSS disables overlapping legacy sticky toolbars inside unified activity.
Backend/API/contracts, authorization, payloads/revisions and polling remain unchanged.

## Targeted proof

52 distinct component/session/journal cases passed across affected checks:
PaperTradePage30, ProtectionPanel11, PaperOrderList1, ManualOrderForm5,
ManualOrderSession2, protectionJournal3. Tests retained from prior valid results
where untouched; after the latest label/layout change the affected page30 and
journal/session5 passed. Typecheck and scoped ESLint passed on final sources.

New integration proof: one common two-level navigation; FAILED warning visible
from normal/history; current/history routing; independent tablist keyboard focus;
no POST on navigation. Real useProtectionAttempt/journal with lost receipt persists
same key/payload through tabs and retries with original identity. No owner account
was used. Existing edit/cancel exact payload/revision, paging/incomplete results,
details refresh/missing/scope and disabled gates remain covered.

Browser8 scenarios:2locales×2themes×2widths(1440/375), real PaperTradePage and query/
recovery components, synthetic intercepted GET data; chart module excluded. No
mutation requests and no page errors. Navigation, persistent warning, current/
history, contained overflow, Modal focus trap/Escape/return and separate keyboard
navigation passed. Screenshots/results and fixture/runner copies retained. This
is rendering/recovery-navigation proof, not financial real-DB E2E or owner account
acceptance. Desktop/mobile dark captures inspected. Fixtures were removed from
served frontend after validation.

Initial test discrepancies retained: first activity tab-count assertion counted
manual form tablists as well; corrected its scope to the activity container.
First browser run matched both English Filled header/status; corrected selector to
the status cell, preserving expected history state. Temporary typing errors in
new test queries were corrected; final types/lint passed. No criteria reduced.
Affected existing real-DB protection E2E selectors were adapted, not rerun because
no mutation/data contract changed; prior financial proof is retained in scope.

## Local/runtime and remaining gates

Current owner local API proxy health200. Read-only fresh DB confirms all four
gates false and CANCELED2. Latest cancellation was recorded06:54:55Z, before this
UI task's source work; do not claim that prior FAILED group remains active or
attribute its cancellation to this code. No agent order, protection mutation,
STOP, reset or gate-opening occurred. New source is served by existing local Vite.
No owner session forged; browser financial requests were intercepted fixtures.

UI amendment implementation/checks complete. Await owner-commanded final UI review;
no automatic review/refactor/Git action. Required CI needs authorized publication.
F17 Batch/Release/dependency gates remain pending and F17 is not Completed.
