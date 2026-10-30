# F18-R28 — ขอบเขตความจุ Paper และ W2 แบบ bounded saturation

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-10-29**
วันที่: 2026-10-29

## 1. เหตุผลและสิ่งที่ต้องตัดสินใจ

เจ้าของต้องการรองรับ 100 กระเป๋าพร้อมกันและลดการพัฒนาที่วนทดลองหลายวัน
W1 ผ่านบน VM 3 GiB: 10 logical commands/s, 100 owners ×20 baseline orders,
6,000 commands/1,200 cycles, RESET 100 รายการ และ R25/financial/resource gates ผ่าน
ส่วน W2 เดิมกำหนด 100 commands/s ×300s =30,000 commands/6,000 cycles
ครบภายใน 360s แต่ล้มที่ deadline; ประวัติ Failed ต้องคงไว้

หลักฐานเดิมชี้ cycle มัธยฐาน 21.455s เทียบ nominal interval 5s ต่อ owner
scheduler ปัจจุบันเป็น closed-loop: รอ cycle เดิมก่อนส่งงานถัดไป จึงไม่ได้เสนอ
100 API requests/s จริงเมื่อ owner ยุ่ง ข้อมูล dispatch ล่าสุดชี้ processing มี
ต้นทุนมากกว่า scan/claim แต่ยังเลือก optimization ที่พิสูจน์ว่าถึง 100/s ไม่ได้
ดูรายละเอียดและ source/configuration ใน evidence/m5-final-candidate.md

**ข้อเสนอนี้ปรับการรับรองเป็น client-bounded saturation ของ 100 กระเป๋า**
ไม่ใช่ server/API overload certification ที่ 100 incoming requests/s
เป็นการระบุขอบเขตทดสอบให้ตรงกลไกจริงก่อนปิด Paper validation

หากต้องรับรอง 100 incoming API requests/s จาก clients อิสระ ต้องเลือกอีกขอบเขต:
เพิ่ม authoritative server admission/queue bounds และทดสอบ open-loop จริง
ปัจจุบันมี throttle NEW/CANCEL รายผู้ใช้ 20/s แต่ไม่มี global queue bound ที่รับรองแล้ว
งาน server backpressure นี้ไม่ถูกอนุมัติหรือถือว่าพิสูจน์แล้วโดย R28

## 2. ขอบเขตความจุที่เสนอให้รับรอง

- Paper ระยะแรก: W1 100 owners ×20 active baseline LIMIT orders, 10 logical
  commands/s ตาม deterministic five-command mix เดิม บน configuration ที่ผ่าน
- W2: saturation ของ clients 100 owners ที่ใช้ workflow เดิมและ backpressure
  หนึ่ง active cycle ต่อ owner; nominal demand 100 logical commands/s นาน 300s
- ไม่อ้างว่า 10/s เป็นค่าสูงสุดของระบบ หรือ 100/s เป็น throughput ที่ทำได้จริง
  ไม่อ้าง front-door HTTP/network capacity จาก harness ที่เรียก shared intake
- W1/W3/W4, F15 profile ทั่วไป, F16 HTTP contracts, Live และ bot ไม่เปลี่ยน
  server overload นอกขอบเขตข้างต้นยังไม่รับรอง ไม่ประกาศว่าเพดาน test driver
  เป็น production queue cap หรือเงื่อนไขที่ backend บังคับกับทุก client

## 3. W2 demand, backpressure และ deadline

1. ตรึง dataset/ทรัพยากร/flags เดิม: 100 owners ×20 baseline orders, book/price
   cadence เดิม, VM UI 3 GiB, app/risk/PG/Redis CPU/RAM/pools เดิม, R10+R22,
   monitor 4 ไม่มี diagnostic flags ใน acceptance
2. ตรึง 6,000 cycle slots/30,000 planned logical commands ก่อนเริ่มวัด
   nominal owner interval 5s; owner offset ตาม manifest เดิม ทุก slot มี owner,
   cycle index, due time และ deterministic order/key identities ไม่ซ้ำ
