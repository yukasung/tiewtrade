# STOP actions inside Settings — Local checkpoint

วันที่: 2026-11-12 (Asia/Bangkok)
สถานะ: **Ready for Code Review — รอ review code/owner acceptance/required CI**
อ้างอิง: [Approved amendment](../settings-stop-actions-amendment.md),
[validation](../validation.md), [candidate ก่อนหน้า](settings-checkpoint.md)
Branch `feature/responsive-top-navigation` จากmain `afb2adb`; ยังไม่commit/push
Frontend fingerprint `25a545de6c70`; full per-file manifest/runner/config/trace
และ fixture screenshots อยู่ private `frontend/test-results/navigation-runtime/`

## ผล implementation

- ปุ่ม STOP Paper/Live อยู่เฉพาะใน Settings กับรายละเอียด/ลองซ้ำ; Settings ขวาสุด
  ของแถวบนทั้ง desktop/compact. Read-only status/warnings แยกโหมดอยู่นอก Settings
- AccountHeader ใช้ grid areas และ DOM order คงที่; เพิ่ม readouts wrapper คงที่
  ย้าย primary buttons เข้า portal target เดิม ไม่ย้าย query/mutation/recovery/attemptKey
  หรือสร้าง StopControl เพิ่ม และไม่สลับ component tree/key ตาม breakpoint
- Popup อยู่ใต้ measured header/status และเลื่อนเองได้; keyboard order ตรงภาพ,
  click/resize/menu ไม่มีmutation, STOP/retryครั้งเดียว, summaryคืนfocusที่Settings
- ไม่เปลี่ยน financial, journal, resume, session, API/schema/backend/dependencies/CI
  หรือLive capability; ใช้shared template controls/icon/tokens/i18nเดิม

## หลักฐานล่าสุด

- Vitest5ไฟล์ AccountLayout/AccountNavigation/AccountSession/KillSwitchControls/
  TopNavigation: **65Passed (2.33s)** บน source นี้ รวม storage failures6กรณี,
  same-key retry, late receipts, owner switch และ UI settings lifecycle
- `npm run lint`, `npm run typecheck`, `npm run build`: **Passed**; warningbundle>500kB
  เดิมยังมี ไม่เปลี่ยนlimitหรือเพิ่มrefactorเพื่อกลบwarning
- Browser **8Passed (23.0s)** บนfixtureฐานใหม่: 375/768/1024/1279/1280/1440px,
  th/en, light/dark, 48ภาพ navigation+Settings พร้อม computed geometry/color/hit tests
- ตรวจ Settings ขวาสุดเทียบทั้งviewport edgeและcontrolsอื่น, STOP hiddenเมื่อเมนูปิด
  และมีครบPaper/Liveเมื่อเปิด, statusอยู่นอกpopup, Tabตาม4actions, Escape/focus return,
  popupใต้headerไม่บังcontrols/nooverflow และscrollในcompact panel
- Pending/unknown request keyคงเดิมข้ามmenu/resize; retry POSTครั้งเดียวต่อexplicitclick
  และไม่มีPOSTจากnavigation. Main menu→Settings→details, resizeและdialogfocusผ่าน
- ปรับ F19 browser accessors/assertionsให้เปิดSettingsก่อนSTOPและตรวจread-only status
  ด้านนอก คงmoney/generation/key/Live capabilityassertions. Dedicated risk-limitsE2E
  ยังรอrequiredCIตามworkflowเดิม; UI fixturesไม่แทนbackendfinancial/concurrencyproof

ไม่มีfailed development/browser candidateในamendmentนี้; คงประวัติก่อนหน้าไว้
ตามcandidateเดิม ไม่อ้างsourceเก่าว่าเป็นผลผ่านของUIล่าสุด

## Environment/cleanup/รายการค้าง

Fixture DB `tiewtrade_e2e_navigation_actions_20261112`, bootstrap/migration0066เดิม;
API8018/Vite5188 แยกจากเจ้าของ, workers1/retries0/timeout/assertionsเดิม
ไม่รันfinancialworkers ไม่ส่งLive ordersและไม่ทำรายการในบัญชีเจ้าของ
หลังจบปิดserversทดสอบและลบเฉพาะfixtureDBแล้ว;ไม่หยุดcontainers/flushRedis
หน้าเจ้าของ5173ยังรันbranchนี้และรับHMR รีเฟรช
`http://127.0.0.1:5173/paper/trade` เพื่อทดสอบUIใหม่ได้

NAV-V18–20 Passed(local); V21 Partial(localPassed/requiredCINotRun)
NAV-V14–17เป็นหลักฐานของSettingsฉบับก่อนซึ่งถูกแทนด้วยamendmentล่าสุด
Code review/refactor/owner visual acceptance/required CIยังค้าง; F17FullValidationเดิม
ขั้นถัดไป: Ready for Code Review แล้วรอ `review code`; ยังไม่commit/push/PR/mergeเอง
