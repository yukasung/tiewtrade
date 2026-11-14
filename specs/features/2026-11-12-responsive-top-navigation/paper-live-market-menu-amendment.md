# Paper / Live market menus

สถานะ: **Approved — เจ้าของตอบ approve สำหรับ Requirements/Plan/Validation วันที่ 2026-11-13**

## Requirements

เจ้าของให้เมนูระดับบนเป็น Paper และ Live เมื่อคลิกให้แสดง Spot และ Futures
อ้างอิงรูป dropdown ที่ส่งมา

- Paper เปิดรายการ Spot และ Futures โดย Spot ไปหน้า Paper trading
- Live เปิดรายการ Spot และ Futures โดย Spot ไปหน้า Live Spot
- Futures แสดงสถานะยังไม่เปิดใช้งานตามขอบเขตที่เจ้าของเลือกไว้ก่อนหน้า
- แสดง active mode บนปุ่ม Paper หรือ Live และ active market บน Spot
- Mobile/tablet มีรายการเดียวกันในเมนูหลัก

## Plan ที่อนุมัติ

ใช้ template components/ui/dropdown/Dropdown.tsx และ DropdownItem.tsx เป็นฐาน
ตัวอย่างการประกอบคือ components/chats/ChatBoxHeader.tsx และ components/header/UserDropdown.tsx
ใน application ใช้ frontend/src/components/ui/Dropdown.tsx และ Button เดิมที่ปรับจาก template แล้ว

ปรับ AccountNavigation ให้แสดงกราฟ, Paper และ Live
Paper/Live เป็น disclosure buttons มีลูกศรและ aria-expanded/aria-controls
แต่ละรายการ Spot เป็นลิงก์เดิม /paper/trade หรือ /live/trade
Futures เป็น disabled item พร้อมข้อความแปลสถานะ

Desktop เปิด dropdown ใต้ trigger ส่วน compact แสดงรายการย่อยภายในพื้นที่เมนู
เปิดทีละกลุ่มและปิดเมื่อเลือกหน้า กด Escape คลิกภายนอก หรือเปลี่ยน breakpoint
จัด focus ของ submenu ร่วมกับ compact menu และ Settings โดยตรวจ interaction ของแต่ละชั้น
Active mode derive จาก route เดิมผ่าน navigation handlers ที่ใช้อยู่

## Validation ที่อนุมัติ

ทุกเกณฑ์เป็น Feature

- Paper/Live เปิดรายการถูกกลุ่ม Spot ไป route ถูกต้อง และ Futures disabled
- Active mode/market, deep link, Back/Forward, modified click, chart flag และสิทธิ์ผู้ดูแล
- Tab, Escape, outside click, focus return, scroll lock และ submenu ใน compact menu
- ค่าฟอร์มและ STOP request identity ผ่านเปิด/ปิดเมนูและ resize
- Browser375/768/1024/1279/1280/1440px ไทย/อังกฤษ light/dark และไม่มี navigation overflow
- Targeted navigation/layout/session/STOP tests พร้อม frontend lint/typecheck/build

เมื่อ implement และตรวจครบ แจ้ง Ready for Code Review แล้วรอ review code


## ทะเบียนเกณฑ์

| ID | ระยะ | เกณฑ์ | ผล |
|---|---|---|---|
| NAV-V38 | Feature | Paper/Live เปิดSpot/Futures,active mode/market,route/native history/modifiedclick และdisabledFuturesตามภาษา/สิทธิ์ | Passed (local) |
| NAV-V39 | Feature | keyboard/focus/outside/compact submenu/scrolllock/Settings/breakpointถูกต้องบน6width/สองภาษา/สองธีม | Passed (local) |
| NAV-V40 | Feature | ฟอร์ม/session/STOP pending/unknown/key และไม่มีmutationจากmenu/resize | Passed (local) |
| NAV-V41 | Feature ก่อนmerge | targeted/static/browserและrequiredCIบนfinalcandidate | Partial — local Passed; required CI Not Run |

หลักฐานเดิมใช้ต่อเฉพาะส่วนที่ยังvalid NAV-V26ถูกแทนด้วยV38
สถานะreview/owner acceptance/requiredCIติดตามตามworkflowของfeature


รายการย่อยแบบinlineใช้ Dropdown option outsideEvent="click" เพื่อให้ focus/pointer ไม่ปิดรายการจนปุ่มข้างเคียงเลื่อนก่อน click จบ
Callback ของแต่ละกลุ่มปิดเฉพาะกลุ่มตัวเอง ขณะ keyboard Tab ยังคงปิดเมื่อ focusออกตามเดิม
Shared Dropdown ค่าเริ่มต้นเป็น pointerdown ตามเดิมสำหรับ consumers อื่น


## ผลตรวจล่าสุด

Implementation และ local checks ผ่านตาม [market menu checkpoint](evidence/paper-live-market-menu-checkpoint.md)
Ready for Code Review รอ review code, owner acceptance และ required CI
