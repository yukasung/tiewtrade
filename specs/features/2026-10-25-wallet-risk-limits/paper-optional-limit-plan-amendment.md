# F-18 — Paper MANUAL ไม่บังคับเพดานขาดทุน — Plan Amendment

สถานะ: **Approved — เจ้าของอนุมัติ plan/validation amendment วันที่ 2026-10-31**
วันที่: 2026-10-31
อ้างอิง: [Requirements amendment](paper-optional-limit-requirements-amendment.md) **Approved 2026-10-31**

## 1. Domain และ policy contract

- เพิ่มสถานะที่สื่อความหมายชัดว่า Paper MANUAL “ไม่ได้ตั้งเพดาน” ได้รับข้อยกเว้น
  โดยไม่สร้าง `RiskSetting`, `RiskEvaluation`, baseline, audit หรือค่าเพดานปลอมเพื่อให้ผ่าน.
- ใช้ `TransactionalRiskPolicy`, owner lock, pair catalog lock และ financial/publication fence เดิม;
  ไม่สร้าง allow-all policy หรือ cache ผล unset ข้าม transaction.
- ทั้ง intake และ execution ต้องตรวจ scope, active Paper wallet/episode, MANUAL use,
  catalog, authoritative holdings/reservations และ global admission control ตามเดิม.
- BUY ที่ไม่มีเพดานไม่ต้องราคาเพื่อ valuation ของ loss-limit เท่านั้น;
  book/market source และ exchange/order constraints ที่ matching ต้องใช้ยังบังคับตามเดิม.
- SELL/reduction/cancel ไม่เปลี่ยน behavior.

## 2. Intake, matching และ race safety

- `resolve` อนุญาต Paper MANUAL BUY เมื่อ setting ยัง unset และ global admission พร้อม
  โดยยังตรวจ holdings/reservations และ scope เหมือนเดิม.
- `execution_context` และ matching ต้องแยก “unset ที่อนุญาต” ออกจาก “source unavailable”
  และตรวจ global control ซ้ำก่อนทำ financial effect.
- ก่อน fill ทุกครั้งต้องอ่าน setting ใหม่ภายใต้ owner/fence เดิม. ถ้ามี SET เข้ามา
  หลัง intake ต้องเลิกใช้ข้อยกเว้นและกลับไป replay/evaluate/latch เต็มรูปก่อน fill.
- ถ้า setting ใหม่ยังไม่ READY, latched หรือ source/price ไม่พร้อม ต้องพัก/ปฏิเสธตาม
  contract เดิม ห้าม fill โดยอ้างผล unset จาก intake.
- คง request/command idempotency, fill identity, cash/position atomicity และ retry behavior เดิม.

## 3. API, activation และ UI

- `GET /paper/trade` ไม่ใส่ `RISK_LIMIT_UNSET` ใน admission reasons สำหรับ Paper MANUAL;
  response schema เดิม และเหตุบล็อกอื่นยังแสดงครบ.
- Protocol activation ถือว่า zero configured Paper settings ไม่ใช่ dependency failure;
  ถ้ามี configured owner แล้ว ต้องผ่าน readiness เดิมครบ.
- `/paper/trade` สื่อว่าเพดานเป็นทางเลือก และไม่ disable ปุ่มเพราะ unset.
- `RiskLimitPanel` แสดงช่องว่างและข้อความกลางว่า “ตั้งได้ภายหลัง” ใน Paper;
  Live ยังต้องแสดงว่าบังคับตั้ง จึงต้องใช้ mode-specific copy แทนแก้ shared message ให้ผิดความหมาย.
- BOT และ Live ไม่เปลี่ยน; ไม่ส่ง Live order ในการตรวจ.

## 4. ผลกระทบและการใช้ของเดิม

- คาดว่าแก้ core risk policy/context, Paper matching integration, manual-order trade view,
  Paper trade/risk UI และ tests เท่าที่จำเป็น; ไม่เปลี่ย public API หรือ schema.
- ใช้ Money/Quantity, locks, fences, idempotency journal และ shared UI components เดิม.
- ผล W1–W4 ของ configured-owner candidate ยังใช้ต่อได้ถ้า diff ไม่เปลี่ยน scheduler,
  cadence, financial calculation หรือ configured-limit path; ต้อรัน configured-limit regression ที่ได้รับผลกระทบ.

## 5. เวลาโดยประมาณ

Implementation และ targeted verification **35–55 นาที** หากผ่านครั้งแรก;
isolated browser/manual acceptance อีกประมาณ **5–10 นาที** ไม่รวม required remote CI
หรือการแก้ finding ใหม่.

## Needs Clarification

ไม่มีสำหรับ Paper `MANUAL`; BOT/Live อยู่นอกขอบเขต.
