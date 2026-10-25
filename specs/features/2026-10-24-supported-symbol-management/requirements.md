# F-37 — รายการคู่เทรดที่รองรับและการจัดการ — Requirements

สถานะ: **Approved — เจ้าของอนุมัติข้อเสนอ Q-1 ถึง Q-7 วันที่ 2026-10-24**

วันที่เริ่ม: 2026-10-24

---

## ทำไมต้องมี

ระบบรองรับเฉพาะคู่เทรดที่คัดไว้เพื่อคุมคุณภาพสภาพคล่องและให้ตรวจความถูกต้องได้ครบ
แต่ catalog ปัจจุบันของ F-38 เป็นค่าคงที่ `BTC/USDT` และ `ETH/USDT` ในโค้ด การเพิ่มหรือ
ถอนคู่จึงต้อง deploy โค้ดและไม่มี workflow สำหรับ Platform Admin ตามที่ `mission.md` กำหนด

F-16 ต้องใช้ catalog นี้เป็นด่านปฏิเสธคำสั่งเพิ่มความเสี่ยง ขณะที่ผู้ใช้ยังต้องลดความเสี่ยง
ของ position เดิมได้หลังคู่ถูกถอน ถ้าการเปลี่ยน catalog ไม่เป็น atomic หรือแต่ละ service เห็น
คนละ revision ออเดอร์อาจเปิดความเสี่ยงใหม่หลัง Admin ถอนคู่แล้ว หรือระบบอาจกันผู้ใช้ออกจาก
ทางลดความเสี่ยงของตนเอง

## ขอบเขต

### ทำ

- มี catalog กลางแบบ persistent สำหรับคู่ Spot ที่แพลตฟอร์มรองรับ โดยเริ่มจาก
  `BTC/USDT` และ `ETH/USDT` ตาม F-38
- ให้ Platform Admin เพิ่มและถอนคู่ผ่าน API และหน้าจอจัดการที่ตรวจสิทธิ์ฝั่ง server
- ใช้ catalog เดียวกันกับ API, order safety gate, Paper/Live domain path, market data,
  indicator, chart และตัวเลือกคู่เทรดใน frontend; cache หรือ generated contract ต้องตรวจ
  revision ได้และ fail closed เมื่อไม่แน่ใจ
- ตรวจความพร้อมของคู่กับ Binance TH และข้อมูลที่ระบบต้องใช้ก่อนอนุญาตคำสั่งเพิ่มความเสี่ยง
- ถอนคู่แล้วห้ามเปิดความเสี่ยงใหม่ทันที แต่คงประวัติ, ออเดอร์ที่เกิดแล้ว, balance และ
  position เดิม และยังอนุญาตคำสั่งที่ลดความเสี่ยงตาม safety gate เดิม
- หยุดบอทที่ผูกกับคู่ที่ถอนและสร้างหลักฐานสำหรับแจ้งผู้ใช้ โดยไม่เปิดบอทกลับเองเมื่อเพิ่มคู่คืน
- เก็บประวัติการเปลี่ยน catalog และ audit log แบบเพิ่มอย่างเดียว รวมผู้กระทำ เหตุผล
  revision และผลสำเร็จ/ล้มเหลว
- รองรับคำขอซ้ำ การเปลี่ยนพร้อมกัน การ restart และ service ที่ถือ cache เก่าโดยไม่ทำให้
  catalog ย้อนกลับหรือเปิดช่องส่งออเดอร์
- แสดงสถานะ loading, empty, error, stale, pending และผลกระทบก่อนยืนยันการถอน โดยใช้
  component/pattern จาก `references/admin-template/` และข้อความผ่านระบบแปล

### ไม่ทำ

- ไม่เพิ่ม Futures, Binance.com หรือ exchange อื่น
- ไม่กำหนดสูตรคัดเลือกสภาพคล่องหรือเพดานขนาดไม้ใหม่; Admin รับผิดชอบการคัดตามคำตัดสิน Q-2
- ไม่บังคับปิด position และไม่ขายสินทรัพย์แทนผู้ใช้
- ไม่ลบหรือเขียนทับ order, fill, balance, position, ledger หรือ audit history
- ไม่เปิด Live Trading และไม่ส่งออเดอร์จริงในการตรวจรับ
- ไม่ขยายอำนาจ Platform Admin ไปถึงการดู secret, สั่งออเดอร์แทนผู้ใช้,
  ปิด position หรือแก้ audit log
