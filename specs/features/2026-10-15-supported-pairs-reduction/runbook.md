# F-38 — Migration and restore runbook

ใช้กับการเปลี่ยน runtime catalog จาก 5 คู่เป็น BTC/USDT และ ETH/USDT เท่านั้น.
คำสั่งต้องรันจาก repository root และต้องใช้ credentials ของ environment นั้นผ่าน environment
variables; ห้ามใส่ secret ลง log หรือไฟล์หลักฐาน.

## ก่อน migration

1. หยุด `market-data` และ `indicator-builder` ทุก replica และยืนยันว่า
   `indicator_build_slot.state = 'IDLE'`.
2. สร้าง PostgreSQL custom-format backup ไปยังที่เก็บนอก repository.
3. บันทึก revision, count แยก table/base และ deterministic digest ของ BTC/ETH รวมทั้ง
   count/digest ของตาราง user/order/balance/position/audit ที่มีอยู่.
4. ยืนยันว่า binary ใหม่พร้อม deploy แต่ยังไม่เปิด worker.

## Migration

1. รัน `alembic upgrade head` ด้วย migrator role.
2. Migration `0030` ขอ exclusive locks, ตรวจ builder ว่าง, purge SOL/XRP/DOGE,
   เปลี่ยน constraints, seed/fair-scheduling functions และ production ready gate เป็น 16 series.
3. ถ้า migration ล้ม ห้ามเปิด worker; transaction ต้อง rollback และต้องตรวจ revision/data
   ก่อน retry.

## ตรวจหลัง migration

- revision เป็น `0030` และทุก market/indicator table มีเฉพาะ BTC/ETH.
- count/digest ของ BTC/ETH เท่าก่อน migration; ตาราง trading/user/audit ไม่เปลี่ยน.
- `seed_indicator_build_jobs()` ระบุ BTC/ETH เท่านั้น, fair cursor มี 16 slots และ
  PREPARED transition ต้องการ 16 READY heads.
- negative insert ของ SOL/XRP/DOGE ถูก CHECK constraint ปฏิเสธ.
- เปิด API binary ใหม่ก่อน แล้วเปิด `market-data`; ห้ามนำ worker binary catalog เก่ากลับมา.
- ตรวจ price rows = 2, candle demand/preview = 16 series, feed ต่อกลับ และไม่มีคู่ที่ถอด
  เกิดใหม่หลังอย่างน้อยสอง reconnect/refresh cycles.

## Restore

Schema downgrade ไม่คืนข้อมูลที่ purge. หากต้องย้อนข้อมูล ให้หยุด writer ทั้งหมด, สร้างฐาน
disposable จาก backup และตรวจ revision/count/digest ก่อน จากนั้นจึงสลับฐานตาม runbook
deployment ของ environment. ห้าม restore ทับฐานที่กำลังรับ write และห้ามใช้ downgrade
แทน backup restore.
