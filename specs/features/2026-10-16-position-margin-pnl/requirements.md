# Position, Margin และ PnL — Requirements

สถานะ: **Approved** — เจ้าของอนุมัติ requirements และปิด NC-44–NC-49 วันที่ 2026-10-16
วันที่: 2026-10-16

## ทำไมต้องมี

F-13 มีเงินและรอบของ Paper แล้ว แต่ยังพิสูจน์ไม่ได้ว่ารอบปัจจุบันไม่มี position
จึงต้องปฏิเสธ reset ด้วย `ACTIVITY_UNKNOWN` เสมอ ขณะเดียวกันงานส่งออเดอร์,
TP/SL, เพดานขาดทุน, สรุปผลงาน และ strategy ต้องอาศัยความหมายของ position และ PnL
ชุดเดียวกัน มิฉะนั้น Paper กับ Live อาจตัดสินใจจากตัวเลขคนละแบบ

งานนี้กำหนดสถานะ position และการคำนวณ PnL จากผลการจับคู่ที่ยืนยันแล้ว โดยใช้ตรรกะ
โดเมนร่วมกันระหว่าง Paper และ Live ตาม ADR-004 พร้อมจัดเตรียมหลักฐาน authoritative
ด้าน position ให้ F-13 ใช้ร่วมกับหลักฐาน open order จาก F-15 ก่อนเปิด reset success

## ขอบเขต

### ทำในงานนี้

- นิยาม position ของ Spot ที่เกิดจากผลการจับคู่ซึ่งระบบยอมรับแล้ว
- คำนวณปริมาณคงเหลือ, ต้นทุน, realized PnL และ unrealized PnL ตามกฎที่เจ้าของอนุมัติ
- รองรับ partial fill และ fill หลายรายการโดยให้การประมวลผลซ้ำได้ผลเดิม
- เก็บ provenance, ลำดับ/revision และเวลาของข้อมูลที่จำเป็นต่อการพิสูจน์ความพร้อม
- ใช้ calculation/state-transition implementation เดียวกันสำหรับ Paper และ Live
- แยกข้อมูลตามผู้ใช้, โหมด และรอบ Paper อย่างเด็ดขาด
- ให้แหล่ง authoritative ระบุได้ว่า position ของรอบ Paper มีอยู่, ไม่มีอยู่
  หรือยังพิสูจน์ไม่ได้ โดยไม่เปลี่ยน unknown ให้เป็น idle
- กำหนด contract ที่ F-15 และงาน Live ภายหลังส่งผลการจับคู่เข้ามาใช้ร่วมกัน

### ไม่ทำในงานนี้

- ไม่จำลองการจับคู่ออเดอร์หรือกำหนด slippage/fee ของ Paper ซึ่งเป็น F-15
- ไม่ส่ง, ยกเลิก หรือกระทบยอดออเดอร์กับ Binance ซึ่งเป็น F-22/F-23
- ไม่สร้างหน้าสั่งออเดอร์, TP/SL, risk-limit workflow หรือหน้าสรุปผลงาน
- ไม่รองรับ Futures, leverage, borrowed assets, funding, maintenance margin,
  liquidation หรือ short position เพราะเวอร์ชันแรกรองรับ Spot เท่านั้น
- ไม่เปิด reset success ของ F-13 จากหลักฐาน position เพียงด้านเดียว;
  ต้องมี authoritative open-order source และ single-writer protocol จาก F-15 ด้วย