- ไม่ทำระบบผู้ดูแลแพลตฟอร์มทั่วไปนอกสิทธิ์ที่ F-37 จำเป็นต้องใช้; F-37 เพิ่มเฉพาะ role,
  bootstrap และ authorization ตาม Q-3 ส่วนอำนาจอื่นอยู่ใน F-29
- ไม่ทำ notification product ทั้งชุดของ F-26/F-36/F-27; F-37 ทำ durable contract ตาม Q-7
  และรอ in-app integration ของ F-26 ก่อนเปลี่ยนสถานะเป็น Completed

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | Catalog ต้องมีแหล่งความจริง persistent เพียงแห่งเดียวและมี revision ที่เพิ่มขึ้นเท่านั้น; service/UI อาจ cache ได้แต่ห้ามถือค่าที่เก่ากว่าเป็นสิทธิ์เปิดความเสี่ยงใหม่เมื่อพิสูจน์ความสดไม่ได้ | architecture §5; trading-safety §3 |
| RQ-2 | ข้อมูลตั้งต้นหลัง migration ต้องมี `BTC/USDT` และ `ETH/USDT` อยู่ในสถานะรองรับ โดยไม่ทำลายข้อมูลหรือหลักฐานของ F-38 | F-38; mission §6 |
| RQ-3 | เฉพาะ Platform Admin และ Platform Owner เท่านั้นที่ขอเพิ่มหรือถอนคู่ได้; endpoint ต้องตรวจสิทธิ์ฝั่ง server แบบ default-deny ผู้ใช้ทั่วไปต้องเปลี่ยน catalog ไม่ได้แม้แก้ request เอง | mission §2/§6; security §2 |
| RQ-4 | ก่อนเพิ่มคู่ ระบบต้องยืนยันจาก Binance TH ว่า symbol มีจริง เป็น Spot และอยู่ในสถานะที่ซื้อขายได้ พร้อมมีข้อจำกัดที่จำเป็นต่อการตรวจ order; ความล้มเหลว ข้อมูลไม่ครบ หรือข้อมูลเก่าต้องไม่ทำให้คู่ active | mission §6; trading-safety §3/§5; security §3 |
| RQ-5 | คู่ใหม่จะอนุญาตคำสั่งเพิ่มความเสี่ยงได้ต่อเมื่อ runtime dependency ที่จำเป็นพร้อมตามเกณฑ์ที่ plan/validation ระบุ; หน้าเว็บต้องไม่แสดงเพียงว่า “พร้อมเทรด” ขณะ backend ยัง fail closed | trading-safety §3/§6/§12 |
| RQ-6 | การถอนคู่ต้องสร้าง catalog revision ใหม่และทำให้ทุกเส้นทางปฏิเสธคำสั่งเพิ่มความเสี่ยงของคู่นั้นก่อนตอบว่าสำเร็จ; การตรวจครั้งก่อนเข้าคิวอย่างเดียวไม่พอ ต้องตรวจ authoritative revision อีกครั้งที่ขอบส่งคำสั่ง | mission §6; trading-safety §3; testing §4 |
| RQ-7 | หลังถอนคู่ คำสั่งที่ลดความเสี่ยงจริงและขนาดไม่เกิน position ต้องยังผ่าน safety gate เดิมโดยไม่ตรวจ active catalog; คำสั่งเกิน position ต้องถูกปฏิเสธเหมือนคำสั่งเพิ่มความเสี่ยง | trading-safety §3 |
| RQ-8 | การถอนคู่ห้ามแก้หรือลบ position, balance, order/fill/ledger/audit history เดิม และห้ามบังคับปิด position ของผู้ใช้ | mission §2/§6; database §4 |
| RQ-9 | บอทที่ผูกกับคู่ที่ถอนต้องหยุดแบบ durable แยกสาเหตุว่า catalog ถอนคู่ รอด restart และห้ามกลับมาทำงานเองเพียงเพราะเพิ่มคู่คืน | mission §6; หลัก Live ไม่เปิด/กลับเองโดยปริยาย |
| RQ-10 | การเพิ่ม/ถอนต้อง atomic กับ catalog history และ audit event; audit ล้มเหลวต้องไม่เปลี่ยน catalog และ catalog เปลี่ยนสำเร็จต้องมี audit ที่สอดคล้องกัน | trading-safety §9; architecture §5; database §4 |
| RQ-11 | Audit ต้องบันทึก actor, action, base/quote, revision ก่อน/หลัง, เหตุผล, เวลา, outcome และรหัสข้อผิดพลาดโดยไม่มี secret; ประวัติ catalog/audit แก้หรือลบย้อนหลังไม่ได้ | trading-safety §9; security §4; database §4 |
| RQ-12 | คำขอ mutation ต้องมี idempotency key และผลเดิมสำหรับคำขอซ้ำ; การเพิ่ม/ถอนพร้อมกันต้อง serialize หรือ reject conflict อย่างชัดเจน ห้าม lost update และห้าม revision ถอยหลัง | trading-safety §4; concurrency safety |
| RQ-13 | Worker และ service ที่ถือ revision เก่าต้องหยุดสร้าง demand/subscription/job ใหม่และห้าม publish สถานะที่ทำให้คู่ถูกถอนกลับมา active; restart ต้องสร้าง state จาก PostgreSQL ไม่ใช่ Redis อย่างเดียว | architecture §5; F-38 |
| RQ-14 | Frontend ต้องอ่าน catalog จาก server ไม่เก็บรายการคู่ซ้ำเป็นค่าคงที่ และต้อง invalidate/cache ตาม revision; URL/state เก่าของคู่ที่ถอนต้องไม่ยิงคำขอที่เพิ่ม demand หรือเปิดความเสี่ยง | frontend §3/§4; F-38 |
| RQ-15 | หน้าถอนต้องแสดงคู่, ผลว่าห้ามเปิดใหม่, จำนวนบอท/ออเดอร์/position ที่ทราบและข้อจำกัดของ snapshot ก่อนยืนยัน; ห้ามกล่าวว่าไม่มีผลกระทบเมื่อข้อมูล stale หรืออ่านไม่ครบ | frontend §1/§4; mission §6 |
| RQ-16 | UI ต้องใช้ shared controls และ interaction pattern จาก admin template, รองรับ keyboard/focus/accessibility, responsive และไทย/อังกฤษ; ห้ามใช้ native confirmation เมื่อมี modal pattern กลาง | frontend §2/§6 |
| RQ-17 | API และ UI ต้องแยกสถานะ requested/preparing/active/removed/failed ตาม workflow ที่ plan กำหนด และห้ามแสดงว่าสำเร็จก่อน safety effects ที่เป็นเงื่อนไขสำเร็จเสร็จจริง | truthfulness; trading safety |
| RQ-18 | Automated validation ห้ามส่งออเดอร์ Live และต้องพิสูจน์อย่างน้อย: authorization, venue validation, revision/concurrency/idempotency, cache stale/restart, add readiness, remove fail-closed, queued dispatch race, ลดความเสี่ยงได้, ไม่แตะประวัติเดิม, bot stop durability และ audit atomicity | testing §4/§5/§7 |