3. เมื่อถึง slot ถ้า owner ว่างจึงเริ่ม five-command positive cycle เดิม ถ้า owner
   ยังมี active cycle ให้บันทึก `NOT_SUBMITTED_BACKPRESSURE` สำหรับ slot นั้นทันที
   ไม่ส่ง request, ไม่สร้าง order/receipt, ไม่เลื่อน slot ไปสะสมเป็นคิวรอภายหลัง
4. เพดาน **test driver**: active cycles ≤100 และแต่ละ owner ≤1; workflow เดิม
   ส่ง logical command แบบต่อเนื่องทีละรายการ ไม่เพิ่ม concurrency/workers/pools
   producer ต้องเดินครบทุก slot แม้ owner ยุ่ง ไม่ใช้การรอ owner เพื่อหยุด demand clock
5. หยุดเริ่ม cycle ใหม่เมื่อ elapsed ≥300s; cycle ที่เริ่มแล้วต้องทำจบตาม deadline
   เดิม ไม่ cancel admitted trading work เพียงเพื่อให้ตัวเลขผ่าน
   global drain จบไม่เกิน elapsed 360s และต้องมี automatic timeout/cleanup guard
   ไม่รอให้ทุก cycle คืนค่าก่อนจึงตรวจว่าเกินเวลาเหมือน scheduler เดิม
6. คง R26: normal cycle ≤60s; selected first recovery ≤120s เฉพาะ phase ที่บันทึก,
   normal ≤60s และ outer ≤180s; inner request/stop/price deadlines เดิม
   selected first slot ต้องเริ่มตามเดิมและผ่านก่อน scheduled RESET เริ่มที่180s
7. เกณฑ์ progress เสนอ: completed positive cycles ≥600 (≥3,000 logical commands)
   ภายใน 300s+60s drain และทุก owner ต้องจบอย่างน้อยหนึ่ง cycle
   นี่คือ baseline floor ที่อิง normal rate 10/s ×300s โดยใช้ drain เดิม
   ไม่รับรอง steady-state 100/s; ต้องรายงาน actual offered/accepted/completed rates
8. ทุก started cycle ต้อง COMPLETE; rejected/failed/timed-out positive cycles เป็น
   Failed ไม่เปลี่ยนเป็น backpressure ย้อนหลัง คำสั่งที่ส่งหรือ commit แล้วห้ามนับ
   เป็น NOT_SUBMITTED แม้ client จะยังไม่เห็นผลหรือเกิด UNKNOWN

## 4. Oracle และข้อมูลที่ต้องครบ

- `STARTED + NOT_SUBMITTED_BACKPRESSURE = 6000` cycle slots; ไม่ใช้ unstarted
  demand เป็น submitted/accepted/rejected requests หรือ completed throughput
- ตอนปิดงานต้อง `started_cycles = completed_cycles`, active/unknown cycles =0;
  `logical_offered = logical_completed = 5 × completed_cycles`, rejected =0
  setup, risk scenarios, RESET และ replay counts แยกตามกฎเดิม
- เก็บ row ของทุก slot: owner/index/due/decision time/state; ทุก started cycle
  มี command keys/receipts/outcomes/timing ครบ duplicate slot/order/effect =0
- ใช้ actual completed slot identities และ completed-cycle count ต่อ owner เป็น
  input ของ independent F15 financial oracle เดิม ไม่ปรับ expected ตามผลเงินจาก SUT
  cycle indices อาจไม่ต่อเนื่องเพราะ backpressure; ต้องตรวจ exact ID sets ด้วย
- คงสูตร expected fills/cancels/replays และ selected-scenario adjustments เดิม;
  ไม่ลดการตรวจ balances/positions/reservations/PnL/history หรือข้าม partial cycles
- คง scheduled RESET 100 owners, ≤1/s, due180..279 และ selected owner ท้ายตาม R27
  ทุก RESET/selected restoration ต้อง APPLIED ภายในขอบเขตเวลาเดิม
- Risk R25: ทุก ready input ≤5s, ≥99.9%≤3s ทั้งต่อ owner และรวม; expected inputs,
  unacknowledged, clock errors, late inputs และเวลารอทั้งหมดต้องครบ target1s ยังรายงาน
- Processing p95≤500ms/p99≤1s, resource/connection/5s physical cleanup gates เดิม
  ไม่ตัด busy periods หรือเปลี่ยนช่วง non-fault เป็น fault/backpressure เพื่อซ่อน SLA miss
