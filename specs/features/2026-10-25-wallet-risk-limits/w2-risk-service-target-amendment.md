# F18-R29 — Paper risk service target ภายใต้ W2 saturation

สถานะ: **Approved — เจ้าของตอบ “อนุมัติ R29” วันที่ 2026-10-29**
วันที่: 2026-10-29

## เหตุผลและขอบเขต

เจ้าของสั่งให้ปรับเพื่อปิด F-18 โดยด่วน หลังใช้เวลาหลายวัน คำสั่งนี้อนุญาตให้
จัดข้อเสนอปรับเกณฑ์ แต่ยังไม่ได้ระบุตัวเลขหรือขอบเขตความเสี่ยงที่ยอมรับใหม่
R28 W2 ล่าสุดจบ 1,038 cycles ครบทุก 100 owners และ RESET 100/100 แล้ว
แต่ verifier อ่านคอลัมน์ balance ที่ไม่มีอยู่ก่อน overflow (แก้แล้วพร้อม DB tests)
และหลักฐาน risk ราย owner ไม่ผ่าน R25 แยกต่างหาก

หลักฐาน: 237,981 expected inputs มี acknowledgement ครบ ไม่มี clock error
มี 3 inputs ของ owner เดียวช้า 3.053604s; owner นั้นมี 2,381 inputs
จึงผ่านภายใน 3s ประมาณ 99.874% ต่ำกว่า 99.9%; global quota ผ่านและไม่มี input >5s
ข้อมูลนี้พิสูจน์เฉพาะผลรอบนั้น ไม่รับประกันรอบถัดไปหรือความเหมาะสมต่อ Live
รายละเอียดและ artifact/source identity อยู่ใน evidence/m5-final-candidate.md

## เกณฑ์ที่เสนอให้เปลี่ยนหนึ่งเรื่อง

เฉพาะ **F18 Paper W2 แบบ R28 bounded saturation**:

| เกณฑ์ | ปัจจุบัน R25 | ข้อเสนอ R29 |
|---|---|---|
| Ready inputs ที่ commit ผล/latch ภายใน 3s ต่อ owner | อย่างน้อย 99.9% | อย่างน้อย **99.5%** |
| Ready inputs ที่ commit ภายใน 3s รวมทั้ง run | อย่างน้อย 99.9% | **99.9% เดิม** |
| เวลาสูงสุดของทุก ready input | ไม่เกิน 5s | **5s เดิม** |

W1/W3 และ profile อื่นคงราย owner 99.9% เดิม ค่า 99.5% เป็นข้อเสนอด้านผลิตภัณฑ์
สำหรับช่วง saturation ไม่ใช่มาตรฐาน Binance หรือค่าที่พิสูจน์ว่าปลอดภัยโดยทั่วไป
ไม่เลือก 3.054s เป็นขีดใหม่ตามผลรอบล่าสุด และไม่เปลี่ยน production monitor

ผลที่ยอมรับเพิ่ม: ภายใต้ W2 กระเป๋าหนึ่งอาจมีการตรวจ risk ช่วง 3–5s ได้ถึง
0.5% จากเดิม 0.1% (quota เพิ่มห้าเท่า) แต่ทุกกระเป๋ารวมกันยังไม่เกิน 0.1%
ตัวอย่าง 2,381 inputs: ยอมได้ไม่เกิน 11 inputs จากเดิม 2 inputs โดยใช้การเทียบ
จำนวนเต็ม `(expected - late) * 1000 >= expected * 995` ไม่ปัดเปอร์เซ็นต์ให้ผ่าน
กระเป๋าที่ช้าซ้ำยังถูกจำกัดด้วย quota ราย owner และ hard bound ทุก input
ในช่วงที่ช้า การบันทึก breach/latch และเริ่ม background stop อาจล่าช้าตามนั้น
เกณฑ์นี้ไม่ใช่การรับประกันขาดทุนสูงสุดหรือ deadline การปิดสถานะ

คง expected inputs/ack/clock errors/late receipts ทุกตัว รวมเวลารอทั้งหมด
คง freshness, financial fences, replay ทุก frame, transient breach, isolation,
Money/Quantity, duplicate prevention, balances/positions และ authorization
คง processing p95<=500ms/p99<=1s, R26 deadlines, R27-A RESET/restoration,
R28 volume/backpressure, overflow/recovery, resources และ physical cleanup เดิม
ไม่มีการปรับ API/schema/ทรัพยากร หรือเปิด Live/bot/production admission

## Implementation และหลักฐานหลังอนุมัติ

1. อัปเดตข้อยกเว้น W2 ใน requirements.md, plan.md, validation.md ก่อนแก้ oracle
2. ใช้ `sla_summary` เดิมใน backend/tests/infra/risk_limits/profile_workload.py
   เพิ่ม phase-specific owner quota โดย default ยังคง 999/1000; production
   acceptance W2 เลือก 995/1000 ชัดเจนและบันทึกทั้ง owner/global targets ในผล
3. ใช้ tests เดิมใน backend/tests/test_paper_acceptance.py เพิ่ม boundary checks
   สำหรับราย owner 99.5%, global 99.9%, >5s, missing ACK และ default W1/W3
   ไม่สร้าง oracle ใหม่ซ้ำ; ตรวจ lint/format/types เฉพาะผลกระทบ
4. ใช้ผล W1 เดิมต่อเมื่อยืนยัน default/production dependencies ไม่เปลี่ยน
   ผล W2 เก่ายังคง Failed/Partial; การคำนวณด้วยเกณฑ์ใหม่ย้อนหลังต้องระบุว่า
   counterfactual เฉพาะ SLA ไม่ใช่รับรอง W2 เพราะ overflow/final gates ยังขาด
5. รัน W2 ใหม่หนึ่งชุดหลัง preflight และ verifier checks ผ่าน; ถ้าผ่านทุก gate
   จึงไป W3 ตามเวลา 30 นาทีเดิม แล้ว W4/ด่านปิดงานตาม applicability
   หากเกิด failure ใหม่ให้เก็บหลักฐานและหยุด ไม่ปรับเกณฑ์หรือวนรันเอง

## เวลาและจุดตัดสินใจ

ประมาณหลังอนุมัติ: แก้ spec/oracle/targeted checks 10–15 นาที;
W2 เตรียม/วัด/overflow/สรุป 10–15 นาที; หากผ่าน W3 เตรียม/วัด/สรุป 35–45 นาที
W4 และด่านปิดงานยังต้องประเมินจากหลักฐานที่ใช้ต่อได้ก่อนเริ่ม ไม่รับประกัน
ว่าจะปิดทั้งหมดในหนึ่งชั่วโมงหรือว่า W3 ซึ่งยังคงเกณฑ์เดิมจะผ่าน
required CI/manual acceptance ที่ขาดต้องระบุค้าง ไม่แทนด้วยผล local

เจ้าของอนุมัติ owner quota 99.5% เฉพาะ W2 และวิธีตรวจตามเอกสารนี้แล้ว
ไม่มี Needs Clarification ของ R29 ค้าง การอนุมัติ R6–R28 และขั้นตรวจเดิมยังมีผล
Paper/F18 ยังคง Pending Full Validation; V22/V23 Pending Dependency
แม้ Paper ผ่านในอนาคตก็ยังไม่ใช่ F18 Completed จน dependency/ด่านบังคับครบ
