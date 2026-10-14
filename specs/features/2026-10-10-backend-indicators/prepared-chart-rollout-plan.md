# F-11 / F-12 — แผนปิด readiness ของ PREPARED สำหรับกราฟ

สถานะ: **Milestone A/B Approved** — 2026-10-13; เจ้าของอนุมัติรอบตรวจรับเต็ม
ตามคำตอบ “อนุมัติ ตรวจรับรอบเต็มต่อ”; Milestone C ยังไม่อนุมัติเปิดใช้งาน

เอกสารนี้ต่อยอด [performance-plan-v2](performance-plan-v2.md) และ
[validation](validation.md) ไม่แทนที่เกณฑ์เดิม ไม่อนุมัติเปิด PREPARED โดยอัตโนมัติ
และไม่เปลี่ยน requirements หรือสูตร indicator

## ปัญหาและหลักฐาน

- หลังแก้ startup delay ของ F-12 การสลับ 1h → 1m เริ่ม request ใน 16ms
  และรับ body ครบใน 3777ms; ตัว request ใช้ 3761ms ตาม
  [หลักฐาน F-12](../2026-10-12-candlestick-chart/evidence/final-candidate.md)
  นี่ไม่ใช่เวลา paint ของแท่งหรือ indicator และไม่ใช่ผล capacity
- LEGACY ยังอ่าน calculation window เต็มเพื่อคำนวณและตรวจ digest;
  PREPARED มี implementation อยู่แล้ว แต่ยังเปิดใช้งานจริงไม่ได้จนผ่าน gates
- [Capacity report](profiling/capacity-report.md) มี C2 Failed เดิม:
  API lag 109.465ms เกิน 100ms; C1 ผ่านใน candidate เดิม
- C3/C5 ยังไม่รัน, C4 Partial, C6 Failed และส่วนที่พึ่ง capacity ยังรอตรวจรับ
- R2-7 exact fixture 525,600 slots ผ่าน functional แล้วตาม
  [ทะเบียนหลักฐาน](profiling/merge-validation-mapping.md) และ
  [roadmap](../../roadmap.md); cold/warm/resource measurement ยังรอ
  ห้ามใช้ข้อความประวัติใน capacity report สรุปว่า exact fixture ยังไม่มี
- การแก้ gap/reset ล่าสุดอาจช่วย worker แต่ยังไม่มีหลักฐานว่าปิด C2 ได้

## ขอบเขตและการใช้ของเดิม

ใช้ worker, checkpoint, source proof, global slot และ maintenance protocol ตาม v2
ใช้ harness เดิมใน `backend/tests/services/indicator_builder/`:
`profile_capacity.py`, `profile_capacity_steady.py`, `profile_capacity_app.py`
และ `profile_capacity_evidence.py`; ตรวจ flags/side effects ก่อนเรียก
ใช้ F-12 browser scenarios ใน `frontend/e2e/candlestick-chart.spec.ts`
และตาราง validation เดิมเพื่อ trace เกณฑ์ ไม่สร้าง acceptance ชุดใหม่แทน

## Milestone A — ตรวจจุดช้าแบบจำกัดก่อนรอบเต็ม

หลังอนุมัติแผนนี้:

1. ตรวจ harness และ hash ของ candidate/fixture เทียบหลักฐานเดิม
   ระบุ tests ที่ผลยังใช้ได้และส่วนที่เปลี่ยนจาก gap/reset/digest
2. เตรียมฐานข้อมูลและบริการแยกจาก application DB; ไม่ใช้ fixture setup
   กับฐานข้อมูลที่ผู้ใช้เปิดกราฟอยู่ ไม่ส่ง exchange orders
3. เก็บ profile ระยะสั้นของ prepared read และ worker ที่ทำงานพร้อมกัน
   แยก HTTP/body, event-loop lag, DB, CPU, admission และ head freshness
   จำกัดช่วงวัด smoke ไม่เกิน 5 นาทีต่อ scenario ไม่รวม setup;
   บันทึกเวลา setup แยกและหยุดเมื่อหลักฐานพอระบุจุดช้า
4. ถ้าพบ bottleneck ให้เสนอ diff/วิธีแก้เฉพาะจุดที่มีหลักฐาน
   การเปลี่ยน implementation ที่เกินแผนที่อนุมัติเดิมต้องขออนุมัติก่อน
   ห้ามเพิ่ม concurrency, ผ่อน deadline/freshness หรือข้าม source proof เพื่อให้เร็ว
5. ตรวจ browser บนระบบแยก: first load, 1h → 1m, กลับ TF เดิม,
   สลับเร็วระหว่าง request และ source update ระหว่างอ่าน
   แยกเวลารอ admission, request, body complete และการแสดงข้อมูลจริง
   ต้องตรวจว่าแสดง series/TF และ indicator ตรง response ไม่ใช้ panel visible แทน

Checkpoint A ส่งหลักฐาน จุดช้าที่พบ และรายการแก้ที่จำเป็น;
smoke ไม่เปลี่ยน C2/C6 เป็น Passed และไม่รับรอง latency SLA ใหม่

## Milestone B — ตรวจรับเต็มที่ release checkpoint

รันเมื่อกำหนด checkpoint ชุดที่ 9 และเจ้าของรับทราบช่วงรันยาวแล้ว
ไม่รันชุดนี้เพียงเพื่อจบ Milestone A:

