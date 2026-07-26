# Public Binance Market Data Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เชื่อม Binance Public REST/WebSocket เข้ากับ completed-candle flow ที่ Warm-up Indicator, ซ่อม gap และ fail closed เมื่อข้อมูลไม่สด โดยไม่ใช้ API Key หรือส่ง Order

**Architecture:** `MarketDataRuntime` แบบ async เป็นผู้ประสาน Historical Warm-up, live stream, continuity, stale deadline, reconnect และ backfill ผ่าน consumer-owned contracts ส่วน `integrations/binance` แปลง Spot หรือ USDⓈ-M Futures payload เป็น `Candle` ตาม Market Type ที่ application composition เลือก Paper Spot Session แยก indicator-only Warm-up ออกจาก live Strategy evaluation อย่างชัดเจน

**Tech Stack:** Python 3.12, `asyncio`, `aiohttp>=3.11,<4`, `Decimal`, pytest, Ruff, mypy

## Global Constraints

- ใช้ `BTCUSDT 5m` เป็น Internal Alpha acceptance scenario แต่รับ `symbol` และ `timeframe` จาก configuration ห้าม hardcode ใน business logic
- Spot และ USDⓈ-M Futures ใช้ Runtime contract เดียวกัน แต่เลือก Public Kline endpoint คนละ profile และห้ามแทนข้อมูลกัน
- Warm-up เตรียม Indicator เท่านั้น ห้ามสร้าง Entry Intent, Fill หรือ Basket
- Warm-up deadline เท่ากับ 30 วินาที
- Stale grace เท่ากับ 30 วินาทีหลัง expected completed-candle boundary
- Reconnect delay เท่ากับ 1, 2 และ 4 วินาที แล้วจบที่ `FAILED_CLOSED`
- ไม่เก็บ Candle ลง SQLite และไม่เพิ่ม Chart UI
- ห้ามใช้ API Key, private endpoint, Binance Testnet หรือ Live Order
- Automated tests ใช้ fake transport/mock session เท่านั้นและต้องไม่ใช้ network
- อ้างอิง Binance Spot Kline REST/stream จาก official Spot API docs และ USDⓈ-M Futures base endpoint จาก official Binance Developer docs

---

### Task 1: เพิ่ม Indicator-only Warm-up ให้ Paper Spot Session

**Files:**
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `tests/unit/application/test_paper_spot_session.py`

**Interfaces:**
- Consumes: `Iterable[Candle]`, UTC `received_at`
- Produces: `PaperSpotSession.warm_up_completed_candles(candles, *, received_at) -> None`

- [ ] **Step 1: เขียน failing test ว่า Warm-up ไม่สร้าง trading side effect**

เพิ่ม test ที่สร้างชุด completed candles ซึ่งมีทั้ง RSI reset และ bullish recovery แล้วเรียก Warm-up ทั้งชุด ก่อนส่ง live candle ถัดไป:

```python
def test_warm_up_seeds_indicators_without_creating_trade_side_effects() -> None:
    application = paper_session()
    warm_up = indicator_ready_candles_with_entry_signal()

    application.warm_up_completed_candles(
        warm_up,
        received_at=warm_up[-1].close_time,
    )
    snapshot = application.process_completed_candle(
        next_candle_after(warm_up[-1]),
        received_at=next_candle_after(warm_up[-1]).close_time,
    )

    assert snapshot.entry_fill is None
    assert snapshot.closed_basket_count == 0
    assert snapshot.basket_entry_count == 0
```

- [ ] **Step 2: รัน test เพื่อยืนยันว่า fail เพราะยังไม่มี Warm-up API**

Run:

```bash
.venv/bin/python -m pytest tests/unit/application/test_paper_spot_session.py::test_warm_up_seeds_indicators_without_creating_trade_side_effects -q
```

Expected: FAIL ด้วย `AttributeError: 'PaperSpotSession' object has no attribute 'warm_up_completed_candles'`

- [ ] **Step 3: เพิ่ม minimal Warm-up implementation**

