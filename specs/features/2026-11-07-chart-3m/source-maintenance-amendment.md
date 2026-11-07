# NC-3M-01 — Populated source maintenance / 3m schema

สถานะ: **Approved A — เจ้าของตอบ “อนุมัติ A” วันที่ 2026-11-07**
วันที่: 2026-11-07
อ้างอิง: requirements RQ-3M-07, plan P2.5, validation V3-04

## หลักฐานและข้อขัดกัน

- Empty source: migration0065→0066→0065→0066ผ่านบนฐานทดสอบแยก
- เมื่อเปิดsource proofและมีcandles/READY generations/headsจริง การDROP timeframe
  CHECKถูกปฏิเสธด้วย SOURCE_MAINTENANCE_SCOPE_REQUIRED และtransactionrollback
- begin_indicator_source_maintenance() ในmigration0015เป็นกลไกเดิมที่อนุมัติแล้ว:
  เปลี่ยนsourceepoch/revision/journalfloor, expirederivedgenerationsและลบindicatorheads
  แม้ข้อมูลแท่งเทียนไม่ได้ถูกแก้เลย การเรียกกลไกนี้จึงไม่ผ่านข้อกำหนดstateคงเดิม
  ในplanP2.5และdigestassertionsของtestใหม่
- ห้ามปิดtrigger/ปลอมscope/แก้sourceproofเพื่อให้DDLผ่านโดยไม่ได้อนุมัติarchitecture
- Runtimeของเจ้าของยังอยู่0065และไม่ถูกแตะ ไม่มีfinancial/order/position change

## ทางเลือก A — ใช้maintenanceเดิมและสร้างderived resultsใหม่ (แนะนำ)

ขอแก้RQ-3M-07/P2.5/V3-04ให้แยกimmutable/source/businessfactsออกจากderived state:

1. คงcandles/observations/sourcechange records, job identities, user/session/audit,
   order/cash/positionและประวัติการเทรดทั้งหมด ไม่ลบ/แปลง3mหรือbackfillข้อมูลปลอม
2. หยุดreaders/market-data/builderที่เกี่ยวข้องและยืนยันwriterdrainedก่อนDDL
   ใช้begin_indicator_source_maintenanceเดิมในtransactionที่ล็อกตารางตามpatternเดิม
3. อนุญาตเฉพาะผลตามmaintenanceเดิม: เปลี่ยนsourcefenceepoch/revision/journalfloor,
   generationสถานะเดิมที่กลไกกำหนดเป็นEXPIRED, ลบderivedheads และให้builderสร้างรุ่นใหม่
   ไม่ลบgeneration/checkpoint/sourcehistoryหรือเปลี่ยนformula/seed/retention
4. ทดสอบold/newTF, pre/postdigestsของfacts, expectedderivedchanges, faultrollback,
   claims/oldwriterfencing และconcurrentdowngradeguardกับDBจริงก่อนreview
5. localactivationยังต้องผ่านreview/refactor/Feature gatesตามแผน ตรวจความพร้อม
   ก่อนรายงานกราฟใช้ได้ ระหว่างrebuildแสดงRECOVERING/NOT_READYตามจริง
   การอนุมัติไม่รับประกันว่าการสร้างใหม่จะเสร็จในเวลาหนึ่งหรืออนุญาตขยายtimeout

ผลกระทบ: reuseกลไกที่มีอยู่และไม่เพิ่มmaintenanceprotocolใหม่ แต่กราฟ/indicator
ที่พึ่งderivedheadsอาจไม่พร้อมชั่วคราวจนrebuildผ่าน ไม่รับรองcapacity/releaseจากtestนี้
เวลาตรวจtargetedDBเพิ่มประมาณ5–15นาทีเบื้องต้นหลังแก้ ไม่รวมพัฒนา/rebuild/CI

## ทางเลือก B — ออกแบบmetadata-only maintenanceแยก

คงข้อกำหนดเดิมที่ให้heads/generations/sourceepochคงเดิม แต่ต้องออกแบบและขออนุมัติ
protocolสำหรับDDLที่ไม่เปลี่ยนsourcefacts พร้อมlocks/authorization/footprint checks,
oldwriterfencing, rollbackและnegative testsที่พิสูจน์ว่าไม่ใช้ทางนี้แก้source/triggerได้
ไม่ใช้การเขียนscopekindหรือปิดguardตรงๆเป็นimplementationโดยปริยาย

ผลกระทบ: รักษาderivedstateได้ แต่เพิ่มarchitectureและขอบเขตsecurityreview/testing;
ยังไม่กำหนดimplementationหรือเวลาพัฒนาจนกว่าจะมีแผนที่อนุมัติ ไม่ใช่ทางลัดลดtests

## คำตัดสินและ checkpoint

เจ้าของเลือก A; บันทึก requirements/plan/validation ตามคำตัดสินก่อนแก้ migration
ทางเลือก B ไม่ได้รับอนุมัติ ผล populated test เดิมยังคง Failed ในหลักฐานย้อนหลัง
ตรวจผลใหม่ตาม preservation contract ที่แก้แล้วก่อนรายงาน Passed
ยังไม่ migrate ฐานเจ้าของ, commit/push/merge หรือรัน campaign ยาวในรอบพัฒนา
เมื่อ implementation และ targeted checks ครบ แจ้ง Ready for Code Review และหยุดตามแผน
