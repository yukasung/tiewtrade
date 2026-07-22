# Paper Spot Core Tracer Bullet Implementation Plan

> **Execution:** ใช้ Test-Driven Development ทีละ Issue และทำตามลำดับ dependency
> ใน `PROJECT_PLAN.md`

## Goal

สร้าง headless Paper Spot vertical slice ที่ replay completed Candles ผ่าน RSI Step
Grid, Entry Pair, Basket Take Profit และ conservative Paper Fill ได้อย่าง
deterministic โดยไม่เชื่อมบัญชี Binance และไม่ส่ง Live order

BTCUSDT 5m เป็น acceptance scenario ของ Internal Alpha ค่า symbol, timeframe,
capital allocation และ maximum Entries ต้องเข้าระบบผ่าน configuration/policy ไม่ฝัง
อยู่ใน Strategy หรือ market-data implementation

## Architecture

Tracer Bullet ใช้ feature-first modular monolith ภายใต้ `src/tiewtrade`:

- `market_data` เป็นเจ้าของ Candle, timeframe conversion และ continuity checks
- `strategies/rsi_step_grid` เป็นเจ้าของ Versioned Preset, Wilder indicators และ
  Entry Intent
- `trading` เป็นเจ้าของ shared `SessionConfig`, policies, capital, Basket,
  Entry Pair และ PnL
- `application` จัดลำดับ completed Candle, Strategy, lifecycle และ execution
- `execution` เก็บ concrete Paper Spot implementation ที่จำลอง Fill โดยไม่มี
  Binance side effect

Paper และ Live ใช้ business rules ใน `strategies` กับ `trading` ร่วมกัน แต่ไม่ใช้
execution implementation เดียวกัน ยังไม่สร้าง generic execution interface ใน tracer
เพราะมี production adapter จริงเพียงแบบเดียว

## Global Constraints

- เวลา domain ทั้งหมดเป็น timezone-aware UTC
- ใช้ `Decimal` สำหรับราคา quantity ทุน fee slippage และ PnL
- Strategy เป็น Long-only RSI Step Grid และประเมิน completed Candle เท่านั้น
- Preset version ตรึง RSI/ATR thresholds และ Take Profit multiplier ระหว่าง Session
- `max_entries` เป็น `EntryPolicy` ของ Session ไม่ใช่ Strategy Preset parameter
- `trading_capital_ratio` เป็น `SpotTradingPolicy` และ Reserve derive จากส่วนที่เหลือ
- 80% กับ 10 Entries เป็น form defaults; tests ต้องใช้ค่าอื่นเพื่อพิสูจน์ว่าไม่ hard-code
- Basket, Capital และ Entry Pair ต้องรับ policies จาก Session เดียวกัน
- Paper Entry จาก signal Candle `N` Fill ที่ราคาเปิด Candle `N+1`
- Take Profit ห้าม Fill ใน Candle เดียวกับ Entry Fill
- ห้ามสร้าง base strategy, registry, factory หรือ catch-all module ล่วงหน้า
- ทุก Task ใช้ failing test → minimal implementation → refactor → verification

## Existing Foundation

งานต่อไปนี้พร้อมแล้วและห้ามสร้าง implementation ซ้ำ:

- `trading/session_config.py` — shared immutable `SessionConfig`
- `trading/entry_policy.py` — configurable even `max_entries`
- `trading/spot_policy.py` — configurable Spot Trading Capital Ratio
- `market_data/config.py` — symbol/timeframe configuration
- `market_data/candle.py` และ `completed_candle_stream.py`
- `trading/capital.py`, `symbol_rules.py`, `basket.py` และ `entry_pair.py`

## Target File Map

สร้างไฟล์เมื่อ Task ที่เป็นเจ้าของพฤติกรรมเริ่มขึ้นเท่านั้น:

```text
src/tiewtrade/
├── application/
│   └── paper_spot_session.py
├── execution/
│   └── paper_spot.py
├── replay/
│   └── paper_spot.py
├── strategies/
│   └── rsi_step_grid/
│       ├── indicators.py
│       ├── preset.py
│       └── strategy.py
└── paper_replay_main.py
tests/
├── acceptance/
│   └── test_paper_spot_replay.py
├── fixtures/
│   └── btcusdt_5m_tracer.csv
└── unit/
    ├── application/test_paper_spot_session.py
    ├── execution/test_paper_spot.py
    └── strategies/
        ├── test_rsi_step_grid_indicators.py
        └── test_rsi_step_grid_strategy.py
```

## Task 1 — DEV-78 RSI Step Grid Indicators and Entry Intent

### Interfaces

- Consumes: `Candle`, session ID, immutable Preset และ lifecycle permission
- Produces: `IndicatorSnapshot`, `EntryIntent` และ stateful Strategy decision

### Test-first steps

1. สร้าง failing tests สำหรับ immutable Preset และ Wilder warm-up
2. พิสูจน์ RSI เริ่ม Wilder smoothing หลัง price changes ครบ period และ ATR เริ่ม
   หลัง true-range samples ครบ period
3. สร้าง failing tests สำหรับ reset, bullish confirmation, pending Intent และ
   reset consumption หลัง Fill
4. พิสูจน์ deterministic idempotency key จาก Session, Preset, Candle และลำดับ Entry
5. Implement minimal Preset, indicators และ Strategy โดยไม่สร้าง base class
6. รัน focused tests แล้ว refactor หลัง green เท่านั้น

### Required behavior

Preset v1 ตรึง `rsi_period`, reset threshold, entry threshold, `atr_period` และ
Take Profit ATR multiplier แต่ต้องไม่มี `max_entries`, capital ratio, symbol หรือ
Trade Mode

