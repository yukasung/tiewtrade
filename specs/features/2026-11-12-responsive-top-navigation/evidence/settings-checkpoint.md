# Settings amendment — Local checkpoint

วันที่: 2026-11-12 (Asia/Bangkok)
สถานะ: **Ready for Code Review — รอคำสั่ง review code; ยังไม่พร้อม merge**
อ้างอิง: [amendment ที่อนุมัติ](../settings-menu-amendment.md), [validation](../validation.md),
[หลักฐานก่อน Settings](checkpoint.md)
ฐาน main `afb2adb`; branch `feature/responsive-top-navigation` ยังไม่ commit/push
Frontend working-tree fingerprint `df278c36d368`; full per-file hashes/runner/config
อยู่ใน private `frontend/test-results/navigation-runtime/` ไม่ใช้ base SHA แทน source ใหม่

## Implementation

- KillSwitchControls มี Settings หนึ่งปุ่ม และกลุ่ม Paper/Live ภายใน; ปุ่มหยุดและสถานะ/
  unknown/storage warning ยังอยู่ด้านบน รายละเอียดและ retry อยู่ใน Settings เท่านั้น
- StopControl owner/mode scopes เดิมไม่ถูกย้ายหรือสร้างซ้ำ; ย้ายเฉพาะ action UI ผ่าน
  portal เข้า stable hidden surface ของ shared Dropdown (keepMounted opt-in เท่านั้น)
- Unknown ปิดปุ่มหลักตาม amendment; explicit retry ใน Settings ใช้ mutation/recovery/
  attemptKey เดิมครั้งเดียว ไม่แก้ request, receipt, journal, financial หรือ resume rules
- Details ปิด Settings ก่อนเปิด summary เดิม; ปิด summary แล้วคืน focus ไป Settings
  surface hidden ไม่รับ Tab; route/owner/breakpoint/outside/Escape ปิดโดยไม่สร้าง mutation
- ใช้ settings-alt.svg จาก admin template, shared Button/Dropdown/tokens/i18n ไทย–อังกฤษ
  ไม่เปลี่ยน API/schema/session/สิทธิ์/dependency/CI policy หรือเปิด Live

## Tests และประวัติผล

- Targeted5ไฟล์: **65 distinct cases Passed** โดยชุด64กรณีผ่านหลังปรับ Settings และ
  TopNavigation19กรณีผ่านล่าสุดหลังเพิ่มกรณี primary STOP ขณะเมนูเปิด (เพิ่ม1กรณี)
  ไฟล์ AccountLayout/AccountNavigation/AccountSession/KillSwitchControls/TopNavigation
- รักษา assertions เดิมเรื่องเงิน, same-key retry, late receipts, owner switch,
  durable recovery, Paper/Live isolation และ storage fault ทั้ง6provider cases
- รอบแรก61/62Passed: test late old receipt กด primary ก่อน recovery เก่าจบ ขณะ UI ใหม่
  unknown ถูก disable ตาม amendment; เพิ่มการรอ enabled หลัง recovery ตาม scenario เดิม
  ไม่เปลี่ยน request-key assertions หรือ production recovery เพื่อให้ test ผ่าน
- `npm run lint`, `npm run typecheck`, `npm run build`: Passed; หลังเพิ่ม/ปรับเฉพาะ tests
  ตรวจ scoped ESLint/typecheck และ affected test ต่อแล้วผ่าน ไม่มี remaining failure
  Build ยังมี warning bundle>500kB เดิม ไม่ขยาย refactor นอกงาน
- Browser authenticated fixture + intercepted STOP/status: **8Passed (31.0s)**
  375/768/1024/1279/1280/1440px ×th/en ×light/dark ทั้ง main navigation และ Settings
  เก็บ48ภาพ (24navigation+24Settings) และ computed color/geometry/hit-testing
- Browserเพิ่มเติมเฉพาะ1280px ที่เพิ่ม resize จาก focused Settings action:
  **1Passed (8.7s)**, ยืนยันปิด panel/คืน focus โดยไม่ remount/request mutation
- Pending/unknown retry คง key ข้าม resize/menu; Settings ปิดก่อน details dialog;
  dialogยังรับ focusหลังresizeและคืน Settings หลังEscape; browserใช้API fixtures
  เป็น UI proof ไม่แทน backend financial/concurrency proof
- ปรับ F19 browser selectors ให้เปิด Settings และคืนfocusไปSettings ตาม spec;
  ไม่เปลี่ยนassertionsเงิน/STOP generation/Live capability. Dedicated risk-limits E2E
  ไม่รันซ้ำทั้งชุด local; ต้องผ่าน required CI ภายหลัง publication ตาม workflow เดิม

## Runtime, cleanup และรายการค้าง

ใช้ fixture DB ใหม่ `tiewtrade_e2e_navigation_settings_20261112`, bootstrap/migrateจากCI
เดิมถึง0066 บนAPI8018/Vite5188, workers1/retries0/timeoutเดิม ไม่รัน financial workers
ไม่ส่งคำสั่งในบัญชีเจ้าของหรือ Live order. หลังจบ API/Viteทดสอบหยุดแล้วและลบเฉพาะ
fixture DB สำเร็จ ไม่หยุดcontainers/flushRedis/เปลี่ยนข้อมูลในฐานเจ้าของ

Local frontend ของเจ้าของที่5173รันbranchนี้อยู่แล้วและรับsourceผ่านHMR; URLเดิม
`http://127.0.0.1:5173/paper/trade` รีเฟรชเพื่อดู Settings ได้ ไม่ต้องสลับบัญชี/ฐานข้อมูล
ไม่มีagentกดSTOP/รายละเอียด/resumeในบัญชีเจ้าของระหว่างรอบนี้

NAV-V14–16 Passed(local); NAV-V17 Partial(local passed; required CI Not Run).
NAV-V12 owner review/refactor/required CI และ owner visual acceptance ยังค้าง;
หลักฐานก่อน Settings ใช้ต่อเฉพาะสิ่งไม่กระทบ F17 Full Validation ไม่เปลี่ยน
ขั้นถัดไป: แจ้ง Ready for Code Review และรอคำสั่ง `review code`; ยังไม่ refactor/
commit/push/PR/merge เอง
