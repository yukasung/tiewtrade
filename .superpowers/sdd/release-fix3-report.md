# DEV-138 Release Fix 3 Report

## ขอบเขต

- Fixed point: `f6b1620`
- แก้ chart ที่ตาม Runtime ไม่ทันถาวรเมื่อ completed candle ข้าม `ChartRange.end`
- แทน `CompletedCandleFacts` Protocol ที่มี contract ไม่ครบด้วย concrete
  `ChartCandle = Candle` ที่ application boundary
- ใช้ Paper/public market data และ fake adapters เท่านั้น ไม่มี Live/private endpoint
  หรือ credentials

## Root Cause

1. `ChartWorkflow` ยอมให้ refresh เฉพาะ candle ที่อยู่ใน visible range หรือเปิดตรง
   `ChartRange.end` ขณะที่ pending state เก็บเฉพาะ completed candle ล่าสุด เมื่อ Runtime
   ข้าม candle อย่างน้อยหนึ่งแท่ง event ล่าสุดจึงถูกทิ้ง และ event ถัดไปไม่สามารถทำให้
   chart ตามทันได้อีก
2. `CompletedCandleFacts` ตรวจเพียง `symbol`, `timeframe`, `open_time` และ
   `close_time` แต่ `ChartHistory` cast เป็น `Candle` และ painter ใช้ OHLCV ต่อ จึงมี
   structurally valid object ที่ไม่มี OHLCV หลุดผ่าน runtime check ได้

## TDD Evidence

### RED

- `test_refresh_after_candle_gap_reloads_latest_bounded_range_and_durable_fills`
  ล้มเพราะไม่มี historical request สำหรับ latest bounded range (`1 failed`)
- `test_completed_candle_gap_advances_and_keeps_following_runtime_updates`
  ล้มเพราะ candle `00:25` และ `00:30` ถูกทิ้งทั้งคู่ (`refreshed_minutes == []`)
- partial-candle regressions ล้มทั้ง workflow และ `ChartSnapshot` boundary (`2 failed`)
  เพราะ object ที่ไม่มี OHLCV ผ่าน Protocol/runtime validation
- full suite รอบแรกเปิดเผย static architecture gate ว่า `ui` ห้าม import
  `market_data` โดยตรง และ acceptance test รอเพียง LOADING state ทำให้ worker callback
  ชน widget ที่ถูกลบ (`2 failed, 998 passed`)

### GREEN

- Gap ที่ range จบ `00:20` และ Runtime ส่ง candle เปิด `00:25` จะเลื่อน window
  ขนาดเดิมไปจบ `00:30`, reload history, merge runtime candle ล่าสุด และ query durable
  fills ใน range ใหม่
- Candle เปิด `00:30` ถัดมาจะเลื่อนต่อไปจบ `00:35` จึงไม่เกิด permanent lag
- `ChartCandle` เป็น concrete runtime alias ของ `Candle`; `ChartWorkflow` ใช้
  `isinstance` กับ concrete class และ `ChartSnapshot` ปฏิเสธค่าที่ไม่ใช่ `Candle`
- `ui` รับ concrete type ผ่าน application-owned alias จึงไม่ละเมิด dependency rule
- acceptance test รอ terminal `EMPTY` state ก่อน teardown เพื่อไม่ทิ้ง worker ค้าง

## Code Review

- Standards axis พบ possible duplicated range-shift logic ระดับ Low; รวมเป็น branch
  เดียวแล้ว
- Spec axis ไม่พบ missing requirement, scope creep หรือ implementation ที่ผิด

## Final Verification

```text
Focused chart/static acceptance: 36 passed in 0.31s
Full pytest:                      1000 passed in 7.07s
Ruff check:                       All checks passed
Ruff format --check:              175 files already formatted
mypy:                             Success: no issues found in 175 source files
git diff --check:                 passed (no output)
```

## Remaining Concerns

- หาก bounded public history reload ล้มเหลว workflow ยังคงเปลี่ยนเฉพาะ chart เป็น
  `UNAVAILABLE` ตาม design เดิม และผู้ใช้ retry ได้; Bot Control และ table state ไม่ถูก
  เปลี่ยน
- Pending state ยังคงเก็บ event ล่าสุดเพียงหนึ่งรายการ แต่ gap path จะ reload ช่วงที่ขาด
  และ merge latest runtime candle จึงไม่ทำให้ chart ค้างถาวร
- ไม่ได้รัน docs-site checks เพราะไม่มีการแก้ docs-site หรือ content source
