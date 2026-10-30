# F-18 — เพดานความเสี่ยงต่อกระเป๋า — Requirements

สถานะ: **Approved** — เจ้าของตอบ “approve” อนุมัติ requirements และ NC-F18-01..08 วันที่ 2026-10-25
เกณฑ์ปัจจุบัน: **R32 Approved 2026-10-29 — Paper fixture 5Hz**; ดู [amendment](paper-source-cadence-amendment.md) ซึ่งแทนเฉพาะ 10Hz ในข้อความเก่า
โหมดตรวจรับปัจจุบัน: **R33 Approved 2026-10-29 — explicit child publisher** ตาม [amendment](child-acceptance-mode-amendment.md); ใช้เกณฑ์ล่าสุดด้านล่าง
วันที่: 2026-10-25
เกณฑ์ล่าสุด: **R34 Approved — source count ขาดได้ 1/channel/run และ risk ราย owner 99.5% ภายใน3s สำหรับ W1–W3**; [ขอบเขตและการใช้หลักฐานเดิม](paper-acceptance-tolerance-amendment.md)

## ทำไมต้องมี

F-15/F-16 มีทางรับและดำเนินคำสั่ง Paper แล้ว แต่ production NEW admission ยังปิด
เพราะยังไม่มี risk policy จริง F-18 ต้องใช้กฎเพดานขาดทุนจาก trading-safety §13
เพื่อให้การตั้งค่า การนับขาดทุน การชนเพดาน และการรีเซ็ตมีความหมายเดียวกันทั้ง
Paper/Live โดยไม่เปิด Live execution หรือใช้ test policy แทนความปลอดภัยจริง

NC-07 เป็นกฎระดับผลิตภัณฑ์ รายละเอียดตัวเลขและ lifecycle ของ F-18 ได้รับอนุมัติ
ในคำตัดสิน NC-F18-01..08 ด้านล่างแล้ว

## ขอบเขต

### ทำ

- ตั้งค่า อ่านสถานะ และรีเซ็ตเพดานขาดทุนของเจ้าของบัญชี แยก Paper/Live
- ตรรกะนับขาดทุน/ชนเพดาน/รีเซ็ตร่วมกันตาม ADR-004 และ Money/Quantity เดิม
- ประเมินจาก authoritative position/PnL และราคาที่เชื่อถือได้ พร้อมเก็บเหตุการณ์ชนเพดาน
- เชื่อม policy จริงกับ F-15/F-16 ทั้งตอนรับคำสั่งและก่อน execution โดยยังคง gates เดิม
- แสดงค่าเพดาน ผลประเมิน เหตุที่ถูกบล็อก และสถานะราคา/ข้อมูลไม่พร้อมเป็นไทย/อังกฤษ
- วางขอบเขตการเชื่อม stop mechanism ของ F-19 และการจัดการ queued/active orders
  ก่อนเปิด Paper จริงตามคำตัดสิน NC-F18-07

### ไม่ทำ

