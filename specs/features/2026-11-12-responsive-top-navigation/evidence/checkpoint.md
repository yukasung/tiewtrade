# Responsive Top Navigation — Implementation checkpoint

วันที่: 2026-11-12 (Asia/Bangkok)
สถานะ: **Implementation/Local Validation — รอ Code Review และ required CI; ไม่ใช่ Completed/พร้อม merge**
ฐาน: main `afb2adb29e416f3e7e71aa0d497c842cb761ba6c`
Branch: `feature/responsive-top-navigation`; source ยังไม่ commit/push ตาม workflow

## ขอบเขตและ candidate

- เปลี่ยน authenticated AccountLayout/AccountHeader เป็น horizontal navigation ที่1280px
  และ compact fullscreen panel ใต้ header/safety row ที่ขนาดต่ำกว่านั้น
- AccountNavigation ใช้ accountPages/filter/navigation handler เดิมร่วมกัน; account/admin
  อยู่ disclosure บน desktop และใน panel บน compact ไม่มี sidebar/collapse/backdrop/gutter
- KillSwitchControls อยู่ safety wrapper เดียวตลอด breakpoint/menu lifecycle; ไม่แก้
  financial code, STOP/receipt/journal logic, session, backend, API, schema หรือ dependencies
- Shared Dropdown อิง template Dropdown/UserDropdown; header อิง HeaderSix ตามข้อยกเว้น
  ที่อนุมัติ ใช้ token เดิมและเพิ่ม shadow-theme-lg ที่คัดจาก template; ลบเฉพาะ sidebar tokens
  ที่ไม่มี consumer ส่วน theme preference failures ไม่ทำให้ shell หรือ STOP render ไม่ได้
- Candidate manifest เก็บ hash ทุกไฟล์ frontend ที่เปลี่ยนและสำเนา runner/config แบบ private
  ใน `frontend/test-results/navigation-runtime/`; full hashes/trace/fixture identities ไม่ลง repo
  working-tree fingerprint `f992afe23de1`; ไม่อ้าง base SHA ว่าเป็น implementation commit

## Local tests และ static checks

Runtime: Node22.23.4; npm lock เดิม (`npm ci --no-audit --no-fund`), Python3.12.15/uv lock เดิม
สำหรับ API fixture; ไม่เปลี่ยน lockfile หรือ dependency version

- Vitest10ไฟล์ที่ได้รับผลกระทบ: **127 distinct tests Passed** จากหลักฐาน122กรณีหลังแก้header
  และอีก5กรณี native-navigation ที่เพิ่มภายหลัง; rerun AccountNavigation13 และ TopNavigation16 ผ่าน
- ไฟล์: AccountLayout, AccountNavigation, AccountSession, KillSwitchControls, TopNavigation,
  AuthPanel, AuthPanelLogout, AuthLayout, CandlestickChartPanel, TradingAccountPanel
- `npm run typecheck`: Passed หลังแก้ทั้งหมด
- `npm run lint`: ตรวจทั้งfrontend พบเฉพาะunused bindingในbrowser testและfloating act
  ในtestใหม่ แก้แล้วและscoped ESLint ของไฟล์ที่แก้ต่อมาผ่าน; ไม่มีremaining lint finding
- `npm run build`: Passed หลัง source สุดท้าย; warning bundle>500kB เดิมยังมี
  ไม่เปลี่ยนbundle limit/code splittingนอกขอบเขต navigation
- NAV-V13: property getter/getItem/setItem ล้มด้วย SecurityError/QuotaExceededError รวม6กรณี
  ใช้ real AccountLayout+ThemeProvider+KillSwitchControls+QueryClient/mock API;
  ยืนยัน light fallback, toggle/DOM/theme-change event, unknown exact retry key และ POST counts
- Native navigation ครอบ ctrl/meta/shift/alt, middle click, target blank, download,
  external/prevented clicks และ same-page/popstate; route/role/chart flag/session regression ผ่าน

## Browser และการแยก runtime

ใช้ฐานใหม่ `tiewtrade_e2e_navigation_20261112` bootstrap/migrate ตาม CI เดิมบน PostgreSQL
local; Redis test logicalDB14. API8018/Vite5188 แยกจาก runtimeเจ้าของทั้งหมด ไม่มี
financial worker, ไม่มี Live orders และไม่มีคำสั่งในบัญชีเจ้าของ

Private runner/config ดัดแปลงจาก `frontend/playwright.config.ts` เฉพาะ ports/cwd,
baseURL/test selection/evidence path; ยังผ่าน `e2eEnvironment` และ throttle isolation
ที่มีอยู่ ใช้workers1/retries0 และ timeout/assertions เดิม ไม่มี automatic rerun
Auth/session จริงบน fixture DB; STOP/status เป็น intercepted fixtures เพื่อพิสูจน์ UI
และจำนวนrequestเท่านั้น ไม่ใช้เป็น financial/concurrency proof