เพิ่ม method ที่ผ่าน continuity เดิมและอัปเดตเฉพาะ Indicator:

```python
def warm_up_completed_candles(
    self,
    candles: Iterable[Candle],
    *,
    received_at: datetime,
) -> None:
    for candle in candles:
        if not self._candles.accept(candle, received_at):
            raise ValueError("warm-up requires new completed candles")
        self._indicators.update(candle)
```

เพิ่ม `from collections.abc import Iterable` และห้ามเรียก `_strategy.evaluate`, `_executor` หรือ `_lifecycle.record_fill` ใน method นี้

- [ ] **Step 4: รัน Paper Spot Session tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/application/test_paper_spot_session.py -q
```

Expected: PASS ทุก test ในไฟล์

- [ ] **Step 5: Commit Task 1**

```bash
git add src/tiewtrade/application/paper_spot_session.py tests/unit/application/test_paper_spot_session.py
git commit -m "feat: add indicator-only candle warm-up"
```

---

### Task 2: Normalize Binance Spot และ Futures Kline Payloads

**Files:**
- Create: `src/tiewtrade/integrations/binance/__init__.py`
- Create: `src/tiewtrade/integrations/binance/kline_parser.py`
- Create: `src/tiewtrade/integrations/binance/public_endpoints.py`
- Create: `tests/unit/integrations/binance/__init__.py`
- Create: `tests/unit/integrations/binance/test_kline_parser.py`
- Create: `tests/unit/integrations/binance/test_public_endpoints.py`

**Interfaces:**
- Consumes: Binance REST kline arrays, WebSocket JSON objects, `MarketDataConfig`, `MarketType`
- Produces: `parse_rest_kline`, `parse_websocket_kline`, `BinancePublicEndpoints.for_market_type`

- [ ] **Step 1: เขียน failing parser และ endpoint-profile tests**

```python
def test_rest_kline_maps_exact_decimal_and_utc_values() -> None:
    candle = parse_rest_kline(
        [1767225600000, "100.10", "102.20", "99.90", "101.30", "12.50"],
        MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
    )
    assert candle.open == Decimal("100.10")
    assert candle.open_time == datetime(2026, 1, 1, tzinfo=UTC)


def test_open_websocket_kline_is_not_emitted() -> None:
    assert parse_websocket_kline(open_kline_payload(), config()) is None


def test_market_type_selects_distinct_public_endpoint_profiles() -> None:
    spot = BinancePublicEndpoints.for_market_type(MarketType.SPOT)
    futures = BinancePublicEndpoints.for_market_type(MarketType.FUTURES)
    assert spot.rest_klines_url != futures.rest_klines_url
    assert spot.websocket_base_url != futures.websocket_base_url
```

เพิ่มกรณี closed WebSocket payload, symbol/timeframe mismatch, malformed array และ invalid decimal ให้ reject ด้วย `BinanceMarketDataPayloadError`
รวมทั้งยืนยันว่า integration boundary ยอมรับเฉพาะ Binance intervals ที่ผลิตภัณฑ์รองรับ
คือ `3m`, `5m`, `15m`, `30m`, `1h`, `4h` และ reject ค่าอย่าง `7m` ก่อนเรียก network

- [ ] **Step 2: รัน tests เพื่อยืนยัน import failure**

Run:

```bash
.venv/bin/python -m pytest tests/unit/integrations/binance/test_kline_parser.py tests/unit/integrations/binance/test_public_endpoints.py -q
```

Expected: FAIL ด้วย `ModuleNotFoundError`

- [ ] **Step 3: เพิ่ม endpoint profiles และ pure parsers**

สร้าง immutable profile:

```python
@dataclass(frozen=True, slots=True)
class BinancePublicEndpoints:
    rest_klines_url: str
    websocket_base_url: str

    @classmethod
    def for_market_type(cls, market_type: MarketType) -> BinancePublicEndpoints:
        if market_type is MarketType.SPOT:
            return cls(
                "https://data-api.binance.vision/api/v3/klines",
                "wss://data-stream.binance.vision/ws",
            )
        return cls(
            "https://fapi.binance.com/fapi/v1/klines",
            "wss://fstream.binance.com/ws",
        )
