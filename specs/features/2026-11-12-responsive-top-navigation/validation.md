# Responsive Top Navigation — Validation

สถานะ: **Approved — เจ้าของตอบ “อนุมัติ” วันที่ 2026-11-12 สำหรับฉบับปรับ ThemeProvider/NAV-V13**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), testing standard§7
ผล local ล่าสุดตาม [Right panel checkpoint](evidence/right-panel-top-alignment-checkpoint.md)
NAV-V01–11/V13/V22–24/V28/V31–33/V35–36/V38–40/V42–43 Passed(local)
V25/V29/V34/V37/V41/V44 Partial(localPassed/requiredCINotRun) และ V12 Not Run
Owner acceptance ของ candidate ล่าสุดยัง Not Run ประวัติแต่ละ candidate อยู่ใน checkpoint
V14–21/V26–27/V30 ถูกแทนด้วย amendments ล่าสุด

## เสร็จหมายถึง

| ID | Requirements | เกณฑ์และวิธีตรวจ | ระยะ | ผล |
|---|---|---|---|---|
| NAV-V01 | RQ-01/02 | ทุกauthenticated routeไม่มีsidebar/icon rail/left gutter; desktop>=1280มีtop links; chart/trade/full-width และaccount/breadcrumb boundsเดิมยังถูกต้อง | Feature | Passed (local) |
| NAV-V02 | RQ-02/03/11 | primary/account/admin groupingครบและactiveถูกต้อง; chart flag0/1และuser/admin fixturesตรงเงื่อนไขเดิม; ไม่มีadmin linkสำหรับuserปกติและไม่เปลี่ยนroute guard | Feature | Passed (local) |
| NAV-V03 | RQ-04/05 | compact header56pxแถวเดียวมีbrand/account/hamburger/Settings; main menuเริ่มใต้headerจริงและscrollเอง; Settingsยังเห็นเมื่อmenuเปิดตามamendmentล่าสุด | Feature | Passed (local) |
| NAV-V04 | RQ-07 | desktop disclosureเปิด/ปิด,aria-expanded/current,Tab,Escapeคืนfocus,click-outsideไม่steal focus; ไม่มีhidden linkรับfocus | Feature | Passed (local) |
| NAV-V05 | RQ-05/06/07 | compact focusเริ่มปุ่มปิด/วนTabทั้งสองทิศ,background inert+scrolllock,Escape/close/routeปิดได้; คืนoverflow/inertเดิมหลังclose/unmountโดยไม่มีlistenerค้าง | Feature | Passed (local) |
| NAV-V06 | RQ-08/10 | open/close/resizeไม่remountKillSwitchControls/selected module/QueryClientและไม่ล้างฟอร์ม; ที่1279↔1280ปิดเมนูเก่า/คืนfocusเฉพาะhidden control; owner changeยังใช้scopeเดิมของF19 | Feature | Passed (local) |
| NAV-V07 | RQ-08/09 | mocked API pending/unknown/storage-unavailable STOPคงreceipt/keyผ่านmenu/resize; navigationเองPOST0, explicit STOPผ่านhandlerเดิมครั้งเดียว; explicitretryยังใช้keyเดิมและไม่เพิ่มautomatic request | Feature | Passed (local) |
| NAV-V08 | RQ-06/07/09 | เปิดcompact menuแล้วกดSTOPหรือSettings→details: menuปิดและclickเดิมทำงานไม่ซ้ำ; existing summary dialogได้focus/keyboard/scrolllockตามเดิม,Escapeไม่ปิดผิดlayer/ส่งคำขอเพิ่ม; ทดสอบno-owner layoutด้วย | Feature | Passed (local) |
| NAV-V09 | RQ-10/11 | direct link/reload/back/forward/เลือกหน้าปัจจุบัน/modified click/new-tab/downloadเหมือนเดิม; auth provider/sessionไม่ถูกreset,logoutคืนshell/scroll; existing AccountSession proofผ่าน | Feature | Passed (local) |
| NAV-V10 | RQ-12/13/14 | viewport375/768/1024/1279/1280/1440: ไทย/อังกฤษ,light/dark,header Paper/Live mode cue,menu/header/STOP normal/pending/unknown/error อ่านได้และfocus controlsไม่ถูกบัง; default/hover/focus/active/disabledตรงtemplate; screenshots+computed geometryยืนยันnavไม่ทำpage-level horizontal overflow | Feature | Passed (local) |
| NAV-V11 | RQ-13/14 | targeted UI/session/navigation/KillSwitch tests,frontendlint/typecheck/buildผ่าน; CSS/common controls/Modal regressionsที่เกี่ยวข้องผ่าน; ไม่มีbackend/API/schema/dependencyหรือunrelated diff | Feature | Passed (local) |
| NAV-V12 | RQ-14 | owner code review/findings/refactor checkpointตามAGENTSและrequiredCIทุกด่านผ่านบนfinalpublishedSHA; use exactrunlinks,localผลไม่แทนCI; post-mergeติดตามเมื่อownerสั่งmerge | Feature ก่อนmerge | Not Run |
| NAV-V13 | RQ-08/09/10/12/14 | real AccountLayout+ThemeProvider+KillSwitchControls ยัง render และใช้เมนู/STOP ได้เมื่อ theme storage accessor/read/write ล้ม; light fallback, theme toggle/DOM/event และ STOP identity ถูกต้องตาม fault matrix ด้านล่าง | Feature | Passed (local) |
| NAV-V14 | RQ-03/04/07/12 | Settingsหนึ่งปุ่ม; STOP/สถานะ/warningอยู่ด้านบนและdetails/retryอยู่ข้างใน; ตามamendment | Feature | Superseded — prior candidate |
| NAV-V15 | RQ-08/09 | pending/unknown/storage failuresไม่remount/สร้างPOSTจากmenu/resize; retryจากSettingsใช้keyเดิม; primary unknown disabled | Feature | Superseded — prior candidate |
| NAV-V16 | RQ-06/07/09/10 | main menu/Settings/details/STOP, focus/Tab/Escape/outside/route/owner/breakpointถูกต้องและไม่มีmutationจากlifecycle | Feature | Superseded — prior candidate |
| NAV-V17 | RQ-12/13/14 | Settings browser6ขนาด/สองภาษา/สองธีม,affected testsและstatic checks; requiredCIfinalcandidateตามamendment | Feature ก่อนmerge | Superseded — prior candidate |
| NAV-V18 | RQ-03/04/07/12 | STOPอยู่ในSettingsเท่านั้น, Settingsขวาสุด, Paper/Live status/warningsอยู่นอกpopup | Feature | Superseded — prior candidate |
| NAV-V19 | RQ-08/09 | menu/resizeไม่remount/สร้างPOST; pending/unknown/storage fault, STOP/retryรักษาkey/owner/mode/receiptตามเดิม | Feature | Superseded — prior candidate |
| NAV-V20 | RQ-06/07/09/10 | Tab order/main menu/Settings/STOP/details/Escape/outside/resize/dialog focusถูกต้อง ไม่มีmutationจากlifecycle | Feature | Superseded — prior candidate |
| NAV-V21 | RQ-12/13/14 | browser6ขนาด/2ภาษา/2ธีมและtargeted/static checks; requiredCIบนfinalcandidateตามamendment | Feature ก่อนmerge | Superseded — prior candidate |
| NAV-V22 | RQ-03/04/07/12 | ไม่มีSTOP status/warningsนอกSettings; เปิดแล้วPaper/Liveครบ; Settingsขวาสุดทุกหน้า/compactไม่มีแถวสถานะค้าง | Feature | Passed (local) |
| NAV-V23 | RQ-08/09 | hidden/open menu/resizeคงquery/pending/unknown/key/owner/mode; latest query stateแสดงเมื่อเปิด; ไม่มีPOSTจากlifecycle/explicitretryครั้งเดียว | Feature | Passed (local) |
| NAV-V24 | RQ-06/07/09/10 | focus/Tab/hidden controls/Escape/outside/scroll/menu/dialog/resizeถูกต้อง; long warningsอ่านได้ในpopupไม่บังtrigger | Feature | Passed (local) |
| NAV-V25 | RQ-12/13/14 | targeted/staticและbrowser6ขนาด/2ภาษา/2ธีม/long warningsผ่าน; requiredCIfinalcandidateตามamendment | Feature ก่อนmerge | Partial — local Passed; required CI Not Run |
| NAV-V26 | RQ-02/11/12 | Paper/Spot labels/route/current/native behaviorเดิม; Futuresdisabledในสองlayout/ภาษา ไม่มีhref/request/route; chart/adminfilterเดิม | Feature | Superseded — V38; prior candidate |
| NAV-V27 | RQ-02/04/08/10 | brandไม่มีmodebadge,workspacePAPER/LIVEcueยังเห็นระหว่างscroll,formไม่reset/Livegatesเดิม | Feature | Superseded — V32; prior candidate |
| NAV-V28 | RQ-04/07/12/13 | header64/56pxทั้ง6width/2ภาษา/2ธีม; controls>=44px; menu/Settings/stickybar/focus/nooverflowและจอเตี้ยถูกต้อง | Feature | Passed (local) |
| NAV-V29 | RQ-14 | affected tests/lint/typecheck/build/browserผ่าน; requiredCIfinalcandidateตามamendment | Feature ก่อนmerge | Partial — local Passed; required CI Not Run |
| NAV-V30 | RQ-02/04/12/14/15 | header icons20px/targets>=44px; defaultไม่มีborder/ring/shadow,hover/focus-visible/disabledถูกต้อง th/en light/dark; header64/56และSettingsขวาสุด | Feature | Superseded — V43; prior candidate |
| NAV-V31 | RQ-02/04/12/14/15 | trade inset4/panel gap4/inner padding8ตามscope; account/securityเดิมไม่เปลี่ยน; responsiveไม่มีnavigation/chartpage horizontal overflowและไม่ซ่อนfields/tables/errors | Feature | Passed (local) |
| NAV-V32 | RQ-02/04/12/14/15 | ไม่มีmodeBadgeหน้าคู่เทรดหรือข้างbrand; activePaper/LiveบนdesktopและPaper/Liveบนcompact triggerยังเห็นขณะscroll/menu/dialog/resize; Futuresdisabled/Livegatesเดิม | Feature | Passed (local) |
| NAV-V33 | RQ-02/04/12/14/15 | chart frame/canvasเติมcontent boxจริง,desktopมีchartส่วนใหญ่และordersยังscrollได้,stacked chart>=420px; renderer/series/timeframe/selection/draftไม่reset; axes/legend/attribution/error/retryยังเห็นและกดถึง | Feature | Passed (local) — corrected candidate, owner recheck pending |
| NAV-V34 | RQ-02/04/12/14/15 | affected tests/lint/typecheck/build และbrowser6width/สองภาษา/สองธีม+short viewport ผ่าน; requiredCIfinalcandidateก่อนmerge | Feature ก่อนmerge | Partial — local Passed; required CI Not Run |
| NAV-V35 | RQ-14/15 | Timeframe รวม3m/resetต่อจากpair dropdownในแถวเดียวกัน หลังtarget nodeถูกแทนที่,parent rerender,resizeและnavigation คงdraft/series/rendererและkeyboard behavior | Feature | Passed (local) |
| NAV-V36 | RQ-15 | Desktop chart/orders16:9หลังpairbarภายใน1percentage point เมื่อminimumไม่ทำงาน Open Orders/Order Historyสูงเท่ากันภายใน1px ตรวจ7widthรวม2553×1240และcanvasfill/error | Feature | Passed (local) |
| NAV-V37 | RQ-14/15 | targeted chart/PaperTradePage/renderer tests,lint/types/buildและbrowserที่กระทบผ่าน requiredCIบนfinalpublishedcandidate | Feature ก่อนmerge | Partial — local Passed; required CI Not Run |
| NAV-V38 | RQ-02/04/08/09/10/11/12/14 | Paper/Live เปิดSpot/Futures,active mode/market,route/native history/modifiedclick และdisabledFuturesตามภาษา/สิทธิ์ | Feature | Passed (local) |
| NAV-V39 | RQ-02/04/08/09/10/11/12/14 | keyboard/focus/outside/compact submenu/scrolllock/Settings/breakpointถูกต้องบน6width/สองภาษา/สองธีม | Feature | Passed (local) |
| NAV-V40 | RQ-02/04/08/09/10/11/12/14 | ฟอร์ม/session/STOP pending/unknown/key และไม่มีmutationจากmenu/resize | Feature | Passed (local) |
| NAV-V41 | RQ-02/04/08/09/10/11/12/14 | targeted/static/browserและrequiredCIบนfinalcandidate | Feature ก่อนmerge | Partial — local Passed; required CI Not Run |
| NAV-V42 | RQ-01/03/04/12/14/15 | แถบคู่เทรดกว้างฝั่งกราฟ Formเริ่มระดับเดียวกับbarและสูงถึงขอบworkspaceในPaper/Live พร้อมscrollถึงปุ่มท้ายฟอร์มและchart/orders64:36 | Feature | Passed (local) |
| NAV-V43 | RQ-01/03/04/12/14/15 | Header glyph24px,target44px,desktop icon centers44px/gap0,borderless/focus/disabled/menu/Settings/STOPถูกต้องทั้ง7width/สองภาษา/สองธีมตามส่วนที่กระทบ | Feature | Passed (local) |
| NAV-V44 | RQ-01/03/04/12/14/15 | targeted/static/browserผ่าน และrequiredCIบนfinalcandidate | Feature ก่อนmerge | Partial — local Passed; required CI Not Run |