- Live execution/activation/reconciliation ของ F-22–F-24 หรือ Futures
- เพดานขนาดไม้ leverage drawdown รายวัน หรือ cooling-off เพิ่มเติมที่เจ้าของไม่ได้กำหนด
- เปลี่ยน cost basis, fee/rebate, matching หรือกฎราคาเดิมของ F-14/F-15
- ปิด position อัตโนมัติ หรือยกเลิก TP/SL เพราะชนเพดาน
- ทำ bot lifecycle/strategy หรือระบบแจ้งเตือนทุกช่องทางแทน feature ที่รับผิดชอบ

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | เพดานเดียวที่ระบบเพิ่มจากข้อจำกัดตลาดคือเพดานขาดทุนที่ผู้ใช้กรอก ไม่มี business maximum ของขนาดไม้หรือมูลค่าเพดานขาดทุนที่ตั้ง; ขอบเขตตัวเลขยังอยู่ภายใต้ Money เดิม | trading-safety §13; AGENTS §6 |
| RQ-02 | ต้องกรอกเพดานก่อนเปิด Live และ Paper ใช้กฎเดียวกัน ห้ามสร้างค่าเพดานอัตโนมัติเพื่อให้ผ่าน gate; หน่วย/ช่วงค่าต่ำสุด/จุดบังคับตั้ง Paper ตาม NC-F18-01 | trading-safety §1/13 |
| RQ-03 | แยกสถานะและการตั้งค่าตามเจ้าของและโหมด server กำหนดโหมด ไม่รับ browser mode เป็นอำนาจเปลี่ยนขอบเขต; Admin/Owner ไม่สั่งเทรดหรือปิด position แทนผู้ใช้ | mission §2/4; ADR-004 |
| RQ-04 | ส่วนที่ปิดใช้ realized PnL จาก execution facts ของ F-14 รวมส่วนที่ขายแล้วของ position ที่ยังไม่เป็นศูนย์ ต้องประเมินผลของแต่ละ partial fill ที่ commit แล้วโดยไม่รอ order filled ทั้งใบหรือ position ปิดหมด; ส่วนที่ยังถือใช้ unrealized loss ตามกฎเดิม ห้ามนับ realized ซ้ำในส่วนที่ยังเปิด ไม่ใช้ balance หรือทุนตั้งต้นเป็น PnL; สูตรหักล้างกำไรและฐานหลัง reset ตาม NC-F18-02/03 | trading-safety §13; F-14 RQ-13/NC-45/46 |
| RQ-05 | ชนเพดานแล้วต้องค้างจนผู้ใช้รีเซ็ต ไม่ปลดเองเมื่อราคาเด้งกลับหรือเปลี่ยนวัน; การเพิ่มเพดานไม่ถือเป็นการรีเซ็ตโดยปริยาย | trading-safety §13 |
| RQ-06 | Reset เริ่มนับจากศูนย์ ณ เวลาที่กดและไม่นับขาดทุนค้างเดิมของไม้เปิด ไม่บังคับปิดไม้เพื่อ reset; partial sell/buy เพิ่ม/ปิดไม้และ corrections ต้องมีความหมายชัดตาม NC-F18-03 | trading-safety §13; F-14 correction contract |
| RQ-07 | ทุกคำสั่งเพิ่มความเสี่ยงทั้งมือ/บอทผ่าน gate กลาง และตรวจซ้ำก่อน execution; ห้ามใช้ป้าย SELL เป็นหลักฐานว่าลดความเสี่ยง หรือใช้ UI validation แทน server | trading-safety §3/4; F-16 RQ-7/8; ADR-004 |
| RQ-08 | ชนเพดานห้ามขวางคำสั่งลดความเสี่ยงที่พิสูจน์ได้จริง; คำสั่งลด position ยังผ่านข้อจำกัดคู่ ปริมาณที่ถือหลัง reservations และ durable intent/audit ตามกฎเดิม โดยไม่ต้องผ่าน active catalog หรือเพดานขาดทุน; การยกเลิกใช้ RQ-18 แยกต่างหาก | trading-safety §3/9; NC-F16-01; F-16 RQ-8 |
| RQ-09 | ชนเพดานหยุดบอทในขอบเขตนั้นผ่านกลไกเดียวกับ F-19 ไม่เปลี่ยน BOT เป็น MANUAL ไม่ปิด position ไม่ยกเลิก TP/SL; ต้องครอบคลุมคำสั่งเพิ่มความเสี่ยงที่อยู่ในคิวและการจัดการ active orders ตาม trading-safety §8 ไม่ถือว่าการบล็อก NEW หรือบันทึก stop request อย่างเดียวเท่ากับจัดการครบ; ขอบเขตผู้รับผิดชอบและ checkpoint ก่อน activation ตาม NC-F18-07 | trading-safety §8/13 |
| RQ-10 | เมื่อไม่มีราคาที่เชื่อถือได้ห้ามใช้ราคาเก่าหรือศูนย์แทนเพื่อคำนวณ loss; บอทพักและไม่ประเมินเพดานชั่วคราว กลับมาประเมินทันทีเมื่อราคาและ reconciliation พร้อม โดยไม่ล้างสถานะชนเพดานเดิม | trading-safety §6/10/12/13 |
| RQ-11 | การพักเพราะราคาไม่พร้อมแยกจากการหยุดค้าง; เทรดมือยังใช้กฎราคาเดิมสำหรับเพิ่ม/ลดความเสี่ยง ไม่เพิ่มข้อยกเว้นใหม่; เวลาแจ้งพักตาม NC-F18-06 | trading-safety §6/13 |
| RQ-12 | อ่านข้อมูลเสี่ยงที่ไม่ครบ/ขัดกันต้องแสดง unavailable ห้ามแทนด้วย loss=0 หรือแสดงว่า risk check ผ่าน; บอทไม่ทำงานเมื่อข้อมูลบัญชีไม่พร้อมตาม §12 และเมื่อราคาไม่พร้อมใช้ RQ-10/11; การอนุญาต manual เพิ่มความเสี่ยงขณะ PnL/reconciliation unavailable ใช้ลำดับกฎ §3/12 ตาม NC-F18-08 ไม่อ้างข้อยกเว้นแบบเหมารวม; ลดความเสี่ยงและ cancel ใช้ RQ-08/18 ตามสัญญาเดิม ไม่อ้างว่า Live พร้อมก่อน F-23 | trading-safety §3/6/10/12; F-14 NC-49 |
| RQ-13 | การตั้งค่า/รีเซ็ต/ชนเพดานต้องมี durable audit ตามผู้กระทำ ขอบเขต เวลา และผล; ประวัติ financial/audit เพิ่มอย่างเดียว ไม่เกิดผลซ้ำเมื่อ retry/restart/lost acknowledgement | trading-safety §4/9/10/13 |
| RQ-14 | การประเมิน loss, latch, reset, fills/corrections และ order execution ต้องใช้ authoritative revision และ single-writer protocol เดียวกัน ไม่อนุญาตจาก snapshot ครึ่งก่อนครึ่งหลังหรือข้าม reset ใหม่ | architecture §4/5; trading-safety §3/4/9 |
| RQ-15 | แสดงเพดาน ขาดทุนที่นับ ฐานการนับ สถานะชนเพดาน/พัก/ข้อมูลไม่พร้อม และเวลาข้อมูลให้เข้าใจได้; reset ต้องบอกผลที่เริ่มนับใหม่ทั้งที่ยังถือไม้ติดลบ ไม่ทำ optimistic financial state | frontend standard; trading-safety §13 |
| RQ-16 | ใช้ domain implementation เดียวสำหรับ Paper/Live และ parity fixtures เดียวกัน; แยกเงิน/ข้อมูล/credential/executor จนถึงปลายทาง ห้ามส่ง Live order ใน automated validation | ADR-004; trading-safety §1 |
| RQ-17 | ปิด F-16 V-18 ได้ต่อเมื่อทดสอบ browser→API→engine ด้วย production risk composition จริงครบ loss-limit, unavailable, price outage, reduction และ isolation รวมผลต่อ queued commands และ active manual orders เมื่อชนเพดานตาม NC-F18-07; การเปิด NEW admission ต้องไม่ bypass safety dependencies ที่ยังขาด และห้ามใช้ durable stop request ที่ยังไม่มี consumer เป็นหลักฐานว่าคำสั่งค้างถูกจัดการแล้ว | F-16 validation V-18; F-15 NC-F15-06; trading-safety §8/13 |
| RQ-18 | ชนเพดานต้องไม่ปิดทางผู้ใช้ยกเลิกออเดอร์ของตน; cancel ใช้ ownership/mode/order identity/state, idempotency และ durable intent/audit ตาม F-15/F-16 ไม่ผ่านเงื่อนไขรับออเดอร์ใหม่ เช่น minimum notional/quantity, active catalog, เงินพอหรือมี position ให้ขาย; ห้ามคืน reservation หรือแสดง canceled ก่อนยืนยัน terminal fact และห้ามยกเลิก TP/SL อัตโนมัติเพราะชนเพดาน | F-15 lifecycle/reservations; F-16 RQ-9/10/12; trading-safety §8/9/13 |

