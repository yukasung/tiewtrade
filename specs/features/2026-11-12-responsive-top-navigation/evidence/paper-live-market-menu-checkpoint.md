# Paper / Live market menu checkpoint

วันที่ 2026-11-13 Asia/Bangkok
สถานะ Ready for Code Review รอ review code, owner acceptance และ required CI
อ้างอิง [approved amendment](../paper-live-market-menu-amendment.md) และ [validation](../validation.md)
Branch feature/responsive-top-navigation จาก main afb2adb
Frontend fingerprint 22965d3714f8 ตาม private manifest ใน frontend/test-results/navigation-runtime

## พฤติกรรมและ implementation

เมนูหลักเป็นกราฟ, Paper และ Live เมื่อคลิก Paper/Live เปิดรายการ Spot และ Futures
Spot ใช้ลิงก์ /paper/trade หรือ /live/trade ตามกลุ่ม Futures disabled พร้อมข้อความแปลสถานะ
Active mode อยู่บนtrigger และ active Spot อยู่บนลิงก์ในรายการ
Compactใช้รายการย่อยภายในpanel ส่วนdesktopใช้dropdownใต้trigger
Template source คือ ChatBoxHeader, UserDropdown และ ui/dropdown ของ TailAdmin
ใช้shared Dropdown/Button และ registry/navigation handlerเดิม

AccountNavigation เปิดทีละกลุ่ม ปิดเฉพาะกลุ่มที่เป็นเจ้าของcallback
Escapeในรายการย่อยคืนfocusและปิดชั้นนั้นก่อนcompact menu
Shared Dropdown เพิ่ม outsideEvent="click" ให้กลุ่มmarket เพื่อให้เป้าหมายในflowไม่เลื่อนก่อนclickจบ
ระหว่างpointer gestureให้รอclickก่อนdismiss ส่วนkeyboard focusออกยังปิดตามปกติ
ค่าเริ่มต้นpointerdownของDropdownใช้ต่อกับSettings/account consumers

ไฟล์หลักคือ layout/AccountNavigation.tsx, components/ui/Dropdown.tsx, accountMessages.ts,
styles/admin-theme.css รวม tests, browser helper และ caller risk-limits ที่เลือกSpotผ่านเมนูใหม่
มีการถอดCSSของLive suffixที่เลิกใช้

## หลักฐาน

- Vitest6ไฟล์73tests Passed รอบสุดท้าย5.87s
  AccountLayout, AccountNavigation, AccountSession, CompactMarketNavigation,
  TopNavigation และ KillSwitchControls ครอบgroup/route/nativeclick/current/disabled,
  admin/chart flag,focus/resize/session/storagefailureและSTOPkey
- Typecheck, lint, build Passed Build1.21s มีbundlewarning>500kB
  หลังแก้เฉพาะrisk browser callerตรวจtypecheckและscopedlintทดแทน
- Browser15distinct cases Passed เมื่อรวมผลตามส่วนที่ยังvalid
  6width375/768/1024/1279/1280/1440 ×ไทย/อังกฤษ ×light/dark
  96ภาพnavigation/Settings/Paper/Live menusอยู่ในหลักฐานล่าสุดของแต่ละwidth
  ตรวจSpotroute/disabledFutures,keyboardTab/Escape,outside,focus,inert/scrolllock,
  account/Settings/dialog,active mode,session และไม่มีnavigation overflow
- STOPfixture pending/unknownผ่านการสลับPaper→Liveและresize คงrequestkeyเดิม
  Explicitretryครั้งเดียวใช้keyเดิมตามassertionsเดิม
  Lifecycle/navigationไม่มีfinancialPOST ใช้fixtureDBและsynthetic market data
- Realchart exact data/keyboardselectionผ่าน พร้อม inline timeframe3m/reset,
  draft123.45/canvasnodeผ่าน7widthรวม2553×1240,chart/orders64:36,
  Open Orders/Historyสูงเท่ากัน และtypederror/retry/Live disabledsubmit
- Helper navigationLink เปิดmain menuและmarket submenuตามroute
  risk-limits callerที่ยังเลือกSpotตรงเปลี่ยนเป็นhelperเดียวกัน
  Dedicated risk financial E2Eยังใช้requiredCIและผลเดิมที่ไม่ถูกกระทบ

## ประวัติผล

รอบแรก market-menu-browser.log ได้14Passed/1Failed ภายใน1.2m
พบLiveเมนูปิดก่อนfocusSpotระหว่างSTOPpending เก็บtrace/contextในmarket-menu-round1-results
แก้callbackให้ปิดเฉพาะกลุ่มและเพิ่มproofสลับสองกลุ่ม
รอบสอง7casesได้2Passed/5Failed ภายใน1.2m พบcompact layoutขยับจากdismissตอนpointerdown/focus
เก็บผลในmarket-menu-round2-results

แก้opt-in click dismissal และgesture trackingในDropdown พร้อมunit/static checksผ่าน
รอบสาม targeted375px/STOPpending 2Passed8.8s อยู่ในmarket-menu-round3-targeted-results
ตรวจgeometryอีก5widthบนcandidateเดียวกัน 5Passed28.1s อยู่ในresults
ใช้8casesที่ไม่ถูกกระทบจากรอบแรกต่อ รวม15distinct cases
รักษาtimeout/assertionsเดิมและเก็บผลFailedก่อนหน้า

Typecheckระหว่างพัฒนาพบtuple testยังไม่เป็นreadonlyและRTLoptionsมีexact แก้จนผ่าน
คำสั่งtestครั้งแรกเรียกจากrootและถูกยกเลิกก่อนใช้ผล จากนั้นใช้Vitest4.1.11ในfrontend
Native modifiedclick testกันnavigationของjsdomหลังตรวจReacthandlerเพื่อเก็บdefault/native semantics

## Cleanup และขั้นถัดไป

TestDB tiewtrade_e2e_navigation_marketmenu_20261113 ใช้bootstrap/migrationเดิม
เมื่อbrowserจบตรวจports8018/5188ปิดแล้วและdropเฉพาะfixtureDB
เก็บrunner/config/manifest/screenshots/traceส่วนตัวในtest-results และสำรองcandidateก่อนหน้าไว้
Localfrontend5173ยังตอบ200 URL http://127.0.0.1:5173/paper/trade

NAV-V38–40 Passed(local),V41 PartialรอrequiredCI ส่วนV26ถูกแทนด้วยV38
Owneracceptanceล่าสุดยังNot Run Review/refactorและrequiredCIรอworkflowถัดไป
ขั้นถัดไปแจ้ง Ready for Code Review แล้วรอ review code
Reviewerควรเน้นpointer/keyboard dismiss timingในcompact submenuและSTOPrequestidentity
