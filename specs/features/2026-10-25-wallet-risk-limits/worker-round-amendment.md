# F18-R7 — สลับ manual intake กับ matching รอบเล็กใน runtime

สถานะ: **Approved** — เจ้าของตอบ “อนุมัติ R7” วันที่2026-10-27 ก่อน implementation

## ปัญหาที่พิสูจน์แล้ว

R6 read-only API price catch-up ผ่าน safety tests และ reseed20 แบบเดี่ยวผ่าน
58.18s แต่ยังไม่ผ่านวงจรพิเศษทั้งวงจรภายใน60s บน100owners/2000baselineorders
หลังแก้ evidence batching และ failure-backoff bookkeeping แล้วด้วย

`r6-full-cycle-r4` ใช้ trade IDs ต่อจาก frozen source อย่างถูกต้อง ผ่าน partial
fill→breach→stop→reset แล้วค้างระหว่าง reseed:20 NEW requests รวม buyแรก,
19 commands completed ณ deadline60s ยังไม่ถึงคำสั่งท้ายวงจร จึงไม่ใช่ V21 pass
W1 r10 ถูกหยุดก่อน measurement เพื่อแก้ payload ซ้ำ; W2/W3 ยังไม่ได้รัน

รอบ full-cycle r2/r3 สร้าง trade IDs ย้อนจาก3456มาเริ่ม1 เป็นข้อผิดพลาดของ
external diagnostic; core ปฏิเสธถูกต้อง ไม่ใช่หลักฐานว่า matching authorityผิด
เก็บ failure ทั้งหมดและไม่ใช้ผลเหล่านั้นยืนยัน capacity

## ข้อเสนอที่ต้องอนุมัติใหม่

F15 plan §worker lifecycle ระบุ tick20ms/batch20/claim30s และ retry1s/5s/30s/5m
R6 อนุมัติ API read protocol ไม่ได้อนุมัติการเปลี่ยน runtime scheduling นี้

1. ใน F18-integrated Paper runtime เรียก manual round **limit1** แล้ว matching
   round **limit1** และ sleep20msเดิม แทนการจบ phaseละ20 candidatesก่อนสลับ
2. ใช้ `run_manual_order_round`/`run_paper_order_round` และ due/claim/CAS/owner
   fairness เดิม ไม่สร้าง dispatcher/authority ใหม่ ไม่เปลี่ยน FIFO ภายใน owner
3. บริการและ F18 harness ต้องใช้ค่าเดียวกันและบันทึก batch limits ใน manifest
   F15 standalone harness/default service functions ยังคง20 เพื่อไม่เปลี่ยน
   profile/หลักฐานเดิมโดยเงียบ ๆ
4. คง10Paper+1risk, pools, risk concurrency4, aggregate app4CPU/2GiB,
   PG4CPU/3GiB, same image/schema/role isolation และ request/input rates เดิม
5. ไม่เปลี่ยน owner/publication/catalog fences, replay budgets, financial proofs,
   Money/Quantity, eligibility/freshness, stop/reset, idempotency หรือ backoff values
6. ไม่เปลี่ยน W1/W2/W3 10/5/30นาที,100×20, progress60s, p95<=250ms/p99<=1s,
   every ready evaluation<=1s และ financial/resource/fault/restore oracles

สมมติฐานคือการสลับ phaseเร็วขึ้นช่วยเวลารอของ inbox/command ที่เพิ่งรับ และลด
งานบน hints ที่เก่าแล้วขณะเดิน batchยาว **ยังไม่มีผลพิสูจน์ว่า limit1 เร็วกว่า**
จึงต้องวัดและไม่ประกาศผ่านจากการเปลี่ยนค่าเพียงอย่างเดียว

## ขอบเขตไฟล์และการพิสูจน์หลังอนุมัติ

- `services/engine/paper_order_main.py`: explicit phase limits1 ใน runtime
- `tests/infra/execution_market/profile_workload.py`: optional worker batch limit
  default20; F18 callerส่ง1เท่านั้น ไม่เปลี่ยน F15 default/oracles
- `tests/infra/risk_limits/profile_workload.py`: reuse runtime limits และ manifest
- ตรวจ supervision/worker composition, owner concurrency/claims/FIFO/stale CAS,
  manual intake/fill/stop/rollback/idempotency ที่ได้รับผลกระทบ
- เปรียบเทียบ selected-owner full cycle บน cloneข้อมูลเดิมพร้อมต่อ source IDs
  อย่างถูกต้อง รันทีละชุด เมื่อผ่านจึง W1→W2→W3 ตามแผนเดิม
- Reuse W4 r8 หาก scheduling change ไม่กระทบ replay/restore contract; หากพบ
  ผลกระทบใหม่จึงตรวจเฉพาะส่วนเพิ่ม ไม่สร้าง fixtureใหม่โดยไม่มีเหตุผล
- หากไม่ดีขึ้นให้ย้อน scheduling ในขอบเขตการทดลองนี้ เก็บผล Failed/Partial;
  เปลี่ยนวิธีใหม่นอกข้อเสนอนี้ต้องขอ amendment ตาม plan301 อีกครั้ง

เจ้าของอนุมัติ R7 แล้ว; ผนวกใน plan ก่อนเปลี่ยน runtime/harness scheduling
