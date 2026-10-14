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

## Follow-up — calendar history without endTime (2026-10-14)

Public probes using `startTime=1501545600000&limit=1000` without `endTime`
returned BTC 479 weekly rows and 111 monthly rows, starting in August 2017.
See [approved batch amendment](calendar-history-batch-amendment.md).
The evidence below still applies to requests supplying both bounds, but its
single-slot implementation conclusion is superseded for calendar history.

## Amendment — native `1w`/`1M` และ REST 7-day limit (2026-10-14)

เอกสารทางการ Binance TH ระบุทั้ง REST Kline และ WebSocket Kline รองรับ `1w` กับ `1M`
โดยตัวพิมพ์ใหญ่ `M` หมายถึงเดือน. REST `/api/v1/klines` จำกัด `limit` สูงสุด 1,000 แถว,
เรียงเก่าไปใหม่ และระบุว่าแท่งมี identity จาก open time. WebSocket ใช้ชื่อ
`<symbol>@kline_<interval>`, payload มี `t`/`T`/`i`/OHLCV/`x`; connection เดียวรับได้สูงสุด
1,024 streams. หน้าเอกสารระบุทั้งข้อความว่า update ทุกวินาทีและค่า `2000ms` จึงไม่ใช้ตัวเลขนี้
เป็น SLA เช่นเดียวกับหลักฐานเดิม.

Public REST observation แบบไม่ใช้ credential เมื่อ 2026-10-14 พบว่า request ของ `1w`
ที่ครอบ 14 วันและ `1M` ที่ครอบสองเดือนถูกปฏิเสธเหมือนกันด้วย HTTP 400,
code `-4088`, message `Maximum time interval is 7 days.` ขณะที่ request ช่วง 7 วัน
ตอบ native weekly/monthly row ได้. ดังนั้น adapter ต้องรักษา upstream range ≤7 วัน:
weekly และ monthly ดึงครั้งละหนึ่งแท่ง; monthly query ใช้เจ็ดวันแรกจาก monthly open
แต่ตรวจ `T+1` กับวันเปิดเดือนถัดไปตาม calendar จริง. ข้อจำกัดนี้เปลี่ยนวิธีแบ่ง backfill
โดยไม่เปลี่ยน retention 5 ปี, native candle identity หรือ logical monthly window.

Fixtures สาธารณะที่เก็บหลังยืนยันข้อจำกัด:

| Fixture | ช่วง request | SHA-256 |
|---|---|---|
| `backend/tests/venues/binance_th/fixtures/16-btc-usdt-1w.json` | weekly open 2026-08-03, 7 วัน, limit 1 | `d578c01e193d89165474fd24d02044a5b5413d4962e7f40be84ad1121caafd56` |
| `backend/tests/venues/binance_th/fixtures/17-btc-usdt-1M.json` | monthly open 2026-09-01, 7 วัน, limit 1 | `8eb9633649c5d89134fda4786171768a23762e2f1ebb4cd1b8a0edfffbc68772` |

ทั้งสองไฟล์เก็บเฉพาะ public response และ rate-limit/date headers ที่ไม่เป็นความลับ;
ไม่มี API key, signature, account หรือ order request.


## 2026-10-14 ? oldest native history discovery

Public read-only probes to `https://api.binance.th/api/v1/klines` with
`symbol=BTCUSDT&startTime=0&limit=1` returned:

- `interval=1M`: open `1501545600000` (2017-08-01 UTC).
- `interval=1w`: open `1502668800000` (2017-08-14 UTC).

The [Binance TH API documentation](https://www.binance.th/api-docs/en/)
describes chronological responses. Discovery omits endTime; ordinary fetches
retain the observed seven-day upstream bound. Empty/malformed discovery is a
source failure, never proof of the beginning of history. Bounds are stored per
pair/timeframe; BTC evidence is not reused as another pair inception.
