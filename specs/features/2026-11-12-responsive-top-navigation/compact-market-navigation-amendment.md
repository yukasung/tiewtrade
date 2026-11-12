# Responsive Top Navigation — Paper / Spot / Futures and compact header

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-12 สำหรับ Requirements/Plan/Validation ฉบับนี้**
วันที่: 2026-11-12 (Asia/Bangkok)
อ้างอิง: [requirements](requirements.md), [plan](plan.md), [validation](validation.md),
[frontend standard](../../standards/frontend.md), [mission](../../mission.md)

## Requirements ตามคำสั่งล่าสุด

- เปลี่ยนชื่อเมนูเทรดเป็น `Paper`, `Spot`, `Futures` ทั้งไทย/อังกฤษ; เมนูกราฟเดิมคงอยู่
- `Paper` ไป `/paper/trade` เดิม; `Spot` ไป `/live/trade` เดิมโดยคง Live unavailable/
  disabled submit และ authorization/financial gates เดิมทั้งหมด
- เจ้าของเลือก `Futures` แบบ “ยังไม่เปิดใช้งาน กดไม่ได้”; เป็น presentation item
  ไม่เพิ่ม route/API/engine/Futures trading code หรืออ้างว่ารองรับตลาด Futures แล้ว
- ลบ mode badge ข้าง TiewTrade ใน global header; แบรนด์คงเฉพาะ TiewTrade
  ป้าย PAPER/LIVE ใน TradingWorkspace เดิมยังอยู่เพื่อแยก Paper/Live ให้ชัดเจน
- ลดความสูง global header ตามภาพอ้างอิง Binance: เสนอ desktop64px จากปัจจุบัน76px
  และ compact56px จากปัจจุบัน60px โดยยังใช้ controls44px, template tokens/colors
  และ Settings ขวาสุดตามแผนเดิม

ขอบเขตเป็น UI/navigation เท่านั้น ไม่เปลี่ยนชื่อโหมดใน API หรือเปลี่ยน Live เป็น Paper
Futures disabled เป็นตัวเลือกที่เจ้าของยืนยัน ไม่ใช่การเริ่มพัฒนา Futures ที่ mission/NC-12
ยังไม่เปิดให้ทำ

## Plan ที่อนุมัติ

### เมนูและชื่อ

- ใช้ `accountMessages.ts` keyเดิมสำหรับPaper/Spot; เพิ่ม Futures/unavailable label
  ผ่านi18nทั้งสองภาษา ใช้ label Paper/Spot/Futures แบบ English trading terms ตามคำขอ
- AccountNavigation ใช้ href/route registry/filter/native click handler เดิม เพิ่ม
  disabled Futures ต่อท้าย primary groupทั้งdesktop/compactผ่านshared Button
  ไม่มีhref/handlerที่เปิดหน้า/ส่งคำสั่ง; aria-disabled/disabled และคำอธิบายแปลได้
- Active state ของ Paper/Spotอิง routeเดิม; Futures ไม่เป็น current page หรือรับ Tab
  ไม่แก้ chart flag, role filtering, session, history, deep links หรือ guards

### Header และการแยกโหมดอย่างปลอดภัย

- AccountHeader ถอดเฉพาะ brand mode Badge และ props/calculation/import ที่เลิกใช้จริง
  ไม่ลบ Badge component กลางหรือ mode ใน TradingWorkspace/ฟอร์ม/ข้อมูลการเทรด
- ใช้height64px desktop /56px compactแบบborder-box, paddingแนวตั้งตามพื้นที่ที่เหลือ
  คงcontrols44pxและfocus ring ไม่บีบclick target; ใช้breakpoint1280pxเดิม
- Headerวัดความสูงจริงด้วยResizeObserverเดิม; ให้ CSS custom property อยู่ที่
  authenticated workspace rootร่วมกัน เพื่อให้ main menu/Settings และ trade bar
  ใช้ค่าเดียวกัน ไม่คัดลอกความสูงหรือเพิ่มglobal business state