```

สร้าง parser ที่คืน `None` เฉพาะ WebSocket kline ที่ `k.x is False`; payload ผิดรูปต้อง raise stable domain-specific error และทุกจำนวนต้องสร้างจาก string ด้วย `Decimal`

- [ ] **Step 4: รัน parser/profile tests และ lint เฉพาะไฟล์**

```bash
.venv/bin/python -m pytest tests/unit/integrations/binance/test_kline_parser.py tests/unit/integrations/binance/test_public_endpoints.py -q
.venv/bin/python -m ruff check src/tiewtrade/integrations/binance tests/unit/integrations/binance
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 5: Commit Task 2**

```bash
git add src/tiewtrade/integrations/binance tests/unit/integrations/binance
git commit -m "feat: normalize Binance public klines"
```

---

### Task 3: สร้าง aiohttp Public Candle Source พร้อม REST Pagination

**Files:**
- Modify: `pyproject.toml`
- Create: `src/tiewtrade/integrations/binance/public_market_data.py`
- Create: `tests/unit/integrations/binance/test_public_market_data.py`

**Interfaces:**
- Produces:
  - `BinancePublicMarketData.load_recent(config, *, count, completed_before) -> tuple[Candle, ...]`
  - `BinancePublicMarketData.load_range(config, *, start, end) -> tuple[Candle, ...]`
  - `BinancePublicMarketData.stream_completed(config) -> AsyncIterator[Candle]`
  - `BinancePublicMarketData.close() -> None`

- [ ] **Step 1: เขียน failing tests สำหรับ recent, paginated range และ live closed candles**

ใช้ fake aiohttp session ที่บันทึก URL/params และคืนสอง REST pages:

```python
def test_load_range_paginates_and_returns_ascending_completed_candles() -> None:
    source = source_with_rest_pages([page_1(), page_2()])
    candles = asyncio.run(
        source.load_range(
            config(),
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2026, 1, 5, tzinfo=UTC),
        )
    )
    assert tuple(candle.open_time for candle in candles) == expected_open_times()
    assert source.request_count == 2


def test_stream_completed_ignores_open_updates() -> None:
    candles = asyncio.run(collect(source_with_ws(open_payload(), closed_payload())))
    assert len(candles) == 1
    assert candles[0].open_time == datetime(2026, 1, 1, tzinfo=UTC)
```

เพิ่ม test ว่า HTTP non-2xx, Binance error object, malformed JSON และ source close เป็น idempotent failure/lifecycle behavior

- [ ] **Step 2: รัน tests เพื่อยืนยัน source ยังไม่มี**

```bash
.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py -q
```

Expected: FAIL ด้วย import error

- [ ] **Step 3: เพิ่ม aiohttp dependency**

เพิ่มใน `[project].dependencies`:

```toml
dependencies = [
  "aiohttp>=3.11,<4",
]
```

- [ ] **Step 4: Implement Binance source โดยใช้ selected endpoint profile**

`load_recent` ต้องส่ง `limit=count` พร้อม `endTime` ที่ millisecond สุดท้ายก่อน boundary ของ completed candle ล่าสุด เพื่อให้ response ปกติคืน completed candles ครบ `count` และยังตัด candle ที่ close boundary อยู่หลัง `completed_before`; `load_range` ต้องใช้ completed boundary เดียวกัน, คืนเฉพาะ candle ใน `[start, end)` ที่ `close_time <= end` และเลื่อน `startTime` จาก candle ล่าสุดทีละ `config.interval` จนถึง `end`; WebSocket URL ใช้ `<lowercase-symbol>@kline_<timeframe>` และ `close()` ปิด session เพียงครั้งเดียว

- [ ] **Step 5: รัน source tests, Ruff และ mypy**

