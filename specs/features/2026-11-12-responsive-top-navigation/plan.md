# Responsive Top Navigation — Plan

สถานะ: **Approved — เจ้าของตอบ “อนุมัติ” วันที่ 2026-11-12 สำหรับฉบับปรับ ThemeProvider/NAV-V13**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [validation](validation.md)
ฐาน/branch: main `afb2adb` / `feature/responsive-top-navigation`

## 1. แนวทางและขอบเขต

เปลี่ยนเฉพาะ authenticated application shell เป็น top navigation ทุกหน้า
Desktop>=1280px ใช้ primary links+account dropdown; ต่ำกว่า1280px ใช้ hamburger
พร้อมSettingsขวาสุดในheaderแถวเดียว; panelเต็มพื้นที่ที่เหลือ ตามRQ-01–14ที่อนุมัติ
ใช้ AccountLayout/ThemeProvider/AuthPanel เดิม คง children และ QueryClient/provider
ไว้ ไม่ทำ responsive ด้วยการสลับต้นไม้ desktop/mobile ทั้งชุด

ไม่มี API/schema/migration/dependency/infrastructure/financial implementation
change ไม่มีการย้าย logout/เปลี่ยนภาษาออกจากหน้าบัญชีเดิม หรือเพิ่ม route/ความสามารถ
จาก Binance source of truth สำหรับสีและ controls ยังคงเป็น admin template

## 2. ของเดิมที่จะใช้ซ้ำ

| แหล่งเดิม | การใช้ |
|---|---|
| `frontend/src/layout/{AccountLayout,AccountHeader,PageBreadcrumb}.tsx` | shell/header, content widths, trading mode และ breadcrumb เดิม |
| `frontend/src/accountNavigation.ts` | AccountPage/accountPages, navigateAccountPage/useAccountPage, native modified clicks/history/route guards |
| `frontend/src/components/ui/{Button,Badge,Modal}.tsx` | controls/badgeเดิม; อ้างอิง keyboard/focus/scroll behavior จากModal โดยไม่แก้พฤติกรรมฟอร์ม/dialogอื่น |
| `frontend/src/KillSwitchControls.tsx`, `StopSummaryModal.tsx`, `context/ThemeContext.tsx` | ใช้component/hookเดิม; owner-scoped request identity และธีมยังอยู่ที่เดิม |
| `references/admin-template/src/components/example-layout/example-header/header-six.tsx` และ `layout/AppHeader.tsx` | sticky header, desktop/mobile controls, spacing/icons/breakpoint |
| `references/admin-template/src/components/header/UserDropdown.tsx` และ `components/ui/dropdown/{Dropdown,DropdownItem}.tsx` | shared dropdown surface, list/link styles, click-outside; เติมkeyboardตามRQ-07 |
| `frontend/src/styles/{admin-theme,admin-colors}.css`, `accountMessages.ts`, `chartMessages.ts` | tokens, icon assets และข้อความสองภาษาเดิม |
| `frontend/tests/{AccountLayout,AccountNavigation,AccountSession,KillSwitchControls}.test.tsx`, `frontend/e2e/helpers/{test,ui,environment}.ts` | existing regression/fixture guards/browser capture |

**ข้อยกเว้น template ที่อนุมัติพร้อมแผนนี้:** ตัวอย่างlayoutทั้ง6แบบใช้sidebar
จึงจัด header เป็น horizontal navigation และcompact panelเต็มพื้นที่ตามคำขอเจ้าของ
ใช้tokens/statesของtemplateเดิม; เติมfocus/inert/scrollและแถบหยุดที่templateไม่มี
เพื่อaccessibility/trading safety ไม่เปลี่ยนเป็น Binance branding/colors

## 3. โครงสร้างและ interaction

### Routing และรายการเมนู

- ให้ accountNavigation เป็นแหล่งรายการเดียว: primary=`chart,paper/trade,live/trade`,
  account=`account,security,api-keys,trading-account`, admin=`supported-symbols,system-safety`.
  deriveจากaccountPagesเดิม ไม่สร้าง route registry คู่ขนาน
