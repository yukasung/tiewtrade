# F-12 history recovery checkpoint

วันที่: 2026-10-13 (Asia/Bangkok)
เจ้าของ approve recovery-plan-amendment; NC-42 closed. Preview ordering change
รอ NC-43 แยกต่างหาก ไม่ถือว่าการอนุมัติ history อนุญาตเปลี่ยน dominance.

## Implemented

- CandleSource ประกาศ optional max_request_span; Binance TH กำหนดเจ็ดวัน,
  FakeVenue ไม่มี span cap โดย default. Adapter ปฏิเสธ oversized request ก่อน HTTP.
- Ingestion จำกัด actual fetch unit ให้ไม่เกิน source span และ 1,000 slots ก่อน
  reserve/HTTP; forward/repair/refresh ใช้ขอบเขตเดียวกัน. Reclaimed old oversized
  unit ลดช่วงที่ fetch ภายใต้ fenced claim เดิมโดยรักษา unit ID/attemptcount/token;
  tail ยังอยู่ใน desired window และ cursor ไม่ข้าม tail.
- คง rate-limit, request timeout และ **สี่ HTTP attempts ต่อ round** ของโค้ดเดิม.
  ข้อเสนอครั้งแรกเขียน 20-attempt ผิดจาก implementation; แก้เอกสารเป็นสี่แล้ว
  โดยไม่ได้เพิ่มงบจริง. ไม่แก้ jobs/backoff/DB candles ด้วยมือหรือส่ง Live orders.
- เพิ่ม sanitized conflict log เฉพาะ public series และ trade-count/IDs เพื่อระบุ
  preview failure; ไม่ log prices/raw payloads/secrets และไม่เปลี่ยน ordering.

## Tests / evidence

| Check | Evidence | Result |
|---|---|---|
| Adapter / ingestion / fake protocol / main | [history-span-tests.xml](history-span-tests.xml) | 65 passed, 4 failed จาก fixtures ใหม่ไม่ reset test DB ระหว่าง cases |
| Span splitting หลังใช้ isolation helper เดิม | [history-span-fixed.xml](history-span-fixed.xml) | 4 passed |
| Expand span tests: full/gap/empty ทั้ง 15m/1h/4h/1d | [history-span-repair.xml](history-span-repair.xml) | 12 passed; bounded units, complete coverage หลัง repair |
| Old oversized unit: fenced claim/attempt budget/tail | [history-unit-reclaim.xml](history-unit-reclaim.xml) | 1 passed |
| Preview writer / realtime supervisor / chart routes | [history-preview-integration.xml](history-preview-integration.xml) | 25 passed; 1 upstream testclient deprecation warning |
| Static | affected Ruff/format; configured mypy (370 files); import-linter | Passed. Initial test import typing issue fixed; Windows import-linter output encoding fixed with PYTHONUTF8 then 7 contracts kept. A file-only mypy invocation failed package resolution; configured invocation on final inputs passed |
| Development deployment | build/recreate **market-data only**, chart dev override | Exit 0; image `sha256:1f681fe2d86c044a48e395fc88e39c5dc269b0493b732c9af95a66915e3392c2` |
| Read-only actual DB observation | SELECT grouped market_candles + demand/feed state | New rows appeared for 15m/1h/4h/1d; examples BTC 1h 168, BTC 4h 42, DOGE 15m 672, DOGE 1d 7. Counts are a point-in-time observation, not full coverage |
| Local real browser → API → development PG | Chromium 1440×1000, separate normal smoke account | History HTTP 200, **444 actual candles / 1,000 indicator rows**, no pageerror; [screenshot](history-recovery-browser.png). Smoke account remains in dev DB; no orders/mode changes |

Failed artifacts are retained. Successful results come from scoped commands,
not a new full-suite run or single all-green regression of all final inputs.

## Preview root cause and remaining

Actual supervisor log captured:
`candle progression conflict: DOGE/USDT 1m old=(0, -1, -1) new=(1, 1625345571, 1625345571)`.
Core requires matching first trade IDs, so empty→first trade is treated as conflict.
See [preview-first-trade amendment](../preview-first-trade-amendment.md) for proposed
strict empty-baseline handling and tests. No change to dominance/READY yet.

History is **recovering / partially loaded**, not complete for every series/range.
The unchanged four-request/30-second rounds fill long backfills incrementally;
source failures recorded before deployment remain subject to normal retry/demand
policy. Browser counts prove OHLC is now delivered; do not prove latest viewport
or all 1,000 slots complete. Preview can still become STALE on first-trade conflict.

Owner approval of NC-43 is needed before that ordering change. V-17 remains
Pending Full Validation and F-12 remains In Progress; existing review/manual/CI
and coverage gaps remain. No full suites or benchmarks were run in this step.