```bash
.venv/bin/python -m pytest tests/unit/integrations/binance/test_public_market_data.py -q
.venv/bin/python -m ruff check src/tiewtrade/market_data src/tiewtrade/integrations/binance tests/unit/integrations/binance
.venv/bin/python -m mypy src
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 6: Commit Task 3**

```bash
git add pyproject.toml src/tiewtrade/integrations/binance/public_market_data.py tests/unit/integrations/binance/test_public_market_data.py
git commit -m "feat: add Binance public candle source"
```

---

### Task 4: ส่ง Warm-up และ Live Candle ผ่าน Runtime State Machine

**Files:**
- Create: `src/tiewtrade/market_data/candle_source.py`
- Create: `src/tiewtrade/market_data/runtime_state.py`
- Create: `src/tiewtrade/market_data/runtime.py`
- Create: `tests/unit/market_data/test_runtime.py`

**Interfaces:**
- Produces:
  - `HistoricalCandleSource.load_recent` และ `load_range`
  - `LiveCandleSource.stream_completed`
  - `MarketDataRuntimeState`
  - `MarketDataRuntimeSnapshot`
  - `MarketDataCandleSink.warm_up` และ `process_completed`
  - `MarketDataRuntime.run()` และ `stop()`

- [ ] **Step 1: เขียน failing tests สำหรับ state, Warm-up และ live delivery**

```python
def test_runtime_warms_sink_before_live_delivery() -> None:
    source = FakeSource(recent=warm_up_candles(), live=[next_live_candle()])
    sink = RecordingSink()
    runtime = runtime_for(source, sink)

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert sink.calls == [
        ("warm_up", tuple(warm_up_candles())),
        ("process_completed", next_live_candle()),
    ]
    assert MarketDataRuntimeState.LIVE in runtime.visited_states


async def run_until_sink_receives(
    runtime: MarketDataRuntime,
    sink: RecordingSink,
    *,
    count: int,
) -> None:
    task = asyncio.create_task(runtime.run())
    await sink.wait_for_live_candle_count(count)
    await runtime.stop()
    await task


def test_warm_up_timeout_fails_closed_without_live_delivery() -> None:
    runtime = runtime_for(TimeoutWarmUpSource(), RecordingSink())
    asyncio.run(runtime.run())
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.WARM_UP_TIMEOUT
```

เพิ่มกรณี insufficient candles, malformed batch, sink Warm-up failure และ duplicate live candle

- [ ] **Step 2: รัน tests เพื่อยืนยัน import failure**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime.py -q
```

Expected: FAIL ด้วย import error

- [ ] **Step 3: สร้าง consumer-owned source contracts, immutable state และ scheduler seam**

สร้าง Protocol ใน `market_data` พร้อม Runtime ซึ่งเป็น consumer จริง:

```python
class HistoricalCandleSource(Protocol):
    async def load_recent(
        self,
        config: MarketDataConfig,
        *,
        count: int,
        completed_before: datetime,
    ) -> tuple[Candle, ...]: ...

    async def load_range(
        self,
        config: MarketDataConfig,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]: ...


class LiveCandleSource(Protocol):
    def stream_completed(
        self, config: MarketDataConfig
    ) -> AsyncIterator[Candle]: ...
```

```python
class MarketDataRuntimeState(StrEnum):
    STARTING = "starting"
    WARMING_UP = "warming_up"
    LIVE = "live"
    BACKFILLING = "backfilling"
    STALE = "stale"
    RECONNECTING = "reconnecting"
    FAILED_CLOSED = "failed_closed"
    STOPPED = "stopped"


class MarketDataRuntimeReason(StrEnum):
    START_REQUESTED = "start_requested"
    WARM_UP_COMPLETED = "warm_up_completed"
    WARM_UP_TIMEOUT = "warm_up_timeout"
    LIVE_CANDLE_ACCEPTED = "live_candle_accepted"
    GAP_DETECTED = "gap_detected"
    BACKFILL_COMPLETED = "backfill_completed"
    DATA_STALE = "data_stale"
    SOURCE_DISCONNECTED = "source_disconnected"
    RECONNECT_EXHAUSTED = "reconnect_exhausted"
    SOURCE_ERROR = "source_error"
    SINK_ERROR = "sink_error"
    STOP_REQUESTED = "stop_requested"


@dataclass(frozen=True, slots=True)
class MarketDataRuntimeSnapshot:
    state: MarketDataRuntimeState
    reason: MarketDataRuntimeReason
    transitioned_at: datetime
    last_accepted_open_time: datetime | None
```

