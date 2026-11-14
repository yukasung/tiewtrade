# Right panel alignment and 24px icons checkpoint

วันที่ 2026-11-13 Asia/Bangkok
สถานะ Ready for Code Review รอ review code, owner acceptance และ required CI
อ้างอิง [approved plan](../right-panel-top-alignment-amendment.md) และ [validation](../validation.md)
Branch feature/responsive-top-navigation จาก main afb2adb
Candidateก่อนspacing correction fingerprint6fe05f66bc7f ตาม private manifest ใน frontend/test-results/navigation-runtime

## การปรับ

Trading workspace สองคอลัมน์ใช้ grid areas bar/form, chart/form, orders/form
แถบ BTC/USDT–Timeframe–รีเซ็ตกว้างเฉพาะฝั่งกราฟ Formด้านขวาเริ่มระดับเดียวกันและสูงถึงขอบล่างworkspace
กรณีไม่มีordersใช้bar/form,chart/form คงform22.5remและgap4pxตามแผน
Header glyphธีม/บัญชี/Settings/hamburgerเป็น24pxพร้อมclick targetsอย่างน้อย44px
Source runtimeที่เปลี่ยนคือ CandlestickChartPanel.css และ styles/admin-theme.css
เพิ่มgeometry assertionsในtop-navigation.spec.tsและเอกสารที่เกี่ยวข้อง

## หลักฐาน

- Vitest3ไฟล์46tests Passed2.90s ได้แก่ AccountLayout, CompactMarketNavigation และ PaperTradePage
  Session/STOP/renderer logicใช้หลักฐานก่อนหน้าที่ไม่ถูกกระทบต่อ พร้อมbrowserproofรอบนี้
- Typecheck, lint, build Passed Build1.09s มีbundlewarning>500kBเดิม
  หลังเพิ่มเฉพาะwide browser caseตรวจtypecheckและscopedESLintผ่าน
- Browserรอบแรก14cases Passed51.8s ตามpanel-top-browser.log
  Geometry6width375/768/1024/1279/1280/1440 ×th/en×light/dark
  และSTOPpending/unknown/key,detailsdialog/focus,storagewarnings,modecue/scroll4sizes,realchartlayout
- เพิ่มgeometry2553pxเพื่อให้matrixครบ7widthทั้งสองภาษา/ธีม
  เฉพาะcaseใหม่Passed10.8sตามpanel-top-wide-browser.log รวม15distinct browsercases
  ทั้งสองรอบผ่านครั้งแรก มี112ภาพเมนู/navigation/Settingsในmatrix7width
- Realchartcaseตรวจ7widthและภาพ2553×1240 ทั้งPaperและLive no-orders
  BarกับFormมีtopต่างกันไม่เกิน1px Bar/chart/ordersกว้างเท่ากัน
  Formเริ่มหลังขอบbarด้วยgap4px และbottomตรงขอบworkspaceภายใน1px
  ตรวจdesktop chart/orders64:36และOpen Orders/Historyสูงเท่ากันตามเกณฑ์เดิม
- Paper1024×480เลื่อนถึงsubmitในformได้ โดยscrollTop>0และdraft123.45ยังอยู่
  Live no-ordersตรวจbar/form alignmentและfull-heightที่1024/1440/2553 พร้อมsubmitdisabled
- ตรวจinline3m/reset,chartfill/axes/legend/attribution,error/retryและcanvasnodeผ่านresize
  Header glyph24×24px/targets44px,borderless/focusและSettingsขวาสุดผ่านทุกwidthในmatrix
  Browser lifecycle/navigationไม่มีfinancialPOST STOPfixture explicitretryใช้keyเดิม
- ตรวจภาพ2553×1240แล้วเห็นฟอร์มเริ่มตรงระดับpair barใต้เมนูหลักและiconsใหญ่ขึ้นตามแผน
  Screenshot/trace/config/runnerและmanifestเก็บprivateในtest-results

## Cleanup และขั้นถัดไป

FixtureDB tiewtrade_e2e_navigation_paneltop_20261113 และ tiewtrade_e2e_navigation_paneltop_wide_20261113
ถูกdropหลังtestservers8018/5188ปิดแล้ว ใช้bootstrap/migrationเดิม
ผล14casesอยู่panel-top-round1-results ส่วนwidecaseอยู่results พร้อมlogและmanifestcandidateก่อนหน้า
Localfrontend5173ยังตอบ200 URL http://127.0.0.1:5173/paper/trade

NAV-V42/V43 Passed(local),V44 PartialรอrequiredCI ส่วนV30เป็นประวัติglyph20pxที่ถูกแทนแล้ว
Owner recheckล่าสุดยังNot Run Review/refactorและrequiredCIรอworkflowถัดไป
ขั้นถัดไป Ready for Code Review แล้วรอ review code
Reviewerควรเน้นgridทั้งwith/without orders,sidebar scrollและresponsiveของheader icons


## Desktop icon spacing correction

เจ้าของให้ลดระยะตามภาพBinance จึงเอาgap8pxในdesktop actionsและgap16pxก่อนSettingsออก
Targets44pxเรียงติดกันโดยไม่ทับกัน Glyph24pxมีระยะกึ่งกลาง44pxเท่ากัน
Brandยังมีระยะ16pxก่อนprimary navigation

Frontend fingerprintล่าสุด091e9050ebbfตามcandidate-manifest.json
Lint/typecheck/build Passed Build1.13s และbrowser4cases Passed23.8sตามicon-spacing-browser.log
ตรวจ375/1280/1440/2553px ทั้งไทย/อังกฤษ/light/dark พร้อมTab/Escape/Settings/menu
Computed boundsยืนยันgapระหว่างtargetsเป็น0ภายใน1px และระยะกึ่งกลาง44pxภายใน1pxทั้ง3ปุ่ม
Settingsอยู่ขวาสุด ไม่มีnavigation overflow ใช้unitและหลักฐานส่วนอื่นก่อนหน้าที่ไม่กระทบต่อ

FixtureDB tiewtrade_e2e_navigation_iconspacing_20261113 ถูกdropหลังports8018/5188ปิด
หลักฐานwideก่อนหน้าอยู่panel-top-wide-results ส่วนspacingปัจจุบันอยู่results
Local5173ยังพร้อมให้ตรวจ Owner acceptance/review/requiredCIยังรอตามworkflowเดิม
