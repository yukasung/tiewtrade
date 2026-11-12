# Responsive Top Navigation — Borderless controls and dense chart workspace

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-12 สำหรับ Requirements/Plan/Validation ฉบับนี้**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[compact header amendment](compact-market-navigation-amendment.md),
[mission§4](../../mission.md), [frontend standard§1](../../standards/frontend.md)

## Requirements ที่เจ้าของเลือก

1. ปุ่มไอคอนบนheaderไม่มีกรอบ ปรับขนาดglyphให้พอดี; ครอบคลุม theme/account/
   Settings/hamburger โดยคงfocus-visibleและขนาดกดถึงได้
2. ลดช่องว่างและpaddingของcardในหน้าเทรด/กราฟตามโครงสร้างภาพBinanceเพื่อเพิ่มพื้นที่
   เนื้อหา โดยยังใช้สี/ตัวอักษร/controlsจากadmin templateและไม่เปลี่ยนหน้าบัญชีทั่วไป
3. ลบPAPER/LIVE Badgeหน้าคู่เทรดในTradingWorkspace ทั้งสองโหมด; เจ้าของเลือกใช้
   เมนูactiveบนdesktopและข้อความโหมดบนปุ่มเมนูมือถือเป็นตัวบอกโหมดทดแทน
4. กราฟใช้เต็มคอลัมน์กราฟและเพิ่มสัดส่วนพื้นที่ตามภาพ โดยคงฟอร์มด้านขวาและตาราง
   ด้านล่าง/scrollเดิม ไม่ใช่เปลี่ยนเป็นfullscreenที่ซ่อนส่วนส่งคำสั่ง

## Plan ที่อนุมัติ

### Header icon controls

- ใช้Button/ThemeToggleButton/icon assetsเดิม; glyph20px, click target>=44px
  คงglobal header64px desktop/56px compactและSettingsขวาสุด
- ปรับshared header stylesให้defaultพื้นหลังโปร่งใส, border/ring/shadowเป็น0
  ทั้งlight/dark; hover/focus/disabledยังอ่านได้ และkeyboard focus-visibleยังมีoutline
- Scopeเฉพาะheader controls ไม่ถอดกรอบinput/dropdown/ปุ่มส่งคำสั่ง/STOP/ฟอร์มทั่วไป
  อ้างอิงborderless patternในtemplate `layout/AppHeader.tsx`/UserDropdown และ
  ThemeToggleButton โดยบันทึกข้อยกเว้นappearanceตามคำขอเจ้าของ

### การแยก Paper/Live หลังถอด Badge

- TradingWorkspaceถอดBadgeข้างpair selectorและimportที่ไม่มีconsumerจริง
  คงmode prop, route, input ids, session/owner scope, dataและfinancial gatesเดิม
- Desktop: Paper activeบอกโหมดPaper; Spot activeมีคำกำกับ `Live` ขนาดเล็กแบบข้อความ
  ไม่มีpillเพิ่ม เพื่อให้รู้ว่าSpot routeเป็นLive ชื่อเมนูหลักยังPaper/Spot/Futures
- Compact: ปุ่มเมนูมีข้อความ `Paper` หรือ `Live` ตามrouteเฉพาะหน้าเทรด พร้อมiconเดิม
  ไม่อยู่ข้างTiewTradeและไม่ใช้Badge; aria description/labelสื่อcurrent modeด้วย
  หน้าอื่นคงtriggerปกติ ใช้i18nทั้งสองภาษาและไม่เก็บmodeสำเนาในglobal/session state
- ตำแหน่งนี้ต้องเห็นขณะscrollและไม่ซ่อนในSettings/main menu; Futuresยังdisabled
  และSpotยังรักษาLive unavailable/disabled submit/gatesเดิมทุกข้อ

### Dense workspace และพื้นที่กราฟ

- หน้าtradeใช้outer inset4px, ช่องคั่นpanel4px และpaddingtoolbar/form8px
  (template spacing1/2); standalone chartคงouter inset0pxเดิมและตัดinner gutter16px
  เปลี่ยนเฉพาะshared trading/chart styles ไม่ลดspacingฟอร์มบัญชี/securityทั่วไป
- คงform columnกว้าง22.5remเดิมเมื่อมีสองคอลัมน์; chartใช้พื้นที่ซ้ายที่เหลือทั้งหมด
  Desktop chart:ordersประมาณ4:1 โดยtableมีพื้นที่ขั้นต่ำ10remและscrollภายในได้
  หน้าไม่มีordersให้chartกินพื้นที่ที่เหลือทั้งหมด
- Workspace heightอิงviewport/measured header/outer inset แทนoffset6.8125remที่ค้าง
  จากlayoutเดิม คงflowของsafety banners/errorsเพื่อไม่ให้เนื้อหาถูกซ่อน
- เอาpaddingซ้อนของembedded chart/trading-chart-areaออก ให้chart-frame/canvas
  เติมพื้นที่content boxจริงและเหลือdividerเดียว ไม่ตัดprice/time axes,legend,
  TradingView attribution,selection/error/loading/retry controls