## กฎความปลอดภัยที่เกี่ยวข้อง

- `specs/standards/trading-safety.md` §3: ทุก order ผ่าน safety gate เดียวกัน;
  active catalog ใช้เฉพาะคำสั่งเพิ่มความเสี่ยง คำสั่งลดความเสี่ยงต้องยังทำได้
- §4: mutation และผลข้างเคียงต้องทนคำขอซ้ำ
- §5, §6, §10, §12: ข้อมูลจากตลาด/บัญชีไม่แน่นอนต้อง fail closed และสถานะที่แสดงต้องตรงจริง
- §9 และ `database.md` §4: catalog history กับ audit เพิ่มอย่างเดียวและแก้ย้อนหลังไม่ได้
- `architecture.md` §5: PostgreSQL เป็นความจริง; Redis/cache หายแล้วต้องสร้างกลับได้
- ห้ามระบบปิด position ของผู้ใช้หรือเปิด Live/bot กลับเอง

## คำตัดสินของเจ้าของ — 2026-10-24

เจ้าของตอบ “approve” หลังได้รับข้อเสนอ Q-1 ถึง Q-7 จึงเลือกข้อเสนอแรกของทุกข้อ
ด้านล่าง ไม่มี Needs Clarification ที่ค้างอยู่สำหรับการจัดทำ `plan.md` และ `validation.md`