## สิ่งเดิมที่ตรวจพบสำหรับขั้นวางแผน

- `backend/src/tiewtrade/core/positions.py`: position/realized/unrealized และ corrections ตาม F-14
- `backend/src/tiewtrade/core/money/`: ชนิดเงิน/ปริมาณและกฎ arithmetic เดิม
- `backend/src/tiewtrade/core/orders.py`: `AdmissionPolicy` และ order contracts
- `backend/src/tiewtrade/core/manual_trading.py` และ `infra/paper_orders/manual_policy.py`:
  manual account policy ที่รับ delegate และใช้ authoritative holding/reservation
- `backend/src/tiewtrade/infra/paper_orders/request_worker.py`, `worker.py`:
  ทางรับและ execution เดิมที่ต้องประกอบ policy จริง
- `backend/src/tiewtrade/infra/paper_orders/trade_views.py`: รายงาน risk policy unavailable เดิม
- F-13 Paper episode reset กับ F-14 append-only correction มีอยู่แล้ว แต่ไม่ใช่ loss reset ของ F-18

รายการนี้เป็นหลักฐานสำรวจ ไม่ใช่ implementation plan; `plan.md`/`validation.md`
จัดทำในขั้นถัดไป และต้องขออนุมัติแยกก่อนแก้โค้ด

