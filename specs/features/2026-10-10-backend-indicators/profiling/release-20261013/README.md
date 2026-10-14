# PREPARED release checkpoint — 2026-10-13

สถานะ: **In Progress** — เจ้าของอนุมัติ Milestone B และรับทราบช่วงวัดอย่างน้อย 4 ชั่วโมง
อ้างอิง [แผน](../../prepared-chart-rollout-plan.md) และ validation เดิม
ไม่ใช่การอนุมัติ Milestone C/production activation

## Environment / preflight

- capacity PostgreSQL 55434/Redis 56380 แยกจาก application DB และไม่มี exchange orders
- เก็บฐาน smoke เดิมโดย rename เป็น `tiewtrade_smoke_20261013`; ฐาน `tiewtrade`
  ใหม่ migrate ถึง 0024 และ seed 3,387,785 rows ก่อน measurement
- Preflight ครั้งแรกหยุด SOURCE_BOOTSTRAP_REQUIRED ก่อนเริ่ม worker/measurement:
  ฐานใหม่ไม่ได้รับ DB-local event triggers จากฐานเดิม แก้โดยติดตั้ง
  `backend/db/bootstrap/10-event-trigger.sql`, protect partitions และ activate source proof
  ตรวจ trigger validity=true, jobs=0 แล้วใช้ source fixture เดิมต่อ ไม่ seed ซ้ำ
- เก็บ stopped capacity API/builder เก่าโดย rename suffix `archive-20261013`
- API/builder ใช้ image เดียวกับ candidate ปัจจุบัน ตัวละ 2 CPU/1 GiB;
  [C1 environment](c1/environment.json) ระบุ immutable image
- Harness full phases ใช้ source producer แยกจาก observer/HTTP เหมือน smoke ที่แก้แล้ว
  ไม่เปลี่ยน workload, thresholds, source proof หรือ retry budget
  เพิ่มการสร้าง fixture accounts เมื่อ reuse source จาก DB ใหม่ที่ยังไม่มี accounts
- Focused producer/admission tests 4 ผ่าน, Ruff ผ่าน, mypy ของ capacity harness
  2 files ผ่านเมื่อใช้ MYPYPATH=src; ไม่รัน full suite เพื่อยืนยัน harness edits

## Gates

| Gate | ผล |
|---|---|
| C1 bootstrap + parity | PASSED; [result](c1/result.json), ครบ 30/30 ที่ observation 360s |
| R2-7 exact cold/warm/resource | FAILED รอบ C1: 525,599 slots; ทั้ง 6 requests ถูกต้อง 200 แต่ยังต้องตรวจ exact 525,600 แยก ไม่ผ่อนจำนวน |
| C2 steady 60m | Interrupted ก่อนเริ่มช่วงวัดเต็ม เพื่อกลับมาแก้/ตรวจแบบเร็ว; ยังไม่ผ่าน |
| C3 dirty/recovery 60m | Pending C2 |
| C5 steady/dirty rejected-load | Pending C3 |
| C4/C6, dependent release criteria | Pending aggregate evidence |
| F-12 V-17/V-18 | Pending Full Validation |

Failed/Partial ในรายงานก่อนยังมีผลจนมีหลักฐานครบของ candidate สุดท้าย
ผล smoke 30/30 และ 60/60 ไม่ใช้แทนด่านในตารางนี้

## C1 result

- ช่วงวัดจริง 600s, 60 observations และ 10 probe rounds; ผลราย series ครบ 30 rows
- API metrics 306 requests รวม cold/warm: max lag 87.750ms, max RSS delta
  65,482,752 bytes; worker 43 attempts, max 48.458s, max RSS delta 3,182,592 bytes
- Worker หยุดแบบ DRAINED / exit 0; ไม่ถูก kill ระหว่างปิดงาน
- Cold 1/warm 5: 203–281ms, ทุก response 200 และ full-scan parity ผ่าน;
  logical slots 525,599 จึงยังไม่ผ่าน R2-7 แม้ latency/resource ผ่าน
- Process exit 1 เป็นผล R2-7 fixture count; C1 result แยกเป็น PASSED
  จึงเริ่ม C2 ตาม prerequisite เดิม ไม่ถือว่า aggregate/release ผ่าน
- `harness-hashes.json` เป็น final harness หลังแก้ reuse-source fixture accounts;
  การเปลี่ยนหลังเริ่ม measurement มีเพียงจัดรูปแบบ SQL string โดยไม่เปลี่ยน query

C2 เริ่มเตรียม fresh heads หลัง C1 แต่ถูกหยุดก่อนครบ baseline และก่อนเริ่มช่วงวัด
60 นาทีตามคำสั่งให้แก้และทดสอบอย่างรวดเร็ว จึงไม่มี `result.json` และห้ามนับเป็น Passed.