### Q-1 — หน่วยของ catalog และ quote asset

F-38 และโค้ดปัจจุบันใช้ “คู่เทรด” base/quote แต่ mission ใช้คำว่า “เหรียญ”:

- **ข้อเสนอ:** F-37 รอบนี้จัดการคู่ Spot แบบ `BASE/USDT` เท่านั้น เพิ่ม SOL/XRP/DOGE
  กลับได้เมื่อผ่านเกณฑ์; ไม่เปิด THB หรือ quote อื่น
- ทางเลือก: จัดการ symbol Spot ทุก quote ที่ Binance TH มี ซึ่งจะกระทบ wallet, position,
  PnL, market data และ UI มากกว่า

**คำตัดสิน:** ใช้คู่ Spot `BASE/USDT` เท่านั้นใน F-37 ไม่เปิด THB หรือ quote อื่น

### Q-2 — ใครตัดสินว่าคู่ใหม่ผ่าน และใช้เกณฑ์ใด

การมีอยู่และสถานะ `TRADING` ที่ Binance TH พิสูจน์เพียงว่าตลาดรับคำสั่ง ไม่ได้พิสูจน์ว่า
สภาพคล่องดีพอ ตาม mission ต้อง “คัดไว้” และ “ทบทวนเป็นระยะ” แต่ยังไม่มี threshold:

- **ข้อเสนอ:** F-37 ไม่ตัดสินสภาพคล่องอัตโนมัติ Admin เป็นผู้รับผิดชอบการอนุมัติรายการ
  หลังตรวจนอกระบบ โดยต้องกรอกเหตุผล; ระบบตรวจอัตโนมัติเฉพาะ existence/status/filters
- ทางเลือก: กำหนด volume/spread/depth threshold ใน requirements นี้ก่อน implement

**คำตัดสิน:** Admin เป็นผู้รับผิดชอบการคัดสภาพคล่องนอกระบบและต้องกรอกเหตุผล ระบบตรวจ
อัตโนมัติเฉพาะ existence, Spot/TRADING status และ filters; ไม่สร้าง liquidity threshold ใหม่

### Q-3 — ตัวตนและสิทธิ์ Platform Admin

ระบบปัจจุบันไม่มี role ของผู้ใช้ และ F-29 “ระบบผู้ดูแลแพลตฟอร์ม” ยัง Planned/ติด NC-02:

- **ข้อเสนอ:** F-37 เพิ่มเฉพาะ role `PLATFORM_ADMIN`/`PLATFORM_OWNER`, bootstrap ที่ปลอดภัย
  และ authorization ของหน้าจอนี้ ไม่เพิ่มอำนาจ admin อื่น; F-29 ใช้ role เดียวกันต่อภายหลัง
- ทางเลือก: ให้ F-37 รอ F-29 และทำ F-29/ปิด NC-02 ก่อน

**คำตัดสิน:** F-37 เพิ่ม role และ bootstrap เฉพาะที่จำเป็นกับหน้าจอนี้ ไม่รอ F-29 และไม่
เพิ่มอำนาจ admin อื่น วิธี bootstrap ที่ไม่ยกระดับผู้ใช้ทั่วไปเองต้องระบุใน plan เพื่ออนุมัติ

### Q-4 — ออเดอร์ค้างเมื่อถอนคู่

mission ระบุว่า position เดิมไม่ถูกแตะ แต่ไม่ได้ตัดสินออเดอร์เปิดที่ส่ง/ค้างอยู่แล้ว ซึ่งอาจ
fill หลังถอนและสร้าง position ใหม่:

