# F-20 — ส่วนต่อประสานกลยุทธ์ + วงจรชีวิตบอท — Requirements

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-19 หลังปิด NC-F20-01..04**
วันที่: 2026-11-19 (Asia/Bangkok)
Branch: `feature/f-20-bot-lifecycle`

## ทำไมต้องมี

ระบบต้องมีขอบเขตกลางระหว่างกลยุทธ์กับผู้ดำเนินการเทรด เพื่อให้บอททำงานต่อได้
โดยไม่ต้องเปิดเว็บ ใช้ตรรกะเดียวกันใน Paper/Live และหยุดหรือกู้คืนได้โดยไม่สั่งซ้ำ
F-18/F-19/F-37 มีข้อกำหนดที่รอเชื่อมกับบอทจริง ส่วน F-21 ต้องใช้ contract นี้
เพื่อเพิ่มกลยุทธ์โดยไม่เขียนการส่งออเดอร์หรือวงจรชีวิตใหม่ทุกครั้ง

แผง Paper Spot ปัจจุบันเป็น UI ที่ปุ่มเริ่มยัง disabled ตาม requirements วันที่
2026-11-13 ชื่อ `Grid Close System` ใน selector ไม่ใช่ข้อกำหนดกลยุทธ์ที่อนุมัติแล้ว
และไม่ใช่หลักฐานว่าเริ่มบอทได้

## ขอบเขต

### ทำใน F-20

- Contract ข้อมูลเข้า ผลการตัดสินใจ และสถานะของกลยุทธ์ โดยแยกจาก execution
- วงจรชีวิตเริ่ม ทำงาน พัก หยุด เปิดกลับ และ recovery หลัง restart/takeover
- Durable authority สำหรับ bot run, สาเหตุหยุด/พัก และความคืบหน้าที่จำเป็นต่อการกันคำสั่งซ้ำ
- การเชื่อม common order admission, Paper execution, risk, kill switch, protection
  และ supported-symbol catalog ตาม contracts เดิม
- หน้าสถานะและควบคุมบอทของเจ้าของบัญชี รวมเริ่ม/หยุด/เปิดกลับ; การเลือกกลยุทธ์และพารามิเตอร์อยู่ F-21 ตาม NC-F20-02
- Contract/parity/isolation tests รวม test strategy ที่ใช้เฉพาะการทดสอบ ไม่เผยแพร่ให้เทรดจริง

### ไม่ทำใน F-20

- สูตรเข้า/ออก, Grid, การแบ่งงบ/ขนาดไม้, defaults, parameter editor และการเผยแพร่
  กลยุทธ์ตัวแรก เป็น F-21; ไม่อนุมานกฎจากชื่อบอทหรือ indicator
- Backtesting, AI, กลยุทธ์ที่ผู้ใช้เขียนเอง, Futures หรือหลายบอทเกินเพดานเดิม
- Live executor/reconciliation/activation แทน F-22/F-23/F-24 และช่องทางแจ้งเตือน
  แทน F-26/F-36/F-27; ไม่เปิด production admission หรือ Live ด้วยการ merge F-20
- เปลี่ยน loss formula/limit/reset, TP/SL failure policy, Kill Switch SLA,
  สิทธิ์ admin หรือกฎเปลี่ยน MANUAL/BOT
- ปลด disabled ของแผง Paper Spot เพียงเพราะมี lifecycle; ต้องผ่าน F-21 และ
  activation gates ที่เกี่ยวข้องก่อน พร้อมแก้ขอบเขต UI-only เดิมอย่างชัดเจนใน spec

## ข้อกำหนด

