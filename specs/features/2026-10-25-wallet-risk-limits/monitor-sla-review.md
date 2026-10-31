# F18 — Review of the one-second monitor requirement

สถานะ: Approved — เจ้าของสั่ง “แก้เป็น 3 วินาที” วันที่2026-10-28; Paper hard bound3s/target1s แทนการเลือก2sก่อนหน้า

## ข้อค้นพบ

NC-F18-05 กำหนดทุก authoritative price/fill/correction ที่พร้อมถึง durable
result/latch ≤1s และ validation§5 ผูกไว้กับ100owners×20orders พร้อมโหลดคำสั่ง
และกำหนดทุก ready input ผ่าน ไม่มี percentile ยกเว้นรายการช้า
เอกสารที่ตรวจไม่ระบุ risk-budget calculation ที่พิสูจน์ว่า1sเป็นเส้นแบ่งความ
ปลอดภัยโดยเฉพาะ แต่อย่างไรก็เป็นข้อกำหนดที่เจ้าของอนุมัติ จึงยังมีผลจนอนุมัติเปลี่ยน

ต้องแยกสองหน้าที่:
- Background monitor: ความเร็วตรวจพบ/บันทึก breach และเริ่ม stop โดยไม่ต้องมี
  browser หรือคำสั่งใหม่ การช้าลงทำให้ durable latch, status และการเริ่มจัดการ
  queued/active orders ช้าลงจริง ไม่ควรเรียกว่าไม่มีผลต่อความเสี่ยง
- Financial boundary: ตรวจ authoritative risk ใหม่ก่อนเพิ่มความเสี่ยง/execute
  ใช้ owner lock, replay และ publication fence เดิม; pending/unavailable ไม่ใช่
  สิทธิ์ผ่านด้วย projection เก่า ส่วนนี้ต้องคงเดิม ไม่ใช้ SLA ใหม่เป็น grace period

หลักฐานโค้ด: infra/risk_limits/policy.py::execution_context และเส้นทางเรียกใน
infra/paper_orders/worker.py; replay_monitor/_evaluate_frames เก็บ transient breach
จากทุก verified frame. นี่เป็นเหตุผลทางสถาปัตยกรรม ไม่ใช่การรับรอง safety ครบ
ทุก interleaving แทน tests/review. Guard ไม่ทำให้การหยุด background ทันที และ
ไม่รับประกันเพดานขาดทุนจริง: position ยังเปิดอยู่และไม่ใช่คำสั่ง stop-loss

## ข้อเสนอให้เจ้าของตัดสิน

แนะนำทบทวนเฉพาะ Paper: เป้าหมาย background monitor1s แต่ hard acceptance
bound เป็น3s ต่อทุก ready input ภายใต้ workload/resource เดิม รวม idle owners
และ recovery ใน non-fault phases.3sเป็นข้อเสนอเวลาตอบสนองเชิงผลิตภัณฑ์ที่
เจ้าของต้องยอมรับ ไม่ใช่ค่าที่พิสูจน์ว่าเหมาะสมจาก latencyล่าสุด1.70s หรือเป็น
มาตรฐานของตลาด และไม่ใช่คำรับรองว่า candidate จะผ่านชุดเต็ม

หากอนุมัติ ต้องยอมรับว่า background latch/status/การเริ่ม stop อาจช้ากว่าเดิม
ได้ถึงกรอบใหม่; actual cancellation completion ใช้เกณฑ์เดิมแยกต่างหาก ไม่อ้าง
ว่าจบการยกเลิกภายใน3s. ไม่ใช้เกณฑ์ Paper ใหม่นี้รับรอง Live; Live ยังคง1sตาม
ข้อกำหนดเดิมและ Pending Dependency จนทบทวน/พิสูจน์บน executor จริงต่างหาก
Shared domain/formulas ยังคงเหมือนกัน ความต่างคือ operational timing contract

สิ่งที่คงเดิมทั้งหมด:
- ตรวจครบทุก ready input และ transient breach; ไม่ใช้เฉพาะราคาสุดท้าย
- Every-input hard bound, จำนวน late/unacknowledged/max และ distribution
  บันทึกทั้งจำนวนเกิน1sและเกิน3s; zero unacknowledged ไม่มีการทิ้ง tail
- F10 freshness/lease/generation, fail-closed admission/execution, owner isolation,
  Money/Quantity, latch/reset, financial fences, retry/idempotency และ stop oracles
- W1/W2/W3 10/5/30นาที,100owners×20orders, rates/resources, F15 command latency
  p95/p99 และ W4/regression/CI/manual gates เดิม ไม่ถือว่าผ่านทั้งชุดตาม SLA ใหม่นี้

ทางเลือกหากยอมรับ background delay3sไม่ได้: คง1sและดำเนินงาน performance ต่อ
โดยระบุ budget/ขอบเขตการทดลองใหม่ก่อน หรือแยกทบทวน capacity/hardware contract
ไม่ลดจำนวนowner/โหลดหรือขยายทรัพยากรโดยปริยายในข้อเสนอนี้

## ขั้นตอนหลังตัดสิน

ก่อนอนุมัติ: ไม่มี runtime/test-threshold change, NC-F18-05/plan/validationเดิม
ยังมีผล และ Failed/Pending เดิมยังอยู่
หลังอนุมัติ: แก้ NC-F18-05, plan, validation และ SLA oracle tests ให้ระบุ Paper/
Live และ hard boundชัด ตรวจขอบ1s/3s, missing acknowledgements, transient breach,
concurrent financial writers และ final candidate gates ที่ได้รับผลกระทบ
รักษาผล Failed เก่า ไม่เปลี่ยนย้อนหลังให้เป็น Passed; ผลเก่าใช้วิเคราะห์ได้เท่านั้น
