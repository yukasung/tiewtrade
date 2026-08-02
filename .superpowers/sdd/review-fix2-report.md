# DEV-138 Review Fix 2 Report

## ขอบเขต

- Branch: `dev-138-dark-candlestick-chart`
- Starting HEAD: `66a7806`
- Implementation commit: `c27e87c`
- ใช้ root virtual environment: `/Users/chainarong.j/Projects/TiewTrade/Projects/tiewtrade/.venv`
- Worktree package ถูกเลือกด้วย `PYTHONPATH=src`; Qt tests ใช้ `QT_QPA_PLATFORM=offscreen`

## สิ่งที่แก้

1. `ChartWorkflow._refresh_finished` drain `_pending_request` ก่อน pending completed candle และเริ่มเฉพาะ request รุ่นล่าสุด จึงไม่ค้าง `LOADING` เมื่อผู้ใช้เปลี่ยน visible range ระหว่าง runtime completed-candle refresh
2. `_refresh_succeeded` บันทึก `result.chart_range` เป็น retry range ล่าสุด ทำให้ retry หลัง runtime shift ใช้ช่วงที่ผู้ใช้กำลังเห็นจริง
3. `application.chart_history` ไม่ import `SQLiteTradeHistory` หรือ integration ใดแล้ว โดยรับ focused callables สำหรับโหลด candles และ list Session fills; composition root เป็นเจ้าของ concrete Binance source lifecycle และ SQLite binding
4. `application.chart_data` เป็น owner เดียวของ `latest_completed_boundary` และ default 120-candle visible range
5. `ChartWorkflow.start(session)` เป็นเจ้าของ initial range behavior; `MainWindow` เหลือเพียงสั่ง start และ chart widget reuse completed-boundary calculation เดียวกัน

## TDD Evidence

### Pending load ระหว่าง refresh

RED:

```text
test_load_queued_during_refresh_is_drained_and_latest_request_wins
IndexError: list index out of range
1 failed
```

สาเหตุที่พิสูจน์ได้: หลัง refresh task จบ ไม่มี load task ของ `_pending_request` ถูกสร้าง

GREEN:

```text
1 passed in 0.01s
```

Focused workflow หลังแก้ slice นี้: `9 passed in 0.02s`

### Retry runtime-refreshed range

RED:

```text
test_retry_uses_latest_runtime_refreshed_visible_range
At index 1: initial ChartRange != refreshed ChartRange
1 failed
```

GREEN:

```text
1 passed in 0.01s
```

### Callable dependency seam

RED:

```text
3 failed
TypeError: ChartHistory.__init__() got an unexpected keyword argument 'load_candles'
```

GREEN:

```text
tests/unit/application/test_chart_history.py
3 passed in 0.01s

tests/unit/application/test_chart_history.py tests/unit/test_desktop_main.py
17 passed in 0.68s
```

Composition regression ยืนยันว่า Spot/Futures สร้างและปิด concrete public source ทุก request และ `application/chart_history.py` ไม่มี `tiewtrade.integrations` dependency

### Application-owned range policy

RED:

```text
ImportError: cannot import name 'default_chart_range'
AttributeError: 'ChartWorkflow' object has no attribute 'start'
```

GREEN:

```text
tests/unit/application/test_chart_data.py
10 passed in 0.01s

test_start_loads_application_owned_default_visible_range
1 passed in 0.01s
```

## Final Verification

```text
Focused chart/application/UI/composition:
89 passed in 2.14s

Acceptance chart:
2 passed in 0.15s

Full suite:
996 passed in 7.20s

Ruff check:
All checks passed!

Ruff format check:
175 files already formatted

mypy:
Success: no issues found in 175 source files

git diff --check:
passed (no output)
```

## ความเสี่ยงคงเหลือ

- ไม่พบ known functional concern จากขอบเขต re-review นี้
- Qt verification เป็น offscreen deterministic test path; ไม่ได้เพิ่ม manual GUI interaction เพราะการแก้ไม่มี visual/layout change
- ไม่มี Live/private Binance request, credentials หรือ trading execution side effect เพิ่มขึ้น
