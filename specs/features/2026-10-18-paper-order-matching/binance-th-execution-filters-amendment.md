# NC-F15-13 — Binance TH execution filters

สถานะ: Approved 2026-10-30

เจ้าของอนุมัติ “F-15 amendment รองรับ Binance TH execution filters จริง” หลัง
localhost ปฏิเสธ BTC/USDT และ ETH/USDT ด้วย `ORDER_UNSUPPORTED` ตามหลักฐานจริงว่า
ทั้งสองคู่มี `PERCENT_PRICE`, `MAX_NUM_ORDERS` และ `MIN_NOTIONAL.avgPriceMins=5`.

## กฎที่อนุมัติ

- แปลง `PERCENT_PRICE` เป็นช่วง LIMIT price จาก weighted average ของ public trades
  ในหน้าต่าง `avgPriceMins`; ขอบล่างปัดเข้าช่วงและขอบบนปัดเข้าช่วงด้วย Money เดิม
- `MIN_NOTIONAL` ของ MARKET ที่ `applyToMarket=true` ใช้ weighted average หน้าต่าง
  ที่ตลาดประกาศ ไม่ใช้ latest price แทน
- `MAX_NUM_ORDERS` จำกัดจำนวน Paper orders ที่ยังไม่ terminal ของ owner/episode/pair
  ก่อนรับ NEW; retry/idempotency ของคำสั่งเดิมไม่กินโควตาซ้ำ
- weighted average = ผลรวม `price × quantity` หารผลรวม quantity จาก public aggregate
  trades ในหน้าต่างเวลาปิดเดียวกัน แล้วต่อด้วย public trade stream; คำนวณผ่าน
  `Money`/`Quantity` และปัดครั้งสุดท้ายแบบ toward-zero
- bootstrap ต้อง paginate `/aggTrades` จนครบหน้าต่างที่ตรึงไว้ก่อนประกาศ book READY;
  gap, malformed page, incomplete coverage, disconnect หรือ stale reference ปิด admission
- กฎมีผลตาม order type: PERCENT_PRICE ใช้กับคำสั่งที่มีราคา, MARKET notional average
  ใช้กับ MARKET และ MAX_NUM_ORDERS ใช้กับทุก NEW order
- unknown filter, filter shape ที่ไม่ตรง, rule version เปลี่ยน หรือ reference ไม่ครบยัง
  fail closed; ห้ามลบชื่อ rule เพื่อให้ UI ผ่าน

## ขอบเขตการเปลี่ยน

ขยาย core constraint DTO/check, Binance TH public adapter, execution metadata/codec,
market-data bootstrap และ Paper admission/execution recheck. ไม่มี Live order, API secret,
float/Decimal เปล่า, synthetic production fallback หรือการเปลี่ยน risk/fee/PnL.

## Validation

ตรวจ parser exact shapes, paginated history/gap/duplicate/boundaries, weighted-average
precision, percent exact/below/above, market min-notional, max open orders พร้อม concurrent
NEW/idempotent retry, codec/restart/recovery, intake และ pre-execution fail-closed. รัน affected
venue/core/storage/pipeline/manual-order/matching tests และ static checks; real localhost
browser flowเป็น manual acceptance ไม่แทน F-15/F-18 full validation.
