# F-18 — Paper manual trading without a configured loss limit — Requirements Amendment

สถานะ: **Approved — เจ้าของอนุมัติ requirements amendment วันที่ 2026-10-31**
วันที่: 2026-10-31

## เหตุผล

เจ้าของกำหนดให้ผู้ใช้ Paper Trading ส่งออเดอร์เทรดมือได้แม้ยังไม่ตั้งเพดานขาดทุน
เพื่อไม่ให้การตั้งค่าความเสี่ยงที่เป็นทางเลือกขวางการเริ่มทดลองใช้ Paper Trading

ข้อกำหนดนี้เปลี่ยนข้อบังคับเดิมใน F-18 RQ-02, NC-F18-01, V-01 และ
`specs/standards/trading-safety.md` §13 เฉพาะขอบเขตที่ระบุด้านล่าง

## ข้อกำหนดที่แก้

| ID | ข้อกำหนด |
|---|---|
| POL-RQ-01 | Paper `MANUAL` สามารถส่งคำสั่งเปิดความเสี่ยงใหม่ได้เมื่อยังไม่มี `risk_limit_settings` ของ Paper; `RISK_LIMIT_UNSET` ต้องไม่เป็นเหตุปฏิเสธคำสั่งในขอบเขตนี้ |
| POL-RQ-02 | Live ยังคงต้องตั้งเพดานก่อน activation/เปิดออเดอร์ตามกฎเดิม ไม่มีข้อยกเว้น Live |
| POL-RQ-03 | เมื่อผู้ใช้ตั้งเพดาน Paper แล้ว ทุกกฎเดิมยังบังคับครบ: authoritative evaluation, source freshness, latch, stop, queued/active-order handling, reduction/cancel, audit และ retry/idempotency |
| POL-RQ-04 | การไม่ตั้งเพดานห้ามสร้างค่า default, baseline, setting, evaluation หรือ audit ปลอม และห้ามใช้ค่าอนันต์/ค่าสูงมากแทน “ไม่ได้ตั้ง” |
| POL-RQ-05 | การอนุญาต Paper แบบ unset ไม่ bypass กฎออเดอร์อื่น: authentication/CSRF, MANUAL use, wallet/episode, เงินและ position, catalog/exchange filters, order-book/price readiness, duplicate prevention และ durable request/command protocolยังคงเดิม |
| POL-RQ-06 | ถ้าผู้ใช้ตั้งเพดานภายหลัง ขณะมี position หรือออเดอร์อยู่ ต้องใช้ SET/baseline และ financial fence เดิมเพื่อประเมิน authoritative state; ห้าม optimistic enable หรือย้อนหลังแก้ผลออเดอร์เดิม |
| POL-RQ-07 | UI ต้องสื่อว่าเพดานขาดทุนของ Paper เป็นทางเลือก ไม่แสดง “ยังเปิดออเดอร์ไม่ได้” เพราะ unset และยังให้ผู้ใช้ตั้งค่าจากหน้าจัดการบัญชีได้ |
| POL-RQ-08 | Global protocol activation/fences และ fail-closed behavior เมื่อ subsystem ที่จำเป็นต่อออเดอร์ไม่พร้อมยังคงเดิม การไม่มี Paper setting เพียงอย่างเดียวไม่ถือเป็น dependency failure |

## ขอบเขตที่ไม่เปลี่ยน

- ไม่เพิ่มสิทธิ์ Live และไม่ส่ง Live order
- ไม่เปลี่ยน Money/Quantity, PnL, leverage, margin, liquidation หรือ exchange filters
- ไม่เพิ่มการลบ/unset เพดานที่เคยตั้งแล้ว
- ไม่เปลี่ยน BOT behavior ใน amendment นี้; bot/Live authority ยังคง Pending Dependency
- ไม่ใช้การเปลี่ยนนี้ย้อนเปลี่ยนผล W1-W4 เดิม; owner ที่มี setting ยังใช้เกณฑ์ R34 เดิม

## ผลต่อเอกสารมาตรฐาน

หลัง requirements amendment ได้รับอนุมัติ ต้องแก้ `trading-safety.md` §13 ให้ระบุข้อยกเว้น
Paper MANUAL แบบ unset อย่างชัดเจน และแก้ F-18 requirements/validation pointers โดยไม่
ลดข้อบังคับ Live หรือ Paper ที่มี setting แล้ว

## Needs Clarification

ไม่มีสำหรับ Paper `MANUAL` ตามบริบทหน้า `/paper/trade` ปัจจุบัน หากต้องการให้ BOT เปิด
ความเสี่ยงได้โดยไม่มีเพดาน ต้องเป็น requirement decision แยกต่างหากก่อน implementation
เพราะมีผลต่อ F-19/F-20 และการเปิดกลับของบอท