- ป้ายโหมดที่คงไว้ใน trade-workspace-bar ต้องยังเห็นเมื่อใช้หน้าส่งคำสั่ง:
  desktopคงbarเหนือgridที่เลื่อนภายใน; compactที่หน้าเลื่อนทั้งเอกสารให้trade bar
  stickyใต้global header ด้วยheight propertyเดียวกันและพื้นหลังtemplateเดิม
  ไม่เปลี่ยนfield/order flowหรือทำให้โหมดไปซ่อนในhamburger
- นี่เป็นข้อยกเว้นtemplateด้านheader heightตามภาพเจ้าของ และ sticky trade bar
  เพื่อรักษาfrontend standard§1ที่กำหนดให้แยกPaper/Liveได้ตลอด ไม่ใช่เพิ่มtrading rule
- ข้ามbreakpoint/เปิดเมนูไม่remountworkspace/STOP scopes/ล้างdraft; main menu/Settings
  ยังมีscroll/focusและpopupตำแหน่งถูกต้องตามmeasured header heightใหม่

ไฟล์: `AccountHeader.tsx`, `AccountNavigation.tsx`, `accountMessages.ts`, shared
`admin-theme.css`, `CandlestickChartPanel.css` เฉพาะtrade-workspace-bar/height adapter,
และaffected tests/E2E; ใช้TradingWorkspace/Badge/Button/Dropdownเดิม ไม่เพิ่มdependency

## Validation ที่อนุมัติ — Feature

| ID | เกณฑ์ | ผล |
|---|---|---|
| NAV-V26 | Paper/Spot labelsและhref/current/native navigationถูกต้อง; Futures disabledทั้งสองlayout/ภาษา ไม่มีroute/request/mutation; chart/admin filteringเดิม | Passed (local) |
| NAV-V27 | global brandไม่มีPAPER/LIVEbadge; workspaceยังแยกPAPER/LIVEด้วยBadgeเดิมและเห็นโหมดขณะscrollหน้าเทรด โดยไม่เปิดLiveหรือresetฟอร์ม | Passed (local) |
| NAV-V28 | header64px>=1280และ56px<1280ที่6viewport; controls>=44px,focusไม่ถูกตัด; main menu/Settings/sticky trade barไม่ทับกัน/nohorizontaloverflow th/en light/dark | Passed (local) |
| NAV-V29 | affected layout/navigation/session/STOP/trade-workspace testsและlint/typecheck/buildผ่าน; browserfixturesไม่ส่งowner/Live orders; requiredCIfinalcandidateก่อนmerge | Partial — local Passed; required CI Not Run |

- เปลี่ยนเฉพาะnav label/brand/header expectationsเดิม คง financial/key/receipt/
  POST counts/auth/role/native-click assertions; เพิ่ม Futures disabledและtrade bar
  scroll proofที่เดิมยังไม่มี ไม่ใช้testผ่านเพราะredirectFuturesไปหน้าที่ไม่เกี่ยวข้อง
- เริ่มtargeted5ไฟล์เดิมร่วมกับPaperTradePage/workspace testsที่stickyกระทบ;
  browserตรวจ6width375/768/1024/1279/1280/1440และtrade scrollบนfixture/ข้อมูลอ่านอย่างเดียว
  แจ้งขอบเขต/เวลารวมก่อนbrowser และคงtimeouts/assertionsเดิม
- ใช้ฐานทดสอบแยกและSTOP/status fixturesเดิม ไม่ทำรายการในบัญชีเจ้าของหรือส่งLive orders
  หลักฐานเก่าใช้ต่อเฉพาะสิ่งไม่กระทบ; คงผลก่อนamendmentตามcandidateจริง

## Checkpoint

เจ้าของอนุมัติก่อนแก้sourceแล้ว implementation/local checksตาม
[หลักฐานล่าสุด](evidence/compact-market-checkpoint.md). Ready for Code Review และรอ
`review code`; owner acceptance/requiredCIยังค้าง ไม่refactor/Gitpublicationเอง