### ส่วนต่อประสานกลยุทธ์

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | กลยุทธ์พึ่ง `core` เท่านั้น ไม่อ่านฐานข้อมูล/ไฟล์/นาฬิกา ไม่ใช้ค่าสุ่ม เครือข่าย credential หรือเรียก executor; engine ประกอบ dependencies และส่ง inputs ที่จำเป็นให้ | architecture §1–3; mission §8 |
| RQ-02 | Contract ระบุตัวตนและรุ่นกลยุทธ์ รุ่น/ค่าพารามิเตอร์ ขอบเขตคู่เทรด/timeframe และข้อมูลที่ต้องพร้อม รวมการประกาศว่าต้องมี TP/SL หรือไม่; เงื่อนไข trigger, warm-up และกฎเทรดเฉพาะตัวต้องมาจาก requirements ของกลยุทธ์ที่อนุมัติ ไม่กำหนดให้ทุกกลยุทธ์ซื้อขายเมื่อแท่งปิดโดยปริยาย | mission C-6; trading-safety §11; F-11; F-21 |
| RQ-03 | Input เป็น snapshot ที่ระบุแหล่งข้อมูล/เวลา/รุ่นที่ตรวจสอบความสอดคล้องได้ พร้อมตลาด indicator จาก backend สถานะบัญชี/order/position และสถานะกลยุทธ์ที่จำเป็น; ข้อมูลขาด ไม่พร้อม หรือยัง warm-up ไม่ครบต้องไม่กลายเป็นสัญญาณซื้อขายโดยใช้ศูนย์หรือข้อมูลเก่าแทน | tech-stack §3; trading-safety §5/6/12; F-09/F-11 |
| RQ-04 | Output แยกการไม่ทำอะไร ออกจากคำสั่งที่ตั้งใจส่งและสถานะกลยุทธ์ถัดไป; intent ไม่ใช่ order ที่ส่งสำเร็จ การยอมรับ/ปฏิเสธ/partial fill/cancel/unknown ต้องใช้ผลจริงจาก execution contract กลางในการปรับสถานะต่อ ไม่ถือว่ามี position เพียงเพราะเกิด signal | ADR-004; trading-safety §3/4/10 |
| RQ-05 | เมื่อ inputs รวมเวลา พารามิเตอร์และสถานะเหมือนกัน ต้องได้ decision และสถานะถัดไปเหมือนกันใน Paper/Live ใช้ implementation เดียวกัน; เงิน/ราคา/ปริมาณใช้ `Money`/`Quantity` จาก `tiewtrade.core.money` และ numeric contracts เดิม ไม่ใช้ float หรือสร้างกฎปัดใหม่ | AGENTS.md กฎ 6; ADR-004; F-02/F-11 |
| RQ-06 | Run ที่สร้างแล้วต้องอ้างอิง strategy/config version ที่กู้คืนได้ การ deploy หรือแก้รายการกลยุทธ์ต้องไม่สลับตรรกะหรือพารามิเตอร์ของ run เดิมเงียบ ๆ; หากโหลดรุ่นเดิมหรือ state ที่เข้ากันไม่ได้ ห้ามเริ่ม/ทำงานต่อโดยเดาค่าแทน | deterministic recovery; trading-safety §10; ADR-004 |

### วงจรชีวิตและการควบคุม

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-07 | ทุก run มีเจ้าของ บัญชี โหมด และ identity ชัดเจน เปลี่ยนโหมดภายหลังไม่ได้; เพดานแยกโหมดต่อบัญชี: Paper 1 บอท และ Live 1 บอท ตามคำตัดสิน NC-F20-01 ไม่ใช่ 1 บอทต่อคู่เทรด และการมี Paper ไม่ให้สิทธิ์เปิด Live | mission §5; F-08 RQ-7; trading-safety §1 |
| RQ-08 | เริ่มได้เมื่อบัญชีเลือก BOT และมีหลักฐานความพร้อมครบตามโหมด: กลยุทธ์/ค่าตั้งที่อนุมัติ ตลาดและข้อมูลบัญชีพร้อม กระทบยอดเสร็จ เพดานขาดทุนและ loss evaluation ใช้ได้ ไม่มี stop/latch ที่ห้าม และไม่ละเมิดเพดานบอท; Paper MANUAL ที่ไม่ตั้ง loss limit ไม่ใช่ข้อยกเว้นของ BOT; การเริ่มไม่เลือก BOT หรือเปิด Live ให้อัตโนมัติ | F-08 RQ-4..7; F-18; trading-safety §1/3/5/12/13 |
| RQ-09 | แยกคำขอเริ่มที่รับไว้/กำลังตรวจ ออกจากบอทที่ทำงานจริง และแยกกำลัง recovery, พักชั่วคราว, หยุดค้าง พร้อมเหตุผลที่ตรวจสอบได้; สถานะบอทหยุดไม่เท่ากับออเดอร์จัดการครบ ใช้ stop progress ทั้ง 3 สถานะของ F-19 ต่อ | F-19 RQ-01..23; frontend §5 |
| RQ-10 | การหยุดใช้ authority/cutoff และ order handling ของ F-19 ไม่สร้างปุ่มหยุดอีกความหมายหนึ่ง; หยุด decision ใหม่ทันทีโดยไม่รอ cancel และไม่เปลี่ยน BOT เป็น MANUAL; reconciliation, cancel, protection และการลดความเสี่ยงตามกฎเดิมยังดำเนินต่อ | trading-safety §8/10/11; F-19 |
| RQ-11 | ไม่มีราคาที่เชื่อถือได้หรือข้อมูลบัญชีไม่พร้อมต้องพักบอท ห้ามออก decision จากข้อมูลที่ไม่พร้อม; เมื่อข้อมูลกลับมาและกระทบยอดเสร็จให้ประเมิน loss ใหม่ก่อนทำงานต่อ ถ้าชน limit ให้หยุดค้าง การฟื้นของข้อมูลต้องไม่ล้าง stop/latch สาเหตุอื่น | trading-safety §6/12/13; F-18 |
| RQ-12 | แยก cause ที่อนุญาตให้ทำงานต่อเองหลัง crash/deploy ออกจาก user/platform/system stop; restart/takeover ต้องกู้ state และกระทบยอดก่อนทำงานต่อ หากไม่มีหรืออ่าน cause ไม่ได้ให้คงหยุด การเปิดกลับต้องใช้สิทธิ์ หน้าสรุป cause-specific proof และข้อยกเว้น 2FA เดิมของ F-19 ไม่ใช่สร้าง run ใหม่เพื่อข้าม stop | trading-safety §8/10; F-19 NC-F19-02 |
| RQ-13 | ต้องบอกผู้ใช้ได้ว่าเหตุใดเริ่มไม่ได้/พัก/หยุด มี position ใดค้างและการป้องกันอยู่จริงหรือไม่; แจ้ง abnormal stop ตาม §11 โดยไม่ปิดไม้หรือตั้ง SL เพิ่มเอง ยกเว้น protection failure policy ที่อนุมัติใน F-17 | trading-safety §11; F-17 |
| RQ-14 | ตาม NC-F20-03 เริ่ม run ใหม่หรือเปลี่ยนกลยุทธ์ได้เมื่อพิสูจน์ว่าไม่มี position/order ที่ระบบดูแลในขอบเขตบัญชีและโหมดนั้น; หากหลักฐานไม่พร้อมต้องปฏิเสธ ห้ามรับช่วง inventory หรือยกเลิก/ขาย position เพื่อให้เริ่มได้เอง การเปิดกลับ run เดิมพร้อมรายการเดิมใช้ F-19 และต้องไม่ทำประวัติความรับผิดชอบของรายการเดิมหาย | เจ้าของตัดสิน NC-F20-03 วันที่ 2026-11-19; mission §5; trading-safety §8/11 |