- เพิ่มpure helperสำหรับ visible/grouped pages โดยรับchartEnabled/isPlatformAdmin
  ใช้เงื่อนไขเดิม; labelใช้accountText/chartText และเพิ่มข้อความmenu trigger/close
  ที่จำเป็นในaccountMessagesทั้งไทย/อังกฤษ
- สร้างlayout link rendererร่วมสำหรับdesktop/dropdown/compact panel ใช้จริง<a href>
  และnavigateAccountPageเดิม พร้อมaria-current เฉพาะหน้าปัจจุบัน
- ordinary internal clickปิดเมนูแม้เลือกหน้าปัจจุบัน; modified clicks/new tab/download
  คงnative behavior; popstate/page/owner changeปิดเมนูโดยไม่เพิ่มmutationหรือสิทธิ์

### Header และ responsive geometry

- AccountHeaderรับpage/isPlatformAdmin/owner; modecueเป็นactivePaper/Spot·LiveบนdesktopหรือPaper/Liveบนcompact triggerตามdense amendment; ยกเลิกpropsของ
  sidebar expanded/collapse จากAccountLayout ใช้matchMedia1280pxพร้อมcleanup listener
- Desktop64pxเรียงbrand→primary links(กราฟ/Paper/Spot/Futuresdisabled)→theme→account→Settings; status/actionsอยู่ในSettings.
  Compact56pxแถวบนbrand→account anchor `/account`→hamburger/Xพร้อมmode textเฉพาะหน้าเทรด→Settings;
  ไม่มีแถวstatusด้านนอก และpanelเรียงprimary→account/admin→theme
- KillSwitchControlsอยู่ในsafety wrapperเดิมเพียงชุดเดียวตลอดอายุowner scope;
  เปลี่ยนตำแหน่งด้วยCSS ไม่ย้ายด้วยconditional wrapper/key และไม่แตะhook/receipt logic
- Header stickyและmodecueอยู่header; tradebarยังstickyด้วยworkspace-root height property; compact panel fixedใต้headerจริงถึงขอบล่างviewport ใช้100dvhและ
  ResizeObserverวัดheader heightเพื่อรองรับสถานะ/ข้อความที่wrap ไม่เดาความสูงตายตัว
  panelมีscrollของตัวเอง; hidden controlsไม่รับfocus
- ปรับตำแหน่งข้อความunknown/errorเฉพาะที่ต้องสัมพันธ์กับheader/safetyใหม่ ให้ยังอ่าน
  ได้และไม่บังปุ่มหรือหลุดviewport ใช้tokensเดิมและอยู่ใต้z-indexของStopSummaryModal
- คงThemeProviderเดียว desktopมีtheme controlด้านขวา compactมีcontrolในpanel
  ใช้ThemeToggleButtonเดิม ไม่มีtheme storeใหม่

### ThemeProvider เมื่อ preference storage ใช้ไม่ได้

- ครอบการเข้าถึง `window.localStorage` รวมทั้ง property getter, `getItem` และ
  `setItem` ที่อาจโยน exception เพื่อไม่ให้ ThemeProvider ทำให้ authenticated shell
  และ KillSwitchControls render ไม่ได้ ใช้ key `theme` เดิม; เฉพาะค่า `dark` เลือก
  dark ส่วนค่าขาด/ผิดรูป/อ่านไม่ได้ใช้ค่าเริ่มต้น light เดิม
- เมื่อบันทึกไม่ได้ ให้ธีมที่ผู้ใช้เลือกยังมีผลใน React state ตลอด mount นั้น และ
  อัปเดต DOM class `dark`, `data-color-scheme` และ event `tiewtrade-theme-change`
  ตามเดิมแม้ persistence ล้ม ไม่เพิ่ม theme store, toast หรือ log ข้อความ exception
- fallback นี้ใช้เฉพาะ preference ของ UI ไม่ใช้กับ session หรือ business data;
  ไม่ล้าง/เขียนทับ STOP journal หรือ storage key อื่น และไม่เปลี่ยน receipt/retry logic
- เพิ่ม fault tests ผ่าน real AccountLayout, ThemeProvider และ KillSwitchControls
  ร่วมกับ QueryClient/API fixtures เดิม ไม่ใช้ผลจาก standalone controls แทน
  หลักฐานว่า outer provider ยัง render shell และคง STOP identity ได้ (NAV-V13)

