# Responsive Top Navigation — Requirements

สถานะ: **Approved — เจ้าของตอบ approve วันที่ 2026-11-12 สำหรับ requirements ฉบับนี้**
วันที่: 2026-11-12 (Asia/Bangkok)
ฐาน: main `afb2adb29e416f3e7e71aa0d497c842cb761ba6c`
Branch: `feature/responsive-top-navigation`

## ทำไมต้องมี

Sidebar ใช้พื้นที่แนวนอนของกราฟและหน้าเทรด เจ้าของต้องการย้ายการนำทางไว้ด้านบน
และใช้ hamburger แบบ Binance บน mobile/tablet โดยคงรูปแบบ UI ของ admin template
และการเข้าถึงปุ่มหยุดตามกฎความปลอดภัย

เจ้าของเลือกทุกหน้าหลัง login, desktop เมนูหลักพร้อมบัญชีรวม และแถบหยุดใต้ header
บน mobile/tablet จากนั้นสั่ง implement แผนเดียวกัน งานนี้แยกจาก F-17 ซึ่ง merge แล้ว
และรักษาไฟล์ค้าง/บริการ local ของงานเดิมไว้

## ขอบเขต

ครอบคลุม authenticated application shell, navigation, dropdown, responsive menu,
focus/scroll และตำแหน่ง controls เดิม รวมหน้าผู้ดูแลตามสิทธิ์
หน้าสมัคร/เข้าสู่ระบบใช้ AuthLayout เดิม ชื่อเมนูและปลายทางใช้ของ TiewTrade
ภาพ Binance อ้างอิงโครงสร้างและ interaction; สี/typography/spacing/control states
ใช้ admin template และ component กลางของโครงการ

ไม่เปลี่ยน API/schema/session/สิทธิ์/ข้อมูลบัญชี/กฎเงินหรือการส่งออเดอร์ ไม่เพิ่ม
Spot/Futures/currency functionality จากภาพอ้างอิง ไม่เปิด gate หรือ Live และไม่
ใช้รอบตรวจนี้เปลี่ยนสถานะ Full Validation/Dependency ของ F-17

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-01 | ทุกหน้าหลัง login ไม่มี sidebar/icon rail หรือพื้นที่เยื้องที่เหลือจาก sidebar; คงรูปแบบความกว้างเฉพาะของกราฟ/หน้าเทรด/หน้าบัญชี | เจ้าของเลือกทุกหน้าหลัง login; แผนที่สั่ง implement |
| RQ-02 | Desktop>=1280px: TiewTradeและกราฟ/Paper/Liveด้านซ้าย; Paper/LiveเปิดSpot/Futures โดยFuturesdisabled; activePaperหรือLiveบอกโหมดขณะscroll | Paper/Live market menu amendment Approved |
| RQ-03 | Desktop header64pxด้านขวามีธีม/บัญชีและSettingsขวาสุด; STOP/status/warnings/รายละเอียด/ลองซ้ำของPaper/Liveอยู่ในSettingsตามamendmentล่าสุด; account dropdown/สิทธิ์เดิม | Settings status amendment Approved |
| RQ-04 | <1280px: header56pxแถวเดียวมีแบรนด์ไม่มีmodebadge,account/hamburgerและSettingsขวาสุด; primary menuในpanelมีPaper/Live เปิดรายการSpot/Futuresdisabled; หน้าเทรดมีPaper/Liveบนhamburger; STOP/status/warningsอยู่ในSettings | Paper/Live market menu amendment Approved |
| RQ-05 | Hamburger เปิดเมนูแนวตั้งเต็มพื้นที่ใต้headerและเปลี่ยนเป็นปุ่มปิด; เรียงกลุ่มหลักก่อนกลุ่มบัญชีและมีตัวเปลี่ยนธีม; เมนูเลื่อนภายในได้ | ภาพอ้างอิงและแผนที่สั่ง implement |
| RQ-06 | เปิดเมนูmobileแล้วเนื้อหาด้านหลังเลื่อนหรือรับการกดไม่ได้; ปิดเมื่อเลือกหน้า, Escape หรือปุ่มปิด; คืนscroll/focusถูกต้องและไม่บังSettings | แผนที่สั่ง implement; frontend accessibility/safety |
| RQ-07 | Desktop dropdown รองรับTab, Escape, คลิกภายนอกและactive state; mobileจัดการfocusและทำงานร่วมกับdialogของปุ่มหยุดเดิมได้ | แผนที่สั่ง implement |
| RQ-08 | คงKillSwitchControlsเพียงชุดเดียวและไม่remountเมื่อเปิดเมนูหรือข้ามbreakpoint; pending/unknown/error/request identityยังอยู่และอ่านข้อความสถานะได้ | แผนที่สั่ง implement; F-19/trading-safety§8 |
| RQ-09 | เปิดSettingsระหว่างmain menuเปิดต้องปิดmain menu; STOP/retryปิดSettingsและเรียกhandlerเดิมครั้งเดียว; detailsไม่แย่งfocusจากdialog; เมนู/resizeไม่ส่งmutation | Approved amendment; idempotency/trading safety |
| RQ-10 | ข้ามbreakpointแล้วปิดเมนูที่เลิกใช้และคืนscroll/focus โดยไม่resetฟอร์ม/เนื้อหาหน้าปัจจุบันหรือauthentication provider | แผนที่สั่ง implement; session/stateless standards |
| RQ-11 | คงURL/deep link/Back/Forward/native modified click และการกรองchart flag/เมนูผู้ดูแลเดิม; SpotในPaper/Liveใช้routeเดิม,Futuresdisabled; การย้ายลิงก์ไม่เพิ่มสิทธิ์หรือเปลี่ยนserver authorization | accountNavigationเดิม; security standards |
| RQ-12 | ทุกข้อความใช้ระบบแปลเดิม; ไทย/อังกฤษและlight/darkทำงานครบ พร้อมdefault/hover/focus/active/disabled; ไม่มีpage-level horizontal overflowจากnavigation | mission R-20; frontend standards |
| RQ-13 | ใช้Header/UserDropdown/controlsของtemplateเป็นฐานและshared componentsก่อนสร้างใหม่; บันทึกข้อยกเว้นhorizontal/fullscreen layoutตามคำขอเจ้าของในplan | frontend standards§2.1; คำสั่งเจ้าของ |
| RQ-14 | ตรวจtargeted layout/navigation/session/KillSwitch regressions, browserที่375/768/1024/1279/1280/1440px, frontendlint/types/buildและrequiredCI; ใช้fixturesสำหรับSTOP และไม่ทำรายการในบัญชีเจ้าของ/Live | แผนที่สั่ง implement; testing standards§7 |
| RQ-15 | Header icons24pxไม่มีกรอบและtargets>=44px; trade inset4/panel gap4/inner padding8; chartเต็มพื้นที่โดยคงorder form/orders/axes/error controlsและdraft/renderer state; toolbarอยู่ต่อจากpair dropdownและdesktop chart/orders64:36ตามcorrection plan | Dense workspace amendment Approved |