### Persistence, concurrency และ execution

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-15 | Bot lifecycle และความคืบหน้าที่จำเป็นต่อ recovery เป็นข้อมูลใน PostgreSQL ไม่พึ่ง browser, process memory, sticky session หรือ Redis เป็นแหล่งจริง; ปิดเว็บ restart/redeploy และเปลี่ยน instance ต้องไม่สูญเสียสถานะหรือเปิดบอทที่หยุดไว้ | AGENTS.md Stateless; architecture §5; tech-stack §5/7 |
| RQ-16 | คำขอเริ่ม/หยุด/เปิดกลับที่ซ้ำหรือ timeout ต้องตรวจผลเดิมได้และไม่สร้าง run/transition/order ใหม่ซ้ำ; inputs/execution events ซ้ำหรือผิดลำดับต้องไม่เกิด financial side effect ซ้ำ มี durable linkage ระหว่าง run, decision และ order ที่ตรวจย้อนหลังได้ | trading-safety §4/8/9/10 |
| RQ-17 | หลาย API/engine instances ต้องคง single writer ต่อบัญชี ใช้ transaction/concurrency control ของระบบเดิม; concurrent start, stop, loss latch, catalog withdrawal, account-use change และ worker takeover ต้องไม่ให้ผู้เขียนเก่าหรือ decision จากก่อน cutoff สร้างความเสี่ยงหลังถูกห้าม | architecture §4; AGENTS.md Stateless; F-18/F-19/F-37 |
| RQ-18 | ทุก intent ของบอทผ่าน admission และ safety gates กลางเดียวกับคำสั่งอื่น ไม่มี direct execution path; ตรวจ readiness/stop/risk/catalog และข้อจำกัดที่เกี่ยวข้องอีกครั้งก่อน execute ไม่อาศัยเพียงผลตรวจตอนเริ่ม run; บอทไม่กำหนดเองว่าคำสั่งเป็น reduce-only | trading-safety §3/4/8; F-16; ADR-004 |
| RQ-19 | เก็บ decision progress/state และ durable intent ให้กู้คืนสัมพันธ์กันได้; crash ก่อน/หลัง commit, Redis loss หรือ acknowledgement หายต้องไม่ทำ intent หายแล้วเดิน state ต่อ หรือสร้างคำสั่งใหม่แทนใบที่ยัง unknown; replay/catch-up ต้องไม่กลายเป็นการส่งสัญญาณย้อนหลังโดยไม่มี policy ของกลยุทธ์รองรับ | architecture §5; trading-safety §4/10; ADR-004 |
| RQ-20 | Strategy exception, output ผิด contract หรือกู้ strategy version/state ไม่ได้ต้องหยุดค้างเฉพาะ run คง position/การป้องกันเดิม และแจ้งผู้ใช้ถึงเหตุและ exposure; ไม่ส่ง output ที่ไม่สมบูรณ์ ไม่ retry หรือสลับรุ่นอัตโนมัติ เปิดกลับเมื่อมี cause-specific proof ว่าแก้แล้วและผู้ใช้รับทราบตาม F-19 คงงาน reconciliation/protection ที่จำเป็นและไม่ให้ผู้ใช้อื่นหยุดตาม | เจ้าของตัดสิน NC-F20-04 วันที่ 2026-11-19; backend §4; trading-safety §10/11 |
| RQ-21 | Consume durable catalog withdrawal event ของ F-37 เพื่อหยุดบอทที่เทรดคู่ที่ถูกถอนและบันทึกเหตุแจ้งผู้ใช้; duplicate/reordered delivery หรือ restart ต้องไม่ทำให้เปิดต่อ ไม่ขาย position/ยกเลิก TP/SL และไม่ให้การเพิ่มคู่กลับปลุกบอทโดยปริยาย | mission §6; F-37 Q-7; trading-safety §3/8/11 |
| RQ-22 | กลยุทธ์ประกาศ protection requirement และ intent ผ่าน F-17; partial fill ต้องได้ protection ตามขนาดจริง และ failure ของบอทใช้ policy ที่อนุมัติแล้ว ไม่เพิ่ม SL หรือตาข่ายความเสี่ยงใหม่ ชื่อกลยุทธ์ไม่มีสิทธิ์ข้ามกฎเหล่านี้ | trading-safety §11; F-17; ADR-004 |