## คำตัดสิน NC-F18-01..08 — Closed (2026-10-25)

เจ้าของตอบ **“approve”** อนุมัติ requirements และชุดคำตัดสินทั้ง 8 ข้อวันที่
2026-10-25 หลังแก้ review findings 5 ข้อ คำตัดสินด้านล่างใช้แทนทางเลือกในร่าง
ไม่ถือเป็นการอนุมัติ plan/validation หรือ implementation

| NC | คำตัดสินที่อนุมัติ |
|---|---|
| NC-F18-01 | ใช้ USDT มากกว่า 0 ไม่มีค่าเริ่มต้นหรือเพดานธุรกิจด้านบนภายใต้ Money เดิม; Paper ต้องตั้งก่อนรับคำสั่งเพิ่มความเสี่ยงครั้งแรก Live ต้องตั้งและแสดงให้ผู้ใช้เห็นก่อน activation |
| NC-F18-02 | เลือก A: ใช้ realized สุทธิหลังปรับฐาน reset รวมทุก partial close หักล้างขาดทุนของส่วนที่ยังเปิดได้; unrealized บวกไม่หักล้างไม้ลบ ขาดทุนที่นับต่ำสุด 0 ชนเมื่อ >= เพดาน |
| NC-F18-03 | ยกเว้นเฉพาะขาดทุนค้าง ณ reset ไม่ให้ข้อยกเว้นนั้นสร้างกำไร: −100→เปิด/ปิดที่−130 นับขาดทุน30, −100→เปิด/ปิดที่−70 นับ0 ไม่มีเครดิต+30; ถ้าปิดเป็นกำไรจริงจึงนับกำไรจากต้นทุนจริงตาม F-14 สำหรับไม้เดิม+100→ยังเปิด+20 นับ0 และเมื่อปิด+20 นับ realized+20 ตาม NC-F18-02 ไม่ถือการลดลง80เป็น loss; partial close จัดสรรข้อยกเว้นตามจำนวนที่ขาย/ยังถือ ข้อยกเว้นส่วนที่ขายหมดไปแม้ใช้ไม่ครบ ไม่ย้ายไปใช้กับจำนวนที่เหลือ ซื้อเพิ่มไม่เพิ่มข้อยกเว้น reset ซ้ำตั้งฐานใหม่จากขาดทุนค้างปัจจุบันแทนการบวกทบ; correction ทำให้ unavailable จน rebuild ฐานได้ โดยไม่ล้าง latch |
| NC-F18-04 | เปลี่ยนตัวเลขได้โดยไม่เปลี่ยนฐาน/ปลด latch; ลดเพดานแล้วประเมินใหม่เมื่อข้อมูลพร้อม Paper episode ใหม่เริ่มฐานผลใหม่แต่คงค่าเพดานและ latch จนเจ้าของสั่ง loss reset; เปลี่ยน Live key ไม่ล้างฐาน/ประวัติเอง |
| NC-F18-05 | เกณฑ์ที่อนุมัติ: เมื่อ authoritative price/fill/correction พร้อมและถูกบันทึกให้ engine ใช้ได้ Paper ต้องประเมินและบันทึกผล/latch อย่างน้อย99.9%ของreadyinputsภายใน3วินาที ทั้งต่อownerและทั้งrun และทุกreadyinputภายใน5วินาที โดยตั้งเป้าหมาย1วินาที (R25 Approved2026-10-29); Live คงเกณฑ์ 1 วินาทีและ Pending Dependency จนมีหลักฐานของ Live โดยเฉพาะ แม้ browser ปิด วัดจากเวลาที่ข้อมูลพร้อมในระบบถึงผล durable ไม่รวมเวลาที่ตลาดยังไม่ส่งข้อมูล; ใช้ราคาและ connection/lease freshness ของ F-10 เดิม และตรวจสถานะล่าสุดที่ใช้ได้ซ้ำที่ขอบรับ/ดำเนินคำสั่ง ไม่ใช้กรอบเวลานี้เป็นสิทธิ์ผ่านด้วยข้อมูลเก่า หากพิสูจน์เกณฑ์ไม่ได้ต้องคง admission ปิดและรายงาน Failed/Partial ไม่ผ่อนเกณฑ์เอง |
| NC-F18-06 | ยืนยันพักเพราะราคาไม่พร้อมต่อเนื่อง 5 นาทีแล้วแจ้งเหตุพักผ่านข้อความที่คงอยู่ในหน้า risk/trade; คำเตือนตลาดไม่พร้อม 60 วินาทีของ F-10 ยังทำงานตามเดิม ชนเพดาน/ยกเลิกค้างหรือมีปัญหาแสดงสถานะและแจ้งตามเวลาของ §8/13 ไม่รอครบ5นาที ให้ F-18 รวมข้อความ/สถานะจำเป็นสำหรับ Paper ส่วน notification center/Email/Telegram/LINE รอ F-26/F-36/F-27 ตาม roadmap ต้องบันทึก Pending Dependency และไม่รับรอง Live หรือ F-18 Completed แทนการแจ้งเตือนที่ยังไม่พร้อม |
| NC-F18-07 | รวมผู้ดำเนินการจัดการ queued/active Paper orders และ recovery ที่จำเป็นต่อการชนเพดานไว้ใน F-18 ก่อนเปิด Paper manual จริง ออกแบบ stop contract ให้ F-19 ใช้ร่วมในขั้น plan ไม่ทำหน้าปุ่ม Kill Switch หรือ bot lifecycle แทน F-19/F-20; การรับรองบอทและการเปิดกลับยัง Pending Dependency |
| NC-F18-08 | คำสั่งเพิ่มความเสี่ยงทั้ง manual/bot ของทั้งสองโหมดถูกบล็อกเมื่อคำนวณ loss ไม่ได้หรืออ่าน latch ไม่ได้; latch ที่ชนแล้วต้องบล็อกจน loss reset แม้ข้อมูลอื่นกลับมาพร้อม ลดความเสี่ยง/cancel ใช้สัญญาเดิมโดยไม่ติด loss gate; ให้แก้ trading-safety §12 ให้ข้ออนุญาต manual ขณะข้อมูลบัญชีไม่พร้อมไม่ยกเว้น loss gate ตาม §3/13 โดยคงข้อยกเว้นของการตรวจยอดเบื้องต้นและเงื่อนไข reduce-only เดิม |

