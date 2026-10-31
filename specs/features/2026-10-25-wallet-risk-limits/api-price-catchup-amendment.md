# F18-R6 — bounded read-only price catch-up ที่ API intake

สถานะ: **Approved** — เจ้าของตอบ “อนุมัติ R6” วันที่ 2026-10-27 ก่อน implementation

## ปัญหาและหลักฐาน

W1 `w1-v2-r9` สร้าง baseline100owners×20ordersครบและ partial-fill oracle ผ่าน
แต่ FAILED/Partial ในช่วงวัด หลัง15cycles/210completed commands โดย60s progress
deadlineหมดขณะ reseed20baseline orders หลัง breach/stop/reset ไม่ใช่ baseline setup
ห้ามยกผลนี้เป็น W1ผ่าน หรือเพิ่ม deadlineให้ผ่าน

API ปัจจุบันต้องให้ durable projection cursor เท่ากับ publication watermark
ใน statement ที่อ่าน evidence จึงประเมินว่า READY แม้ book/revision/proof ครบ
producer อาจเลื่อน watermark ระหว่าง monitor snapshot/commit หรือระหว่าง
client อ่าน hint กับตรวจ policyเต็ม ทำให้ opening ถูกปฏิเสธซ้ำอย่างปลอดภัย
short final fence ช่วยให้ monitor commit ที่ watermark ปัจจุบัน แต่ยังไม่ให้
API admission มีหน้าต่างเวลาที่แน่นอนพอในโหลดจริง

หลักฐาน: same-budget isolated-service diagnostic20/20 requests completed;
five-command+reset diagnostic บน100owners/2000baseline ผ่าน21.52s พร้อม
cash delta−1.197901USDT/heldกลับ0/เพิ่ม2fillsตรงจริง ส่วน serial20reseedยัง
timeout60s ทั้งก่อนและหลัง final drain จึงยังไม่พิสูจน์ capacity/SLA เต็ม
เมื่อหยุด concurrent publication แล้ว publish/replay cut ปัจจุบันให้ครบ
ทั้ง engine evaluation/API evidence เป็น READY และ full API policy ผ่าน
ข้อมูลนี้สนับสนุนปัญหา admission/readiness ไม่ใช่หลักฐานว่าแก้ R6 แล้วจะผ่าน

## ข้อที่ต้องอนุมัติใหม่

อนุญาตให้ API derive current risk evidence แบบอ่านอย่างเดียว เมื่อ durable
projection มีเพียง price cursor ตามหลัง แต่ financial snapshot ของ owner ครบ
แทนการถือว่าราคาเปลี่ยนหนึ่ง frame ทำให้ evidence unavailable โดยอัตโนมัติ
นี่เป็นการขยายวิธีตรวจ readiness ที่ API จาก R5 จึงไม่ถือว่าได้รับอนุมัติแล้ว

### เงื่อนไขและวิธีทำ

1. ใช้ shared pure checker สำหรับ API NEW intake ภายใต้ owner lock เดิม และ
   Paper read snapshots ที่ใช้ checker เดียวกัน เพื่อให้ UI readiness สอดคล้องกับ
   intake โดย GET ต้องคง consistent read snapshot และไม่สร้าง mutation/hint
   ไม่เปลี่ยน ENGINE matching/financial gate หรือเปิด Live
2. ต้องตรง owner/mode/wallet/episode/setting revision และ F14 source revision/proof/
   position completeness, latest financial boundary ต้อง replayครบ และทั้ง
   owner/evaluation ต้องไม่มี replay_pending ข้อมูลด้านการเงินไม่ครบยัง unavailable
3. ถ้า price cursor ตามหลังไม่เกิน100frames อ่านทุก committed frame ผ่าน
   `read_frames` เดิม ตรวจ count/order/checksum/typed price/readiness ครบ
   ประเมินทุก frame กับ book ที่ owner lockตรึงไว้ด้วย core evaluator เดิม
   ไม่ skip/coalesce frames ไม่ข้าม boundary ไม่ใช้ naked Decimal/float
4. หากพบ transient breach แม้ราคาฟื้นแล้ว ต้อง refuse พร้อม durable evaluation
   hint เดิม ไม่เขียน latch/audit/stop/baseline/financial state ใน API และไม่แสดง
   latch ที่ยังไม่ durable เป็นผลสำเร็จ
5. หากไม่มี breach และ cut ปัจจุบันพร้อม จึงใช้ pure result ตรวจ intakeได้
   ทุก intakeยังตรวจ policyเต็ม ไม่เชื่อ scheduling hint เป็น authorization
   ENGINE ต้อง replay/ตรวจแบบ fully fenced ใหม่ก่อน admission/fillจริงตามเดิม
6. เมื่อเกิน100frames, pending, source/boundary mismatch หรือ journalหาย/เสีย
   ให้ unavailable เหมือนเดิม ไม่เพิ่ม timeout หรือเปิด bypass

ไม่เปลี่ยนสูตร/limit/reset/allowance/fee/quantity/PnL, idempotency, CPU/RAM/pools,
live defaults หรือ role grants ไม่มี API financial writes และไม่มี Live orders
คง W1/W2/W3 เวลา10/5/30นาที,100×20, rates10/100/10, cycle60s,
p95<=250ms/p99<=1s และทุก ready evaluation<=1s รวม financial/resource oracles

## งานและการตรวจหลังอนุมัติ

- ผนวก protocol นี้ใน plan ก่อนแก้ `infra/risk_limits/views.py` และ `policy.py`
  reuse `read_frames`, core evaluator และ refusal/hint path เดิม
- Tests: fresh price tail, transient breach→recovery, unavailable→recovery,
  missing/corrupt/overflow100frames, financial revision/boundary/reset race,
  false READY hint, API cannot write latch/เงิน, owner/mode isolation,
  full ENGINE recheck blocks a newer breach after API accepts
- ตรวจ GET Paper trade/risk snapshot กับ NEW ใช้เกณฑ์ readiness เดียวกัน
  source/evaluated timestamps ต้องระบุ snapshotจริง และไม่แสดง API-observed
  breach เป็น durable latch จน engine commit ไม่ใช้ UI readiness เป็น authorization
- ตรวจ callers/contracts/safety ที่ได้รับผลกระทบ ใช้ full regressionเดิมเฉพาะ
  ผลที่ยัง valid; ไม่ลดเกณฑ์หรือรันซ้ำชุดเดิมโดยไม่มีเหตุผล
- รัน reseed reproduction เดิมก่อน W1; เมื่อแก้นิ่งรัน W1/W2/W3ทีละชุด และ
  W4เฉพาะ recoveryที่ผลได้รับผลกระทบ เก็บ Failed/Partial เดิมทุกครั้ง
- หากยังผ่านไม่ได้ให้คง admissionปิด/Failed ไม่ประกาศ Completed
