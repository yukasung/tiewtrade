# F-09 — ดึงและเก็บแท่งเทียนผ่านชั้น venue

สถานะ: **Approved** — เจ้าของตอบ approve วันที่2026-10-07 หลังอ่านข้อกำหนดฉบับนี้; รวมNC-35 amendmentsที่เจ้าของอนุมัติเมื่อ2026-10-10
วันที่: 2026-10-07
Branch: feature/f-09-market-data

Amendmentที่เสนอโดยF-11 NC-35: [prepared indicators รอบ2](../2026-10-10-backend-indicators/performance-plan-v2.md)
เป็น **Approved** เจ้าของอนุมัติamendmentเมื่อ2026-10-10 ตามคำสั่ง “approve”; แยกlogical365วัน/physicalgraceและsourcejournal proof
รวมsourcewrite scopeก่อนpre-locks/DMLและmaintenance relation-firstตามADR-002
amendmentNC-35ที่อนุมัติใช้แทนbaselineเฉพาะส่วนที่ระบุเปลี่ยน ข้อกำหนดส่วนอื่นคงเดิม
แก้reviewรอบ2ข้อ5: ข้อเสนอรวมmixed-versionrollout/rollback retentionในS0..S5
ของแผนF-11รอบ2; ห้ามlegacycleanupลบseedระหว่างมีpreparedreader/validv2

## ทำไมต้องมี

กราฟและ indicator ต้องใช้ประวัติราคาชุดเดียวกันที่ตรวจสอบแหล่งที่มาและช่วงข้อมูลได้
หลัง F-08 มีการจัดการบัญชีแล้ว แต่ PriceSource เดิมคืนราคาล่าสุด ไม่ใช่ OHLCV
และ market-data service ยังไม่มี ingestion จริง

เจ้าของยืนยัน NC-09/T-04 วันที่2026-10-07:
- Timeframe 1m,5m,15m,1h,4h,1d
- Indicator เริ่มต้น EMA20/50/200, RSI14, MACD12/26/9, ATR14 เป็นงานF-11
- เก็บ PostgreSQL365วัน เริ่มสูงสุด1,000แท่งล่าสุดต่อคู่/timeframeภายในช่วงเก็บ
  แล้วเติมย้อนหลังเมื่อร้องขอและซ่อมช่วงที่ขาด

แหล่งคำตัดสินหลักอยู่ใน mission.md/tech-stack.md และ
[decision record](../../research/2026-10-07-f09-decisions.md)
ข้อเท็จจริงตลาดอยู่ใน [research](../../research/2026-10-07-f09-candle-history.md)

## ขอบเขต

เพิ่มสัญญาแท่งเทียนกลางผ่าน venues และตัวเชื่อม Binance TH public REST
ให้ market-data process ดึง/เก็บประวัติใน PostgreSQL พร้อมขอบเขตการอ่านข้อมูล
และความครบของช่วงเวลา เพื่อเป็นฐานให้ F-10/F-11/F-12
ใช้รายการตั้งต้น BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT ตาม mission
ไม่เพิ่มหน้าจอ admin จัดรายการเหรียญของ F-37

ไม่สร้างกราฟ F-12, ไม่คำนวณ indicator F-11, ไม่เปิด WebSocket/reconnect F-10
ไม่ใช้ API key ของผู้ใช้ ไม่อ่านยอด/position ไม่ส่งออเดอร์หรือเปลี่ยน MANUAL/BOT
ไม่เพิ่ม Paper/Live execution และไม่เปิด Live จากการมีข้อมูลตลาด

## ข้อกำหนด