- **ข้อเสนอ:** หยุดบอทก่อน, ทิ้ง queued risk-increasing commands และพยายามยกเลิก
  open entry orders ของคู่นั้น; ไม่ยกเลิก reduce-risk/TP/SL หากยังปกป้อง position เดิม
  การยกเลิกไม่สำเร็จต้องแสดง/แจ้งตามจริงและคู่ยังคง inactive
- ทางเลือก: ไม่แตะออเดอร์ที่ส่งแล้ว ยอมให้ fill หลังถอน

**คำตัดสิน:** หยุดบอท ทิ้ง queued risk-increasing commands และพยายามยกเลิก open entry
orders; คง reduce-risk/TP/SL ที่ปกป้อง position เดิม คู่ต้อง inactive แม้ยกเลิกบางใบไม่สำเร็จ
แต่ต้องแสดงเป็นผลข้างเคียงค้าง/ล้มเหลว ห้ามแสดงว่าจัดการครบแล้ว

### Q-5 — Market data หลังถอนคู่

ผู้ใช้ที่มี position/order เดิมยังต้องเห็นราคาและส่งคำสั่งลดความเสี่ยง แต่การหยุด worker
ทั้งหมดทันทีจะทำให้ข้อมูล stale:

- **ข้อเสนอ:** ห้ามสร้าง public chart/backfill demand ใหม่ แต่คง feed/filters ขั้นต่ำตราบใดที่
  ยังมี exposure หรือ order ที่ต้องดูแล; เก็บ history ตาม retention เดิมและไม่ลบเพราะถอนคู่
- ทางเลือก: หยุด market-data ทั้งหมดทันทีและพึ่ง venue request ตอนปิด position

**คำตัดสิน:** ห้าม public chart/backfill demand ใหม่ แต่คง feed และ filters ขั้นต่ำขณะยังมี
exposure/order ที่ต้องดูแล เก็บ history ตาม retention เดิมและไม่ลบเพราะถอนคู่

### Q-6 — การยืนยันการเปลี่ยน catalog

การเพิ่มคู่เปิดความเสี่ยงใหม่ได้ทั้งแพลตฟอร์ม แต่ spec ยังไม่ระบุ step-up หรือผู้อนุมัติสองคน:

- **ข้อเสนอ:** Admin/Owner ต้องยืนยัน TOTP ใหม่และกรอกเหตุผลทุกครั้ง ใช้ผู้มีสิทธิ์คนเดียว
  ไม่ทำ four-eyes approval ใน F-37
- ทางเลือก: ใช้ session ปกติ หรือบังคับผู้อนุมัติสองคน

**คำตัดสิน:** mutation ทุกครั้งต้องยืนยัน TOTP ใหม่และกรอกเหตุผล ใช้ผู้มีสิทธิ์คนเดียว
ไม่ทำ four-eyes approval ใน F-37

### Q-7 — การแจ้งผู้ใช้และ dependency กับบอท

mission บังคับให้หยุดบอทและแจ้งผู้ใช้ แต่ F-20 (บอท) และ F-26/F-36/F-27
(ช่องทางแจ้งเตือน) ยังไม่ทำ:

- **ข้อเสนอ:** F-37 ทำ catalog, safety gate และ durable domain/audit event พร้อม contract test;
  เมื่อ F-20/F-26 ทำจริงต้อง consume event นี้และ F-37 ยังไม่เป็น Completed จน integration
  “หยุดบอท + in-app notification” ผ่าน ส่วน Email/Telegram/LINE ตามงานของตน
- ทางเลือก: ย้าย F-20 และ F-26 มาก่อน F-37 หรือรวมส่วนที่จำเป็นเข้าขอบเขต F-37

**คำตัดสิน:** F-37 ทำ durable event และ contract tests ตอนนี้; F-20/F-26 ต้อง consume event
เพื่อหยุดบอทและแจ้งในแอพก่อน F-37 เป็น Completed ส่วน Email/Telegram/LINE อยู่ในงานเดิม
