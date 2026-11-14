# Chart toolbar and height correction checkpoint

วันที่ 2026-11-12 Asia/Bangkok
สถานะ Ready for Code Review รอ review code, owner recheck และ required CI
อ้างอิง [approved plan](../chart-toolbar-height-correction.md) และ [validation](../validation.md)
Branch feature/responsive-top-navigation จาก main afb2adb
Frontend fingerprint d3ed36707577 ตาม private manifest ใน frontend/test-results/navigation-runtime

## การแก้ไข

CandlestickChartPanel แสดง timeframe/reset ใน trading-market-bar ของตัวเอง
เอา toolbarTargetId, one-time DOM lookup, portal และ target state ออก
PaperTradePage, LiveTradePage และ TradingWorkspace ใช้ chart panel ตาม lifecycle เดียวกัน
ใช้ shared Select/Button และ chart-controls เดิม

CSS ใช้ desktop grid16fr:9fr แทน4:1 ทำให้ chart panelประมาณ64% และ orders36%
Heightอิงviewportและheaderที่วัดไว้ มีminimum22remสำหรับchartและ10remสำหรับorders
Embedded chartเป็นflex column โดย toolbarอยู่ก่อนcanvas ส่วน mobile/tabletแยกtoolbarออกจากchart areaขั้นต่ำ420px
Open Orders และ Order History ใช้ orders containerเดียวกันและscrollภายในบนdesktop

ไฟล์หลักคือ CandlestickChartPanel.tsx/.css, TradingWorkspace.tsx, PaperTradePage.tsx,
LiveTradePage.tsx และ testsของchart/navigation รวม approved specและหลักฐาน

## Tests และหลักฐาน

- Vitest4ไฟล์ 76tests Passed 3.43s ครอบ CandlestickChartPanel, PaperTradePage,
  CompactMarketNavigation และ chart-renderer
  กรณี toolbarทดแทนตรวจ3m/resetอยู่ภายในchartหลังparent rerender พร้อมstateเดิม
  คงtestsเงิน,receipt,precision,viewport,keyboardselectionและการrecoveryที่เกี่ยวข้อง
- Frontend typecheck, lint, build Passed Build1.18s มีbundlewarning>500kB
  หลังปรับเฉพาะbrowserproofตรวจlint/typecheckทดแทนผ่าน
- Browserรอบแรก6cases Passed 22.6s บนฐานแยก workers1/retries0
  actual chart panes/exact values/keyboardselection และmodecue/scroll4viewports
  รวมcase realchart resize7width 375/768/1024/1279/1280/1440/2553
  จอ2553×1240ใช้ขนาดตามภาพเจ้าของ
- ปรับproofให้รอexact3m candle200.000000000000000001ก่อนเก็บภาพ เพื่อให้ภาพแสดงข้อมูลครบ
  และเพิ่มdarkthemeในcaseนี้ ตรวจเฉพาะcaseที่เปลี่ยน Passed13.2s
  ชุด6casesแรกยังvalidสำหรับสิ่งที่ไม่ได้เปลี่ยน รวม6distinct browsercases
  เก็บรอบแรกใน chart-layout-round1-results และผลล่าสุดใน results ไม่ลบประวัติ
- ตรวจframe/canvas/rendererภายในchart areaต่างกันไม่เกิน2px
  Desktop chartheight/(chartheight+ordersheight) ต่างจาก0.64ไม่ถึง0.01
  Open OrdersและOrder Historyสูงต่างกันไม่เกิน1px ทุกdesktopwidthในcase
  คงdraft123.45/pair/timeframe3mและcanvasnodeหลังresize
  ControlsและTradingView attributionเห็นได้ พร้อมtyped504/error/retryทั้งstandaloneและembedded
- ตรวจmobile375/desktop/shorttablet1024×480 ไม่มีpage horizontal overflowจากnavigation
  Modecueยังเห็นขณะscroll และSpotsubmitยังdisabled
  FinancialPOST0ในcaseการตรวจlayout ใช้walletreadsnapshotfixtureตามPaperTradePage tests
  ส่วนcandles/API/rendererใช้existing isolated realDBfixture ไม่ส่งowner/Liveorders
- รูปdesktop2553ยืนยันจุดแบ่งchart/ordersใกล้ระดับภาพอ้างอิง
  ภาพmobileล่าสุดตรวจด้วยตาแล้วเห็นtimeframe3m/reset/OHLC/canvas/axes/attributionครบ
  Screenshot/trace/config/runnerและhashทั้งหมดเก็บprivateในtest-results

## Cleanup และสถานะ

Fixture DB tiewtrade_e2e_navigation_chartlayout_20261112 ใช้bootstrap/migrationเดิม
หลังbrowserจบตรวจAPI8018/Vite5188ปิดและdropเฉพาะfixtureDBแล้ว
Local5173ยังตอบ200และรับHMRจากworktreeนี้
URL http://127.0.0.1:5173/paper/trade

ผลpreviewเดิมที่เจ้าของรายงานcontrolsหายยังเก็บเป็นFailedของcandidateก่อนหน้า
NAV-V33/V35/V36 Passed(local)ของcandidateแก้ไข ส่วนNAV-V37 PartialรอrequiredCI
Owner recheckล่าสุดยังNot Run Review/refactor/publicationและrequiredCIยังค้าง
หลักฐานnavigation/STOP/sessionที่ไม่ถูกกระทบใช้ต่อจากcheckpointก่อนหน้า

ขั้นถัดไปแจ้ง Ready for Code Review แล้วรอ review code
Reviewerควรเน้นchart flex sizing,toolbar lifecycle,desktop ratioและscrollของorders
