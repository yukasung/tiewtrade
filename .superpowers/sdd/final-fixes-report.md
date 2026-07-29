# รายงาน final fix wave ของ DEV-96

## สถานะและ commit

- Implementation commit: `bd4a1cb fix: preserve Trade History page results`
- ไม่มีการ push, merge, ลบ branch/worktree หรือเชื่อม Live execution

## Root cause

`TradeHistoryWorkflow` เดิมตีความ `BasketHistoryPage.items == ()` ทุกกรณีเป็น
parameterless `baskets_empty()` จึงทิ้ง page object แม้ query สำเร็จและยังมี
`total_items`/aggregate อยู่ เมื่อ result set หดจนหน้าที่ขอเกินหน้าสุด Workflow
จึงไม่แก้หน้า ส่วน `TradeHistoryPage.show_baskets_empty()` สร้าง Net PnL `0`, total
`0` และ Page 1 เอง ทำให้ UI ไม่รักษา application query result

## การแก้ไข

- ให้ Workflow คำนวณ known last page จาก successful result และ requery หน้าสุดผ่าน
  `_request_baskets()` เดิม จึงรักษา generation, pending/latest request,
  reentrancy, Fill invalidation และ loading contracts
- เปลี่ยน semantic signal เป็น `baskets_empty(BasketHistoryPage)` เพื่อส่ง exact
  successful result โดยยังแยก empty ออกจาก ready/unavailable
- ให้ Page ใช้ rendering path เดียวกับ `show_baskets()` จึงไม่คำนวณ summary,
  total หรือ pagination ซ้ำ และไม่เกิด duplicate semantic rendering
- อัปเดต design/plan ให้ตรงกับ signal contract และ shrink recovery
- ปรับ Fill-loading test ให้แสดง Page จริงและตรวจ `fill_state.isVisible()`

## หลักฐาน RED → GREEN

RED command:

```text
env PYTHONPATH=src QT_QPA_PLATFORM=offscreen ../../.venv/bin/python -m pytest \
  tests/unit/ui/test_trade_history_workflow.py::test_empty_basket_page_does_not_query_fills \
  tests/unit/ui/test_trade_history_workflow.py::test_page_beyond_shrunken_results_requeries_last_valid_page \
  tests/unit/ui/test_trade_history_page.py::test_empty_basket_result_is_explicit_break_even_state \
  tests/unit/ui/test_trade_history_page.py::test_fill_loading_clears_stale_fills_and_preserves_basket_selection \
  tests/unit/ui/test_main_window.py::test_empty_trade_history_preserves_exact_query_summary_and_page_state -q
```

ผล RED: `4 failed, 1 passed, 2 errors` โดยล้มตรงสาเหตุที่ต้องการ: signal ไม่มี
page payload, Workflow ไม่ requery last page, Page slot ไม่รับ result และ MainWindow
แสดง `0.00 USDT · Break-even` ที่สร้างเอง

GREEN หลัง minimal implementation: regression 5 รายการ `5 passed in 0.26s`

## ไฟล์ที่เปลี่ยน

- `src/tiewtrade/ui/trade_history_workflow.py`
- `src/tiewtrade/ui/trade_history_page.py`
- `tests/unit/ui/test_trade_history_workflow.py`
- `tests/unit/ui/test_trade_history_page.py`
- `tests/unit/ui/test_main_window.py`
- `docs/superpowers/specs/2026-07-29-dev-96-trade-history-ui-design.md`
- `docs/superpowers/plans/2026-07-29-dev-96-trade-history-ui.md`

## Tests และ gates

- Focused Workflow/Page/MainWindow/SQLite query baseline: `82 passed`
- Focused หลังแก้รวม Desktop acceptance: `88 passed in 1.85s`
- Full Python suite: `684 passed in 4.37s`
- Ruff check: ผ่าน
- Ruff format check: `132 files already formatted`
- Mypy strict: `69 source files`, ไม่มี issue
- docs-site tests: `50 passed`
- docs content check: ผ่าน
- `git diff --check`: ผ่านก่อน commit

## Self-review

- Spec: ครบ last-page requery, exact empty page payload, aggregate/total/page state,
  stale-page regression, Page/MainWindow integration และ Fill-loading visibility
- Standards: ไม่เพิ่ม generic framework, persistence/UI dependency หรือ business
  calculation ใน UI; ใช้ callable/request pipeline และศัพท์เดิมของระบบ
- Concurrency: หน้าที่ out-of-range ไม่ emit transient empty/ready; loading คงเป็นช่วง
  เดียว และ request ใหม่กว่ายัง supersede pending correction ตาม generation guard
- Scope: ไม่แตะ late failed/finished close path ตาม reviewer note

## ข้อกังวลที่เหลือ

ไม่มี blocker ที่ทราบ หาก result set หดต่อเนื่องระหว่าง correction Workflow อาจ query
หน้าสุดซ้ำมากกว่าหนึ่งครั้ง แต่แต่ละรอบเลือกหน้าสุดจาก successful result ล่าสุดและ
ยังถูก supersede ได้ด้วย request ใหม่ จึงเป็นพฤติกรรม deterministic ตาม contract
