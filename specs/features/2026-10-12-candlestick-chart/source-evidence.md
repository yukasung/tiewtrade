# F-12 — แหล่งข้อมูลและหลักฐานก่อนวางแผน

วันที่: 2026-10-12
สถานะ: **Research** — ไม่ใช่ผลผ่าน validation ของ implementation

## เอกสารทางการ

- [Binance TH kline streams](https://www.binance.th/api-docs/en/#klinecandlestick-streams)
  ระบุ stream `<symbol>@kline_<interval>` พร้อม OHLCV, เวลาแท่ง และสถานะ `x`.
  ข้อความอธิบาย cadence กับตัวเลข update speed ในหน้าเดียวกันไม่ตรงกัน
  จึงไม่ใช้เป็น SLA หรือหลักฐาน monotonic ordering.
- [Binance TH WSS](https://www.binance.th/api-docs/en/#general-wss-information)
  ใช้ host เดิมที่ F-10 ตรวจไว้; explicit SUBSCRIBE แทนการเดารูปแบบ URL.
- [Lightweight Charts 5.0](https://tradingview.github.io/lightweight-charts/docs/5.0)
  และ [panes](https://tradingview.github.io/lightweight-charts/docs/5.0/panes)
  ใช้เป็นฐานตรวจการติดตั้ง panes และ attribution.
- [series API](https://tradingview.github.io/lightweight-charts/docs/5.0/series-types)
  รองรับ Candlestick/Histogram/Line และ whitespace; ตรวจ API รุ่นที่ pin อีกครั้ง
  ก่อนนำมาใช้ ไม่ใช้ default indicator หรือคำนวณสูตรจาก library.

ตรวจ npm registry ด้วย `npm view lightweight-charts@5.0 version --json`
เมื่อ 2026-10-12 พบ patch 5.0.0..5.0.9; แผนเลือก pin 5.0.9.
นี่เป็นการตรวจ metadata ไม่ได้ติดตั้ง dependency ของแอป.

## Public observation

เปิด WSS สาธารณะหนึ่ง connection ส่ง SUBSCRIBE หนึ่งครั้งสำหรับ 5 คู่ × 6 intervals
ด้วย timeout รวม 20 วินาที ช่วงรับตัวอย่างสูงสุด 10 วินาที, frame ≤64 KiB,
queue ≤16; ไม่มี API key/บัญชี/ออเดอร์. เก็บเฉพาะสรุปและตัวอย่างสาธารณะด้านล่าง
จากผลเครื่องมือ ไม่เก็บ credentials หรือรันเป็นเทสต์ปกติ.

เวลา UTC: `2026-10-12T07:01:50.629274+00:00` (14:01:50 เวลาไทย)

| สิ่งที่สังเกต | ผล |
|---|---|
| Subscription ack | id=12, result=null |
| Series ที่มี event | 30/30 ตามรายการ F-12 |
| Envelope | stream + data; data.e=kline |
| ตัวอย่าง | btcusdt@kline_5m, open time=1791788400000, inclusive end=1791788699999 |
| OHLC ตัวอย่าง | o=84224.02000000, h=84235.00000000, l=84146.00000000, c=84173.75000000 |
| Volume ตัวอย่าง | v=17.38844000 เป็นข้อความ |
| Finality flag | x=false ทุกตัวอย่างแรกที่เก็บ; ไม่พบ x=true ในรอบนี้ |

ตัวอย่างนี้พิสูจน์การเข้าถึง stream/รูปร่างบางส่วน ไม่พิสูจน์ทุก failure,
ordering, boundary, closure, 24h rotation หรือความเสถียร. ต้องเก็บ raw fixtures
แบบ bounded อีกครั้งในด่าน V-01 ก่อนเขียน adapter และใช้ synthetic fixtures
เพื่อทดสอบ conflict/reconnect ไม่อ้างว่าเห็นเหตุการณ์จริงที่ไม่ได้สังเกต.

## ผลต่อแผน

เสนอ WSS kline สำหรับ preview แยกจากแหล่ง REST history เดิม.
ไม่ใช้ `x=true` เปลี่ยน history เป็น CLOSED ในรอบนี้; indicator ยังใช้ F-11 เดิม.
การยืนยันความสอดคล้องต้องอ่าน OHLC กับผลใน DB snapshot เดียวกัน
ไม่เอา CandleHistoryView กับ IndicatorHistoryView สอง HTTP requests มา join เอง.