## เลือกตรวจตามผลกระทบและใช้ของเดิม

- เริ่ม `AccountLayout.test.tsx`, `AccountNavigation.test.tsx`, `AccountSession.test.tsx`,
  `KillSwitchControls.test.tsx`; เปลี่ยนเฉพาะsidebar expectationsที่requirementแทนที่
  คงauth/role/native-navigation/receipt/unknown-retry assertionsเดิม
- เพิ่มcomponent casesเฉพาะdropdown/compact panel/focus/resize gaps;
  mount countersใช้ร่วมกับreal KillSwitch component+mockfetchเพื่อพิสูจน์request key
  และPOST counts ไม่ใช้mock componentแทนidentity-sensitive proofทั้งหมด
- NAV-V13 ใช้ real AccountLayout, ThemeProvider และ KillSwitchControls ภายใต้
  QueryClient/API fixtures เดิม; จำลอง localStorage property getter, `getItem`
  และ `setItem` โยน `SecurityError` และ `QuotaExceededError` แยกกรณี ตรวจว่า
  shell/header/STOP ยังเข้าถึงได้ ไม่ปล่อย exception ทำให้ shell หาย
- ตรวจค่า theme ขาด/ผิดรูป/อ่านไม่ได้ใช้ light และค่า `dark` เดิมยังใช้ได้;
  เมื่อ write ล้ม toggle ยังเปลี่ยน React theme, DOM class/dataset และส่ง
  `tiewtrade-theme-change` ตามเดิมโดยไม่ต้อง persistence สำเร็จก่อน ไม่เพิ่ม
  toast/log exception หรือเขียนทับ session/STOP journal/storage key อื่น