หลักฐาน browser ครอบ10 distinct cases (8navigationใหม่+2chart navigationเดิม):

- 375/768/1024/1279/1280/1440px ×ไทย/อังกฤษ ×light/dark พร้อม24screenshots,
 computed color/geometry, no navigation horizontal overflow, primary/account grouping
- focusเริ่มclose, Tab/Shift+Tabวน, Escape/outside close, inert/body overflow restore,
 panelเลื่อนเองที่viewportเตี้ยและไม่เลื่อนbackground
- pending/unknown STOP ไม่สร้างPOSTจากmenu/resize; explicit retryใช้keyเดียวกัน
 และ detailsปิดmenuก่อนให้ summary dialogรับfocus; resizeไม่แย่งfocusจากdialog
- headerไม่remountเนื้อหาเดิม; formdraftใช้real-layout component proof;
 route/deep link/Back/Forward/reload/sessionใช้browserและexisting component proofร่วมกัน
- legacy bookmark `/prices` ไม่คืนเมนูราคาสดหรือเริ่มsubscription; chart cancellation
 และ active link assertions เดิมยังอยู่ เปลี่ยนเฉพาะ sidebar selectors/interaction

### ประวัติผล ไม่ลบหรือแปลง Failed เป็น Passed

1. Component development รอบแรก41Passed; TopNavigation รอบแรก13/14Passed:
   focus testจำลองclickโดยไม่ได้ย้ายfocusจึงไม่เกิดfocusin แก้fixtureให้focusจริง แล้ว14Passed
2. Browser round1:4Failed/4Passed (40.9s); DOM tab orderวางsafetyก่อนcompact actions
   แก้ลำดับDOMให้ตรงภาพ แล้วround2:8Passed (21.6s)
3. มีคำสั่ง Vitest ผิดcwdจากrepo root ไม่โหลดfrontend config และรวมPlaywright files
   ถือเป็น invalid verification invocation; ไม่อ้างเป็นผลิตภัณฑ์ regression หรือหลักฐานผ่าน
   รันชุดtargetedที่ถูกต้องจากfrontendหลังจากนั้น127กรณีผ่านตามหลักฐานข้างต้น
4. Browser round3:1Failed/9Passed (ประมาณ1นาที); helperเห็นcompact triggerเดิมทันทีหลัง
   resizeไปdesktopก่อนReactsettle จึงรอclick hidden element แก้helperรอtriggerของ
   breakpointปลายทางโดยไม่เพิ่มtimeout; round4เฉพาะfailed+callers3Passed (18.7s)
5. ภาพบางส่วนจับช่วงtransitionธีม จึงเพิ่มcomputed-color assertionก่อนscreenshot
   และตรวจใหม่เฉพาะgeometry/theme6กรณี: **6Passed (22.7s)** รวม24ภาพที่สีsettleแล้ว

Artifacts แต่ละรอบเก็บแยก `round1-results`, `round2-results`, `round3-results`,
`round4-results` และ `results` ล่าสุด ภายใต้ private runtime path ข้างต้น
ไม่มีraw trace/cookie/credentialsหรือowner identifiersในtracked evidence

## Cleanup

หลังรันจบ Playwright ปิดAPI8018/Vite5188 แล้ว ยืนยันportsไม่รับconnection;
ลบเฉพาะ fixture DB ที่สร้างสำหรับงานนี้สำเร็จ ไม่หยุด PostgreSQL/Redis containers,
ไม่flush Redis/shared storage และไม่หยุดหรือretarget runtime ของเจ้าของ
Schema fixtureเป็น0066จากmigrationเดิม ไม่มีmigrationใหม่

## Coverage และรายการค้าง

NAV-V01–11/V13 ใช้ local evidence ตาม validation; NAV-V12 ยังNot Run เพราะรอ
owner Code Review/findings/refactor และคำสั่งGit publication/required CI บนfinalSHA
Owner visual acceptance ยังNot Run; screenshot/component proofไม่แทนowner acceptance
F17/featureอื่นคง Batch/Release/Full Validation เดิม ไม่รับรองCompletedจากงานนี้

ขั้นถัดไป: แจ้ง **Ready for Code Review** และรอเจ้าของสั่ง `review code` ตามAGENTS;
ยังไม่refactor/commit/push/เปิดPR/mergeเอง การทดสอบระบบที่ต้องตรวจหลังrefactorและ
required CI ดำเนินต่อเมื่อถึงจุดอนุมัติเดิม