### Focus, scroll และปุ่มหยุด

- Desktop dropdownเป็นdisclosureพร้อมรายการลิงก์ ไม่ใช้role=menuที่ต้องเปลี่ยน
  รูปแบบkeyboard เปิดด้วยbutton/aria-expanded/aria-controls; Escapeคืนfocustrigger,
  คลิกภายนอกปิดโดยไม่แย่งfocusจากเป้าหมายที่คลิก และTabตามลำดับปกติ
- Compactเมื่อเปิด ให้header regionที่รวมแถวบน+safety+panelเป็นmodal dialogชั่วคราว
  ที่มีชื่อจากi18n; content wrapperภายนอกซึ่งรวมbanner/pageเป็นinert/aria-hidden
  ขณะเปิด แล้วคืนค่าเดิมเมื่อปิด/unmount ใช้DOMโครงสร้างเดิม เปลี่ยนattributesเท่านั้น
- focusเริ่มที่ปุ่มปิด; Tab/Shift+Tabวนในcontrolsที่มองเห็นของheader+safety+panel.
  Escapeปิดและคืนfocushamburger; body overflowถูกเก็บ/คืนค่าเดิม และไม่เลื่อนเนื้อหา
  หลังpanel; route navigationไม่ดึงfocusกลับไปtriggerของหน้าเก่า
- safety wrapperจับclick captureเพื่อปิดdropdown/compact menuก่อนส่งclickเดิมไป
  KillSwitchControls โดยไม่preventDefault/stopPropagation/เรียกSTOPเอง.
  การปิดเหตุนี้ไม่คืนfocustrigger จึงไม่แย่งfocusจากStopSummaryModalที่เปิดตามมา
- ข้ามbreakpointปิดpopup/panel, คืนscroll/inert; ย้ายfocusเฉพาะเมื่อcontrolเดิมถูก
  ซ่อน ไปยังnavigation triggerที่มองเห็น ไม่แย่งfocusจากฟอร์มหรือStopSummaryModal
- เมื่อlogout/unmountคืนscroll/inertและถอดlisteners ไม่focusDOMที่ถูกถอดแล้ว

## 4. ไฟล์ที่กระทบและการรักษา compatibility

| ส่วน | สิ่งที่จะเปลี่ยน |
|---|---|
| `frontend/src/layout/AccountLayout.tsx`, `AccountHeader.tsx` | shell, stable safety region, responsive/menu state/focus และcontent inert |
| `frontend/src/layout/AccountNavigation.tsx` (ใหม่) | link/group rendererที่ใช้route sourceเดิมร่วมกัน |
| `frontend/src/components/ui/Dropdown.tsx` (ใหม่) | adapttemplateเป็นcontrolled shared disclosure; trigger ref/open/onClose/id/children/className สำหรับ keyboard/outside closure |
| `frontend/src/accountNavigation.ts`, `accountMessages.ts` | visible grouping/i18n; URL/authorization/provider logicเดิม |
| `frontend/src/context/ThemeContext.tsx` และ targeted theme/layout tests | ป้องกัน preference storage accessor/read/write failures; คง light default, DOM/event semantics และธีมระหว่าง mount โดยไม่แตะ session/STOP storage |
| `frontend/src/styles/admin-theme.css` | header/nav/panel/dropdown states; เอาsidebar margin/collapse/backdrop rulesที่เลิกใช้ |
| `frontend/src/layout/AccountSidebar.tsx` | ถอดและลบเมื่อไม่มีcaller; ลบเฉพาะCSS/assetsที่ค้นแล้วไม่มีconsumerใหม่หรือเดิม |
| targeted tests และ `frontend/e2e/top-navigation.spec.ts` (ใหม่) | เปลี่ยนsidebar assertionsเป็นrequirementsใหม่และเพิ่มเฉพาะcoverage gaps |

คงpublic component/route behaviorของเนื้อหาแต่ละหน้า, account width/breadcrumb,
Paper/Live distinction และผู้ดูแลตามเดิม Header props/Dropdownเป็นinternal UI
interfacesเท่านั้น ไม่แก้backend/OpenAPI/types/session/DB และไม่retargetlocal runtime
ของเจ้าของหรือสลับuser dataสำหรับbrowser proof

