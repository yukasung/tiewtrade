# Responsive Top Navigation — STOP status inside Settings

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-12 สำหรับ Requirements/Plan/Validation ฉบับนี้**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[STOP actions amendment](settings-stop-actions-amendment.md)

## Requirements ตามคำสั่งเจ้าของ

เจ้าของยืนยันย้ายส่วนสถานะ Paper/Live และข้อความเตือนในภาพเข้า Settings
เป็นขอบเขตเฉพาะ StopControl status/warnings; แทนข้อกำหนดฉบับก่อนที่ให้ส่วนนี้อยู่นอกเมนู

- กลุ่ม Paper/Live ใน Settings แสดงสถานะล่าสุด, pending count, unknown/error และ
  storage-unavailable warnings ร่วมกับปุ่มหยุด/รายละเอียด/ลองซ้ำที่มีอยู่แล้ว
- เมื่อ Settings ปิด ไม่แสดงส่วนนี้นอกเมนูและไม่ให้ hidden content รับ focus;
  ด้านนอกของระบบควบคุมการหยุดเหลือ Settings ขวาสุดที่กดถึงได้ทุกหน้าหลัง login
- Compact ไม่มีแถวสถานะใต้ header อีก; desktop คงแบรนด์/เมนู/ธีม/บัญชีและ Settings
  ลำดับเดิม ข้อความสถานะ/เตือนจะอ่านได้หลังเปิด Settings ตามคำขอเจ้าของ
- ไม่ล้างผลคำขอเมื่อปิดเมนู; เมื่อเปิดใหม่ต้องแสดงสถานะปัจจุบันตาม query เดิม
  และรักษา pending/unknown/request key รวมเงื่อนไข disabled/retry/resume เดิม

## Plan ที่อนุมัติ

1. ใช้ StopControl/Settings/portal target เดิม ย้าย status/warnings เข้า section
   Paper/Live เดิม แสดงสถานะใต้หัวกลุ่มโดยไม่ซ้ำชื่อโหมด ไม่ย้าย hooks/query/state
   หรือสร้าง StopControl ซ้ำ; StopSummaryModal คงอยู่นอก hidden Settings surface
2. ถอด readouts wrapper/CSS ที่เลิกใช้หลังตรวจ consumer; ปรับ header grid ให้ compact
   เหลือแถวบนเดียว และคง Settings ขวาสุดทั้งสอง breakpoint ด้วย DOM order คงที่
   ใช้ measured header height เดิมกำหนดตำแหน่ง popup/main menu ไม่เดาความสูงตายตัว
3. เก็บ Settings surface แบบ keepMounted เดิม; ปิดเมนูแล้ว polling/recovery ยังคง
   ทำงานตามเดิม ไม่เพิ่ม automatic mutation/retry, ไม่เปลี่ยน key หรือ clear journal
   และไม่เพิ่ม toast/status สำเนานอกเมนู
4. คง Tab/Escape/outside/route/owner/breakpoint closure, scroll และ dialog focus
   ตามเดิม ข้อความยาว/สอง warnings ต้องเลื่อนใน popup ได้และอ่านครบโดยไม่ล้น viewport

ไฟล์ที่กระทบ: `KillSwitchControls.tsx`, `AccountHeader.tsx`, `styles/admin-theme.css`,
ข้อความแปลเฉพาะที่เลิกใช้จริง และ affected tests/E2E; ใช้ shared Dropdown/Button/
template tokens เดิม ไม่เปลี่ยน backend/API/schema/session/financial/journal logic

## Validation ที่อนุมัติ — Feature

| ID | เกณฑ์ | ผล |
|---|---|---|
| NAV-V22 | Settingsปิด: ไม่มีSTOP status/warningsนอกเมนู; Settingsขวาสุด/กดถึงได้ทุกหน้า; compactไม่มีแถวสถานะค้าง; เปิดแล้วแสดงPaper/Liveครบ | Passed (local) |
| NAV-V23 | pending/unknown/error/storage faults แสดงถูกกลุ่มหลังเปิด Settings; ปิด–เปิด/resizeไม่remount/ล้างผล/เปลี่ยนkey/สร้างPOST; explicitSTOP/retryครั้งเดียวและscopeเดิม | Passed (local) |
| NAV-V24 | Tab/hidden controls/Escape/outside/scroll/menu→Settings→details/dialog focusและbreakpointถูกต้อง; popupข้อความยาวอ่านได้ ไม่ล้นหรือบังtrigger | Passed (local) |
| NAV-V25 | targeted tests/static checks และ browser375/768/1024/1279/1280/1440px th/en light/dark ผ่าน; requiredCIบนfinalcandidateก่อนmerge | Partial — local Passed; required CI Not Run |

- ปรับ tests ให้เปิด Settings ก่อนตรวจสถานะ/alerts ตาม UI ใหม่ โดยคง assertions
  เงิน/receipt/key/จำนวนคำขอ/owner/Paper–Live/recovery เดิม ไม่ลด timeout หรือ safety
- ใช้ targeted5ไฟล์และ browser fixtures ชุดเดิมก่อน เพิ่มเฉพาะข้อความยาว/hidden state
  ที่หลักฐานยังไม่ครอบคลุม ใช้ฐานแยก ไม่ทำรายการในบัญชีเจ้าของหรือส่ง Live orders
- เก็บผล candidate ก่อนหน้าเป็นประวัติ; ตรวจซ้ำเฉพาะเกณฑ์ที่การย้ายนี้กระทบ
  NAV-V18ส่วนstatusด้านนอกถูกแทนด้วยV22 และไม่ใช้ผลเดิมรับรองตำแหน่งใหม่

## Checkpoint

เจ้าของอนุมัติก่อนแก้sourceแล้ว implementation/local checksตาม
[หลักฐานล่าสุด](evidence/settings-status-checkpoint.md). Ready for Code Review
และรอ `review code`; owner acceptance/requiredCIยังค้าง ไม่Git publicationเอง
