# Responsive Top Navigation — STOP actions inside Settings

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-12 สำหรับ Requirements/Plan/Validation ฉบับนี้**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[Settings ฉบับก่อน](settings-menu-amendment.md)

## 1. ข้อกำหนดตามคำสั่งล่าสุด

เจ้าของสั่งย้ายปุ่มหยุด Paper/Live ทั้งสองปุ่มเข้า Settings และวาง Settings ขวาสุด
คำสั่งนี้แทนการเลือกก่อนหน้าที่เก็บปุ่มหยุดไว้นอกเมนู; ยังไม่เปลี่ยน runtime ในรอบเอกสาร

- Desktop: Settings เป็น control ขวาสุดของ header ถัดจากธีมและบัญชี
- Compact/mobile/tablet: Settings เป็น control ขวาสุดในแถวบน ถัดจาก account/hamburger
  ปุ่ม Settings มองเห็นและกดถึงได้ทุกหน้าหลัง login รวมเมื่อ main menu เปิด
- ปุ่มหยุด Paper และ Live แสดงเฉพาะใน Settings แยกกลุ่มพร้อมรายละเอียด/ลองซ้ำเดิม
  เข้าถึงคำสั่งหยุดจากหน้าใดก็ได้โดยเปิด Settings แล้วเลือกโหมด (เพิ่มหนึ่งขั้นจากเดิม)
- คงสถานะอ่านอย่างเดียวที่ระบุ Paper/Live และ pending/unknown/error/storage warnings
  นอกเมนู เพื่อไม่ซ่อนผลคำขอ; compact ใช้แถวสถานะใต้ header ไม่มีปุ่มหยุดนอก Settings
- ไม่เปลี่ยน business gates, mutation/recovery/receipt/key, resume confirmation หรือ
  Paper/Live/owner isolation และไม่ทำให้ Live execution เปิดใช้งาน

เป็นการแก้ RQ-03/04/07/08/09/10/12/14 และแทนข้อกำหนด “ปุ่มหยุดอยู่ด้านนอก” ของ
Settings ฉบับก่อนเมื่อ Plan/Validation นี้อนุมัติ ไม่แก้ trading-safety ที่กำหนดให้
ปุ่มหยุดกดถึงได้จากทุกหน้า; เพิ่มทางเข้าอีกหนึ่งขั้นตามคำสั่งเจ้าของและต้องตรวจ keyboard

## 2. Plan ที่อนุมัติ

- ใช้ KillSwitchControls/StopControl/Settings/Dropdown/portal ของ implementation เดิม
  ย้ายเฉพาะปุ่มหลักเข้า section Paper/Live ของ Settings target เดิม ไม่สร้าง controls
  หรือ hooks ชุดใหม่; คง disabled pending/restoring/unknown และ same-key retry เดิม
- รวม read-only status/warnings ของสอง StopControl ใน wrapper คงที่และแยกจาก Settings
  เพื่อวางด้วย header grid areas: desktop `brand primary status actions settings`;
  compact `brand actions settings` และแถว `status` เต็มความกว้างใต้แถวบน
- ปรับ DOM ลำดับ header แบบคงที่ให้ account/theme/compact actions มาก่อน Settings
  เพื่อให้ Tab ตรงกับตำแหน่งภาพ ไม่สลับ component tree/key เมื่อเปลี่ยน breakpoint
- Settings button/popup อยู่ container เดิมตลอดอายุ owner; CSS layout adapters ใช้
  shared admin-theme/tokens และ template icon/Button/Dropdown เดิม ไม่เพิ่ม abstraction
  หรือ dependency ใหม่ ไม่เปลี่ยน session/API/schema/backend
- Popup อยู่ใต้ header+status จริง ใช้ measured header height เดิมและจำกัดความสูงตาม
  viewport มี scroll ภายใน ไม่บัง Settings/สถานะ ไม่ทำ horizontal overflow
- Main menu→Settings ปิด main menu ก่อนเหมือนเดิม; คำสั่ง STOP/retry ปิด Settings
  และเรียก handler เดิมครั้งเดียว; details dialog คืน focus ที่ Settings ตามเดิม
- ปิด Settings เมื่อ route/owner/breakpoint เปลี่ยน, Escape หรือ click/focus outside;
  hidden actions ไม่รับ Tab และเมนู/resizeไม่สร้างคำขอหรือเปลี่ยน key

ไฟล์: `AccountHeader.tsx`, `KillSwitchControls.tsx`, shared `admin-theme.css`,
ข้อความแปลเฉพาะ status label ที่จำเป็นใน `killSwitchMessages.ts`, affected tests/E2E
ไม่แก้ financial functions/journal/StopSummaryModal/backend หรือ CI policy

## 3. Validation ที่อนุมัติ — Feature

| ID | เกณฑ์ | ผล |
|---|---|---|
| NAV-V18 | ไม่มีปุ่ม STOP ที่มองเห็นนอก Settings; เปิดแล้วมี Paper/Live ครบ; Settings ขวาสุดทั้ง desktop/compact; status/warnings แยกโหมดอยู่ด้านนอกทุกหน้า | Passed (local) |
| NAV-V19 | normal/pending/unknown/error/storage faults: เปิด–ปิด/resizeไม่remountหรือสร้างPOST; explicit STOP/retry ส่งครั้งเดียวและรักษาkey/owner/mode scope; recovery/resume assertionsเดิมผ่าน | Passed (local) |
| NAV-V20 | Tab order ตรงภาพ; main menu→Settings→STOP/details, Escape/outside/route/breakpoint/focus restoration/scrollถูกต้อง; dialogไม่ถูกเมนูแย่งfocus | Passed (local) |
| NAV-V21 | browser375/768/1024/1279/1280/1440px ไทย/อังกฤษ light/dark: popup/statusไม่บังcontrols/nooverflow; targeted tests/lint/types/build และ requiredCIfinalcandidate | Partial — local Passed; required CI Not Run |

- ปรับ tests ให้เปิด Settings ก่อน STOP ตาม UI ใหม่ โดยคง assertions เงิน/key/จำนวนคำขอ/
  owner/Paper/Live และ server-state correctness เดิมทั้งหมด ไม่เพิ่ม timeout ให้ผ่าน
- เริ่มชุด targeted เดิม5ไฟล์และ browser navigation/STOP fixtures; reuse หลักฐานเดิม
  เฉพาะส่วนที่ไม่กระทบ ตรวจใหม่ NAV-V03–08/V10/V13–17 เท่าที่การย้ายนี้กระทบ
- Browser ใช้ฐานทดสอบแยกและ intercepted STOP/status ตามเดิม ไม่ทำรายการในบัญชีเจ้าของ
  ไม่ส่ง Live orders; แจ้งขอบเขต/เวลารวมก่อนรัน

## 4. Checkpoint

Implementation/local checksผ่านตาม [หลักฐานล่าสุด](evidence/stop-actions-checkpoint.md)
Ready for Code Review สำหรับขอบเขตรวมและรอ `review code`; owner acceptance/requiredCI
ยังค้าง ไม่refactor/commit/push/PR/mergeเองและไม่เปลี่ยนF17FullValidation
