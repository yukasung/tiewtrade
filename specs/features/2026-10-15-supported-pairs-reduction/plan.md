# F-38 — ลดคู่เทรดช่วงพัฒนา — Plan

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-15**

## แนวทาง

ลด allowlist กลางของ backend เหลือ BTC/USDT และ ETH/USDT ก่อน แล้ว deploy migration
แบบหยุด writer เพื่อกำจัดข้อมูล SOL/XRP/DOGE และบังคับ CHECK constraints ใหม่ หลังจากนั้น
จึงเปิด market-data/indicator workers กลับและตรวจว่าไม่มีคู่ที่ถอดถูกสร้างซ้ำ หน้าเว็บใช้
contract เดียวกับ API และแสดงเพียงสองคู่ โดย BTC/USDT ยังเป็นค่าเริ่มต้น

ชุดตรวจ capacity/workload ที่ใช้เวลานานจะมี profile แยกสำหรับ BTC/USDT ครบ 8 timeframe
ไม่แก้ threshold ต่อ request/series และไม่เปลี่ยนหลักฐานเก่าที่ล้มเหลวให้เป็น Passed

## ของเดิมที่จะใช้ซ้ำ

- `backend/src/tiewtrade/infra/market_data/catalog.py` — allowlist กลางของ ingestion,
  storage, realtime price, preview และ API
- `backend/src/tiewtrade/infra/market_data/storage.py` — validation ของ series ก่อนสร้าง demand
- `backend/src/tiewtrade/infra/market_data/realtime_storage.py` — seed/validate latest-price rows
- `backend/src/tiewtrade/services/market_data/candle_realtime.py` — สร้างรายการ live series จาก catalog
- `backend/src/tiewtrade/venues/binance_th/price_feed.py` และ `candle_feed.py` — transport validation
- `backend/migrations/versions/0013_market_candles.py`, `0014_realtime_prices.py`,
  `0015_prepared_indicator_source.py`, `0024_chart_candle_preview.py` — schema/constraint/FK
  ที่ migration ใหม่ต้องแก้โดยไม่สร้างตารางคู่ขนาน
- `frontend/src/components/ui/Select.tsx` — dropdown ตาม admin template
- `frontend/src/CandlestickChartPanel.tsx` และ `frontend/src/realtimePrices.ts` — ใช้
  generated API contract และรายการคู่ที่ต้องรวมไว้จุดเดียวใน frontend
- `backend/tests/services/indicator_builder/profile_capacity.py` และ
  `profile_capacity_steady.py` — profile runner เดิม โดยรับ explicit test catalog แทนการแก้
  threshold หรือทำ runner ชุดใหม่

## ลำดับดำเนินการ

### 1. Contract และ allowlist

1. ลด `PAIRS` ใน backend catalog เหลือ BTC/USDT และ ETH/USDT
2. เปลี่ยน venue transports ให้ตรวจจาก catalog/ค่าที่ส่งเข้า แทน tuple 5 คู่ที่ฝังซ้ำ
3. ปรับ API schema ของ market prices/catalog ให้ generated frontend type จำกัด base เป็น
   BTC หรือ ETH และ regenerate `frontend/src/api-types.ts`
4. สร้าง frontend market-catalog module จุดเดียวจาก generated type แล้วให้ chart options และ
   realtime decoder ใช้ร่วมกัน; จำนวน rows ที่ decoder คาดหวังต้องเท่ากับ catalog
5. input คู่ที่ถูกถอดต้องถูกปฏิเสธก่อน enqueue/read และ state/cache เก่าในหน้าเว็บต้อง fallback
   ไป BTC โดยไม่ยิง request คู่เดิม

### 2. Migration `0030_supported_pairs_reduction`

ใช้ Alembic migration ถัดจาก `0029` และ transaction เดียว:

1. deployment/runbook หยุด `market-data` และ `indicator-builder` ทุก replica ก่อน migration;
   API ยังไม่รับ binary ใหม่จน migration สำเร็จ
2. สร้าง backup/restore point สำหรับ environment ที่มีข้อมูลถาวร และเก็บ preflight counts
   แยก table/base
3. เรียก maintenance guard เดิมของ indicator และขอ table locks เพื่อกัน writer เก่า
4. ทำให้ global indicator build slot ว่างอย่างปลอดภัยหลังยืนยันว่าไม่มี worker แล้ว จากนั้นลบ
   heads/retry/checkpoints/generations/jobs/source changes ของ SOL/XRP/DOGE ตามลำดับ FK
5. ลบ candle demand/history, latest prices และ candle preview ของ SOL/XRP/DOGE; reset
   feed bootstrap metadata ที่อ้าง catalog เก่าโดยไม่ลบ global epoch/lease แบบไร้เงื่อนไข