## กฎความปลอดภัยที่เกี่ยวข้อง

- trading-safety §1/3/6/8/9/10/12/13 และ ADR-004 ใช้ตามขอบเขต Paper/Live
- **security §1 และ F-06 RQ-6/7:** การขยายเพดานต้องยืนยัน TOTP ใหม่ด้วยกลไกเดิม
  ไม่มี grace period และไม่ใช้ recovery code แทนการยืนยันการเพิ่มความเสี่ยง
  การรีเซ็ตเพดานได้รับยกเว้น TOTP; ทุก route ต้องจัดประเภทตาม F-06
- database/architecture: API รับ durable intent และอ่านภายใต้ RLS;
  engine เป็นผู้แก้ trading state ภายใต้ owner scope และ single-writer เดิม
- testing §7: correctness/safety ตรวจระหว่างพัฒนา ชุดเต็ม performance/workload/
  stress/endurance/resource อยู่ release checkpoint ตาม validation โดยไม่ลดเกณฑ์

## Needs Clarification

ไม่มีข้อเปิดค้างสำหรับ requirements ฉบับนี้ NC-F18-01..08 ปิดด้วยคำอนุมัติข้างต้น
หากขั้นวางแผนพบช่องว่างใหม่ที่เปลี่ยนผลการเทรด ต้องบันทึกใน mission §9 และ
ขอคำตัดสินก่อนแก้ข้อกำหนดหรือ implementation ไม่ใช้ plan เปลี่ยนคำตัดสินนี้