### สิทธิ์ การแสดงผล และการตรวจรับ

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-23 | ตรวจเจ้าของ/โหมดที่ server พร้อม RLS และ CSRF/session controls เดิม; รหัส run ของผู้อื่นได้ not found ไม่เผยข้อมูลหรือผล decision; client เปลี่ยน mode/run ID แล้วข้ามสิทธิ์ไม่ได้ API ไม่แก้ trading state โดยตรง | security §1–4; database §3/5; architecture §3; ADR-004 |
| RQ-24 | คำขอควบคุม transition และเหตุที่กระทบการเทรดต้องมี audit ที่แก้ย้อนหลังไม่ได้ พร้อม actor/cause/scope/เวลา/identity ที่เชื่อม order ได้; ถ้าบันทึก durable authority/audit ไม่สำเร็จ ห้ามตอบสำเร็จหรือสร้างความเสี่ยงต่อ ห้ามมี credential/token หรือ raw exception ที่มีข้อมูลลับ | trading-safety §9; database §4; security §4; F-16 |
| RQ-25 | รวมหน้าสถานะและควบคุมบอทตาม NC-F20-02 โดยต้องต่อยอด `frontend/src/PaperBotPanel.tsx` และ controls เดิม ยึด admin template/component กลาง รองรับไทย/อังกฤษ keyboard light/dark และ responsive; ใช้ server state ไม่คัดลอกเป็น business authority ใน browser แสดงโหมดและเหตุไม่พร้อมชัดเจน ไม่สร้างกลยุทธ์/งบ/ผลตอบแทนสมมติ | frontend §1–6; Paper Spot Bot Panel requirements |
| RQ-26 | ต้องพิสูจน์ lifecycle, replay/idempotency, crash/takeover และ stop/risk/catalog races กับ PostgreSQL จริงในส่วนที่ mock พิสูจน์ไม่ได้ รวม Paper/Live domain parity และ owner/mode isolation; tests ไม่ส่ง Live order และ test strategy ต้องไม่เข้าถึง production strategy catalog | testing §3–7; ADR-004 |
| RQ-27 | ผลตรวจ F-20 ไม่ปิด dependencies ของ feature อื่นอัตโนมัติ; ต้องมี integration evidence ของ F-17/F-18/F-19/F-37 ตาม contract จริงก่อนรับรองส่วนบอท ใช้ Feature gates ก่อน merge และติดตาม Batch/Release เป็น Pending Full Validation จนถึง checkpoint ตาม testing §7 | roadmap ชุดที่ 6; testing §6–7; validation ของ dependencies |

## ของเดิมที่เกี่ยวข้อง