- หลัง drain ต้องผ่าน deliberate overflow/recovery เดิมครบ โดยแยก phase อย่างเดิม
  ไม่ใช้ backpressure แทนการพิสูจน์ overflow หรือ cancellation/stop progress

## 5. วิธีทำหลังได้รับอนุมัติ

เปลี่ยนเฉพาะ harness; ไม่เปลี่ยน production admission, scheduler/claims, API,
schema, throttle, Money/Quantity หรือ financial fences

ใช้ของเดิม:
- `backend/tests/infra/execution_market/profile_workload.py`: deterministic identities,
  positive-cycle constructors, financial/resource/overflow helpers และ default scheduler
- `backend/tests/infra/risk_limits/profile_workload.py`: production intake path,
  owner isolation, R25 oracle, scenarios/RESET และ cleanup
- `backend/tests/infra/risk_limits/profile_timing.py`: R26 deadline/audit contexts

เพิ่ม scheduler mode เฉพาะ F18 W2: coordinator หนึ่งตัวกับ active cycle tasks
ไม่เกิน100; slot decisions ไม่รอ completion; supervise task failure และ publisher
ด้วย pattern เดิม Global window/drain guard ไม่ทำให้ deadline ของ accepted work ยาวขึ้น
F15/W1/W3 default paths ไม่เปลี่ยน ใช้ per-owner executed-slot counts กับ verifier
และตรวจ independent exact identity sets แทนการสมมติว่า cycles ทุก owner เท่ากัน

Tests ก่อน workload: fake-clock slot conservation/busy-owner skipping/ไม่มี deferred
catch-up burst, fairness/concurrency bounds, boundary300/360, all-started drain,
selected recovery, command failure/UNKNOWN ไม่ถูกนับเป็น skipped, duplicate IDs,
exact-set/per-owner financial oracle, cancellation/join/cleanup และ default F15/W1/W3
contracts; lint/format/types เฉพาะผลกระทบ เพิ่ม DB/caller safety checks เมื่อ diff จำเป็น

เมื่อ checks ผ่าน: frozen candidate/config หนึ่งชุด W2 300s+drain+overflow ตามเดิม
หากล้มให้หยุดเก็บหลักฐาน ไม่ rerun/เปลี่ยนหลายตัวแปรโดยอัตโนมัติ
ห้ามเรียกชุดสั้นว่า acceptance; W1 reuse ได้เฉพาะพิสูจน์ default/callers ไม่เปลี่ยน

## 6. เวลาและสถานะ

ประมาณหลังอนุมัติ: harness/oracle/targeted checks 20–40 นาที แล้ว W2 เตรียม/
วัด/overflow/วิเคราะห์ 10–15 นาที เป็น estimate ไม่รับประกันว่าเกณฑ์ที่เหลือจะผ่าน
แจ้งใหม่ก่อนเกินประมาณการ; ไม่ขยาย scope ไปสร้าง server capacity control โดยเงียบ ๆ

R28 ได้รับอนุมัติแล้ว; ข้อกำหนด/แผน/validation เดิมยังมีผลยกเว้น W2 ที่ R28 แทนที่
W1 Passed; W2 เดิม Failed; W3/W4 ยังไม่เริ่ม; Paper Pending Full Validation,
V22/V23 Pending Dependency ไม่มีผล Failed ถูกเปลี่ยนเป็น Passed ย้อนหลัง
หากอนุมัติ R28 ต้องอัปเดตเอกสารหลักก่อนเขียนโค้ด และต้องมีหลักฐานใหม่บน candidate
ที่ตรวจรับครบก่อนปิด Paper ไม่ถือ F18 Completed จาก amendment นี้

## การอนุมัติที่ขอ

ขออนุมัติทั้งขอบเขตความจุ/เกณฑ์ W2 และวิธี harness/validation ในเอกสารนี้:
รับรอง bounded saturation ตามข้อ2–4 แทนการบังคับ30,000commands/360s และยอมรับว่า
ไม่ได้รับรอง aggregate100incoming APIrequests/s หากต้องการ server overload
certification แทน ต้องหยุดร่างแผน admission/queue control แยกก่อน implementation
