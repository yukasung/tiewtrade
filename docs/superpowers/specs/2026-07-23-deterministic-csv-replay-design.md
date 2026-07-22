# Deterministic CSV Replay Design

## Status

- Issue: DEV-80
- Scope: Paper Spot tracer-bullet verification
- Trade safety: local CSV input and Paper execution only

## Goal

สร้างเครื่องมือ command line สำหรับ replay completed Candles จาก CSV ผ่าน
`PaperSpotSession` และคืน stable JSON summary ที่เหมือนเดิมทุกครั้งเมื่อใช้ input,
Session configuration และ Preset version เดิม

เครื่องมือนี้ใช้สำหรับ acceptance และ regression verification เท่านั้น ไม่ใช่
production market-data runtime, SQLite persistence หรือ Backtest framework แบบทั่วไป

## Architecture

แยกความรับผิดชอบเป็นสามส่วน:

```text
CSV file
   |
   v
Strict Candle CSV Loader
   |
   v
Paper Spot Replay Runner
   |
   v
ReplayResult -> Stable JSON -> CLI stdout
```

### Strict Candle CSV Loader

`tiewtrade.replay.csv_candles` เป็นเจ้าของการอ่านไฟล์และแปลงแต่ละแถวเป็น
`Candle` โดย:

- รับ `Path` และ `MarketDataConfig`
- บังคับ header ตามลำดับ `open_time,open,high,low,close,volume`
- ปฏิเสธ header ที่ขาด เกิน ซ้ำ หรือเรียงผิด
- รับ timestamp แบบ ISO-8601 ที่มี UTC offset เท่านั้น
- แปลง OHLCV เป็น `Decimal` โดยไม่ผ่าน `float`
- ใช้ symbol และ timeframe จาก `MarketDataConfig` ไม่อ่านหรือ hard-code ใน CSV
- ส่ง validation ของราคา, range, volume และ timeframe alignment ให้ `Candle`
- รายงาน row number ใน `ValueError` เมื่อข้อมูลไม่ถูกต้อง
- คืน immutable `tuple[Candle, ...]` และปฏิเสธไฟล์ว่าง

Loader ไม่บังคับจำนวน 40 Candles เพื่อให้ใช้กับ fixture อื่นได้ จำนวน 40 เป็น
acceptance contract ของ DEV-80 fixture

### Paper Spot Replay Runner

`tiewtrade.replay.paper_spot` เป็น application-facing replay adapter ที่:

- รับ `SessionConfig`, `MarketDataConfig`, `SymbolRules`, Preset และ Candles
- สร้าง `PaperSpotSession` ใหม่ทุกครั้งเพื่อไม่ให้ state รั่วระหว่าง replay
- ส่ง Candles ตามลำดับไฟล์โดยใช้ `received_at=candle.close_time`
- ให้ `CompletedCandleStream` เป็นผู้บังคับ continuity และ duplicate rules
- ต้องได้รับ `accepted=True` ทุกแถว; duplicate, out-of-order หรือ Candle ที่ไม่ถูก
  ยอมรับทำให้ replay ล้มเหลวแทนการสร้าง summary บางส่วน
- รวม accepted Candle count, current Basket Entry count, closed Basket count และ
  realized PnL จาก `ClosedBasket` แต่ละรายการ
- คืน immutable `ReplayResult`

`ReplayResult.to_json()` แปลง `Decimal` เป็น plain string ด้วย fixed-point format
เพื่อไม่ให้เกิด scientific notation, ใช้ key order คงที่และ compact separators เพื่อให้
เปรียบเทียบ output แบบ exact string ได้

### CLI Composition

`tiewtrade.paper_replay_main` เป็น thin CLI ที่:

- รับ path ของ CSV
- รับ `--available-capital`, `--trading-capital-ratio` และ `--max-entries`
- มี `--symbol` และ `--timeframe` เป็น composition defaults สำหรับ acceptance
  scenario โดยค่าถูกส่งผ่าน configuration ไม่ฝังใน Strategy, loader หรือ runner
