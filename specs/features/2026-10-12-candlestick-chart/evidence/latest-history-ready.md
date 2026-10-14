# Default 1h latest-history / READY checkpoint

วันที่: 2026-10-13 (Asia/Bangkok)

## Defect and change

เมื่อ `desired_end` ขยายทางขวาหลัง lease เดิมตรวจครบแล้ว ingestion ตั้ง
`cursor=desired_start` ทำให้คิวกลับไปต้น retention window ก่อนเข้าถึงแท่งใหม่.
แก้ให้ right-only expansion เริ่มที่ `leased_end`; การขยายทางซ้ายยังเริ่มที่
`desired_start` ตามเดิม. ไม่มีการเปลี่ยน source budget, retry, finality,
Money/Quantity, trading mode หรือการส่งออเดอร์.

## Targeted verification

- Regression test ใหม่สำหรับ complete lease → right expansion → fetch เฉพาะ tail:
  **1 passed in 1.10s**.
- Ingestion, candle realtime และ chart preview ที่ได้รับผลกระทบ:
  **56 passed in 14.83s**.
- Ruff check และ format check ของสองไฟล์ที่เปลี่ยนผ่าน; configured mypy:
  **370 source files, no issues**.
- การเลือก test ครั้งแรกอ้างชื่อไฟล์ preview ผิด จึงได้ `no tests ran`;
  แก้ selector เป็น `tests/infra/market_data/test_chart_preview.py` แล้วชุด 56 tests ผ่าน.
- ไม่รัน full suite หรือ performance validation ซ้ำ เพราะ inputs ที่เปลี่ยนจำกัดอยู่ที่
  ingestion cursor transition และ regression tests.

## Development deployment and actual data

- Build/recreate เฉพาะ `market-data`; image manifest
  `sha256:ff7743a389fd376ac4657ffa1f4025dbe50efdf3a062e8c2c726c73fcc3f9801`.
- Read-only PostgreSQL observation หลัง deploy: default `BTC/USDT 1h` มี 1,071 rows,
  latest history open `2026-10-13T03:00:00Z`, demand `COMPLETE`, cursor/desired end
  `2026-10-13T04:00:00Z`, และ previous-candle settlement เป็นจริง.
- Observation นี้รับรองเฉพาะ default BTC 1h ณ checkpoint; DOGE/XRP 1h ยังอยู่ในคิว
  ระหว่าง snapshot และไม่ถูกใช้ขยายผลว่า 30 series พร้อมทั้งหมด.

## Real browser confirmation

Chromium เปิด `http://localhost:5173/chart` ผ่าน frontend/API/PG จริงด้วยบัญชี smoke ใหม่:

- Default selection: `BTC/USDT`, `1h`.
- History HTTP 200: 1,000 candles และ 1,000 indicator rows; latest candle
  `2026-10-13T03:00:00Z`, result end `2026-10-13T04:00:00Z`.
- Live HTTP 200 แปดครั้งในประมาณ 19 วินาที: ทุกครั้ง `READY`, reason null,
  history end `2026-10-13T04:00:00Z`, current candle `OPEN` ที่ 04:00Z.
  Fingerprint ของ exact live row ต่างกันทั้งแปดครั้ง จึงยืนยันว่าแท่งสดอัปเดต.
- Verify HTTP 200; หน้าแสดง history/proof สอดคล้องและ live พร้อม.
  ไม่มี alert, request failure หรือ JavaScript page error.
- บัญชี smoke ยังคงอยู่ใน dev DB; ไม่มี order request หรือ trading-mode change.

## Manual review and Retry-After correction

ตรวจหน้า chart เพิ่มเติมบน Chromium โดยไม่รัน full suite:

- ภาษาไทย/อังกฤษ, offline/reconnect และความกว้าง 375, 768, 1,440 px ทำงานโดยไม่เกิด
  horizontal overflow หรือ JavaScript page error.
- ทั้งห้าคู่ใน timeframe 1h คืนประวัติที่สอดคล้อง; สถานะ live แสดง READY หรือ stale
  ตามข้อมูลจริง ณ snapshot. Timeframe ที่ backfill ยังไม่ครบแสดง loading/partial/recovering
  ตามจริง และ typed `INDICATOR_BUSY`/`INDICATOR_RATE_LIMITED` หยุดอ่านตามสัญญา.
- พบ defect ที่ปุ่ม manual Retry ยัง disabled หลัง `Retry-After` หมด เพราะ terminal error
  หยุด network timer และไม่มี render รอบใหม่. แก้ controller ให้ตั้ง timer สำหรับปลุก view
  หนึ่งครั้งเมื่อ cooldown หมด โดยไม่ส่ง request อัตโนมัติ และครอบคลุม cooldown จาก refresh
  error ด้วย.
- Regression tests ของ chart controller/panel/API/read episode ผ่าน **32/32**; หลังแก้ lint
  เฉพาะสองไฟล์ผ่าน, frontend typecheck ผ่าน และ controller regression ผ่าน **12/12**.
- Build/recreate เฉพาะ `frontend`; image manifest
  `sha256:965ed8e14cbb72129baaa99401cdf3c89a581e5bd5a2832966b8937dd49ef56f`.
- Browser acceptance บน frontend ที่ deploy จริง: default BTC/USDT 1h ได้ HTTP 200,
  history/proof สอดคล้องและ live READY. เมื่อจำลอง history ตอบ
  `503 INDICATOR_BUSY` พร้อม `Retry-After: 1` มี request เดียวระหว่าง cooldown,
  ปุ่ม disabled ก่อนเวลาและ enabled เองหลังหมดเวลา; การกดปุ่มจึงส่ง request ครั้งที่สอง.
  ไม่พบ auto-retry หรือ JavaScript page error.
- การสมัครบัญชีผ่าน frontend ในรอบนี้ถูก rate limit ตามกฎ จึงสร้างบัญชี smoke ผ่าน API
  พัฒนาโดยตรงที่ใช้ bucket แยก แล้วนำ session เข้า browser; ไม่แก้หรือล้าง throttle.

Checkpoint นี้ปิด defect ของ default 1h latest history/REST settlement ที่ตรวจพบ.
F-12 ยัง In Progress ตาม manual/review/CI/coverage ที่เหลือ และ V-17 ยังคง
Pending Full Validation; smoke นี้ไม่ใช้แทนด่านเหล่านั้น.