6. แทน CHECK constraints ของ market/indicator tables ให้รับเฉพาะ BTC/ETH และแก้ rollout
   ready-count จาก 40 เป็น 16 โดยรักษาโหมด/epoch เดิมตามสัญญา transition
7. postcondition ใน migration ตรวจว่าไม่มี base อื่นเหลือในตารางที่เกี่ยวข้อง และข้อมูล BTC/ETH
   มีจำนวน/digest เท่า preflight ภายใน transaction; ผิดเงื่อนไขให้ raise เพื่อ rollback ทั้งก้อน
8. downgrade ขยาย constraints/catalog-compatible schemaกลับได้ แต่ไม่สร้างข้อมูลที่ลบคืน;
   การคืนข้อมูลต้องใช้ backup ตาม runbook
9. เปิด service binary ใหม่หลัง migration เท่านั้น แล้วตรวจ subscriptions 2 price streams และ
   16 candle streams พร้อมยืนยันว่าไม่มีงานของคู่ที่ถอดเกิดใหม่

### 3. Runtime และ profiles

1. ปรับ bound ที่คำนวณจาก `len(PAIRS) * len(Timeframe)` ให้ได้ 16 โดยไม่ฝังตัวเลขใหม่
2. เปลี่ยนข้อความ/log/health ที่กล่าว 30/40 series ให้คำนวณหรือระบุ runtime 16 series
3. ให้ readiness/bootstrap เตรียม BTC/ETH × 8 timeframe ครบ 16 seriesตาม production gate;
   capacity runner แยก workload catalog เป็น BTC/USDT × 8 timeframe เพื่อสร้างโหลดและวัด
   เพียง 8 series โดยไม่ลด production ready-count
4. แยก evidence path ใหม่และระบุ `BTC-only`; เก็บ C2/C3 และ failure 5 คู่เดิมไว้เป็น historical
   evidence ไม่ใช้ปนกับ candidate F-38

### 4. เอกสารและสถานะ

หลัง code/validation ผ่าน ให้แก้ mission §6 และข้อกำหนด F-09–F-12 ด้วยหมายเหตุว่า pair scope
ถูกแทนโดย F-38, ปรับ validation counts 5/30/40 เป็น 2/16 หรือ BTC-only 8 ตามบริบท และ
อัปเดต roadmap โดยไม่ลบประวัติผลตรวจเดิม

## สิ่งที่จะแก้

| พื้นที่ | การเปลี่ยนแปลง |
|---|---|
| Backend catalog/transports/API | allowlist 2 คู่, fail-closed, schema contract |
| Market-data/indicator workers | subscriptions และ jobs เฉพาะ 16 runtime series |
| Migration 0030 | purge, constraints, rollout count, postconditions |
| Frontend chart/realtime | catalog กลาง 2 คู่, BTC default, stale-state fallback |
| Profile runners | explicit BTC-only 8-series acceptance profile |
| Tests/specs | migration/concurrency/contracts และ traceability ใหม่ |

## ผลต่อฐานข้อมูล

- เป็น destructive data migration: ลบ SOL/XRP/DOGE จาก market-data และ indicator tables
- ไม่ลบ user, credential, audit, order, balance หรือ position table
- migration atomic และ idempotent ในผลลัพธ์; rerun deployment หลังสำเร็จไม่สร้างข้อมูลกลับ
- downgrade ไม่สามารถคืนข้อมูลที่ลบ ต้อง restore จาก backup เท่านั้น
- production-like environment ต้องบันทึก pre/post counts และ restore point เป็นหลักฐาน

## ความเสี่ยงและการควบคุม

| ความเสี่ยง | การควบคุม |
|---|---|
| writer เก่าเขียนคู่ที่ถอดกลับ | หยุดทุก replica, lock ตาราง, deploy binary ใหม่หลัง migration |
| ลบ BTC/ETH โดยผิดพลาด | predicate allowlist, pre/post count+digest และ transaction rollback |
| FK/หัว indicator ค้าง | ลบตาม dependency และตรวจ orphan/constraint หลัง migration |
| API/UI catalog ไม่ตรงกัน | generated contract + contract/component tests |
| ลดจำนวน series แล้วแอบลดเกณฑ์ | คง threshold ต่อ request/series; แยก runtime 16 กับ test 8 ชัดเจน |
| BTC workload ไม่ครอบคลุม ETH | ระบุ Pending ETH workload และไม่กล่าวอ้างว่า Passed |
| rollback ต้องการข้อมูลที่ลบแล้ว | backup/restore runbook; schema downgrade อย่างเดียวไม่ถือว่า restore |

## Checkpoints

1. contract/allowlist และ migration tests ผ่าน
2. runtime 2 คู่/16 series พร้อม post-migration verification
3. targeted backend/frontend regression ผ่าน
4. runtime readiness 16 series และ BTC-only workload 8 series ผ่าน threshold พร้อมอัปเดตหลักฐาน
