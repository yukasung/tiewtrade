# Responsive Top Navigation — Settings amendment

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-12 สำหรับ Requirements/Plan/Validation ฉบับนี้**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md)

## 1. Requirements ที่เจ้าของเลือก

เจ้าของเลือก: “เก็บรายละเอียด/ลองซ้ำใน Settings; ปุ่มหยุดและสถานะอยู่ด้านบน (แนะนำ)”
เป็นการแก้การจัดวาง controls ใน RQ-03/04/07/08/09/12/14 ของ feature เดิม
ไม่ใช่ feature หรือ branch ใหม่ และเจ้าของอนุมัติ Plan/Validation ด้านล่างด้วยคำตอบ approve แล้ว

- เพิ่มปุ่ม Settings หนึ่งปุ่มใน safety region ใกล้ปุ่มหยุด Paper/Live ทั้ง desktop/compact
  เปิด disclosure ที่แยกกลุ่ม Paper และ Live ชัดเจน
- ปุ่มหยุดหลักและสถานะของแต่ละโหมดยังมองเห็นด้านบนตลอด รวมเมื่อ main menu หรือ
  Settings เปิด ข้อความ pending/unknown/storage-unavailable/error ยังอ่านได้จากด้านบน
- ย้าย “ดูรายละเอียด” และ “ส่งคำขอหยุดเดิมซ้ำ” เข้า Settings; รายการรายละเอียดใช้
  เงื่อนไข stop_id/details เดิม ส่วนลองซ้ำแสดงเฉพาะเมื่อผลคำขอยัง unknown
- ไม่มีเมนู Settings สำหรับเปลี่ยนกฎการเทรด/เปิด Live/เปลี่ยนสิทธิ์ และไม่ย้าย resume
  ออกจาก summary dialog เดิมหรือข้าม reconciliation/confirmation gates

## 2. Plan ที่อนุมัติ

### การใช้ของเดิมและไฟล์ที่กระทบ

- `frontend/src/KillSwitchControls.tsx`: เปลี่ยนเฉพาะ presentation/wiring ของ controls
  คง StopControl สอง owner/mode scopes, mutation/recovery/query/journal/attemptKey
  และ lifecycle เดิม ไม่สร้าง StopControl ชุดใหม่ใน Settings
- ใช้ `frontend/src/components/ui/Dropdown.tsx`, `Button.tsx` และ tokens/style จาก
  `references/admin-template/src/components/header/UserDropdown.tsx`,
  `components/ui/dropdown/Dropdown.tsx` และ `src/icons/settings-alt.svg`
  เพิ่มข้อความไทย/อังกฤษใน `killSwitchMessages.ts`; styles อยู่ shared admin-theme
- Settings state อยู่ใน KillSwitchControls; คง settings surface/DOM target เสถียรขณะ
  ปิดด้วย hidden เพื่อย้ายเฉพาะ action presentation เข้า surface ผ่าน React portal
  ไม่ย้าย hooks หรือ financial state. ขยาย shared Dropdown แบบ opt-in keepMounted
  โดย default account dropdown คงเดิม; ไม่ใช้ CSS selector เจาะ state ของ trading domain
- KillSwitchControls/StopControl ไม่ remount เมื่อเปิด–ปิด/resize/route ใน owner เดิม
  ไม่เพิ่ม global store, session cache, dependency, backend, API หรือ schema

### Interaction และ unknown outcome

- คลิก Settings ขณะ compact main menu เปิด: ปิด main menu ก่อนตาม safety capture เดิม
  แล้วเปิด Settings; ปุ่ม Settings ไม่ส่ง STOP หรือ resume และไม่สร้าง request identity
- ปุ่มหยุดหลักเป็นคำสั่งหยุดตาม flow เดิมเมื่อไม่มี unknown; เมื่อ unknown ให้คงปุ่ม
  หยุดหลักแสดงอยู่แต่ disabled พร้อมข้อความ unknown ที่เห็นด้านบน และให้ผู้ใช้กด
  “ส่งคำขอหยุดเดิมซ้ำ” ใน Settings แทน ป้องกันการเข้าใจว่าเป็นคำขอใหม่
  นี่เป็นการเปลี่ยน affordance ของ UI ที่เสนอให้อนุมัติ; server rules ไม่เปลี่ยน
