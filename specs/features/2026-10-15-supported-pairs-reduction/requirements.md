# F-38 — ลดคู่เทรดช่วงพัฒนา — Requirements

สถานะ: **Approved — เจ้าของอนุมัติ 2026-10-15**

วันที่: 2026-10-15

## ทำไมต้องมี

ระบบปัจจุบันเตรียมข้อมูลตลาด ราคาเรียลไทม์ indicator และกราฟสำหรับ 5 คู่ ทำให้การ
backfill และการตรวจ workload/endurance ของ F-11/F-12 ใช้เวลานานระหว่างพัฒนา เจ้าของ
จึงสั่งให้ลดขอบเขตคู่เทรดที่รองรับเหลือ BTC/USDT และ ETH/USDT พร้อมลบข้อมูลเดิมของ
SOL/XRP/DOGE ออกจากฐานข้อมูล และให้ชุดตรวจสมรรถนะที่ใช้เวลานานรันกับ BTC/USDT เท่านั้น

เมื่อ requirements นี้ได้รับอนุมัติ ให้ถือว่าแทนข้อกำหนดรายการ 5 คู่ใน mission §6,
F-09, F-10, F-11 และ F-12 เฉพาะเรื่องรายการคู่เทรดและจำนวน series ส่วนข้อกำหนดเรื่อง
ความถูกต้อง ความสด ความต่อเนื่อง ความปลอดภัย การจำกัดทรัพยากร และ trading safety เดิม
ยังมีผลทั้งหมด

## ขอบเขต

### ทำ

- ให้รายการคู่เทรดที่ระบบรองรับแบบคงที่เหลือ `BTC/USDT` และ `ETH/USDT`
- ใช้รายการเดียวกันใน candle backfill, live price, live candle, indicator API/builder,
  chart API และตัวเลือกคู่เทรดในหน้าเว็บ
- ลบข้อมูลของคู่ที่ไม่รองรับออกจากตาราง market-data และ indicator ที่มีอยู่แล้ว
- ยกเลิก demand, queue, retry, checkpoint, generation, preview และสถานะ feed ของคู่ที่ถูกถอด
  เพื่อไม่ให้งานพื้นหลังสร้างข้อมูลกลับมาอีก
- ปฏิเสธ SOL/XRP/DOGE และคู่อื่นแบบ fail-closed ที่ขอบ API และ ingestion ตามสัญญาเดิม
- ปรับจำนวน series และ resource bounds ที่ขึ้นกับจำนวนคู่จาก 5 คู่เป็น 2 คู่
- ใช้ `BTC/USDT` เท่านั้นในชุด capacity/workload/stress/endurance ที่ใช้เวลานานระหว่าง
  การตรวจรับ F-11/F-12 โดยคงทุก timeframe และ threshold ต่อ request/ต่อ series เดิม

### ไม่ทำ

