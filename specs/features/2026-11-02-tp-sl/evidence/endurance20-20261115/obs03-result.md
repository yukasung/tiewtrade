# OBS-03 — refactor and one short-load diagnostic

สถานะ: Diagnostic workload Passed; timing **NO_TRIGGER / Not Reproduced**. ไม่ใช่ timing acceptance และไม่แทน W3.

## Refactor / checks

ลดการเรียก report() ซ้ำใน M1 tests โดยอ่าน snapshot ครั้งเดียว คง assertions และ callback ordering เดิม ไม่เปลี่ยน runtime/business logic.
4 affected tests และ Ruff/format/mypy ผ่าน ใช้หลักฐาน 170 targeted/real-PG tests จาก M1 ต่อเพราะ runtime ไม่เปลี่ยน.

## One approved campaign

Raw: `validation-artifacts/f17-obs03-smoke-20261116/`; ดู scalar evidence ใน [summary](obs03-result-summary.json).
Preflight 7/7 ก่อน fixture; 20 simulated owners, 400 baseline orders, SMOKE 6 cycles/owner.
รวม 460.986s (7m41s), วัด 300.519s, final-tail 1.209s; 600 offered/admitted/completed, 0 rejected, 240 fills, 120 cancels, 120 replays.
Book inputs 3006/3000. Transaction p95 113.019ms / p99 173.587ms; end-to-end p95 1.085s / p99 1.399s เป็นคนละ metric.
Base/global invariants/resource และ pool contract 21 processes ผ่าน. ผล positions แยกเป็น null ใน SMOKE ไม่อ้างว่าเป็น full rebuild acceptance.
3072 publications RETURNED; fence sampler 0 triggers / 0 errors. Lag task completed/joined; 6429 samples, max loop lag 140.320ms.
ไม่มี phase timing samples จึงไม่สามารถแยกสาเหตุ timeout ของ W3 จากรอบนี้ และไม่ถือว่าแก้สาเหตุแล้ว.

## Cleanup / binding

Candidate/config/migrations/runner pinned ก่อนเริ่ม; source_unchanged=true.
Independent audit: DB absent, 0 connections/locks, Redis เฉพาะงาน absent, worker PID receipts ทั้ง 20 ไม่ทำงานแล้ว. Pool contract ผ่านก่อนปิด.
คำสั่ง docker inspect ใช้ข้อความ `no such object` ตัวพิมพ์เล็ก; audit รอบแรกเทียบตัวพิมพ์ผิด แก้เฉพาะการอ่านผลและยืนยันซ้ำแบบ read-only ไม่ลบทรัพยากรเพิ่ม.

## Remaining / stop

คงผล W3-OBS-01 Incomplete และผลเดิมทั้งหมด; F-17 ยังไม่ Completed.
หนึ่ง campaign ที่อนุมัติใช้แล้ว: หยุด/report ไม่มีรอบเพิ่ม ไม่มี 4h, commit/push/CI/merge.
ขั้นถัดไปควรทบทวนเหตุการณ์ W3 ระยะยาวร่วมกับผล NO_TRIGGER นี้ แล้วจัดทำขอบเขตตรวจครั้งถัดไปที่จับเหตุการณ์เดิมได้ ไม่รัน SMOKE ซ้ำโดยไม่มีสมมติฐานใหม่.
