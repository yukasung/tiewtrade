# F-16 — สั่งออเดอร์เองผ่านหน้าจอ — Requirements

สถานะ: **Approved — เจ้าของตอบ “approve” ต่อ requirements ทั้งฉบับ วันที่ 2026-10-25**
วันที่: 2026-10-25

## ทำไมต้องมี

ผู้ใช้ต้องส่งและยกเลิกออเดอร์ของตัวเองผ่านหน้าจอ โดยเห็นโหมด หน่วย จำนวน
และผลที่ระบบยืนยันจริง ใช้ Paper executor ของ F-15 และกฎความปลอดภัยร่วมกับ Live
ตาม ADR-004 ไม่สร้างตรรกะเงินหรือ matching อีกชุดในหน้าจอ

## คำตัดสินที่อนุมัติแล้ว

เจ้าของตอบ “approve” วันที่ 2026-10-25 ต่อข้อเสนอทั้งสองข้อ:

- **NC-08 — Closed:** MARKET BUY ระบุงบ USDT, MARKET SELL ระบุจำนวน base;
  LIMIT BUY/SELL ระบุจำนวน base และราคา ใช้ GTC พร้อมยกเลิกออเดอร์ได้
  ตามขอบเขต F-15; TP/SL เป็น F-17
- **NC-F16-01 — Closed:** เมื่อฐานข้อมูลล่มหรือบันทึกไม่ได้ ระบบปฏิเสธคำสั่ง
  รวมคำสั่งลดความเสี่ยง สำหรับ Live แจ้งให้ผู้ใช้จัดการตรงที่ตลาด
  ไม่มีทางส่งคำสั่งโดยข้าม durable record/audit

การอนุมัติครั้งแรกปิดสองคำตัดสิน; ต่อมาเจ้าของตอบ “approve” ต่อ requirements
ทั้งฉบับวันที่ 2026-10-25 จึงจัดทำ plan/validation ต่อได้; ต่อมาเจ้าของอนุมัติ
plan/validation ฉบับแก้ F16-R1/R2/R3 ในวันเดียวกัน จึงเริ่ม implementation ตาม milestones ได้

## ขอบเขต

### ทำ

- ฟอร์มส่ง MARKET/LIMIT และยกเลิกออเดอร์ Paper ของผู้ใช้ที่เข้าสู่ระบบ
- แสดงยอดที่ใช้ได้ ออเดอร์และผลคำสั่งที่จำเป็นต่อการเทรดมือจากข้อมูลจริง
- ใช้ component ฟอร์มร่วมตาม ADR-004 แยกหน้า/URL และข้อมูล Paper/Live;
  หน้า Live แสดงความไม่พร้อมและไม่ส่งคำสั่งจนงาน Live พร้อม
- เชื่อม catalog และ safety dependencies เดิม โดยไม่ bypass ด่านที่ยังไม่พร้อม

### ไม่ทำ

- Live execution/reconciliation/activation ของ F-22–F-24, Futures หรือ venue ใหม่
- TP/SL/bracket ของ F-17, การตั้ง/รีเซ็ตเพดานความเสี่ยงของ F-18, Kill Switch F-19
  หรือ bot lifecycle; ไม่ย้าย requirements ของงานเหล่านี้เข้ามาโดยปริยาย
- IOC/FOK, LIMIT_MAKER, amend, MARKET BUY แบบ base quantity,
  MARKET SELL แบบ quote target หรือเปลี่ยนกฎ matching/fee/reservation ของ F-15