รายการนี้เป็นจุดอ้างอิงสำหรับจัดทำ plan หลังอนุมัติ ไม่กำหนด API/schema/worker design ล่วงหน้า:

- `backend/src/tiewtrade/strategies/__init__.py` — package boundary สำหรับกลยุทธ์
- `backend/src/tiewtrade/core/trading_account.py` — MANUAL/BOT เดิม
- `backend/src/tiewtrade/core/money/` — ชนิดข้อมูลเงิน/ปริมาณเดิม
- `backend/src/tiewtrade/services/engine/` — composition ของ Paper order, risk และ kill switch
- `backend/src/tiewtrade/infra/risk_limits/` — durable risk/stop และหลักฐานความพร้อม
- `frontend/src/PaperBotPanel.tsx`, `frontend/src/KillSwitchControls.tsx` — แผงและ controls เดิม
- `specs/decisions/004-shared-paper-live-trading.md` — shared domain/execution boundaries
- `specs/features/2026-11-13-paper-spot-bot-panel/requirements.md` — UI-only scope และ amendments

## กฎความปลอดภัยที่เกี่ยวข้อง

ยึด `specs/standards/trading-safety.md` §1–6 และ §8–13 โดยเฉพาะการแยกโหมด
single writer, durable intent, กระทบยอดก่อนเริ่ม, พักเทียบกับหยุด, cause-specific resume,
การคง protection และ loss latch ใช้รายละเอียดที่อนุมัติใน F-17/F-18/F-19/F-37 ต่อ
ไม่คัดลอก SLA สูตรเงิน หรือ policy retries มาเปลี่ยนใน F-20

## คำตัดสินเจ้าของ — 2026-11-19

- **NC-F20-01 — Closed:** เจ้าของเลือก “แยกโหมด: Paper 1 บอท และ Live 1 บอท”
  แทนการนับรวม 1 บอทข้ามโหมดในถ้อยคำเดิมของ mission/F-08; ไม่เปลี่ยนกฎ
  MANUAL/BOT, single writer, mode isolation หรือด่านเปิด Live
- **NC-F20-02 — Closed:** เจ้าของเลือก “รวมหน้าสถานะและควบคุมบอท; การเลือก
  กลยุทธ์/พารามิเตอร์อยู่ F-21” คงการปิดปุ่มเริ่มจน dependencies/activation gates พร้อม

- **NC-F20-03 — Closed:** เจ้าของเลือก “เริ่ม run ใหม่เมื่อไม่มี position/order ที่ระบบดูแล;
  run เดิมเปิดกลับพร้อมรายการเดิมได้ตาม F-19” ใช้กับการเปลี่ยนกลยุทธ์ด้วยตามคำถาม
  ไม่ให้ run ใหม่รับช่วงรายการเดิม โดยตรวจในขอบเขตบัญชีและโหมดของ run
- **NC-F20-04 — Closed:** เจ้าของเลือก “หยุดเฉพาะ run คง position/การป้องกันเดิม
  แจ้งผู้ใช้; เปิดกลับเมื่อมีหลักฐานว่าแก้แล้วและผู้ใช้รับทราบตาม F-19”
  คง reconciliation/protection และกฎ protection failure ของ F-17 ตามเดิม

คำตอบทั้งสองรอบปิด NC-F20-01..04; ต่อมาเจ้าของตอบ “approve” วันที่ 2026-11-19
อนุมัติ requirements ทั้งฉบับ ไม่ใช่การอนุมัติ plan/validation หรือการเปิดใช้งานบอท

## ยังไม่ชัด — Needs Clarification

ไม่มี Needs Clarification ของ F-20 ค้างอยู่จากรายการ NC-F20-01..04

รายละเอียดกลยุทธ์ เช่น trigger/catch-up, indicator warm-up, ความหมายงบรวม การจองงบ
การแบ่งไม้และการเปลี่ยนพารามิเตอร์ เป็น requirements ของ F-21 ไม่ใช้การอนุมัติ F-20
แทนการอนุมัติกฎเหล่านั้น F-20 ทดสอบ contract ด้วย fixtures ที่ไม่เปิดใช้เทรดจริงได้
แต่ยังรับรอง end-to-end กลยุทธ์จริงหรือ activation ไม่ได้

## จุดหยุดถัดไป

Requirements ได้รับอนุมัติแล้ว จัดทำ `plan.md` กับ `validation.md` ได้
เจ้าของอนุมัติ plan และ validation ฉบับหลังรีวิวแล้ววันที่ 2026-11-19 เริ่ม implementation ตามแผนได้ ภายใต้ด่านเปิดใช้งานเดิม