### Paper monitor timing revision — Superseded by three-second revision below

เจ้าของสั่ง “ถ้าผลการทดสอบไม่เกินสองวิ ให้ใช้สองวิ”: ใช้ hard acceptance bound
2s ต่อทุก ready input ของ Paper, target1s. ต้องพิสูจน์บน final candidate ตาม
validation ก่อนรับรองผ่าน ไม่ถือว่าค่าสูงสุด1.70sของ preflight แทนชุดเต็มได้
คง financial-boundary checks, F10 freshness, Live1s และเกณฑ์อื่นเดิมทั้งหมด
ไม่ใช่การรับรองว่าค่านี้มาจาก Binance; ผล Failed เดิมคงไว้ไม่เปลี่ยนย้อนหลัง

### Paper monitor three-second revision — Approved 2026-10-28; superseded by R25

เจ้าของสั่ง “แก้เป็น 3 วินาที” แทนเกณฑ์2sก่อนหน้า: Paper background monitor
ต้องcommitผล/latchภายใน3sต่อทุก ready input โดยคงtarget1s. Live1sและ
financial-boundary checks/freshness/ทุกเกณฑ์อื่นคงเดิม ต้องผ่านvalidationเต็ม
ก่อนรับรองผ่าน; ไม่เปลี่ยนผลFailedเดิมย้อนหลังหรือถือว่า3sรับรองโดยBinance


### Approved Paper processing latency revision — 2026-10-29

เจ้าของอนุมัติปรับ processing p95 เป็น **<=500ms** สำหรับ F-18 Paper integrated
profile `F18_F15_F16_INTEGRATED_V2` เท่านั้น แทนเกณฑ์ที่สืบทอดจาก F-15 <=250ms.
Processing วัด transaction รวมการรอ connection/lock และ commit ตาม instrumentation
เดิม ไม่ใช่เวลาตั้งแต่ส่งคำสั่งจน fill. คง p99<=1s, Paper timing ตาม R25 ด้านล่าง
(target1s), 100owners×20orders, rates/resources, command deadlines, W1–W4 และ
financial correctness/retry/idempotency ทั้งหมด ไม่เปลี่ยน F-15 standalone หรือ
Live criteria. เก็บผล Failed/Partial เดิม ไม่เปลี่ยนผลย้อนหลังเป็น Passed;
ต้องมีหลักฐาน candidate ใหม่ผ่านเกณฑ์ทั้งหมดก่อนรับรอง Paper validation.


### R25 — Approved Paper service target and connection acceptance (2026-10-29)

เจ้าของอนุมัติ [R25](paper-acceptance-flexibility-amendment.md). ฉบับนี้แทนPaper
hardbound3sเดิม:ต่อownerและทั้งrunต้องมีอย่างน้อย99.9%readyinputs commitผล/latch
<=3s และทุกreadyinput<=5s; target1sเป็นข้อมูลรายงาน. ต้องนับexpectedinputs,
unacknowledged,clockerrorsและเวลารอทั้งหมดครบ เก็บรายการ>3sทั้งหมดแยกจากhardmiss>5s.
ยอมรับว่าการบันทึกbreach/เริ่มstopจากbackgroundmonitorอาจช้าถึง5s;ไม่ใช่deadline
stopcompletionหรือการรับรองLive. คงLive1s, freshness,fully-fencedfinancialchecks,
authorization,Money/Quantity,balances/positions,duplicatepreventionและdeadlinesเดิม.