Strategy สร้าง Intent เมื่อ:

- เคยพบ RSI ต่ำกว่า reset threshold
- RSI ปัจจุบันสูงกว่า entry threshold
- Candle เป็น bullish และ close สูงกว่า reset close
- application ส่ง lifecycle permission ว่าเข้าได้
- ไม่มี Intent เดิมที่ยังรอผล

Strategy ไม่สร้าง Order และไม่รู้จัก Paper หรือ Live

### Verification

```bash
.venv/bin/python -m pytest tests/unit/strategies -q
.venv/bin/python -m ruff check src/tiewtrade/strategies tests/unit/strategies
.venv/bin/python -m mypy src
```

## Task 2 — DEV-79 Conservative Paper Spot Session

### Interfaces

- Consumes: shared `SessionConfig`, `MarketDataConfig`, `SymbolRules`, Preset,
  completed Candles และ concrete Paper executor
- Produces: application snapshot, Paper Fill records และ closed Basket results

### Test-first steps

1. สร้าง failing tests สำหรับ concrete Paper executor ที่คำนวณ slippage, quantity,
   minimum notional และ fee จากค่าของ Session
2. ใช้ค่า `trading_capital_ratio` และ `max_entries` ที่ไม่ใช่ defaults ใน tests
3. สร้าง failing application tests สำหรับ pending Intent และ Fill ที่ next open
4. พิสูจน์ว่า Take Profit เริ่มตรวจใน Candle ถัดจาก Entry Fill เท่านั้น
5. พิสูจน์ว่า Basket ปิดแล้ว reset Entry Pair และเริ่ม Basket ใหม่ได้
6. Implement application orchestration กับ concrete Paper executor โดยไม่สร้าง
   generic execution interface
7. รัน focused tests และ full suite

### Event order

สำหรับ completed Candle แต่ละแท่ง application ต้องประมวลผลตามลำดับที่แน่นอน:

1. ตรวจ configuration identity และ completed-candle continuity
2. บันทึก `basket_existed_at_candle_open` ก่อนทำ Fill แล้ว Fill pending Entry Intent
   ที่ราคาเปิดของ Candle ปัจจุบัน พร้อมบันทึก `entry_filled_on_current_candle`
3. ตรวจ Take Profit เมื่อ `basket_existed_at_candle_open` เป็นจริงและ
   `entry_filled_on_current_candle` เป็นเท็จเท่านั้น
4. คำนวณ Wilder indicator snapshot
5. ขอ lifecycle permission จาก Entry Pair และ Basket capacity
6. ประเมิน Strategy และเก็บ Intent ใหม่สำหรับ Candle ถัดไป
7. คืน immutable snapshot/audit facts ให้ caller

Paper execution คำนวณผลจำลองเท่านั้น ห้าม import Binance SDK, credentials,
Preflight หรือ Live transport

### Session policies

- application ต้องปฏิเสธ Session ที่ไม่ใช่ `PAPER` และ `SPOT`
- `SpotCapitalPlan` รับ `SpotTradingPolicy` กับ `EntryPolicy` จาก Session
- `Basket` และ `EntryPairLifecycle` รับ `EntryPolicy` object เดียวกัน
- symbol rules มาจาก exchange facts หรือ deterministic fixture ไม่ฝังใน executor
- fee และ slippage มาจาก immutable Session configuration

### Verification

```bash
.venv/bin/python -m pytest tests/unit/application tests/unit/execution -q
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
```

## Task 3 — DEV-80 Deterministic CSV Replay and Acceptance

### Interfaces

- Consumes: strict CSV rows, `SessionConfig`, `MarketDataConfig` และ `SymbolRules`
- Produces: `ReplayResult` และ stable JSON summary

### Test-first steps

1. สร้าง CSV fixture 40 Candles ต่อเนื่องแบบ UTC สำหรับ acceptance scenario
2. สร้าง failing acceptance test ที่ replay fixture เดิมสองครั้ง
3. Implement strict CSV loader ที่รับ symbol/timeframe จาก configuration
4. Implement replay runner ที่ประกอบ shared core กับ concrete Paper executor
5. Implement CLI โดยรับ configurable capital, ratio และ maximum Entries
6. เปรียบเทียบ JSON output สองครั้งแบบ exact string
7. รัน final verification และบันทึก completion evidence

### Acceptance

- รับ completed Candles 40 รายการโดยไม่ซ้ำและไม่เกิด gap
- เกิด RSI reset และ bullish confirmation ตาม Preset
- Entry Fill ที่ next open พร้อม fee/slippage
- ปิด Basket อย่างน้อยหนึ่งรายการด้วย Take Profit
- output มี accepted-candle count, Entry count, closed-Basket count และ realized PnL
- replay สองครั้งได้ JSON ตรงกันทุกตัวอักษร
- ไม่มี Binance connection หรือ Live order

### Verification

```bash
.venv/bin/python -m pytest tests/acceptance/test_paper_spot_replay.py -q
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```

## Tracer Completion Evidence

ก่อนปิด tracer ต้องรายงาน:

- commit hashes ของ Strategy, Paper Session และ replay Tasks
- test counts และผล Ruff format/check กับ mypy
- stable JSON output จาก replay สองครั้ง
- ยืนยันว่าไม่ได้เชื่อม Binance หรือส่ง Live order
- ข้อจำกัดที่เหลือตาม `PROJECT_PLAN.md` โดยไม่เรียก tracer นี้ว่า Paper Trading Complete