Scheduler contract ต้องมี `now()`, `sleep(seconds)` และ generic `wait_for(awaitable, timeout)`; concrete implementation delegate ไป `datetime.now(UTC)`, `asyncio.sleep` และ `asyncio.wait_for`

- [ ] **Step 4: Implement Warm-up และ live happy path**

`run()` ต้อง transition `STARTING -> WARMING_UP`, เรียก `load_recent` ภายใน 30 วินาที, validate ทั้ง batch ด้วย `CompletedCandleStream`, เรียก sink Warm-up ครั้งเดียว แล้ว transition `LIVE` ก่อน consume live iterator ทุก Candle ต้องผ่าน stream เดิมก่อน sink และ duplicate ต้องไม่เรียก sink

- [ ] **Step 5: รัน runtime tests และ quality checks เฉพาะ scope**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime.py tests/unit/market_data/test_completed_candle_stream.py -q
.venv/bin/python -m ruff check src/tiewtrade/market_data tests/unit/market_data
.venv/bin/python -m mypy src
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 6: Commit Task 4**

```bash
git add src/tiewtrade/market_data/candle_source.py src/tiewtrade/market_data/runtime.py src/tiewtrade/market_data/runtime_state.py tests/unit/market_data/test_runtime.py
git commit -m "feat: run public candle warm-up and live flow"
```

---

### Task 5: เพิ่ม Gap Backfill, Stale Deadline และ Bounded Reconnect

**Files:**
- Modify: `src/tiewtrade/market_data/runtime.py`
- Modify: `src/tiewtrade/market_data/runtime_state.py`
- Modify: `tests/unit/market_data/test_runtime.py`

**Interfaces:**
- Consumes: `CandleGapError`, fake scheduler outcomes, `load_range`
- Preserves: Runtime public interfaces จาก Task 4

- [ ] **Step 1: เขียน failing gap/backfill tests**

```python
def test_gap_backfills_in_order_before_resuming_live() -> None:
    source = FakeSource(
        recent=[candle_at(0)],
        live=[candle_at(10)],
        ranges={(candle_at(5).open_time, candle_at(10).open_time): [
            candle_at(5),
            candle_at(10),
        ]},
    )
    sink = RecordingSink()
    runtime = runtime_for(source, sink)
    asyncio.run(run_until_sink_receives(runtime, sink, count=2))
    assert sink.live_candles == [candle_at(5), candle_at(10)]
    assert runtime.visited_states[-2:] == [
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.LIVE,
    ]
```

เพิ่มกรณี empty/still-gapped backfill แล้ว `FAILED_CLOSED`

- [ ] **Step 2: เขียน failing stale/reconnect tests**

```python
def test_reconnect_uses_one_two_four_seconds_then_fails_closed() -> None:
    scheduler = FakeScheduler(disconnects=3)
    runtime = runtime_for(AlwaysDisconnectingSource(), scheduler=scheduler)
    asyncio.run(runtime.run())
    assert scheduler.sleeps == [1.0, 2.0, 4.0]
    assert runtime.snapshot.state is MarketDataRuntimeState.FAILED_CLOSED
    assert runtime.snapshot.reason is MarketDataRuntimeReason.RECONNECT_EXHAUSTED


def test_reconnect_backfills_before_returning_live() -> None:
    sink = RecordingSink()
    runtime = runtime_for(disconnect_then_recover_source(), sink=sink)
    asyncio.run(run_until_sink_receives(runtime, sink, count=1))
    assert states_between(runtime, "disconnect", "next_live") == [
        MarketDataRuntimeState.STALE,
        MarketDataRuntimeState.RECONNECTING,
        MarketDataRuntimeState.BACKFILLING,
        MarketDataRuntimeState.LIVE,
    ]
```