## กฎความปลอดภัยและข้อมูล

- โหมดPaper/Liveแยกชัดผ่านactive desktop menu/compact triggerตลอดเวลาบนหน้าเทรด และปุ่มหยุดเข้าถึงได้ทุกหน้าจอตาม
  `specs/standards/frontend.md` §1/5 และ `trading-safety.md` §8
- ไม่เปลี่ยน known/unknown receipt, retry key, completion หรือ resume semantics
  การตรวจด้านนี้ต้องผ่านก่อน merge ไม่เลื่อนไป Batch/Release
- Session/ข้อมูลธุรกิจยังใช้แหล่งข้อมูลร่วมเดิม UI stateเก็บเฉพาะเมนูเปิด/ปิด
  ไม่มีcache/session/role sourceใหม่หรือinfrastructureเพิ่ม
- ไม่ขยายงานไปเปลี่ยนเนื้อหาหน้าเทรด/คำนวณเงิน/การส่งออเดอร์ การตรวจUIใช้
  controlled fixtures; หลักฐานการเงิน/workloadเดิมใช้ต่อเมื่อสิ่งที่พิสูจน์ไม่ถูกกระทบ

## ยังไม่ชัด

ไม่มี Needs Clarification ด้านผลิตภัณฑ์ค้างในขอบเขตที่เจ้าของเลือก
การอนุมัติเอกสารเป็นด่าน workflow: requirements → เจ้าของอนุมัติ → plan/validation
→ เจ้าของอนุมัติ → implementation/tests → Ready for Code Review แล้วรอคำสั่งreview
Commit/push/mergeยังต้องคำสั่งเจ้าของแยกตามAGENTS.md

## ขอบเขตรอบจัดทำเอกสาร (ประวัติ)

รอบแรกจัดทำrequirementsและทะเบียนroadmapเท่านั้น หลังเจ้าของอนุมัติจึงจัดทำ
plan/validationเป็นProposedเพื่ออนุมัติด่านถัดไป ยังไม่แก้source/รันtests/deploy
หรือGit publication งานในworktreeเดิมไม่ถูกเปลี่ยนและระบบlocalเดิมไม่ถูกretarget
มายังbranchนี้ การอนุมัติrequirementsไม่ใช่ผลตรวจimplementation

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


## Chart toolbar and height correction

เจ้าของอนุมัติ [แผนแก้ toolbar และความสูง](chart-toolbar-height-correction.md) แล้ว
Timeframe และปุ่มรีเซ็ตอยู่ต่อจาก dropdown BTC/USDT ในแถวเดียวกัน ส่วน desktop chart/orders ใช้สัดส่วน 64:36 ตามภาพอ้างอิง
Open Orders และ Order History ใช้ panel และความสูงเดียวกัน


## เมนู Paper / Live

เจ้าของอนุมัติ [market menu amendment](paper-live-market-menu-amendment.md) วันที่2026-11-13
ชื่อเมนูระดับบนเป็นPaper/Live เมื่อเปิดแล้วมีSpotและFutures โดยFuturesแสดงสถานะยังไม่เปิดใช้งาน
SpotในPaperไป /paper/trade ส่วนSpotในLiveไป /live/trade


## Right panel alignment และขนาดไอคอน

เจ้าของอนุมัติ [แผนจัดแนวฟอร์มและขนาดไอคอน](right-panel-top-alignment-amendment.md) วันที่2026-11-13
เมื่อมีสองคอลัมน์ แถบคู่เทรดกว้างเฉพาะฝั่งกราฟ ฟอร์มด้านขวาเริ่มที่แนวเดียวกันและสูงถึงขอบworkspace
Header glyph ใช้24pxและtargetsอย่างน้อย44pxตามtemplate


เจ้าของปรับระยะไอคอนdesktopเพิ่มเติมตามภาพBinance ให้กลุ่มธีม/บัญชี/Settingsกระชับและเท่ากันตาม [spacing correction](right-panel-top-alignment-amendment.md)