F18 integratedconnectiongateใช้inventoryของactualprocess/role/poolที่ตรึงก่อนวัด
กับPostgreSQLheadroom ไม่ใช้live end<=start+2. ทุกsampleต้องอยู่ในbudget;
ทุกpoolคืนcheckoutครบเมื่อdrain/ปิดworkers และหลังdisposeต้องไม่เหลือappclient
connectionsในisolatedrunDBภายใน5s ยกเว้นqueryผู้ตรวจและobserverPIDsที่ประกาศก่อนรัน.
Unknowninventory/cleanupเป็นFailed/Pending ไม่ถือPassed. คงresourcegatesอื่นและ
100owners×20orders/rates/CPU/RAM/durations/p95500ms/p991sเดิม. เก็บFailedเดิม;
ต้องมีผลใหม่บนcandidateสุดท้ายก่อนรับรองPaper; V22/V23ยังPendingDependency.


### R26 — Approved recovery-scenario timing (2026-10-29)

Owner approved [R26](recovery-scenario-budget-amendment.md). Supersedes the60s
inclusive selected-scenario bound only: ordinarycycles andnormalelapsedexcluding
onlyone recordedbreach_reset phase remain<=60s. Thatphase alone<=120s; selected
firstcycleouterguard<=180s. Innerstop30s/price10s/request60s,load/rates/counters,
R25risk/processing/resources,financialchecks andfinalelapsed/drainboundsunchanged.
ReuseF15scheduler withoptionaltest-onlycyclecontext,default60s unchanged; F18
tracksoneeligiblephase and itsstages/20reseedidentities usingmonotonic time.
No productionAPI/schema/pools orruntimechanges. OldFailedresultsnotrelabeled;
targetedbudget/default/cancelcontracts beforeonenativeW1,stoponfailure/noautoretry.


### R27 — Approved explicit under-load RESET schedule (2026-10-29)

Owner approved [R27](declared-reset-workload-amendment.md). Remove extraendRESET
frompositivecycles; keep5tradingcommands/60s,R26one120srecovery/180stotal and
selectedcorrection. Add100scheduledRESETs/run,one/owner,<=1/s,from180s,selectedlast,
withdeclaredfault-awareoffsets. Requireselectedrecoverycompletebeforefirstoffer;
noautoextension. EachRESET60sincludingAPIpoolwait;independentcounters/IDs/timing,
all100completebyexistingduration+60s;noalteredpositivecounts/rates/durations.
DoesnotcertifyRESET20/s or100simultaneousRESETs,notaproductionratelimit.
R25/financial/authorization/resource/poolgates unchanged;oldFailedretained.
ReuseFixture.mutation/F15FaultGate/producer-supervision andoracles. Serialize only
per-ownerfinancial-marker evidence reads/cursorupdates whenRESET andfillsrecord
concurrently; no newfinancialwriteSQL/locks. CHECK is nonaccepting anddoesnot
substituteitsreducedownerfixtureforthe100RESETacceptanceprofile.

R27-A approved 2026-10-29 (owner: เริ่มทำ): the post-oracle fixture restoration
uses verified F-06 AUTH authorization and INCREASE. One harness AUTH pool
(size1/overflow0) is included in inventory/return/disposal/cleanup; production
pools, financial rules and all R25/R26/R27 thresholds are unchanged.


### R28 — Approved W2 bounded saturation (2026-10-29)

Owner approve authorizes requirements, harness method and validation in
[w2-bounded-saturation-amendment.md](w2-bounded-saturation-amendment.md). This
supersedes the W2 all30000commands/360s gate only:6000nominalslots,<=100active
cycles/oneperowner, explicit unsubmitted backpressure,300sstartwindow/360sdrain,
allstartedcomplete,>=600completedcycles/everyowner>=1. Actual IDs/perownercounts
drive independent existing oracles; all R25/R26/R27-A safety/RESET/overflow/resource
gates retained. This is client-bounded saturation, not100incomingAPIrequests/s
or a production global queue bound. W1/W3/W4/F15 defaults unchanged; historical
W2Failed retained pending fresh evidence. No production API/schema/trading change.