| รหัส | ข้อกำหนด | ที่มา |
|---|---|---|
| RQ-1 | รับข้อมูลแท่งเทียนผ่านสัญญากลาง venues เท่านั้น; ชื่อ/รูปแบบ Binance TH อยู่ใน adapter โค้ดนอกvenuesไม่เรียกตลาดตรง | architecture §1, F-33/F-35 |
| RQ-2 | รองรับ6timeframesที่ยืนยัน; ปฏิเสธ timeframe/pair ที่ไม่อยู่ในขอบเขต ไม่เพิ่มคู่หรือintervalจากinputเอง | NC-09, mission §6 |
| RQ-3 | อ่านข้อมูลตลาดสาธารณะ ไม่ใช้คำรับรองผู้ใช้ ไม่เพิ่ม endpoint ส่งออเดอร์/โอน/ถอน | F-09 scope, trading-safety §2 |
| RQ-4 | เก็บเวลา UTC และแหล่งที่มา; OHLC/volume ใช้ชนิดข้อมูลกลางที่ผูกหน่วยถูกต้อง ใช้ Money/Quantity ตามF-02 ไม่ใช้floatหรือfinancial Decimalเปล่า | database §1/2, AGENTS §6 |
| RQ-5 | ระบุตัวตนแท่งด้วยแหล่งข้อมูล/คู่/timeframe/open-time; DB uniqueness กันซ้ำ และดึงซ้ำ/retry/concurrent requests ไม่สร้างสองแท่ง | official klines open-time identity, database correctness |
| RQ-6 | สถานะแท่งที่ยังเปิด/ปิดแล้ว/ยังยืนยันไม่ได้ต้องแยกชัด ไม่ประกาศว่าปิดจากสมมติฐานที่ยังไม่พิสูจน์; รักษาลำดับและไม่ให้ข้อมูลเก่าเขียนทับข้อมูลใหม่โดยไม่มีเกณฑ์ | research evidence gaps, frontend §3/4 |
| RQ-7 | อ่านข้อมูลที่เก็บแล้วก่อน; เริ่มโหลดสูงสุด1,000แท่งล่าสุดต่อคู่/timeframeภายในช่วง365วัน ไม่โหลดประวัติทุกช่วงทั้งหมดทันที | T-04 owner decision |
| RQ-8 | ระยะเก็บเป็น365วันคงที่ ไม่ใช่calendar year; กำหนด cutoff UTC ด้วยเวลาอ้างอิงที่เชื่อถือได้ และใช้ร่วมกันกับ initial load/backfill/read/cleanup | T-04, database §2/7 |
| RQ-9 | ขอข้อมูลช่วงย้อนหลังที่ยังไม่มีได้ภายในระยะเก็บ; paginate bounded requests ผ่านvenue โดยdeduplicate/ตรวจขอบเขต ไม่เชื่อ default startTime ของตลาดแทนช่วงที่ผู้ใช้ร้องขอ | T-04, official klines default/max limits |
| RQ-10 | ตรวจและซ่อมช่วงที่ขาดโดยยังเปิดเผย coverage/gaps/สถานะรอข้อมูลแก่ผู้เรียก; ไม่สร้างแท่งปลอมหรือvolume0เพื่อทำให้ข้อมูลดูครบ | owner-approved decision, research gaps |
| RQ-11 | ถ้าตลาดไม่มีประวัติครบ/คู่เพิ่งเริ่ม/คำขอล้มเหลว ให้แสดงข้อจำกัดตามจริง ไม่รับรอง365วันครบทุกคู่ ไม่ส่งข้อมูลบางส่วนในรูปแบบที่สื่อว่าครบแล้ว | research upstream-retention unknown |
| RQ-12 | การอ่านข้อมูลและการขอเติมประวัติต้องมีขอบเขตจำนวน/ช่วงเวลา ป้องกันงานซ้ำ และคงการแยก API/market-data ผ่านPostgreSQL ไม่เรียก HTTP ระหว่างservices | architecture §1/3, database §5 |
| RQ-13 | market-data เขียนเฉพาะตารางข้อมูลตลาด; APIอ่านข้อมูลสาธารณะที่เก็บไว้ได้โดยไม่รับสิทธิ์เขียนราคา/อ่านsecret; migrationใช้migratorเท่านั้น | database §3/5 |
| RQ-14 | ตารางแท่งเทียน partitionตามเวลาตั้งแต่ต้น พร้อมนโยบายเก็บ/cleanup365วันและการสร้างpartitionที่ต้องใช้; cleanupไม่แตะข้อมูลผู้ใช้/audit/ออเดอร์ | database §7, T-04 |
| RQ-15 | ใช้ระบบ rate limit/errors/transport ของvenueเดิม; รับมือ429/418/Retry-After, timeout, malformed payload และpartial failure โดยbounded retry ไม่สร้างretry stormหรือประกาศreadyก่อนข้อมูลcommit | F-33/F-35, official limits |
| RQ-16 | ข้อมูลที่ดึงสำเร็จบางหน้ากับสถานะ coverage ต้องสอดคล้องกับtransaction; restart/retryทำต่อได้โดยไม่สูญเสียสถานะgapหรือคืนsuccessทั้งช่วงที่ยังไม่ครบ | architecture §5, transaction/idempotency |
| RQ-17 | ตรวจ actualroles, boundaries, decimal precision, out-of-order/duplicate/concurrent ingestion, gap/backfill, retention/partition และfailure recovery ด้วยFakeVenue/fixturesตามขอบเขตใหม่ | testing §1/3/5 |
| RQ-18 | เทสต์ปกติไม่ยิงตลาดจริง; หลักฐานpublic contractที่ต้องเก็บใช้คำขอจำกัด/ไม่มีkey ไม่เปลี่ยนกฎการเทรดเพื่อตอบช่องว่างข้อมูล | testing §5, AGENTS |

## ของเดิมที่ต้องใช้ซ้ำในแผน

- `backend/src/tiewtrade/venues/{symbols,prices,moments,limits,errors,fake}.py`
- `backend/src/tiewtrade/venues/binance_th/{transport,endpoints,rate_limit,failures}.py`
- `backend/src/tiewtrade/core/money/` และ domain ความละเอียดฐานข้อมูลของF-02/F-03
- `backend/src/tiewtrade/infra/db/`, `services/market_data/main.py`
- API/OpenAPI generation และ actual-role/disposableDB test patterns เดิม

นี่เป็นข้อกำหนด ไม่ใช่การกำหนด signatures/schema/jobs/cursors หรือเลือกpolling cadence
ของแผน implementation ก่อนเจ้าของอนุมัติ

## หลักฐานที่ตรวจเพิ่มก่อนอนุมัติแผน

ตรวจ17publicGETและบันทึก fixtures แล้วก่อนเจ้าของอนุมัติแผน:
shape12fields/6timeframes, SITE/GLOBAL, bounds/limit และ UTC alignment ตามตัวอย่างที่สังเกตได้
RESTไม่มีclosureproof และยังไม่รับรองประวัติ365วันหรือแยกช่วงก่อนlistingจากgapได้
แผนที่อนุมัติจึงคง UNCONFIRMED และรายงาน missing/unavailable ตามจริง
ข้อเท็จจริงและข้อจำกัดอยู่ใน research ที่อ้างด้านบน; ไม่อนุมาน tariff จาก shared-IP headers

## ขั้นอนุมัติ

NC-09/T-04 ปิดแล้ว; requirements, plan และ validation ได้รับอนุมัติจากเจ้าของแล้ว
ผล implementation/verification อยู่ใน validation.md และสถานะงานอยู่ใน roadmap.md
การอนุมัติเอกสารไม่ใช่คำสั่ง commit/push/merge
