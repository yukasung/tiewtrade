# Chart toolbar and order panel correction

สถานะ: **Approved — เจ้าของตอบ approve สำหรับ requirements, plan และ validation วันที่ 2026-11-12**

เจ้าของแจ้งว่า timeframe dropdown และปุ่มหาย และสั่งให้ความสูงส่วนกราฟกับออเดอร์ที่เปิดอยู่/ประวัติออเดอร์เท่ากับภาพ Binance ที่แนบมา

## Requirements

- Timeframe รวม 3m และปุ่มรีเซ็ตต้องเข้าถึงได้บนหน้า Paper, Spot และกราฟเดี่ยว หลังเปิดหน้า เปลี่ยนหน้า และปรับหน้าต่าง
- ปรับความสูง desktop ของส่วนกราฟและพื้นที่ตารางออเดอร์ร่วมกันตามภาพอ้างอิง
- Open Orders และ Order History ใช้พื้นที่ตารางเดียวกัน เมื่อสลับแท็บความสูงเท่ากัน

## Plan ที่อนุมัติ

- ใช้ trading-market-bar และ chart-controls เดิมภายใน CandlestickChartPanel ทั้ง embedded และ standalone เพื่อให้ controls อยู่กับวงจรชีวิตกราฟ
- เอา toolbarTargetId, DOM lookup, portal state และ div เป้าหมายที่เลิกใช้ออกจาก callers
- Desktop แบ่งพื้นที่ใต้ pair bar ให้ chart panel ประมาณ 64% และ orders panel 36% จากภาพ chart 669px และ orders 377px ใช้สัดส่วน 16fr:9fr พร้อม minimum ของกราฟและตาราง
- Chart panel รวม toolbar และ canvas ใช้ flex column และ canvas เติมพื้นที่หลัง toolbar ส่วน stacked layout ให้ toolbar อยู่นอกความสูง canvas ขั้นต่ำ 420px
- ใช้ตารางเดิมสำหรับ Open Orders และ Order History พร้อม scroll ภายใน

## Validation ที่อนุมัติ

- Targeted tests ของ chart controls, TradingWorkspace, PaperTradePage และ renderer
- เพิ่มกรณี controls อยู่ใน chart panel หลัง parent rerender และเปลี่ยน timeframe ได้
- Browser บน fixture DB ตรวจ 375/768/1024/1279/1280/1440px และภาพอ้างอิง 2553×1240
- ตรวจ timeframe/reset, draft และ renderer identity หลัง resize ตรวจอัตราส่วน chart/orders และความสูงทั้งสองแท็บ
- ตรวจ error/retry, focus, header mode cue และ Live disabled submission ตามหลักฐานที่กระทบ
- Frontend lint/typecheck/build จากนั้น Ready for Code Review ตาม AGENTS.md


## ขอบเขตและการติดตาม

แผนนี้แทนที่สัดส่วน 4:1 และตำแหน่ง controls แบบ portal จาก dense amendment เฉพาะส่วนที่ระบุ
ใช้หลักฐาน navigation/STOP/session ที่ยัง valid ต่อ ผลตรวจรอบนี้อยู่ใน [checkpoint](evidence/chart-layout-checkpoint.md)
NAV-V35 ตรวจ toolbar lifecycle, NAV-V36 ตรวจสัดส่วนและแท็บ, NAV-V37 ตรวจ targeted/static/browser และ required CI
ทุกข้อเป็น Feature ส่วน required CI ยังต้องผ่านบน final published candidate ตาม workflow


## ผลล่าสุด

Implementation และlocal validationผ่านตาม [checkpoint](evidence/chart-layout-checkpoint.md)
NAV-V35/V36 Passed(local), NAV-V37 Partial เพราะrequiredCIยังNot Run
ขั้นถัดไป Ready for Code Review แล้วรอเจ้าของสั่ง review code


## ตำแหน่ง controls ตามคำสั่งเจ้าของล่าสุด

เจ้าของสั่งให้ timeframe และปุ่มอยู่ต่อจาก dropdown BTC/USDT ในแถวเดียวกัน
ใช้ chart-controls และ Select/Button เดิม วางช่องรับ controls ใน trade-pair-controls
TradingWorkspace ส่ง DOM node ที่ได้จาก callback ref ผ่าน React context ให้ chart ใช้ createPortal
การเปลี่ยน node จะอัปเดต context ตาม lifecycle จึงเอา one-time document lookup ออกต่อไป
Standalone chart ใช้ toolbar ภายใน panel ตามเดิม
ตรวจ controls ติดกับ pair selector และยังอยู่หลังเปลี่ยน target node, rerender, resize และเปลี่ยนหน้า
Desktop 64:36 ใช้ต่อ และหน้าจอแคบจัด controls ให้กดถึงได้โดยไม่ล้นหน้า


ผลตำแหน่ง inline ล่าสุดผ่านตาม [inline toolbar checkpoint](evidence/inline-toolbar-checkpoint.md)
ข้อมูลในส่วนแผน toolbar ภายใน panel ข้างต้นเป็นประวัติก่อนคำสั่ง inline ของเจ้าของ
