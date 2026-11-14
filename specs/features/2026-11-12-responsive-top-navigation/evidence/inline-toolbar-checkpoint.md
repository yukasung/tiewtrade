# Inline chart controls checkpoint

วันที่ 2026-11-12 Asia/Bangkok
สถานะ Ready for Code Review รอ review code, owner recheck และ required CI
Branch feature/responsive-top-navigation จาก main afb2adb
Frontend fingerprint f564fa7f8df7 ตาม private manifest ใน frontend/test-results/navigation-runtime
อ้างอิง [คำสั่งแก้ตำแหน่งล่าสุด](../chart-toolbar-height-correction.md) และ [validation](../validation.md)

Timeframe และปุ่มรีเซ็ตอยู่ต่อจาก dropdown BTC/USDT ในแถวเดียวกันบน Paper/Spot
TradingWorkspace ส่ง target ผ่าน callback ref และ React context ให้ CandlestickChartPanel ใช้ portal
เมื่อตัว toolbar เปลี่ยน node callback ref อัปเดต context ตาม lifecycle การ render
Controls จึงย้ายไป node ปัจจุบันพร้อม state ของ timeframe ที่ยังอยู่
Standalone/fallback chart ใช้ toolbar ภายในกราฟ
Mobile ใช้ shared Select/Button เดิมและจัดความกว้างให้ทั้งสาม controls อยู่แถวเดียวกันที่375px
Desktop chart/orders ใช้64:36ตามแผนล่าสุด

Vitest4ไฟล์78tests Passed 3.18s ครอบ chart, PaperTradePage, CompactMarketNavigation และ renderer
เพิ่ม proof ใช้ TradingWorkspace จริงยืนยัน controls อยู่ใน pair bar และจำลอง target node ถูกแทนที่
ยืนยัน3m/resetและcanvasnodeยังอยู่หลัง target replacement พร้อม tests parent rerender เดิม
Lint/typecheck/build Passed Build1.32s มีbundlewarning>500kBเดิม

Browser5cases Passed19.8s ตาม inline-toolbar-browser.log
ครอบ header mode cue/scroll4ขนาด และ realchart7width375/768/1024/1279/1280/1440/2553
วัดตำแหน่ง pair/timeframe/reset อยู่แนวนอนเดียวกันต่างกันไม่เกิน1px และเรียงต่อกันโดยไม่ทับ
รวม3m/data/draft123.45/canvas identity หลังresize,desktop ratio64:36,tabheightเท่ากัน,
standalonechart,typederror/retry และLive disabledsubmitตามเดิม
Navigation/resize financialPOST0 ใช้ฐานfixtureแยกและwalletreadfixtureเดิม
ตรวจภาพ375pxล่าสุดแล้ว ทั้งสามcontrolsอยู่แถวเดียวกันและเห็นกราฟ/legend/axesครบ

TestDB tiewtrade_e2e_navigation_inline_20261112 ถูกdropหลังtestservers8018/5188ปิดแล้ว
เก็บผลรอบก่อนใน chart-layout-final-results และ manifest-before-inline-toolbar ส่วนรอบล่าสุดใน results
Owner frontend5173ยังตอบ200 URL http://127.0.0.1:5173/paper/trade

NAV-V35/V36 Passed(local) และ V37 PartialรอrequiredCI Owner recheckยังNot Run
หลักฐานheader/STOP/sessionและchartที่ไม่กระทบใช้ต่อจาก [checkpointก่อนหน้า](chart-layout-checkpoint.md)
ขั้นถัดไป Ready for Code Review แล้วรอ review code
Reviewerควรเน้นportal target lifecycle,focus/tab orderและinline responsive geometry