| เกณฑ์เดิม | สิ่งที่ต้องปิด |
|---|---|
| R2-7 | fixture exact 525,600; cold 1/warm 5, parity/digest, latency/lag/RSS/body ตาม v2 |
| R2-C1 | candidate สุดท้าย bootstrap 30 series และ fresh READY ภายในเกณฑ์เดิม |
| R2-C2 | steady append 60 นาที; ทุก series พร้อมตามเกณฑ์, lag ไม่เกินงบ |
| R2-C3 | dirty burst 30 series, recovery และ availability ตลอด 60 นาทีตาม v2 |
| R2-C4 | fairness/resource traces จาก workload เต็ม |
| R2-C5 | ทำ C2/C3 ซ้ำพร้อม rejected load ตาม admission เดิม |
| R2-C6 | รวม C1–C5/R2-7, worker/resources/parity ครบ ไม่มี series หาย |
| R2-S5/G7/D7 และ F4/F5/N4/D3/D4 ส่วน load | ผูกหลักฐาน workload กับเกณฑ์เดิมทีละข้อ |
| F-12 V-17/V-18 | workload/resource และ aggregate ตาม validation ของ F-12 |

ช่วงวัด 60 นาทีสี่ phase ของ C2/C3/C5 รวมอย่างน้อย 4 ชั่วโมง
ยังไม่รวม setup/bootstrap/audit/การแก้ failure; ไม่ใช่ประมาณเวลาจบงานทั้งหมด
ใช้ targeted regression ตามผลกระทบ; ด่านบังคับก่อน merge และ release ยังคงเดิม
เก็บผล Failed/Partial เดิมและระบุชุดที่เลื่อนเป็น **Pending Full Validation**
จนมีหลักฐานของ candidate สุดท้ายครบจริง

## Milestone C — เปิดใช้งานและตรวจผล

เมื่อ gates ผ่านแล้ว จัดทำ inventory ของ image/schema/key/roles/source writers
และคำสั่ง maintenance/rollback ที่ตรวจสอบได้ก่อนขอเปิดใช้กับ application DB
ทำตาม S2 drain/proof activation → S3 PREPARING/30 fresh heads →
S4 drain/epoch activation ใน v2; healthcheck อย่างเดียวไม่ใช่ readiness
ไม่ flip mode ผ่าน SQL ลัด ไม่ใช้ stale head หรือ LEGACY fallback แอบแทน

หลังเปิดใช้ ตรวจ first load และ TF switch จริงพร้อม candle/indicator parity,
source freshness, disconnect/recovery และ error contract เดิม
หากไม่ผ่าน ใช้ pause/rollback protocol ที่อนุมัติไว้และรายงานหลักฐาน
ไม่เปิด Live Trading หรือส่งออเดอร์เพื่อทดสอบ

## หลักฐานและการจบงาน

ทุกผลระบุ candidate hash, environment, fixture/source bounds, คำสั่ง,
เวลาและขอบเขตการวัด; แยก functional, smoke และ full acceptance
อัปเดตทะเบียน validation และ roadmap ตามผลจริง ไม่ประกาศ Completed จาก smoke
ตอนจัดทำแผนยังไม่มีการรัน tests, benchmark หรือเปลี่ยนโหมดระบบ

## Checkpoint A — 2026-10-13

ดำเนินการ investigation ที่อนุมัติแล้วตาม [รายงาน smoke](profiling/prepared-chart-smoke/README.md):
idle 1h → 1m body 473ms, ตรวจ UI ประมาณ 882ms ใน fixture แยก;
rapid switch ยังรอ cleanup 2s ตาม contract เดิม; source invalidation smoke ผ่าน
readiness ไม่ผ่าน: สูงสุด 29/30, ETH 1m FAILED_SUPERSEDED หลัง SOURCE_CHANGED ครบ 3 ครั้ง
ไม่เปลี่ยน C2/C6 หรือ release status และไม่เปิด PREPARED ใน application DB
รายการ diagnostic/fix ที่ต้องทำต่ออยู่ในรายงาน; Milestone B/C ยังไม่เริ่ม

## Follow-up ที่เจ้าของสั่งแก้ไข — 2026-10-13

ยืนยันจาก source journal และ attempt timestamps ว่า smoke producer เดิมเติม ETH 1m
หลังเริ่ม build ทั้งสามครั้ง (14:05:06.973, 14:10:08.933, 14:12:10.019 UTC)
สำหรับแท่งที่อยู่ใน calculation bounds; จึงแก้ diagnostic runner ภายใต้คำสั่ง
“เริ่มแก้ไข”: source producer แยก task รอบ 250ms, probes รอ Redis admission window,
หยุดเมื่อมี terminal failure, จำกัดช่วงรอที่เหลือและบังคับ output directory ใหม่
ไม่เปลี่ยน worker/publication/retry/source-proof contracts หรือเปิด PREPARED จริง
ตรวจ targeted producer/error-propagation/admission-clock tests และ real PostgreSQL
source-arrival smoke; ผลนี้ไม่รับรอง full readiness/C2/C6

Follow-up readiness: [รอบที่แก้แล้ว](profiling/prepared-chart-smoke-fixed-r2/README.md)
ครบ 30/30 ที่ 253.469s และ 60/60 HTTP 200 ในช่วง smoke 76.203s
ยังไม่ใช่ cold C1/full C2/C6 และไม่เปิด application PREPARED
