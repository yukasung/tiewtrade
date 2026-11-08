# Single-row activity UI checkpoint

Date:2026-11-08 Asia/Bangkok. Owner approved single-row-activity-ui-amendment.md.
Base e6b32bb, prior uncommitted work preserved; final file identities in manifest.

## Implemented presentation

One OPEN/HISTORY tablist and one shared table, with Protect held assets aligned
right in that same desktop toolbar. No category subtabs or separate TP/SL card.
ProtectionPanel was reused/renamed PaperTradingActivity because it now coordinates
both record types. Existing PaperOrderList query extracted as usePaperOrders with
unchanged owner/episode key, paging and cadence; its row renderer shares the table.
No new grid engine, dependencies, backend/API/schema or financial calculation.

Real order rows retain kind/side, status, quantity/budget, filled/remaining/reserved,
limit/market or unavailable price and snapshot time. Protection rows are explicitly
monitored conditions, not invented exchange orders: one row per protection with
allocation/coverage, residual/null coverage, TP/SL prices, source/failure/conflict
warnings and linked exit state/details. Keys are namespaced even if IDs collide.
Current view includes FAILED/unknown/conflicts; completed/canceled history read-only.
Confirmed empty requires both sources complete; order paging/Load more retained.

All current-wallet/episode PAPER protection symbols are shown, consistent with
normal order scope. Edit/details use the selected row; create captures chart base.
Draft carries its opening scope and base and cannot submit into a changed scope.
Chart changes do not relabel an existing ETH draft as BTC. Actual owner/wallet/
episode/view changes close local dialogs without clearing durable recovery.
Recovery remains mounted and pending/unknown notices remain visible. No new-key
retry from navigation. Removed obsolete second-toolbar styling and tab labels.

## Feature proof and limitations

56distinct targeted component/session/journal cases passed across affected checks:
PaperTradingActivity14, PaperOrderList2, PaperTradePage30, ManualOrderForm5,
ManualOrderSession2, protectionJournal3. After last normal-price null guard, affected
PaperOrderList2 passed again. Final typecheck and scoped ESLint passed.
New proof includes mixed normal/protection rows with colliding IDs; exact normal
cancel callback, different-symbol edit target/revision/string payload, create base
from chart, wallet/episode/mode exclusion, incomplete/error empty-state prevention.
Prior retained cases cover old-key unknown retry after tab changes, form/disabled
states, paging, refresh/missing details, history and scope closure.

Isolated browser8scenarios: Thai/English × light/dark × desktop1440/mobile375.
Real PaperTradePage/query/recovery/table/form modules with synthetic GET data and
chart module stub. One tablist, one toolbar and one table asserted. Desktop tabs/
create button vertical centers within2px. Mixed normal and ETH protection visible
while chart selects BTC; edit ETH and create BTC labels/focus checked without save.
Current/history routing, history no edit and disabled create, Modal Tab/Escape/
return focus, Home/End, contained document overflow passed.0mutation requests and
0page errors. Screenshot/result/fixture/runner retained; dark desktop/mobile views
visually inspected. Inactive tab border is transparent, confirmed separately after
an ambiguous screenshot; no shared tab change needed. Fixtures removed after proof.

Earlier intermediate typing errors after component rename were fixed by adapting
callers/tests; final lint/types passed. Deliberate invalid LIVE response fixture
uses a documented test-only cast because the generated API type permits PAPER
only. No product criteria lowered. Existing real-DB protection E2E selectors now
use shared activity root/history navigation; those financial browser cases were
not rerun for presentation/query extraction, so no new real-DB/owner economic proof
is claimed. Unchanged backend/owner financial proofs retain their original scope.

## Local / next gate

Existing local Vite/API serves this candidate. Fresh read-only DB state: all four
gates false, CANCELED2; no account/order/STOP mutation submitted by agent. No process
reset or source/config changes to backend workers. Local review URL:
http://127.0.0.1:5173/paper/trade . No owner session forged.

Implementation/checks complete within this UI amendment. Next owner-commanded
final UI code review; no automatic review/refactor/commit/push/merge. Required CI
needs authorized publication. F17 Batch/Release/dependencies remain pending; not
Completed or merge-ready from this checkpoint.