เพิ่มกรณี stale ที่ expected boundary + 30 วินาที, sink failure, idempotent stop และ child-task cleanup

- [ ] **Step 3: รัน new tests เพื่อยืนยัน failure**

```bash
.venv/bin/python -m pytest tests/unit/market_data/test_runtime.py -q
```

Expected: FAIL ที่ gap/reconnect/stale assertions

- [ ] **Step 4: Implement backfill และ bounded reconnect**

เมื่อ stream gap ให้คำนวณ `start = last_open_time + config.interval` และ `end = observed.open_time`; transition `BACKFILLING`; ส่งทุก backfill Candle ผ่าน stream เดิมและ sink ตามลำดับ เมื่อ disconnect/stale ให้ transition `STALE`, แล้วแต่ละ delay transition `RECONNECTING`, เปิด stream ใหม่, backfill ถึง latest closed boundary และกลับ `LIVE` เฉพาะ continuity ผ่าน หากครบสาม attempt ให้ terminal `FAILED_CLOSED`

- [ ] **Step 5: Implement safe stop**

`stop()` ต้องตั้ง stop event, cancel freshness wait, ปิด source หนึ่งครั้ง และ transition `STOPPED`; การเรียกซ้ำต้องไม่เปลี่ยน state หรือปิด sourceซ้ำ

- [ ] **Step 6: รัน runtime regression suite**

```bash
.venv/bin/python -m pytest tests/unit/market_data -q
.venv/bin/python -m ruff check src/tiewtrade/market_data tests/unit/market_data
.venv/bin/python -m mypy src
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 7: Commit Task 5**

```bash
git add src/tiewtrade/market_data/runtime.py src/tiewtrade/market_data/runtime_state.py tests/unit/market_data/test_runtime.py
git commit -m "feat: recover public candle continuity"
```

---

### Task 6: เชื่อม Runtime เข้ากับ Paper Spot Application และ Acceptance Flow

**Files:**
- Create: `src/tiewtrade/application/paper_spot_market_data.py`
- Create: `src/tiewtrade/application/public_market_data_runtime.py`
- Create: `tests/unit/application/test_public_market_data_runtime.py`
- Create: `tests/acceptance/test_public_market_data_runtime.py`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: `PaperSpotSession`, `MarketDataRuntime`, selected Binance endpoint profile
- Produces: `PaperSpotMarketDataSink`, `create_public_market_data_runtime` และ
  verified fake end-to-end flow

- [ ] **Step 1: เขียน failing acceptance test**

```python
def test_fake_public_runtime_warms_then_processes_paper_spot_live_candle() -> None:
    paper_session = configured_paper_spot_session()
    sink = PaperSpotMarketDataSink(paper_session)
    runtime = MarketDataRuntime(
        config=MarketDataConfig(symbol="BTCUSDT", timeframe="5m"),
        warm_up_count=15,
        source=FakePublicCandleSource(warm_up=warm_up_15(), live=[live_candle()]),
        sink=sink,
        scheduler=FakeRuntimeScheduler(),
    )

    asyncio.run(run_until_sink_receives(runtime, sink, count=1))

    assert MarketDataRuntimeState.LIVE in runtime.visited_states
    assert runtime.snapshot.state is MarketDataRuntimeState.STOPPED
    assert sink.last_snapshot is not None
    assert sink.live_candle_count == 1
```

เพิ่ม assertion ว่า fake source ไม่รับ credentials และไม่มี Order transport method

- [ ] **Step 2: รัน acceptance test เพื่อยืนยัน import failure**

```bash
.venv/bin/python -m pytest tests/acceptance/test_public_market_data_runtime.py -q
```

Expected: FAIL ด้วย import error ของ `PaperSpotMarketDataSink`

- [ ] **Step 3: Implement focused application sink**

```python
class PaperSpotMarketDataSink:
    def __init__(self, session: PaperSpotSession) -> None:
        self._session = session
        self.last_snapshot: PaperSpotSessionSnapshot | None = None
        self.live_candle_count = 0

    async def warm_up(
        self, candles: tuple[Candle, ...], *, received_at: datetime
    ) -> None:
        self._session.warm_up_completed_candles(candles, received_at=received_at)

    async def process_completed(
        self, candle: Candle, *, received_at: datetime
    ) -> None:
        self.last_snapshot = self._session.process_completed_candle(
            candle, received_at=received_at
        )
        self.live_candle_count += 1
