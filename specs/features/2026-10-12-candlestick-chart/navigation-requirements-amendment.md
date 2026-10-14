# Account navigation — ข้อกำหนดส่วนเพิ่ม

สถานะ: **Approved** — เจ้าของตอบ “approve โดยให้ กราฟแท่งเทียน แสดงเป็น default”
วันที่: 2026-10-12
ที่มา: เจ้าของยืนยันให้แยกแต่ละ module เป็นแต่ละหน้า ไม่รวมหลาย modules ในหน้าเดียว
อ้างอิง: [F-12 plan](plan.md), [F-12 requirements](requirements.md)

## ปัญหาปัจจุบัน

`AccountSidebar` ใช้ anchor เลื่อนไปส่วนต่าง ๆ ในหน้าเดียว และ `AuthPanel`
mount รายละเอียดบัญชี, TOTP, API keys, บัญชีเทรด, ราคาสดและ chart พร้อมกัน.
F-12 plan ที่อนุมัติแล้วระบุ sidebar anchor ใน AccountLayout เดิมอย่างชัดเจน;
การแยกหน้าเป็นการเปลี่ยนแนวทางนี้และมีผลต่อ lifecycle ของ panels เดิม.

## ข้อกำหนดที่เสนอ

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| NAV-01 | แต่ละ module ที่มีอยู่เปิดหน้าของตนเอง แสดงเฉพาะ module ที่เลือก แทนการ scroll ไป section หรือรวมหลาย modules ในหน้าเดียว | คำสั่งเจ้าของที่ยืนยันล่าสุด |
| NAV-02 | แยกเป็นหกหน้า: รายละเอียดบัญชีผู้ใช้, TOTP/2FA, API keys, บัญชีเทรด, ราคาสด และกราฟแท่งเทียน. แต่ละหน้ามีรายการ nav ของตนเอง; logout/logout everywhere คงอยู่ในหน้าบัญชีผู้ใช้ | modules เดิมใน AuthPanel และคำสั่งเจ้าของ |
| NAV-03 | แต่ละหน้ามี URL ของตนเอง รองรับ reload, direct link และ Back/Forward; เมนูแสดงหน้าปัจจุบัน และ navigation บน mobile ปิดหลังเลือกหน้า | ข้อเสนอเพื่อให้แยกหน้าใช้งานได้ครบ |
| NAV-04 | ใช้ AccountLayout และ session boundary เดิม; เปลี่ยนหน้าไม่ logout และไม่ปะปน cache ข้ามผู้ใช้. ออกจากหน้า module ให้ unmount module นั้นและใช้ cleanup เดิม; chart และราคาสดมี lifecycle แยกตามหน้าของตน พร้อมยกเลิกงานและป้องกัน late response | F-12 RQ-18/19, auth flow เดิม |
| NAV-05 | Chart flag เดิมยังควบคุมเมนูและหน้า chart; ไม่เพิ่ม order actions หรือเปลี่ยน mode/trading type และไม่เปลี่ยน backend contracts | F-12 RQ-23 และ scope เดิม |
| NAV-06 | เมื่อเข้าสู่ระบบหรือเปิด URL หลักโดยยังไม่ได้เลือกหน้า ให้กราฟแท่งเทียนเป็นหน้าเริ่มต้น; URL ของ module อื่นที่เปิดโดยตรงยังแสดง module นั้นหลังยืนยันตัวตน | คำสั่งเจ้าของในการอนุมัติ |

## การแก้ไขที่เจ้าของอนุมัติเพิ่มเติม

เจ้าของสั่ง “แก้ไขให้ถูกต้อง” หลังยืนยันว่าต้องการ URL `/chart`, `/account`
และ path ของแต่ละ module โดยไม่มี `#` (2026-10-12). NAV-03/06 ใช้ path routing
พร้อมรองรับ direct link/reload/Back/Forward; ไม่ใช้ hash routing.

## ผลต่อเอกสารที่อนุมัติแล้ว

ข้อกำหนดนี้ได้รับอนุมัติแล้ว; ต้องอนุมัติ [plan ส่วนเพิ่ม](navigation-plan-amendment.md)
และ [validation ส่วนเพิ่ม](navigation-validation-amendment.md) ก่อนเขียนโค้ด:
แทน mount/anchor ใน F-12 plan และระบุ lifecycle/session/nav regression checks
ของ panels ที่ได้รับผลกระทบ โดยคงเกณฑ์ chart และ trading safety เดิม.
ยังไม่เลือก routing implementation หรือเพิ่ม dependency ในขั้นข้อกำหนด.

## Needs Clarification

ไม่มีคำถามธุรกิจค้างเพิ่มเติม; NAV-01..06 ได้รับอนุมัติแล้ว.