- ประกอบ immutable Session configuration, deterministic Symbol rules และ Preset v1
- เขียน stable JSON หนึ่งบรรทัดไปยัง stdout
- คืน non-zero exit code พร้อมข้อความ error ทาง stderr เมื่อ input/config ไม่ถูกต้อง

CLI ห้าม import Binance adapter, credentials, Keyring, Live Preflight หรือเปิด network
connection

## Acceptance Fixture

`tests/fixtures/btcusdt_5m_tracer.csv` มี completed Candles 40 แท่งต่อเนื่องทุก
5 นาทีใน UTC และถูกออกแบบให้เกิด flow ต่อไปนี้:

1. Wilder indicators warm up
2. RSI ลดต่ำกว่า reset threshold
3. bullish confirmation สร้าง pending Entry Intent
4. Entry Fill ที่ราคาเปิด Candle ถัดไป
5. Take Profit ไม่ Fill ใน Entry Fill Candle
6. Candle หลังจากนั้นแตะ Take Profit และปิด Basket อย่างน้อยหนึ่งรายการ

Fixture ไม่มี symbol/timeframe columns เพราะ identity มาจาก `MarketDataConfig`

## Stable Result Contract

JSON summary มีเฉพาะ audit facts ต่อไปนี้:

```json
{"accepted_candles":40,"closed_baskets":1,"current_entries":0,"realized_pnl":"1.23456789"}
```

ค่าจริงของ `closed_baskets` และ `realized_pnl` มาจาก replay แต่ชื่อ field, ชนิดของ
ค่า และ serialization format ต้องคงที่ตาม contract นี้

## Error Handling

- file missing หรือ unreadable: propagate error ที่ระบุ path
- empty CSV หรือ header ผิด: `ValueError`
- timestamp, Decimal หรือ Candle field ผิด: `ValueError` ที่ระบุ row number
- Candle gap, duplicate หรือ out-of-order: replay หยุดด้วย `ValueError` แทนการคืน
  summary บางส่วน
- Session ที่ไม่ใช่ Paper Spot: ใช้ validation เดิมของ `PaperSpotSession`

ไม่มีการข้าม malformed row และไม่มี partial-success mode เพราะจะทำให้ replay ไม่
deterministic และปิดบังข้อมูลตลาดที่เสีย

## Test Strategy

ใช้ Test-Driven Development ตามลำดับ:

1. unit tests ของ strict CSV loader สำหรับ happy path, exact headers, UTC, Decimal
   และ row-numbered errors
2. unit tests ของ `ReplayResult` สำหรับ stable JSON และ Decimal serialization
3. acceptance test replay fixture 40 Candles สองครั้งผ่าน object graph ใหม่คนละชุด
4. assert ว่า outputs ตรงกันทุกตัวอักษรและเกิด Entry Fill/closed Basket/realized PnL
5. CLI test ตรวจ stdout และยืนยันว่า process สำเร็จโดยไม่ใช้ network หรือ Binance

Final verification ใช้ pytest, Ruff check, Ruff format, mypy และ `git diff --check`

## File Map

```text
src/tiewtrade/
├── replay/
│   ├── __init__.py
│   ├── csv_candles.py
│   └── paper_spot.py
└── paper_replay_main.py
tests/
├── acceptance/
│   └── test_paper_spot_replay.py
├── fixtures/
│   └── btcusdt_5m_tracer.csv
└── unit/replay/
    ├── test_csv_candles.py
    └── test_paper_spot.py
```

`README.md` จะระบุ setup, replay command, JSON contract และ verification commands

## Out of Scope

- SQLite persistence และ migrations
- production Binance market-data adapter
- Paper Futures และ funding replay
- Live Spot/Futures execution
- generic Backtest engine, strategy registry หรือ plugin system
- UI สำหรับเลือกหรือ replay CSV
