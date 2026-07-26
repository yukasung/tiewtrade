# DEV-99 Task 3 Report

## RED

Command:

```bash
.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py -q
```

Result: failed at collection with the expected `ModuleNotFoundError` for
`tiewtrade.integrations.binance.public_market_data` before implementation.

## GREEN and verification

```text
.venv/bin/python -m pip install 'aiohttp>=3.11,<4'
  Initial sandbox attempt: DNS resolution failed; approved retry installed aiohttp 3.14.3.
.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py -q
  10 passed in 0.05s
.venv/bin/python -m pytest -q
  223 passed in 0.47s
.venv/bin/python -m ruff check src tests
  All checks passed!
.venv/bin/python -m ruff format --check src tests
  70 files already formatted
.venv/bin/python -m mypy src
  Success: no issues found in 39 source files
git diff --check
  exit 0
```

## Files

- `pyproject.toml`
- `src/tiewtrade/market_data/candle_source.py`
- `src/tiewtrade/integrations/binance/public_market_data.py`
- `tests/unit/integrations/binance/test_public_market_data.py`

## Self-review

- Consumer-owned historical/live Protocols and `aiohttp` dependency are present.
- Every REST page request and the WebSocket handshake validate the Binance interval before network use.
- REST rejects non-2xx, error-object and malformed JSON responses; range pagination exits on empty or non-advancing pages.
- Recent data excludes candles not completed by its UTC boundary; live data emits only closed candles; `close()` awaits session close once.
- Tests use fake HTTP/WebSocket sessions only and make no real Binance request.

## Concerns

None. `close()` is asynchronous because `aiohttp.ClientSession.close()` must be awaited; it resolves to `None` and is idempotent.

## Review fix: completed-candle boundary และ Task 4 contracts

ส่วนนี้แทนสถานะและข้อสรุปเดิมในหัวข้อ Self-review/Concerns หลัง human review
โดยเฉพาะการย้าย source Protocols ออกจาก Task 3

### RED

Command:

```bash
.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py::test_load_recent_requests_and_returns_requested_completed_candle_count -q
```

Result:

```text
F                                                                        [100%]
E       AssertionError: assert {'symbol': 'B...', 'limit': 3} == {'symbol': 'B...9, 'limit': 3}
E         Right contains 1 more item:
E         {'endTime': 1767226199999}
1 failed in 0.14s
```

Test ยืนยันว่าเมื่อ `completed_before` อยู่ที่ `00:12 UTC` สำหรับ timeframe `5m`
request ต้องจบที่ `00:09:59.999 UTC` และ response ปกติต้องคืน completed candles
ครบ `count=3`

### GREEN และ verification

```text
.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py -q
  13 passed in 0.08s
.venv/bin/python -m pytest -q
  226 passed in 0.48s
.venv/bin/python -m ruff check src tests
  All checks passed!
.venv/bin/python -m ruff format --check src tests
  69 files already formatted
.venv/bin/python -m mypy src
  Success: no issues found in 38 source files
npm --prefix docs-site run check:content
  exit 0
git diff --check
  exit 0
```

### Files

- `src/tiewtrade/integrations/binance/public_market_data.py`
- `tests/unit/integrations/binance/test_public_market_data.py`
- ลบ `src/tiewtrade/market_data/candle_source.py`
- `docs/superpowers/plans/2026-07-26-public-binance-market-data-runtime.md`
- `PROJECT_PLAN.md`
- `.superpowers/sdd/task-3-report.md`

### Self-review

- `load_recent` จัด `completed_before` ลง boundary ของ `config.interval` แล้วส่ง
  `endTime` เป็น millisecond ก่อน boundary เพื่อไม่ให้ open candle ใช้ quota ของ
  `limit=count`; local completed-candle filter เดิมยังคงอยู่
- Tests แยกยืนยันว่า `load_recent`, `load_range` และ WebSocket stream reject Binance
  interval ที่ไม่รองรับก่อน REST request หรือ WebSocket handshake
- Task 3 ไม่มี `HistoricalCandleSource`/`LiveCandleSource` หรือไฟล์ Protocol ล่วงหน้า
  แล้ว โดย implementation plan ย้ายการสร้าง consumer-owned contracts ไป Task 4
  พร้อม `MarketDataRuntime` ซึ่งเป็น consumer จริง
- `PROJECT_PLAN.md` แยก public Binance market data ซึ่งอยู่ใน Paper Trading Complete
  ออกจาก Binance Live execution adapters ซึ่งยังต้องเพิ่มตาม Live gates
- ไม่ refactor translation หรือ middle-man code ที่อยู่นอก blocking findings และไม่แตะ
  `.mcp.json`

### Concerns

ไม่มี concern ที่เหลือในขอบเขต Task 3; การตัดสินว่า exchange history มี candles ไม่พอ
ยังคงเป็นหน้าที่ของ `MarketDataRuntime` ใน Task 4 ตามแผน