```

Composition ที่สร้าง real source ต้องเลือก `BinancePublicEndpoints.for_market_type(session.market_type)` ก่อนสร้าง adapter แต่ acceptance test ใช้ fake source เท่านั้น

เพิ่ม composition function ที่ไม่มี business rule:

```python
def create_public_market_data_runtime(
    *,
    session: SessionConfig,
    market_data: MarketDataConfig,
    warm_up_count: int,
    sink: MarketDataCandleSink,
    scheduler: RuntimeScheduler | None = None,
) -> MarketDataRuntime:
    endpoints = BinancePublicEndpoints.for_market_type(session.market_type)
    source = BinancePublicMarketData(endpoints)
    return MarketDataRuntime(
        config=market_data,
        warm_up_count=warm_up_count,
        source=source,
        sink=sink,
        scheduler=scheduler or AsyncioRuntimeScheduler(),
    )
```

เพิ่ม unit assertion ว่า Spot Session เลือก Spot profile และ Futures Session เลือก
USDⓈ-M Futures profile โดย inject source factory เพื่อไม่เปิด network

- [ ] **Step 4: อัปเดต Project Plan status โดยไม่ประกาศ Paper Trading Complete**

เพิ่มสถานะว่า DEV-99 ส่งมอบ public market-data Runtime แล้ว แต่ Paper Futures, Desktop UI และ Recovery ยังอยู่ในลำดับถัดไป

- [ ] **Step 5: รัน acceptance และ integration regression tests**

```bash
.venv/bin/python -m pytest tests/unit/application/test_public_market_data_runtime.py tests/acceptance/test_public_market_data_runtime.py tests/acceptance/test_paper_spot_replay.py tests/acceptance/test_paper_spot_trade_history.py -q
```

Expected: ทุก test PASS

- [ ] **Step 6: Commit Task 6**

```bash
git add src/tiewtrade/application/paper_spot_market_data.py src/tiewtrade/application/public_market_data_runtime.py tests/unit/application/test_public_market_data_runtime.py tests/acceptance/test_public_market_data_runtime.py PROJECT_PLAN.md
git commit -m "feat: compose public market data with Paper Spot"
```

---

### Task 7: รัน Full Verification และเตรียม DEV-99 Review

**Files:**
- Verify only; แก้เฉพาะ defect ที่ tests หรือ quality gates ของ DEV-99 เปิดเผย

**Interfaces:**
- Produces: หลักฐานว่า DEV-99 ผ่าน acceptance criteria โดยไม่ใช้ credentials/network

- [ ] **Step 1: รัน Python tests ทั้ง repository**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS ทั้งหมด, 0 failed

- [ ] **Step 2: รัน Ruff, format และ mypy**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 3: รัน docs-site gates เพราะ Project Plan เป็น Source of Truth**

```bash
npm --prefix docs-site test
npm --prefix docs-site run check:content
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 4: ตรวจ diff hygiene และ secrets**

```bash
git diff --check main...HEAD
git grep -n -E "api[_-]?key|secret" -- src tests
git status --short
```

Expected: `git diff --check` ไม่มี output; grep ไม่มี credential literal; status มีเพียงไฟล์ผู้ใช้ที่ไม่เกี่ยวข้อง เช่น `.mcp.json`

- [ ] **Step 5: ตรวจ commit history และสรุปความเสี่ยงคงเหลือ**

```bash
git log --oneline main..HEAD
git diff --stat main...HEAD
```

Expected: มี design commits และ Task commits ของ DEV-99 เท่านั้น; ยังไม่มี push หรือ merge จนกว่าผู้ใช้ยืนยันแยกกัน