- ไม่ใช้ยอดถือครองจากกระเป๋าเป็นตัวแทน position โดยปริยาย

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | การคำนวณและ state transition ของ position/PnL ต้องเป็น deterministic pure domain logic ชุดเดียวกันสำหรับ Paper และ Live เมื่อ fill, สถานะตั้งต้น และ input อื่นเหมือนกันต้องได้ผลเหมือนกัน | `mission.md` §4; ADR-004 |
| RQ-2 | ค่าที่เป็นเงินและปริมาณทั้งหมดต้องใช้ `Money` และ `Quantity` จาก `tiewtrade.core.money`; ห้ามใช้ `float`, `Decimal` เปล่า หรือสร้างกฎช่วงค่า/การปัดใหม่ภายนอกชนิดกลาง | `AGENTS.md` ข้อ 6; backend standard |
| RQ-3 | ขอบเขตแรกเป็น Spot เท่านั้น Position ต้องไม่ติดลบและห้ามสร้าง short, leverage, margin debt หรือ liquidation state; Futures และ margin trading รอความสามารถของตลาดและ spec ใหม่ | `mission.md` §3/6 |
| RQ-4 | Position เปลี่ยนได้จาก execution/fill fact ที่ผ่าน contract และยืนยันแล้วเท่านั้น ห้ามเปลี่ยนจาก order intent, acknowledgement, ราคาตลาด หรือ UI optimistic state | trading-safety §4/5/6; ADR-004 |
| RQ-5 | fill เดิมที่ถูกส่งซ้ำ, worker restart, lost response หรือ concurrent delivery ต้องไม่เพิ่ม/ลด position, cost, PnL หรือ financial history ซ้ำ; fill identity ต้องตรวจซ้ำได้อย่างถาวร | trading-safety §4/10 |
| RQ-6 | fill หลายรายการของ position เดียวกันต้องถูกใช้ตามลำดับ authoritative ที่กำหนด หากลำดับขาด, ซ้ำ, ย้อนกลับ, ขัดกัน หรือพิสูจน์ไม่ได้ต้อง fail closed และห้ามเผยแพร่สถานะใหม่บางส่วน | trading-safety §5/10/12 |
| RQ-7 | การเปลี่ยน position, realized PnL, financial history, revision และหลักฐาน activity ที่เกี่ยวข้องต้อง atomic ภายใต้ single-writer protocol เดียวกันต่อผู้ใช้/โหมด/บัญชีหรือรอบ ห้ามมี snapshot ครึ่งก่อนครึ่งหลัง | trading-safety §4/9/10; F-13 RQ-7 |
| RQ-8 | ข้อมูลต้องแยกตามผู้ใช้และโหมดที่ server กำหนด Paper ห้ามอ่านหรือเขียน Live position/credential/executor และ Live ห้ามใช้ Paper state เป็นความจริงของบัญชีตลาด | ADR-004; trading-safety §1/5 |
| RQ-9 | Position ของ Paper ต้องผูกกับ episode ของ F-13 ทุก fill และ PnL ต้องอยู่ใน episode เดียวกัน เงินตั้งต้นหรือเครดิต reset ไม่ใช่ realized/unrealized PnL และห้ามย้าย PnL ข้ามรอบ | F-13 RQ-4/9; `mission.md` §4 |
| RQ-10 | ประวัติ fill และ financial effect ต้องเพิ่มอย่างเดียวและตรวจสอบย้อนกลับได้ การแก้หรือการกลับรายการต้องแสดงเป็น fact ใหม่ตาม contract ที่อนุมัติ ห้าม UPDATE/DELETE ประวัติให้ดูเหมือนไม่เคยเกิด | trading-safety §9; database standard |
| RQ-11 | ทุก snapshot ต้องระบุ owner/mode, ขอบเขตบัญชีหรือ Paper episode, revision, source/provenance และเวลา snapshot ให้ผู้เรียกตรวจความสดและไม่ประกอบข้อมูลต่าง revision เข้าด้วยกัน | trading-safety §5/12; frontend standard §5 |
| RQ-12 | การคำนวณ unrealized PnL ต้องใช้ราคาที่เชื่อถือได้ตาม freshness ของ market-data source; ราคาไม่พร้อม/เก่า/ขัดกันต้องคืนสถานะ unavailable ไม่ใช้ราคาศูนย์ ราคาล่าสุดที่หมดอายุ หรือ realized PnL แทน | trading-safety §6/10/13 |
| RQ-13 | realized PnL ต้องเกิดจากปริมาณที่ fill จริงเท่านั้น Partial fill ต้องกระทบเฉพาะส่วนที่ fill และห้ามถือว่า order ทั้งใบสำเร็จ | trading-safety §6/11 |
| RQ-14 | authoritative position activity ต้องตอบสามสถานะได้อย่างชัดเจน: มี position, ยืนยันว่าไม่มี position, หรือ unknown/unavailable พร้อม revision ที่ผูกกับ writer protocol; missing table/row, source error หรือ stale revision ห้ามแปลว่าไม่มี position | F-13 RQ-6; F-13 plan §8; trading-safety §10/12 |
| RQ-15 | F-13 reset จะใช้คำตอบ “ไม่มี position” ได้ต่อเมื่ออ่านภายใต้ synchronization boundary เดียวกับ position writer และยืนยันว่า revision ไม่เปลี่ยนตลอด transaction; position writer ที่แข่งกับ reset ต้องมีผู้ชนะตามลำดับเดียวและห้ามเขียนเข้า episode ที่ถูกปิด | F-13 RQ-6/7; F-13 V-7/V-8 |
| RQ-16 | ข้อผิดพลาดจาก input, unit mismatch, arithmetic/rounding, duplicate conflict, missing sequence, unavailable price และ unavailable activity ต้องแยกชนิดได้โดยไม่เปิดเผยข้อมูลฐานข้อมูลหรือ secret และห้ามคงผลการเงินครึ่งชุด | security standard §3/4; trading-safety §10 |
| RQ-17 | การกระทำที่เปลี่ยน position หรือ PnL ต้องตรวจสอบย้อนหลังถึง fill ต้นทางและ audit ได้ โดย audit ไม่มี secret และแก้ไขย้อนหลังไม่ได้ | trading-safety §9; audit requirements |
| RQ-18 | ตรรกะร่วมต้องพิสูจน์ parity ด้วย fixture เดียวกันสำหรับ Paper/Live และพิสูจน์ isolation ว่า Paper path ไม่โหลดหรือเรียก venue credential/network/Live executor | ADR-004 |
| RQ-19 | การอ่านพร้อมกับ fill, retry, reset หรือ reconciliation ต้องคืน snapshot ที่สอดคล้องหนึ่ง revision เสมอ และต้องไม่แสดงยอด position/cost/PnL จากคนละ episode หรือคนละโหมดปะปนกัน | architecture/database standards; F-13 RQ-14 |