- ภายใต้ fault fixtures ของ NAV-V13 เปิด/ปิดเมนูและ resize1279↔1280 แล้ว
  controls ไม่ remount, navigation POST0, unknown receipt/request key ยังอยู่;
  explicit retry ใช้ key เดิมผ่าน handler เดิมครั้งเดียว ตรวจควบคู่ NAV-V07
  โดยไม่เพิ่ม automatic retry และคง assertions ของ valid-storage behavior เดิม
- Browser `top-navigation.spec.ts` ใช้existing authenticated E2E/guarded DB helpers
  และreal shell/navigation. ใช้controlled intercepted STOP/status fixturesเฉพาะ
  UI statesและการนับnetwork calls ไม่ใช้เป็นหลักฐานfinancial effects/backendidempotency
- ตรวจdesktopและcompactจริงที่ทุกviewportในNAV-V10; resize1279↔1280ขณะmenuเปิด,
  ฟอร์มมีค่า,STOPunknownและsummarydialogเปิด เป็นกรณีบังคับ
- Navigationหลัก/role matricesใช้component fixtures; browserตรวจactual routing/
  layout/focus/theme/locale. ใช้existing backendF19 financial/concurrency/isolation
  proofต่อเพราะsource/contractsไม่เปลี่ยน; หากต้องแตะส่วนเหล่านั้นให้หยุดขยายscopeก่อน
