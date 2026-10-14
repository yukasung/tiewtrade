# F-12 — Post-merge validation checkpoint

วันที่: 2026-10-14 (Asia/Bangkok)

สถานะ: **Partial — merge และด่านอัตโนมัติก่อน merge ผ่าน; ยังไม่ Completed**

เอกสารนี้เป็นหลักฐานล่าสุดหลัง merge และใช้ต่อจากหลักฐานรอบพัฒนาเดิม โดยไม่เปลี่ยน
เกณฑ์ใน `validation.md` และไม่ใช้ smoke แทน V-H1..8 หรือ V-17.

## Source และ CI

- PR [#11](https://github.com/yukasung/tiewtrade/pull/11) merge เข้า `main` แล้วที่
  merge commit `880e9d2a8879ec23beaf049caa766ca8fc487419`.
- Required CI ของ source head `8d6202abb30dac311f7cd7598b9a6c18b55d0c4b`
  ผ่านครบทุก job ใน [run 38563250593](https://github.com/yukasung/tiewtrade/actions/runs/38563250593).
- Backend full regression: **2,710 passed, 2 deselected**, 0 failed; Ruff และ mypy
  374 source files ผ่าน.
- Frontend full regression: **237 passed / 25 files**, 0 failed.
- Browser E2E: **17 passed**, 0 failed.
- API contract, PostgreSQL version pin และ container gates ผ่าน.

ผล CI ชุดนี้ใช้แทนการรัน full suite ซ้ำหลัง merge เพราะ source และ dependencies
ไม่เปลี่ยน. V-17 workload/resource/endurance ไม่ได้รวมอยู่ในผลนี้และยังเป็น
`Pending Full Validation` ตาม checkpoint ที่อนุมัติไว้.

## Runtime browser → API → database smoke

ตรวจบน local Compose ที่ API/frontend/PostgreSQL/Redis healthy และ market-data worker
กำลังทำงาน โดยสร้างบัญชี smoke แยกผ่าน UI; ไม่ใช้ API key และไม่ส่งออเดอร์.

| Timeframe | ผลหน้าเว็บจริง | History response |
|---|---|---|
| default `1h` | chart canvas และ exact OHLCV/live candle แสดง | HTTP 200, 1,000 rows |
| `1w` | chart canvas และ exact OHLCV/live candle แสดง | HTTP 200, 479 rows |
| `1M` | chart canvas และ exact OHLCV/live candle แสดง | HTTP 200, 111 rows |

ปุ่มรีเซ็ตทำงาน, theme เปลี่ยน light → dark ได้, ไม่มี JavaScript page error และ network
log ไม่มี request ไป Binance โดยตรง, `/orders` หรือ `/trading-account/use`.

## Backfill snapshot

หลัง browser smoke ตาราง `market_candle_demand` มี **40 COMPLETE, 0 PENDING,
0 FAILED** ครบ 5 คู่ × 8 timeframe สำหรับช่วงที่ระบบได้รับคำขอแล้ว. Weekly/monthly
เก็บ native history ตามอายุจริงของคู่ เช่น BTC `1w` 479 rows ตั้งแต่ 2017-08-14 และ
BTC `1M` 111 rows ตั้งแต่ 2017-08-01; คู่ที่เปิดตลาดภายหลังมีขอบเก่าต่างกันตามข้อกำหนด.

Read-only continuity query ของ fixed intervals `1m`–`1d` ตรวจ 30 series แล้วพบ
**0 missing slots ภายใน min/max ที่เก็บอยู่** และ **0 duplicate identity groups**.
log ช่วงตรวจมี warning `TRADES NOT_SENT/ConnectError` ชั่วคราว 2 ครั้ง แต่ไม่มี
candle demand ที่ FAILED หรือ worker exception; ผลนี้ไม่ใช้แทน failure/recovery matrix.

สถานะ COMPLETE นี้หมายถึง demand window ปัจจุบันเสร็จ ไม่ได้พิสูจน์ว่า lazy pagination
เคยร้องขอและตรวจครบสามเดือนของ `1m`–`1d`. Snapshot ปัจจุบันของช่วงสั้นยังมีเพียงช่วง
ที่ถูกเรียกจริง เช่น BTC `1m` เริ่ม 2026-10-12 และอีกสี่คู่เริ่ม 2026-10-13.

## งานที่ยังค้าง

- V-H1..V-H8 ยังต้องตรวจ browser/API จริงครบทุก timeframe โดยเลื่อนหลายหน้าถึงขอบ
  สามเดือนของ `1m`–`1d`, ตรวจรอยต่อ/viewport/eviction/reload และ failure/retry ตามเกณฑ์.
- Criteria ที่ยังเป็น Partial ในตาราง TF และ V-01..V-16 ต้องปิด mapping/หลักฐานรายข้อ;
  full CI ที่เขียวไม่ทำให้ข้อย่อยที่ยังไม่ได้พิสูจน์กลายเป็น Passed โดยอัตโนมัติ.
- V-17 และส่วนของ V-18 ที่พึ่ง workload/resource/endurance รอ release checkpoint/ชุดที่ 9.