- รายการลองซ้ำเรียก mutation เดิมครั้งเดียว ใช้ attemptKey/recovery เดิมทั้งหมด
  pending/restoring ยังคง disabled ตามเดิม ไม่มี automatic retry/STOP/clear journal
  จากการเปิด–ปิด Settings หรือเปลี่ยน breakpoint
- รายการรายละเอียดปิด Settings ก่อนเปิด StopSummaryModal เดิม คืน focus ไป Settings
  เมื่อปิด dialog เพื่อไม่ชี้ไปปุ่มรายละเอียดที่ถูกซ่อน; ไม่เปลี่ยน submit/resume flow
- Settings รองรับ Tab/Shift+Tab, Escape คืน focus, คลิก/focus ภายนอกปิดโดยไม่แย่ง focus
  ปิดเมื่อ route/owner/breakpoint เปลี่ยน; ไม่มี nested open menu/focus trap แข่งกับ
  compact main menu หรือ StopSummaryModal และไม่มี scroll lock ค้าง
- หยุดหลักขณะ Settings เปิด: ปิด Settings แล้วส่ง click เดิมครั้งเดียวตาม flow เดิม
  surface hidden ไม่รับ Tab และ popup ไม่บังปุ่มหยุด/สถานะหรือทำ horizontal overflow

## 3. Validation ที่อนุมัติ — ทุกข้อเป็น Feature

| ID | เกณฑ์ | ผล |
|---|---|---|
| NAV-V14 | ปุ่มหยุด/สถานะอยู่ด้านบนทั้งสองโหมด; Settings หนึ่งปุ่ม; รายละเอียดอยู่ข้างในตามเงื่อนไขเดิม; unknown warning ยังเห็นนอกเมนู; ไทย/อังกฤษและlight/dark | Passed (local) |
| NAV-V15 | pending/unknown/storage-unavailable ภายใต้ real layout/provider/controls: เมนู/resizeไม่remount ไม่สร้างPOSTหรือเปลี่ยนkey; unknownปิดการกดหลักและ explicit retryในSettingsใช้keyเดิมครั้งเดียว; owner/Paper/Live isolationเดิม | Passed (local) |
| NAV-V16 | main menu→Settings, Settings→details/STOP, Escape/Tab/outside, route/owner/breakpoint และdialog focus restorationถูกต้อง; summary/resume gatesเดิม ไม่เกิดmutationsจากmenu lifecycle | Passed (local) |
| NAV-V17 | browser375/768/1024/1279/1280/1440px: STOP states/Settingsอ่านได้ไม่บังcontrols/nooverflow; targeted affected testsและfrontend lint/typecheck/buildผ่าน; required CIบนfinalcandidateก่อนmerge | Partial — local Passed; required CI Not Run |

- ปรับ assertions เดิมที่เข้าถึงรายละเอียด/ลองซ้ำตรง ๆ ให้เปิด Settings ก่อน
  คง assertions เงิน/key/จำนวน POST/Paper–Live/recovery/owner isolation ทั้งหมด
- เริ่ม targeted `KillSwitchControls`, `TopNavigation`, `AccountLayout`, session,
  navigation และ summary tests เดิม; เพิ่มเฉพาะ Settings/focus/hidden-controls gaps
- Browser ใช้ authenticated fixture DB และ intercepted STOP/status ตาม NAV-V07/V08 เดิม
  ไม่กด STOP/ส่งออเดอร์ในบัญชีเจ้าของและไม่ส่ง Live order; แจ้งเวลารวมก่อนรัน
- Reuse หลักฐานเดิมเฉพาะส่วนที่ไม่กระทบ; NAV-V03–08/V10/V11/V13 บางส่วนต้องตรวจซ้ำ
  ผลก่อน amendment เก็บเป็นประวัติ ไม่เปลี่ยน Failed เป็น Passed และไม่ใช้แทน CI

## 4. Checkpoint

เจ้าของอนุมัติก่อนแก้sourceแล้ว; implementation และ local verification ตาม
[Settings checkpoint](evidence/settings-checkpoint.md). งานรวมพร้อมแจ้ง
Ready for Code Review และรอ `review code`; owner visual acceptance/required CI
ยังค้าง ไม่ refactor/commit/push/PR/merge เองและไม่เปลี่ยน F17 Full Validation