- ใช้renderer `autoSize:true` เดิมรับขนาดใหม่ ไม่remountchart/เปลี่ยนseries/timeframe/
  reset viewportโดยอัตโนมัติหรือเปลี่ยนhistory/live/WS/retry contracts
- Mobile/tabletคงstacked layoutตามbreakpointเดิม, controlsไม่ต่ำกว่า44px,
  chartเต็มความกว้างที่เหลือ มีความสูงอย่างน้อย420pxในstacked layoutและเลื่อนหน้าได้
  ไม่บีบหรือซ่อนfields/order statusเพื่อทำให้กราฟใหญ่

ไฟล์ที่คาดว่ากระทบ: `AccountHeader.tsx`, `AccountNavigation.tsx`, `accountMessages.ts`,
`TradingWorkspace.tsx`, shared `admin-theme.css`, `CandlestickChartPanel.css` และ
ข้อความแปล/UItestsที่เกี่ยวข้อง ใช้Button/Badgeอื่น/Dropdown/rendererเดิม ไม่มีdependencyใหม่
หรือการเปลี่ยนbackend/API/schema/เงิน/PnL/position/quantity/order logic

## Validation ที่อนุมัติ — Feature; ผลตรวจใน checkpoint

| ID | เกณฑ์ | ผล |
|---|---|---|
| NAV-V30 | header icons20px/targets>=44px; defaultไม่มีborder/ring/shadow,hover/focus-visible/disabledถูกต้อง th/en light/dark; header64/56และSettingsขวาสุด | Passed (local) |
| NAV-V31 | trade inset4/panel gap4/inner padding8ตามscope; account/securityเดิมไม่เปลี่ยน; responsiveไม่มีnavigation/chartpage horizontal overflowและไม่ซ่อนfields/tables/errors | Passed (local) |
| NAV-V32 | ไม่มีmodeBadgeหน้าคู่เทรดหรือข้างbrand; activePaper/Spot·LiveบนdesktopและPaper/Liveบนcompact triggerยังเห็นขณะscroll/menu/dialog/resize; Futuresdisabled/Livegatesเดิม | Passed (local) |
| NAV-V33 | chart frame/canvasเติมcontent boxจริง,desktopมีchartส่วนใหญ่และordersยังscrollได้,stacked chart>=420px; renderer/series/timeframe/selection/draftไม่reset; axes/legend/attribution/error/retryยังเห็นและกดถึง | Passed (local) |
| NAV-V34 | affected tests/lint/typecheck/build และbrowser6width/สองภาษา/สองธีม+short viewport ผ่าน; requiredCIfinalcandidateก่อนmerge | Partial — local Passed; required CI Not Run |

- เริ่มtargeted layout/navigation/session/STOP/CompactMarketNavigation/PaperTradePage
  และchart renderer/resize testsเดิม; เพิ่มเฉพาะborderless/computed geometry/modecue/
  canvas-resize gaps คงassertionsเงิน/key/POST counts/Paper–Live/recoveryเดิม
- Browserตรวจ375/768/1024/1279/1280/1440px รวม1024×480,ทั้งสองภาษา/ธีม, modeและ
  popup/header layering, pair/timeframe/draftผ่านresize และchart/nohorizontaloverflow
  ตรวจchartจริงบนfixtureเพื่อวัดcanvasไม่ใช้placeholderแทนหลักฐานขนาดกราฟ
- ใช้ฐานแยกและfixturesเดิม ไม่ส่งowner/Live orders; แจ้งเวลารวมก่อนbrowser
  ไม่เพิ่มtimeout/ลดassertionsเพื่อผ่าน; reuseผลเก่าเฉพาะส่วนที่ไม่กระทบ
- NAV-V27เรื่องworkspaceBadgeถูกแทนด้วยV32เมื่อamendmentอนุมัติและimplement
  คงผลเก่าเป็นประวัติcandidate ไม่ถือว่าPassedของUIเดิมรับรองตำแหน่งใหม่

## Checkpoint

Local implementation/targeted/browser checks Passed; Ready for Code Review.
Owner acceptance/review/requiredCIยังค้าง ไม่ใช่Completedหรือพร้อมmerge.

เจ้าของอนุมัติและimplementแล้วตามขอบเขตนี้ ผลตรวจอยู่ใน [checkpoint](evidence/dense-workspace-checkpoint.md)
เมื่อหลักฐานครบแจ้งReady for Code Review
และรอ `review code`; ไม่refactor/Gitpublicationเองและไม่เปลี่ยนF17FullValidation


## Amendment หลัง owner preview

เจ้าของอนุมัติ [chart toolbar and height correction](chart-toolbar-height-correction.md) แล้ว
สัดส่วน4:1และexternal controlsถูกแทนด้วย64:36และcontrolsภายในchartตามแผนล่าสุด
ผลฉบับนี้เป็นประวัติcandidate ส่วนผลปัจจุบันอยู่ใน [chart layout checkpoint](evidence/chart-layout-checkpoint.md)