- หน้ารายงานหรือประวัติการเทรดเต็มรูปแบบแทนงานที่ roadmap จัดไว้

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | รับเฉพาะคำสั่ง Spot ตาม NC-08; ชนิด/หน่วยที่ไม่รองรับต้องปฏิเสธ ไม่แปลงคำสั่งเงียบ ๆ | คำตัดสิน 2026-10-25; F-15 RQ-5 |
| RQ-2 | แสดง BUY/SELL, MARKET/LIMIT, คู่, หน่วยงบหรือปริมาณ และราคา LIMIT ให้ชัด; ค่าตัวเลขต้องผ่าน Money/Quantity ฝั่ง server ไม่คำนวณเงินด้วย float หรือ Decimal เปล่า | AGENTS §6; frontend §3 |
| RQ-3 | ผู้ใช้ส่ง/อ่าน/ยกเลิกได้เฉพาะออเดอร์ของตน; Admin/Owner ไม่มีสิทธิ์สั่งหรือปิด position แทนผู้อื่น | mission §2; security |
| RQ-4 | Paper/Live แยก page/URL, API path และข้อมูล/cache ตามผู้ใช้และโหมด; server กำหนดโหมดจากเส้นทาง ไม่เชื่อ mode ที่ browser ส่ง; การเปิดหน้าไม่เปิด Live | ADR-004; trading-safety §1 |
| RQ-5 | Paper ใช้ execution/domain contracts และ simulator F-15 เดิม; เส้นทางคำสั่ง Paper เข้าถึง Live executor/credential หรือส่งออเดอร์ออกตลาดไม่ได้ | ADR-004; F-15 |
| RQ-6 | เปิดไม้ด้วยมือได้เฉพาะประเภท MANUAL; การหยุดบอทไม่เปลี่ยนประเภท การลด position/ยกเลิกยังทำได้ทุกประเภทภายใต้ gates เดิม | mission §5; trading-safety §8 |
| RQ-7 | ทุกคำสั่งผ่าน safety gate กลาง; ตรวจ catalog/ข้อจำกัดคู่/เงินหลังหัก reservation/position/ราคาและเพดานความเสี่ยงตามกฎเดิม; UI validation ไม่แทน server gate | trading-safety §3/§6/§13 |
| RQ-8 | คำสั่งเพิ่มความเสี่ยงตรวจ authoritative catalog ที่ขอบ execution ตาม F-37; คู่ถูกถอนยังจัดการสถานะเดิมได้เมื่อพิสูจน์ว่าเป็นการลดความเสี่ยงจริง ไม่เดาจากป้าย SELL ใน UI | F-37 RQ-6/7; trading-safety §3 |
| RQ-9 | คำขอซ้ำต้องไม่สร้างออเดอร์หรือ financial effect ซ้ำ; timeout/การขาดการเชื่อมต่อต้องตรวจผลคำขอเดิม ไม่สร้างคำสั่งใหม่อัตโนมัติ; cancel แข่ง fill ต้องใช้ผล authoritative เดิม | trading-safety §4; F-15 |
| RQ-10 | รับคำสั่งและบันทึก audit/durable intent ก่อน execution; บันทึกไม่ได้ต้องปฏิเสธ รวมลดความเสี่ยงและยกเลิก ห้ามใช้ browser/local log แทน | NC-F16-01; F-04 Q-7 |
| RQ-11 | ผลไม่ทราบหลังส่งคำขอต้องแสดงว่าไม่ทราบ/กำลังตรวจสอบ ไม่กล่าวว่าปฏิเสธหรือสำเร็จ; กฎฐานข้อมูลล่มไม่เปลี่ยนผลคำสั่งที่อาจ commit ไปก่อนแล้ว | trading-safety §4/§10; F-15 |
| RQ-12 | UI แยกรับคำสั่งแล้ว, รอจับคู่, partial fill, filled, canceled, rejected/expired และไม่ทราบผลตาม contract จริง; cancel ไม่ย้อน fill ที่เกิดแล้ว และไม่คืนยอดก่อน server ยืนยัน | F-15 lifecycle/reservation; frontend §1 |
| RQ-13 | แสดงข้อมูลบัญชี/ตลาดพร้อมสถานะความพร้อมและเวลา snapshot; เมื่อ feed ไม่พร้อมใช้พฤติกรรม F-15 เดิม ไม่แสดงว่าคำสั่งลด position ปิดสำเร็จเพียงเพราะเข้าคิว | F-15 NC-F15-03; trading-safety §6/§12 |
| RQ-14 | เมื่อบันทึกไม่ได้ต้องแจ้งว่าระบบดำเนินคำสั่งไม่ได้; Live ให้ผู้ใช้จัดการตรงที่ตลาด โดยไม่อ้างว่าระบบจัดการให้แล้ว; Paper ไม่ชี้นำให้ส่งเงินจริงเพื่อแก้สถานะจำลอง | NC-F16-01; trading-safety §10 |
| RQ-15 | UI ยึด references/admin-template และ shared controls ใน frontend/src/components/ui รองรับไทย/อังกฤษ keyboard/focus/error/loading/disabled และ responsive; ไม่สร้าง native appearance ทดแทน pattern ที่มี | AGENTS; frontend §2/§6 |
| RQ-16 | ทุก financial mutation มี immutable audit ที่ผูก actor/owner/mode/คำสั่ง/ผล; เพิ่ม action/invariant/database CHECK ให้ครบเมื่อจำเป็น ไม่เผย API secret ผ่าน response/log/error | roadmap F-04; trading-safety §2/§9 |
| RQ-17 | ทดสอบ owner/mode isolation, duplicate/concurrent submission, cancel/fill/reset races, catalog removal, database failure และ recovery ตามผลกระทบจริง; ห้ามส่ง Live order ใน automated validation | testing; F-15/F-37 |
| RQ-18 | Production order admission ต้องยังปิดจน F-18 และ safety dependencies ที่จำเป็นพร้อม; UI ต้องบอกเหตุที่ใช้ไม่ได้ ไม่ bypass หรือจำลอง gate ว่าผ่านเพื่อเปิดให้ใช้ F-16 | F-15 NC-F15-06 |