## กฎความปลอดภัยที่เกี่ยวข้อง

- `standards/trading-safety.md` §1: Paper และ Live แยกเงิน ออเดอร์ และสถานะ
- §3: การจำแนกคำสั่งลดความเสี่ยงต้องอาศัย position ที่บันทึกไว้ ห้ามเดา
- §4: idempotency และ single writer ต่อกระเป๋า
- §5: Live ใช้ Binance เป็นความจริงและต้องกระทบยอดเมื่อข้อมูลไม่ตรง
- §6: ห้ามใช้ราคาที่หมดอายุ และ partial fill ไม่ใช่ผลสำเร็จเต็มใบ
- §9: financial history/audit เพิ่มอย่างเดียว
- §10: เมื่อไม่แน่ใจต้อง fail closed และ recovery ต้องไม่ทำผลซ้ำ
- §11: partial fill ต้องใช้ขนาดที่เข้าจริง
- §12: ต้องแสดงความพร้อมและเวลาของข้อมูลบัญชี
- §13: loss-limit ใช้ closed loss ร่วมกับ unrealized loss ของไม้ที่เปิดอยู่

## ความสัมพันธ์กับ F-13 และ F-15

F-14 เป็น authoritative source เฉพาะด้าน position ส่วน F-15 ต้องเป็น authoritative source
ด้าน open order และต้องใช้ synchronization protocol เดียวกัน การปิด F-13 reset success
ต้องพิสูจน์พร้อมกันว่า position เป็นศูนย์, ไม่มี open order, source ทั้งสองพร้อม และ revision
ไม่เปลี่ยนขณะ reset ปิด episode การมี F-14 เพียงงานเดียวไม่ทำให้ reset ปลอดภัย

## คำตัดสิน NC-44–NC-49 — Closed (2026-10-16)

- **NC-44:** Position ของ Spot แยกต่อคู่เทรด (`Symbol`) ไม่รวมสินทรัพย์ฐานข้ามคู่
  ต้นทุนและ PnL อยู่ใน quote asset ของคู่นั้น
- **NC-45:** ใช้ weighted-average cost การซื้อเพิ่มเฉลี่ยต้นทุน การขายบางส่วนตัดต้นทุน
  ตามต้นทุนเฉลี่ยเดิม เมื่อปริมาณเป็นศูนย์ให้ต้นทุนคงเหลือเป็นศูนย์ การซื้อครั้งถัดไปเริ่มฐานใหม่
- **NC-46:** ใช้ fee/rebate จริงจาก execution fact เท่านั้น Fee ใน base asset ปรับปริมาณสุทธิ,
  fee ใน quote asset เพิ่มต้นทุนซื้อหรือลดรายรับขาย ส่วน fee/rebate ในสินทรัพย์ที่สาม
  เก็บเป็นรายการค่าใช้จ่ายแยกพร้อมหน่วยเดิม ไม่แปลงมารวม PnL ของคู่โดยไม่มีราคา authoritative
- **NC-47:** Unrealized PnL ใช้ราคาซื้อขายล่าสุดที่ยัง fresh ตาม market-data contract ปัจจุบัน
  และไม่หัก estimated exit fee; เมื่อราคาไม่พร้อมให้ผลเป็น unavailable
- **NC-48:** ห้ามแก้/ลบ fill เดิม ให้ append correction ที่อ้าง fill ต้นทาง แล้ว rebuild
  projection จาก event stream อย่าง deterministic; ระหว่างข้อมูลขัดกันให้ source เป็น unknown
- **NC-50 (เจ้าของยืนยัน 2026-10-16):** `REPLACE`/`VOID` คง source sequence และ
  execution identity ของ execution ที่ถูกแก้ มี event identity/เวลาบันทึกแยกต่างหาก และ correction
  ไม่เพิ่ม source completeness; rebuild ใช้ effective leaf ที่ sequence เดิม
- **NC-51 (เจ้าของยืนยัน 2026-10-16):** source initialization conflict ใช้ audit action
  `PAPER_POSITION_CONFLICTED` โดยมี subject เป็น episode activity และเก็บ episode/initialization ID;
  ห้ามสร้าง pair สมมติ ส่วน execution conflict ยังคงมี subject เป็น event พร้อม pair
- **NC-49:** Live position/cost basis คงสถานะ unknown จน F-23 กระทบยอดกับ Binance สำเร็จ
  ห้ามถือเฉพาะ fill ที่ผ่าน TiewTrade ว่าครบ และห้ามใช้ยอดถือครองสร้าง cost basis เอง

คำตัดสินเหล่านี้อนุมัติ requirements เท่านั้น `plan.md` และ `validation.md` ยังต้องได้รับ
อนุมัติแยกก่อน implementation ตาม `AGENTS.md`