- ใช้targeted frontend checksระหว่างพัฒนา; requiredCIเป็นหลักฐานfullfrontend suite
  บนfinalcandidate ไม่รันfullregressionซ้ำทุกpatch หากtargetedเผยshared regression
  ให้ขยายเฉพาะพื้นที่ผลกระทบก่อนพิจารณาชุดใหญ่ตามtesting§7

## คำสั่งและหลักฐาน

ระหว่างพัฒนาเลือกvitest filesข้างต้น+ไฟล์ใหม่ตามdiff และscoped ESLintก่อน
candidateใช้ `npm run lint`, `npm run typecheck`, `npm run build` พร้อมtargeted tests.
Browserเรียกไฟล์navigationใหม่โดยตรงผ่านPlaywrightconfigเดิมบนfixture DB/Redisใหม่
ตั้งworkers1/retries0 เก็บtraceเมื่อfailureแบบprivate ไม่เพิ่มassertion timeoutให้ผ่าน
ตรวจคำสั่ง/เวอร์ชัน/locks/servicesก่อนเริ่ม และแจ้งขอบเขต/เวลารวมก่อนbrowserรอบจับเวลา

เก็บผลใน `evidence/checkpoint.md` เดียว: SHA/diff/config/runtime,คำสั่ง/ผล/เวลาที่วัด,
RQ→NAV coverage,screenshots/computed styles,failuresและcleanup; rawtrace/cookies/
credentials/owner identifiersอยู่นอกrepo. ไม่ตั้งยอดtestsหรือผลPassedล่วงหน้า
ไม่มีการรันtestsในรอบเอกสารนี้; ภายหลังผลเดิมใช้ต่อเมื่อสิ่งที่พิสูจน์ไม่ถูกกระทบ