## Dependencies และเกณฑ์เข้าสู่ขั้นถัดไป

- F-37 Catalog/Order Safety Ready ผ่านแล้ว ไม่ต้องรอ pending Live/bot/release validation
  ของ F-37 เพื่อเริ่ม F-16; ไม่เปลี่ยน F-37 เป็น Completed
- F-13–F-15 ใช้ตามขอบเขตที่รับรองแล้ว ไม่อ้างว่าการมีหน้าจอทำให้ pending validation ผ่าน
- F-18 ยัง Planned: ต้องแยก milestone พัฒนาหน้าจอ/การเชื่อมต่อออกจากเปิดใช้งานจริง
  ใน plan/validation ไม่ให้ F-16 Completed ทั้งที่เกณฑ์ end-to-end ยังถูกบล็อก
- Live ยังต้องผ่าน F-22–F-24 และ clarification ของงานนั้น; F-16 ไม่เพิ่มข้อยกเว้น
  เรื่อง reduce-only หรือความพร้อมของข้อมูลบัญชี Live
- หลังอนุมัติ requirements จึงค้นของเดิมและกำหนด paths/contracts/milestones ใน plan
  พร้อม validation ก่อนขออนุมัติ implementation

## ยังไม่ชัด

ไม่มีคำตัดสินธุรกิจใหม่ที่เสนอให้เดาระหว่าง implementation ในฉบับนี้
NC-08 และ NC-F16-01 ปิดแล้ว; requirements ทั้งฉบับได้รับอนุมัติแล้ว
หากพบช่องว่างใหม่ต้องบันทึก Needs Clarification ใน mission §9 และหยุดส่วนที่เกี่ยวข้อง

## F16-R4 — Compact Trading Workspace amendment — 2026-10-30

สถานะ: **Approved — เจ้าของอนุมัติแผน “ปรับหน้า Paper/Live Trade เป็น Trading Workspace แบบกระชับ” วันที่ 2026-10-30**

- `/paper/trade` และ `/live/trade` ใช้ layout ร่วมแบบ trading workspace: แถบคู่เทรดและสถานะ,
  กราฟ, ฟอร์ม และรายการออเดอร์ โดย desktop วางกราฟซ้ายและฟอร์มขวา ส่วน mobile เรียงลงมา
- ใช้สี typography spacing และ shared controls ที่ปรับจาก `references/admin-template/`;
  ความคล้าย Binance จำกัดที่ลำดับข้อมูลและสัดส่วน ไม่คัดลอกแบรนด์หรือ visual tokens
- ไม่มี Order book, market trade feed, สถิติ 24 ชั่วโมง, percentage slider หรือ TP/SL
  เมื่อ backend ยังไม่รองรับ
- คู่เทรดตัวเดียวควบคุมกราฟและฟอร์ม; การเปลี่ยนคู่ต้องล้าง draft จำนวน/ราคา และรอ
  snapshot ของคู่ใหม่ก่อนเปิด submit
- แสดง balance และ risk limit แบบย่อ เปิดรายละเอียดเมื่อต้องการ แต่ blocking reason,
  stale/disconnected/risk-stop และผลคำขอไม่แน่นอนต้องเห็นใกล้ฟอร์มทันที
- หน้า Live ใช้กราฟตลาดและรูปลักษณ์เดียวกัน แต่คง execution ปิด ไม่แสดงข้อมูล Paper
  และห้ามส่ง Live order
- amendment นี้ไม่เปลี่ยน public API, schema, money/order/risk calculations,
  idempotency journal, pending-submit protection หรือ episode semantics