### R29 — Approved W2 owner service target (2026-10-29)

เจ้าของตอบ “อนุมัติ R29” ตาม [w2-risk-service-target-amendment.md](w2-risk-service-target-amendment.md).
เฉพาะ F18 Paper W2 bounded saturation: ready inputs ต้อง commit ผล/latch ภายใน
3s อย่างน้อย **99.5% ต่อ owner**; รวมทั้ง run คง **99.9%**, ทุก input คง **<=5s**.
ข้อยกเว้นนี้แทน R25/R28 เฉพาะ owner quota ของ W2; W1/W3/default คง99.9%.
นับด้วยจำนวนเต็ม เก็บทุก input/เวลารอ/late receipt; unacknowledged/clock errors
ยังต้องเป็นศูนย์. ยอมรับ quota ที่ล่าช้า3–5sต่อ owner เพิ่มจาก0.1%เป็น0.5%
เฉพาะช่วง saturation. ไม่เปลี่ยน production monitor, เงิน, freshness, fences,
authorization, deadlines, processing500ms/1s, RESET, overflow หรือ resources.
ใช้ sla_summary เดิมแบบระบุ phase และบันทึก owner/global targets แยก;
ทดสอบ boundary/default/missing ACK/hard limit ก่อน W2 ใหม่หนึ่งชุด. ถ้าผ่าน
ทุก gate จึงเริ่ม W3/W4 ตามแผน; หยุดเมื่อ failure ไม่วนรันหรือผ่อนเกณฑ์เอง.
ผล W2 เดิมยัง Failed/Partial; W1 ใช้ต่อได้เมื่อ default/dependencies ไม่เปลี่ยน.
Paper/F18 Pending Full Validation; V22/V23 Pending Dependency.


### R30 — Approved harness measurement and coverage correction (2026-10-29)

Owner approve authorizes R30 in [M5 checkpoint](evidence/m5-final-candidate.md#r30-consolidated-harness-correction--approved-2026-10-29), including NC-R30-01:
price10Hz means10freshBTC and10freshETH observations/s, not lease-only frames or
repeated snapshots. Count committed source data in the fixed nominal window;
report setup/drain separately. Preserve all ready inputs in risk SLA. Historical
W1Passed remains recorded but cannot certify this missing price-load gate; no
automatic W1 reuse or rerun. R25–R29 numeric/safety/resource bounds remain.

Separate overflow injection/recovery/verification and total durations. Start60s
recovery just after final injection commit acknowledgement, before publisher
restart; complete only on captured-watermark progress, READY and consistent live
lag<=20. Normal final drain remains within duration+60; no extra waiting budget.
Check live recovery before stopping source/workers; retain final risk ACK drain
and record shutdown lag separately. W3 gets durable fault/restored/recovered
receipts, transaction-start fault attribution with full raw durations, idle-owner
coverage and fixed1800s RSS windows. W4 compares columnACL/policies/0058roles and
requires base and risk recovery verdicts plus exit0.

Reuse existing publishers, telemetry, resource/fault helpers and restore verifier;
keep shared F15 defaults compatible. Test-only observation helpers are grouped in
backend/tests/infra/risk_limits/profile_observations.py to avoid growing duplicate
phase/source/readiness logic. No production/API/schema/trading/allocation changes.
Implement and run affected tests/static only; the proposed60s measurement and
W1–W4 still require the stated separate authorization/preconditions.

### R32 — Approved Paper source cadence 5Hz (2026-10-29)

เจ้าของยืนยันปรับตาม [R32](paper-source-cadence-amendment.md): book BTC/USDT และ
fresh price BTC/USDT, ETH/USDT อย่างละ5Hzใน F18 Paper fixture เท่านั้น.
ป้อนทุก200msและนับunique actual commitsใน nominal windowเดิม; ไม่เปลี่ยน
100×20, command load, freshness, risk/processing SLA, safety, durations/resources.
ผล10Hzเดิมไม่เปลี่ยนเป็นPassed; ต้องมีหลักฐาน5Hzสำหรับcandidateสุดท้ายก่อนรับรอง.
R31childยังdiagnostic-only, ไม่เริ่มworkloadจากการปรับนี้.
