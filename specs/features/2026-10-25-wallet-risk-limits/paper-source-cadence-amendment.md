# F18-R32 — Paper fixture source cadence 5Hz

สถานะ: Approved — เจ้าของสั่ง “ปรับเกณฑ์ใหม่” หลังเสนอ 5Hz วันที่ 2026-10-29

## เกณฑ์ที่เปลี่ยน

สำหรับ F-18 integrated Paper profile เท่านั้น เปลี่ยนเป้าหมายการป้อนและเกณฑ์จำนวน
ข้อมูลตลาดจาก10Hzเป็น5Hz: BOOK BTC/USDT5ข้อมูลใหม่/s และ fresh PRICE BTC/USDT,
ETH/USDTอย่างละ5observations/s (เป้าหมายรอบละ200ms) ใช้ทั้ง inline/child fixture
และ W1/W2/W3 ของ profile นี้ ไม่เปลี่ยน F-15 standalone หรือ production market feed.

นับ unique source identities ที่ commit จริงในหน้าต่าง nominal เดิม ไม่ใช้ journal
frame ที่เกิดจาก lease renewal หรือราคาซ้ำแทนข้อมูลใหม่ ไม่รวม setup/drain/catch-up
นอกหน้าต่างเพื่อชดเชยจำนวนที่ขาด ใช้ price-fault exemptions เดิมเฉพาะราคาเท่านั้น.
กรณีไม่มี fault แต่ละ channelต้องมีอย่างน้อย W1=3000,W2=1500,W3=9000 commits;
ชุด diagnostic60sต้องมี300commits/channel แต่ยังไม่ใช่ acceptance.
รายงาน max/distribution ของ commit gaps ตามเดิม; 200msเป็น cadence เป้าหมาย
ไม่ใช่การอนุมัติให้ข้อมูลเก่าถูกนำไปเทรดหรือให้ละเลย readiness.

## ขอบเขตการรับรองและสิ่งที่คงเดิม

รับรองได้เฉพาะ profileข้อมูลตลาด5Hz ไม่อ้าง10Hzหรือความพร้อม Live จากผลนี้.
คง100owners×20orders, command rates10/100/10s, R28bounded W2 demand, R25–R29
processing/risk SLA, ทุกready inputและ hard deadlineเดิม, freshness/readiness,
publication/financial fences, authentication, Money/Quantity, idempotency,
no-duplicate/financial oracles, fault schedules, RESET, overflow/recovery,
W1/W2/W3ระยะ600/300/1800s, W4, CPU/RAM/pool/workerlimitsและCI/manual gatesเดิม.
R31 childยังเป็นdiagnostic-onlyและinlineยังเป็นdefault; R32ไม่อนุมัติเปลี่ยน mode.

ผล10HzเดิมคงFailed/Partial ไม่ย้อนแก้เป็นPassed. รอบR31childมีราคาเฉลี่ย6.17Hz
และbook9.32Hz แต่ไม่ได้ป้อนโหลด5Hz จึงไม่ใช่หลักฐานรับรองใหม่ และมีgapเกิน1s
ที่ยังต้องตรวจตาม freshness/risk gates. การลด cadence ไม่รับประกันเกณฑ์อื่นผ่าน.

## การนำไปใช้และตรวจ

Reuse SourcePublisher loops และ cadence_summary เดิม ใช้ค่าคงที่F18เฉพาะหนึ่งแห่ง
สำหรับ targetHz/period และจำนวนที่คาด; ไม่เปลี่ยนstorageหรือสูตรการเงิน.
เก็บ targetHz ในmanifest/oracleพร้อมgap statistics; คงfieldover_100msเพื่ออ่าน
หลักฐานเดิม และเพิ่มสถิติเกิน target period แยกชัดเจน. Tests ต้องพิสูจน์5ข้อมูลผ่าน,
4ข้อมูลไม่ผ่าน, duplicates/drainไม่นับ, price faultไม่ยกเว้นbook รวมsource/native
publication testsที่ได้รับผลกระทบและstatic checks. ไม่รันworkloadอัตโนมัติจากR32.

ก่อนรับงานต้องมีหลักฐานโหลด5Hzบนcandidateสุดท้าย: W1–W3ต้องตรวจใหม่เมื่อพร้อม;
W4/regressionใช้ผลเก่าได้เฉพาะdependenciesยังvalid. F18คงPending Full Validation,
Paper validationแยกจากCompletedที่ยังรอV22/V23.

R32 supersedesเฉพาะ10Hzในข้อกำหนดF18เดิมและR30 NC-R30-01; บทอื่นคงเดิม.
