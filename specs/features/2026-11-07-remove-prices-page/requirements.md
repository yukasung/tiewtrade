# ลบหน้า “ราคาสด” — Requirements

สถานะ: **Approved — เจ้าของตอบ “approve” วันที่ 2026-11-07**
วันที่: 2026-11-07

## ทำไมต้องมี

เจ้าของสั่งลบหน้า `http://localhost:5173/prices` ชื่อ “ราคาสด”
เอกสารนี้เสนอขอบเขตการถอดหน้าเว็บและ navigation ที่เกี่ยวข้อง
โดยต้องอนุมัติการเปลี่ยนข้อกำหนด UI เดิมก่อนเขียนโค้ดตาม AGENTS.md

## ขอบเขตและข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | ถอดหน้า `/prices` และเมนู “ราคาสด” ออกจาก navigation ทั้ง desktop/mobile | คำสั่งเจ้าของ 2026-11-07 |
| RQ-02 | เมื่อเปิด URL เดิมหลังเข้าสู่ระบบ ให้ใช้ fallback ของ route ที่ไม่มีอยู่เดิม คือ `/chart`; คงขั้นตอน authentication เดิม | ข้อเสนอ ใช้ behavior ใน `frontend/src/accountNavigation.ts` |
| RQ-03 | เอาข้อความในหน้ากราฟที่ชี้ไปเมนูราคาสดออก และลบเฉพาะ component/client/hook/style/messages ที่ตรวจแล้วว่าหมดผู้ใช้จากการถอดหน้านี้ | ผลกระทบจาก RQ-01 |
| RQ-04 | ยกเลิกการแสดงราคา สถานะ และคำเตือนการเชื่อมต่อเฉพาะ panel ที่ถูกลบ โดยไม่ย้ายไปหน้าอื่น; ปรับข้อกำหนดและเกณฑ์ตรวจ UI ของ F-10/F-12 ที่เกี่ยวข้องหลังได้รับอนุมัติ เก็บหลักฐานย้อนหลังตามจริง | ข้อเสนอ amendment ต่อขอบเขตเว็บของ F-10 รวม RQ-12/14/15 |
| RQ-05 | คง backend ingestion, price API/WebSocket, freshness, alert_due และ consumer ที่ใช้ราคาสำหรับการเทรดทั้งหมด; คงกราฟและสถานะของกราฟ | คำสั่งลบหน้าเว็บ ไม่ได้สั่งยกเลิกบริการราคา |
| RQ-06 | ปรับ tests ที่ผูกกับหน้าที่ลบ และตรวจ navigation, URL เดิม, หน้ากราฟ และการคง backend contract ตามผลกระทบ โดยไม่ลบ coverage ของ backend/session safety | testing; F-10/F-12 |

## กฎความปลอดภัยที่เกี่ยวข้อง

ไม่เปลี่ยน Money/Quantity, order/risk rules, Paper/Live isolation หรือการตรวจ
ความพร้อมราคาก่อนส่งคำสั่งตาม `standards/trading-safety.md` §6/12/13
ไม่เปลี่ยน session storage หรือเพิ่ม infrastructure

## ยังไม่ชัด — Needs Clarification

| รหัส | ต้องตัดสิน | บล็อกอะไร |
|---|---|---|
| NC-PRICES-01 — Closed (2026-11-07) | เจ้าของอนุมัติ RQ-01..06 รวมการยกเลิก UI/คำเตือนเฉพาะหน้าราคาสด และให้ URL เดิมกลับหน้ากราฟ | requirements/plan/validation Approved; ไม่มี clarification ค้างของงานลบหน้า |

requirements ได้รับอนุมัติแล้ว; [plan.md](plan.md) และ [validation.md](validation.md)
ได้รับอนุมัติแล้ววันที่ 2026-11-07; งานนี้ใช้ branch แยกจาก F-17 และ cleanup