### Dense chart workspace — amendment Approved

ใช้ [dense amendment](dense-trading-workspace-amendment.md) เป็นแผนปัจจุบันของicons/modecue/spacing/geometry. ใช้renderer autoSizeเดิมและsharedCSS; ไม่แก้renderer/data/order logic. Template exceptionsเพิ่มเติมคือborderlessheader iconsและ4/8px trading spacingตามคำขอเจ้าของ; account/security formspacingคงเดิม.

## 5. ความเสี่ยงและหลักฐานที่ต้องได้

| ความเสี่ยง | หลักฐาน |
|---|---|
| remountทำให้unknown STOP/request keyสูญหาย | NAV-V06/V07, existing F19 UI regressions; storage failure+pending receipt fixtures |
| ThemeProvider โยน exception ก่อน shell/STOP render หรือก่อนส่ง theme event | NAV-V13: real layout/provider/controls fault tests ครอบ accessor/read/write และ request identity |
| focus trapชนกับStopSummaryModal/scrolllockค้าง | NAV-V04/V05/V08, real browser keyboard+resize/logout |
| linkหาย/เพิ่มสิทธิ์/รีเซ็ตsession | NAV-V02/V09, existing role/path/session tests; server guardsไม่เปลี่ยน |
| headerล้นบนไทย/tablet/unknown states | NAV-V03/V10, viewport/boundary screenshots/computed geometry |
| CSS sharedกระทบform/Modal/หน้ากราฟ | NAV-V01/V10/V11, reuse component styles, targeted regressions+build |

## 6. ลำดับและ checkpoints

1. เจ้าของอนุมัติplan+validationวันที่2026-11-12ก่อนแก้sourceแล้ว; requirementsApprovedและไม่มีNCค้าง
2. แก้route grouping/shared navigation+dropdown แล้วปรับheader/layout/stylesและ
   ลบdead sidebarตามconsumerจริง; ป้องกัน theme preference storage failures ตาม
   ขอบเขตข้างต้น รวมtest updatesและreal-layout fault testsก่อนตรวจเป็นชุด
3. รันtargeted testsตามvalidation และfrontendlint/typecheck/build; แก้เฉพาะdiffนี้
   ก่อนbrowserตรวจruntime/locks/fixture DB/ports ให้พร้อม; แจ้งขอบเขต/เวลารวมก่อนรัน
4. รันtargeted browserบนฐานแยกตามexisting E2E guards ไม่ใช้บัญชีเจ้าของ; บันทึก
   source/config/ผล/เวลา/cleanupในevidence checkpointเดียว ไม่อ้างUI mockเป็นเงินจริง
5. implementationครบทั้งfeatureให้แจ้ง **Ready for Code Review** พร้อมผลtests/
   เกณฑ์ค้าง/ความเสี่ยง แล้วหยุดรอ `review code` ตามAGENTS ไม่review/refactorเองต่อ
6. หลังowner review/fixes/refactorที่อนุญาต ให้ตรวจเฉพาะผลกระทบและใช้หลักฐานเดิม
   ที่ยังvalid; commit/push/PR/requiredCIและmergeต้องคำสั่งเจ้าของ ไม่เปิดเองในแผนนี้

ก่อนmerge: ทุกNAV Feature criterion/review/requiredCIต้องผ่านfinalcandidate.
RequiredCIยังรันfullfrontend regressionsตามworkflow ไม่รันfullbackend/financial
workloadเองซ้ำเพื่องานlayout; ขยายlocal regressionเมื่อtargeted proofพบผลกระทบใหม่
Batch/ReleaseของF17/งานอื่นคงเดิม ไม่มีworkloadหรือSLAใหม่ในงานnavigation
หากชนNC/approved requirement change/เกณฑ์เดิมไม่ผ่าน3รอบ ให้หยุดตามAGENTS
ไม่ลดtimeout/assertionsหรือใช้ผลlocalแทนrequiredCI

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


## แผนล่าสุดสำหรับ chart toolbar และความสูง