## การตรวจด้วยมือ

หลังimplementationและaffected checksพร้อม ให้เจ้าของตรวจdesktop1440และcompact
375/768/1024: เมนู/กลุ่มบัญชี/ธีม/โหมดอ่านได้,แถบหยุดไม่ถูกบัง,หน้าเดิมไม่กระโดดหรือ
ล้างฟอร์มเมื่อเปิดเมนู/หมุนจอ. การตรวจด้วยมือบนบัญชีเจ้าของเป็นread-only navigation;
การกดSTOP/ส่งออเดอร์เพื่อสร้างหลักฐานใช้fixturesเท่านั้น ไม่เลือกค่าการเทรดแทนเจ้าของ
ผลowner visualยังNot Run และไม่ใช้ภาพpreviewแทนowner acceptanceโดยอัตโนมัติ

## ด่านและรายการที่ไม่เลื่อน

- NAV-V01–13/V22–25/V28–29/V31–44เป็นFeature gatesก่อนmerge; V14–21/V26–27/V30ถูกแทนโดยamendmentล่าสุด; ไม่มีdeferred navigation correctness/safety
- แจ้งReady for Code Reviewเมื่อimplementationครบ แล้วรอownerreviewตามAGENTS;
  หลังreview source findingsต้องรอownerrefactorตามกฎเดิม
- RequiredCI/fullcross-feature checksทำตามworkflowเดิมเมื่อownerสั่งpublication;
  ไม่แก้CIpolicy/skipchecksหรือเปิดPRเองจากการอนุมัติเอกสารนี้
- Batch/Release: ไม่มีworkload/enduranceใหม่ของnavigation. F17และfeatureอื่นยัง
  คงPending Full Validation/Dependencyตามroadmap ไม่ถูกรับรองโดยNAV tests
- ไม่มีfinancial formulasให้สร้างgolden/hypothesisชุดใหม่; UI mutation safetyอยู่
  NAV-V07/V08/V13และใช้proofเดิมของdomain/backend. ไม่มีLive order automated validation
- Failed/Incompleteต้องเก็บตามcandidate; เมื่อเข้าstop conditionในAGENTSให้หยุด
  วิเคราะห์แล้วเสนอทางเลือก ไม่auto-retry/ลดsafety/timeoutเพื่อให้เขียว

## คำขอปรับ Settings หลัง local preview (2026-11-12)