- ไม่เพิ่มหน้า Platform Admin สำหรับเพิ่ม/ถอนคู่เทรด งานนั้นยังเป็น F-37
- ไม่เปลี่ยนสูตร indicator, timeframe, retention, finality, freshness หรือ pagination
- ไม่เปลี่ยนกฎ Money/Quantity, order, balance, position, PnL, margin หรือ Live Trading
- ไม่ส่งออเดอร์จริงและไม่เปิด Live Trading
- ไม่ถือว่าผล workload ของ BTC/USDT เป็นหลักฐานสมรรถนะของ ETH/USDT

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | allowlist กลางต้องมีเพียง `BTC/USDT` และ `ETH/USDT`; ทุก service และ UI ต้องใช้แหล่งเดียวกันหรือ generated contract เดียวกัน ห้ามมีรายการคู่ซ้ำที่คลาดกัน | คำสั่งเจ้าของ 2026-10-15; architecture §2 |
| RQ-2 | หลัง deploy แล้ว ห้ามมี subscription, backfill, preview bootstrap, indicator build หรือ retry ใหม่สำหรับ SOL/XRP/DOGE | คำสั่งเจ้าของ; F-09–F-12 |
| RQ-3 | API ต้องปฏิเสธคู่ที่ไม่อยู่ใน allowlist ก่อนสร้าง demand หรือเขียนข้อมูล และต้องไม่คืนข้อมูลเก่าของคู่ที่ถูกถอด | trading-safety §3; security fail-closed |
| RQ-4 | migration ต้องลบข้อมูล SOL/XRP/DOGE จากทุกตาราง market-data/indicator ที่ผูกด้วย source/base/quote/timeframe รวมทั้ง queue/state ที่อาจสร้างข้อมูลกลับมา โดยลบใน transaction และตรวจจำนวนก่อน/หลัง | คำสั่งเจ้าของให้ลบข้อมูลเดิม; database §2/4 |
| RQ-5 | ก่อน destructive migration ใน environment ที่มีข้อมูลถาวร ต้องมี backup/restore point และรายงานจำนวนแถวแยกตามตาราง/คู่; migration ล้มเหลวต้อง rollback โดยไม่เหลือข้อมูลครึ่งชุด | database §2/4; error recovery |
| RQ-6 | migration ต้อง idempotent: รันซ้ำแล้วสำเร็จและไม่แตะข้อมูล BTC/ETH; ห้ามใช้การลบแบบไม่มี predicate จำกัดคู่ | database §2; trading safety |
| RQ-7 | foreign keys, generation/head/checkpoint และ feed epoch/lease ต้องคง consistency หลังลบ; worker ที่ถือ lease หรือ job เก่าต้องไม่เขียนคู่ที่ถูกถอดกลับมา | concurrency/idempotency; F-11/F-12 |
| RQ-8 | หน้าเว็บต้องแสดงตัวเลือกเฉพาะ BTC/USDT และ ETH/USDT โดย BTC/USDT ยังเป็นค่าเริ่มต้น; URL/state/cache เก่าที่อ้างคู่ที่ถูกถอดต้องกลับสู่ BTC/USDT โดยไม่ยิงคำขอคู่ที่ถูกถอด | คำสั่งเจ้าของ; F-12 |
| RQ-9 | correctness/contract tests ต้องพิสูจน์ allowlist 2 คู่, การปฏิเสธคู่ที่ถูกถอด, migration ไม่แตะ BTC/ETH และ worker ไม่สร้างข้อมูลที่ลบกลับมา | testing §2/3; RQ-1–7 |
| RQ-10 | readiness/bootstrap ต้องเตรียม BTC/USDT และ ETH/USDT ครบ 16 runtime series เพื่อให้ PREPARED gate ไม่รับรอง ETH ก่อนพร้อม; capacity/workload/stress/endurance ที่ใช้เวลานานให้สร้างโหลดและวัดเฉพาะ BTC/USDT ครบ 8 timeframe โดยคง threshold ด้าน latency, freshness, recovery, memory, queue bound และ parity เดิมที่ไม่ขึ้นกับจำนวนคู่ | คำสั่งเจ้าของให้ทดสอบเฉพาะ BTC/USDT; เจ้าของอนุมัติ clarification 2026-10-15 |
| RQ-11 | เกณฑ์รวมที่เดิมระบุ 30/40 series ต้องคำนวณใหม่อย่างชัดเจน: runtime ที่รองรับ 2 คู่มี 16 candle series; acceptance workload ตาม RQ-10 มี 8 series ห้ามเปลี่ยนตัวเลขโดยไม่ระบุว่าเป็น runtime หรือ test profile | traceability; F-11/F-12 validation |
| RQ-12 | หลักฐานต้องแยก runtime readiness 16 series ออกจาก BTC-only workload 8 seriesทุกครั้ง; readiness ของ ETH ไม่ใช่หลักฐาน workload ของ ETH และห้ามเปลี่ยนสถานะ ETH workload เป็น Passed หากต้องรับรองสมรรถนะ ETH ก่อน release ต้องรันหลักฐานเพิ่มหรือบันทึก Pending Full Validation | testing §7; ห้ามกล่าวอ้างเกินหลักฐาน |
| RQ-13 | ประวัติผลตรวจ 5 คู่เดิมยังเก็บเป็นหลักฐานย้อนหลังและทำเครื่องหมาย superseded/ไม่ใช่ผลของ candidate ใหม่ ห้ามลบหรือเขียนทับเพื่อทำให้ failure เดิมหายไป | auditability; testing §7 |

## การลบข้อมูล

ข้อมูลที่ต้องถูกสำรวจและครอบคลุมใน plan อย่างน้อยประกอบด้วย:

- candle history และ candle demand/backfill state
- latest price และ price-feed state
- live-candle preview และ candle-feed state
- indicator build slot/job, generation, head, checkpoint, retry และ source-change metadata

plan ต้องระบุลำดับการหยุด writer, backup, delete, constraint/allowlist deployment, restart และ
verification เพื่อปิด race ที่ writer เก่าอาจเขียน SOL/XRP/DOGE กลับมาระหว่าง migration

## กฎความปลอดภัยที่เกี่ยวข้อง

- `specs/standards/trading-safety.md` §3: คู่ที่ไม่รองรับห้ามใช้เปิดความเสี่ยงใหม่
- `specs/standards/database.md` §2/4: migration ต้อง atomic, ตรวจย้อนกลับได้ และไม่ทำให้
  integrity เสีย
- `specs/standards/testing.md` §7: เลือก targeted tests ตามผลกระทบ แต่เก็บ acceptance
  criteria และสถานะหลักฐานที่เลื่อนไว้ครบ
- ห้ามลบ order, balance หรือ position ของผู้ใช้จากการลด allowlist; หากพบข้อมูลดังกล่าว
  ก่อน migration ต้องหยุดและทบทวนแผน เพราะกฎการถอนเหรียญเดิมกำหนดให้สถานะที่เปิดอยู่
  ต้องไม่ถูกแตะ

## ยังไม่ชัด

ไม่มีข้อที่บล็อกการเขียน plan หลัง requirements ได้รับอนุมัติ