เจ้าของอนุมัติ [correction plan](chart-toolbar-height-correction.md) หลัง preview แล้ว
ใช้ trading-market-bar และ chart-controls ภายใน CandlestickChartPanel แทน external portal
เอา target lookup/state/prop และ div ที่เลิกใช้ออก ใช้ shared Select/Button และ renderer เดิม
Desktop ใช้ grid rows 16fr:9fr พร้อม minimum 22rem/10rem แทนสัดส่วน 4:1 ของ dense amendment
Embedded panel เป็น flex column โดย toolbar กินพื้นที่ก่อน canvas ส่วน stacked layout ให้พื้นที่ chart area อย่างน้อย 420px แยกจาก toolbar
ผลตรวจใน [chart layout checkpoint](evidence/chart-layout-checkpoint.md)


## ตำแหน่ง toolbar ล่าสุดตามคำสั่งเจ้าของ

Timeframe และ reset อยู่ต่อจาก BTC/USDT ใน trade-workspace-bar ตามคำสั่งหลัง preview
TradingWorkspace ใช้ callback ref กับ React context ส่ง target node ให้ chart-controls ผ่าน portal
ใช้ lifecycle ของ ref เมื่อ node ถูกแทนที่และเลิกใช้ document lookup ตามแผนแก้ controls หาย
Standalone ใช้ toolbar ภายในกราฟตามเดิม ผลล่าสุดใน [inline toolbar checkpoint](evidence/inline-toolbar-checkpoint.md)


## แผนเมนู Paper / Live ที่อนุมัติล่าสุด

ใช้ [market menu amendment](paper-live-market-menu-amendment.md) แทนชื่อเมนูระดับบนPaper/Spot/Futures
ใช้ shared Dropdown/Button, registryและnavigateAccountPageเดิม
MarketMenuในAccountNavigationประกอบtriggerและSpot/Futures ตามpatternChatBoxHeader/UserDropdownของtemplate
Desktopใช้dropdown ส่วนcompactใช้รายการย่อยภายในpanel ใช้stateเปิดทีละกลุ่มและderiveactiveจากroute
Escapeในรายการย่อยปิดเฉพาะรายการย่อยและคืนfocusก่อนถึงdocument handlerของcompact menu
Outside/focus/popstate/page/breakpointใช้lifecycleของdropdownและshellที่มีอยู่


## Right panel alignment ที่อนุมัติล่าสุด

[แผนจัดแนวฟอร์ม](right-panel-top-alignment-amendment.md) เปลี่ยนtrade gridเป็น bar/form,chart/form,orders/form
กรณีไม่มีordersใช้bar/form,chart/form ส่วนstacked layoutใช้flowเดิม
Header icon stylesใช้24pxทั้งglyphของธีม/บัญชี/Settings/hamburgerตามAppHeader/UserDropdown template
ผลตรวจติดตามในNAV-V42–44


Desktop icon spacing ตามคำสั่งล่าสุดใช้column-gap0ในheaderและgap0ในdesktop actions
Brandใช้margin-inline-end16pxเพื่อคงระยะก่อนเมนูหลัก Targets44pxเรียงติดกันและglyph24pxมีระยะกึ่งกลาง44pxเท่ากัน


## PR69 dependency corrections — Approved
เจ้าของสั่งเริ่มแก้ 4 จุดตาม publication-ci-corrections-proposal ของ Paper Spot: guard browserSetup เฉพาะ DOM environment; ใช้ compact-navigation aria-controls locator ที่คงเดิมเมื่อชื่อปุ่มเปลี่ยน; ตรวจ element bounds ก่อนแก้ wallet overflow. คง Node isolation, keyboard/focus และ viewport assertions; ไม่เปลี่ยน trading logic.

Wallet diagnosis: local bounds fit360px, so no speculative CSS change. Reuse navigationLink breakpoint readiness pattern in captureUi; attach only element tag/class/bounds on overflow, retain strict viewport check.

PR70 publication correction: backport only F19 STOP Settings/menu test steps already verified on PR69. Keep Paper/Live separation, unknown-request identity, money assertions and90s timeout. No production changes. Target both affected tests on an isolated DB before publishing correction.