เจ้าของเลือกคงปุ่มหยุด/สถานะด้านบน และเก็บรายละเอียด/ลองซ้ำใน Settings.
ข้อกำหนดและ Plan/Validation ได้รับอนุมัติแล้วใน
[Settings amendment](settings-menu-amendment.md); implementation/local checks อยู่ใน
[Settings checkpoint](evidence/settings-checkpoint.md). ใช้หลักฐานก่อนหน้าเฉพาะส่วน
ไม่กระทบ; required CI/owner review/visual acceptance ยังไม่ผ่านแทนกัน

## คำขอปรับตำแหน่ง STOP ล่าสุด (2026-11-12)

เจ้าของสั่งย้ายปุ่ม STOP ทั้งสองเข้า Settings และวาง Settings ขวาสุด;
[Approved STOP actions amendment](settings-stop-actions-amendment.md)
implement/local checksผ่านแล้วตาม [checkpointล่าสุด](evidence/stop-actions-checkpoint.md);
คงหลักฐาน Settings ฉบับก่อนเป็นประวัติตาม candidate

## คำขอย้ายสถานะเข้า Settings (2026-11-12)

เจ้าของเลือกย้าย StopControl status/warnings เข้า Settings ด้วย;
[Approved status amendment](settings-status-amendment.md)
implement/local checksผ่านแล้วตาม [checkpointล่าสุด](evidence/settings-status-checkpoint.md);
owner review/acceptance/requiredCIยังค้าง

## คำขอ Paper / Spot / Futures และ compact header (2026-11-12)

เจ้าของเลือกชื่อPaper/Spot/Futures โดยFuturesกดไม่ได้ ลบbadgeข้างTiewTrade
และลดความสูงheader; [Approved amendment](compact-market-navigation-amendment.md)
implement/local checksผ่านแล้วตาม [checkpoint](evidence/compact-market-checkpoint.md);
owner review/acceptance/requiredCIยังค้าง

## คำขอ borderless / dense chart workspace (2026-11-12)

เจ้าของขอheader iconsไม่มีกรอบ,ลดcardspacing,ถอดBadgeหน้าคู่เทรดและขยายchart;
เลือกmodecueผ่านactive menu/compact menu text. [Approved Plan/Validation](dense-trading-workspace-amendment.md)
อนุมัติและimplementแล้ว; ผลตรวจล่าสุดและรายการค้างอยู่ใน [dense checkpoint](evidence/dense-workspace-checkpoint.md)


## Owner preview correction 2026-11-12

เจ้าของรายงาน timeframe/reset หายบนหน้า local และขอความสูงกราฟ/ตารางตามภาพ Binance
ผล local candidate ก่อนหน้ายังคงเป็นประวัติของรอบนั้น Owner visual acceptance ของฉบับปัจจุบันเป็น Failed
NAV-V33 เคยเป็น Partial ระหว่างรออนุมัติ เจ้าของตอบapproveและแก้ตาม [correction plan](chart-toolbar-height-correction.md) แล้ว
หลักฐาน candidate ใหม่อยู่ใน [checkpoint](evidence/chart-layout-checkpoint.md) Owner recheck ยังNot Run


## Owner requested inline controls

เจ้าของสั่งย้าย timeframe/reset ต่อจาก BTC/USDT ใช้ผลเก่าตาม candidate เดิมและตรวจ NAV-V35/V36/V37 ใหม่ตามผลกระทบ
ผลล่าสุดอยู่ใน [inline toolbar checkpoint](evidence/inline-toolbar-checkpoint.md) Owner recheck และ requiredCI ยังรอ


## PR69 dependency corrections — 2026-11-13

Node environment/browser setup guard and stable compact-navigation locator: 32 targeted unit tests Passed in dependency worktree. Combined candidate: 67 targeted tests, lint/typecheck Passed; wallet, dense-workspace and trading-account browser cases 3 Passed (27.9s). Wallet overflow did not reproduce locally: captureUi now waits for expected breakpoint using existing navigation pattern and attaches element bounds if strict width assertion still fails. No CSS change or relaxed viewport criterion; Linux CI confirmation remains pending. Same-threshold original CI failure remains recorded in bot-panel proposal.
