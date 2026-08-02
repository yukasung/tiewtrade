# รายงานการแก้ไข final whole-branch review ของ DEV-138

## ขอบเขตและผลลัพธ์

แก้ findings ทั้งหมดบน branch `dev-138-dark-candlestick-chart` จาก starting head
`8245dac` โดยไม่เปลี่ยน business/risk policy, ไม่เพิ่ม SQLite candle cache, ไม่เพิ่ม
manual trading, Live/private Binance, credentials หรือ network ใน tests

1. Paper Runtime ส่ง completed `Candle` fact หลัง durable processing ผ่าน
   generation-safe `RuntimeSnapshotRelay` ไปยัง `ChartWorkflow` แล้ว
2. `ChartHistory.refresh_completed()` เลื่อน newest visible range แบบความกว้างคงที่,
   เก็บ latest completed Candle และ query durable Session/range Fills ใหม่โดยไม่โหลด
   Binance ซ้ำ
3. Candle event ที่มาระหว่าง worker ทำงานเก็บเฉพาะ event ล่าสุด และ stale generation
   ไม่ publish ทับ snapshot ปัจจุบัน
4. Next ถูก disable ที่ latest completed boundary และ range ถัดไปที่ใกล้ boundary ถูก
   จำกัดไม่ให้เลยอนาคต
5. `LOADING` ถูก publish/render จริง และ chart-specific Retry โหลด last safe range เดิม;
   `UNAVAILABLE` ไม่ปิด Bot Control หรือ Trade History
6. ลบ `ChartCandleSource`/`ChartFillHistory`; ใช้ `HistoricalCandleSource` เดิมและ
   concrete `SQLiteTradeHistory` ตาม persistence boundary
7. migration v4 test ลบ `trade_fills_session_time_idx` จริงก่อน migrate จึงตรวจ path
   v4→v5 ได้ ไม่ได้ผ่านเพราะ index จาก fresh schema ค้างอยู่
8. desktop composition test เรียก chart loader จริงสำหรับ Spot/Futures และยืนยัน exact
   public REST/WebSocket endpoints โดยใช้ fake public market data ไม่มี private API
9. chart header แสดง `Paper`; painter model มี Buy/Sell triangle geometry, label,
   candlestick body/wick และ volume bars ที่ scale จาก Candle volume จริง
10. UI event boundary ใช้ application-owned `CompletedCandleFacts`; UI ไม่มี import
    SQLite, Binance, execution, strategy หรือ concrete market-data Candle

## หลักฐาน RED/GREEN

### Runtime → Chart และ durable Fill refresh

- RED: controller test ล้มด้วย `unexpected keyword argument
  'completed_candle_callback'` ทั้ง Spot/Futures; workflow ล้มด้วย `unexpected keyword
  argument 'refresh_chart'`; MainWindow acceptance ล้มด้วย `unexpected keyword argument
  'refresh_chart'`
- RED: `ChartHistory` refresh test ล้มด้วย `AttributeError: 'ChartHistory' object has no
  attribute 'refresh_completed'`
- GREEN: targeted Runtime/ChartHistory/Workflow/Desktop acceptance — `5 passed`

### LOADING, Retry และ newest boundary

- RED: targeted 6 tests ล้มตาม behavior ที่ขาด ได้แก่ไม่มี LOADING snapshot, ไม่มี
  `retry()`, ไม่มี `retry_button`, Next ยัง enabled และยัง emit future range
- GREEN: targeted state/navigation/isolation — `6 passed`
- GREEN: chart workflow/widget/MainWindow/desktop acceptance รวม — `15 passed`

### BackgroundTask generation safety

- RED: worker-active completed-candle test ล้มด้วย `IndexError` เพราะไม่มี task สำหรับ
  pending latest Candle
- GREEN: test เดิมผ่านหลัง queue latest event และ drain เมื่อ worker รุ่นปัจจุบันจบ

### Desktop public endpoint composition

- RED: เมื่อ test เรียก loader จริงบน fresh database ล้มด้วย
  `TradeHistoryUnavailableError` จาก `no such table: trade_fills`
- GREEN: composition เรียก database migration ก่อน bounded chart query และยืนยัน
  Spot `https://data-api.binance.vision/api/v3/klines` กับ Futures
  `https://fapi.binance.com/fapi/v1/klines` พร้อม public WebSocket profiles — `1 passed`

### Painter geometry

- RED: geometry test ล้มด้วย `AttributeError` เพราะ `_build_painter_model` ยังไม่มี
- GREEN: widget suite ตรวจ triangle orientation และ volume heights `20/60/40` จาก
  volumes `1/3/2` — `6 passed`

### UI dependency boundary

- RED จาก full suite: `991 passed, 1 failed` โดย acceptance safety gate พบ
  `tiewtrade.market_data.candle` ใน UI
- GREEN: ย้าย event contract ไป `application.chart_data.CompletedCandleFacts`; targeted
  UI safety + workflow + desktop chart — `10 passed`

### Migration v4 test sensitivity

- finding นี้เป็น test weakness; production v4 migration path ถูกต้องอยู่แล้ว จึงไม่มี
  production RED ที่ซื่อสัตย์
- test ใหม่ยืนยันว่า index ไม่มีอยู่ก่อน migrate แล้วจึงตรวจว่าถูกสร้าง — `1 passed`

## Verification ล่าสุด

- Targeted whole affected surface:
  `pytest` สำหรับ chart data/history, Paper Runtime, workflows, painter, MainWindow,
  desktop composition, SQLite history และ desktop acceptance — `144 passed`
- Full suite:
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src ../../.venv/bin/python -m pytest -q` —
  `992 passed in 7.18s`
- `../../.venv/bin/python -m ruff check src tests` — ผ่าน
- `../../.venv/bin/python -m ruff format --check src tests` — `175 files already formatted`
- `../../.venv/bin/python -m mypy` — `Success: no issues found in 175 source files`
- `npm --prefix docs-site test` — `50 passed`
- `npm --prefix docs-site run check:content` — ผ่าน
- `git diff --check 8245dac HEAD` — ผ่าน
- static scan ไม่พบ `ChartCandleSource`, `ChartFillHistory` หรือ forbidden UI imports

หมายเหตุ: worktree ไม่มี `docs-site/node_modules` ตอนเริ่มตรวจ จึงใช้
`npm --prefix docs-site install --offline --ignore-scripts`; dependency tree audit พบ
`0 vulnerabilities` และ `node_modules` ถูก ignore ไม่มี source/package-lock change

## Commits

- `a472195` — `fix: complete runtime candlestick chart flow`
- `7989e2b` — `test: exercise missing v4 chart fill index`
- `adc9457` — `fix: keep chart runtime facts behind application boundary`

## เอกสารและความเสี่ยงคงเหลือ

- ไม่แก้ design spec หรือ implementation plan เพราะเป็น implementation corrections
  ให้ตรง intended design เดิม ไม่มี scope/behavior decision ใหม่
- ไม่มี known blocker; tests ใช้ fake public transport และ Paper adapters ตาม safety
  policy จึงไม่ได้พิสูจน์ availability ของ Binance จริง (ตั้งใจไม่ทำ network acceptance)
- visual verification เป็น painter-model geometry และ offscreen Qt tests; ไม่มี manual
  trading control, Live order หรือ private endpoint ถูกเพิ่ม
