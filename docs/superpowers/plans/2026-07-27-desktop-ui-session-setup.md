# Desktop UI Session Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ส่งมอบ PySide6 Desktop vertical slice ที่สร้างและกู้คืน immutable Active Paper Session สำหรับ Spot หรือ Futures จาก Session Setup ได้โดยไม่เริ่ม Market Data หรือ Trading Runtime

**Architecture:** ใช้ Thin Qt UI เรียก focused application use case ผ่าน worker นอก UI thread Application สร้าง shared domain configuration และส่งให้ concrete SQLite adapter บันทึกแบบ atomic ก่อนคืน durable snapshot ให้ UI โดย UI ไม่ import SQLite, Strategy หรือ Execution

**Tech Stack:** Python 3.12+, PySide6 6.10–6.x, pytest 8–9, pytest-qt 4.5–4.x, SQLite, Ruff, Mypy strict

## Global Constraints

- UI copy เป็นภาษาอังกฤษและใช้ light theme โทน neutral/blue
- แสดงเฉพาะ Paper Mode; ไม่มี Live control, API Key หรือ Binance Private API
- รองรับ Market Type `SPOT` และ `FUTURES` โดยใช้ business policies ชุดปัจจุบัน
- Symbol เป็น `BTCUSDT`; Timeframe เลือกได้จาก `3m`, `5m`, `15m`, `30m`, `1h`, `4h`
- `max_entries` เป็นเลขคู่ 2–20; ค่าเริ่มต้นใน form คือ 10
- Spot Trading Capital Ratio มากกว่า 0 และน้อยกว่า 100%; ค่าเริ่มต้นใน form คือ 80%
- Futures ใช้ One-way Mode, Cross Margin, Trading Capital 50%, Collateral Buffer 50% และ leverage จำนวนเต็ม 1x–5x
- Trading Fee ตั้งแต่ 0 และน้อยกว่า 100%; Slippage ตั้งแต่ 0 และน้อยกว่า 10,000 bps
- ค่าจาก form ต้องกลายเป็น immutable Session configuration ก่อนบันทึก
- มี Active Bot Session ที่ `ended_at_utc IS NULL` ได้สูงสุดหนึ่ง record
- Create Session ไม่เริ่ม Market Data, Strategy หรือ Execution
- SQLite หรือ validation failure ห้ามทิ้ง partial durable state หรือ in-memory success
- ไม่มี generic ViewModel, repository interface, navigation registry หรือ placeholder page
- Tests ต้องใช้ temporary SQLite, `QT_QPA_PLATFORM=offscreen` และไม่มี network

---

## File Map

### Files to create

- `src/tiewtrade/application/paper_session_setup.py` — typed form values, validation error, durable Session snapshot และ Create Paper Session use case
- `src/tiewtrade/integrations/sqlite/active_paper_sessions.py` — atomic create/read mapping และ single-active enforcement
- `src/tiewtrade/ui/__init__.py` — UI package marker
- `src/tiewtrade/ui/session_setup.py` — Paper Session Setup form และ conditional Spot/Futures fields
- `src/tiewtrade/ui/session_overview.py` — read-only durable Session summary
- `src/tiewtrade/ui/session_tasks.py` — focused `QRunnable` workers และ signals สำหรับ create/load
- `src/tiewtrade/ui/main_window.py` — Main Window, navigation และ UI state transitions
- `src/tiewtrade/ui/theme.py` — light neutral/blue stylesheet ที่ใช้จริงโดย Main Window
- `src/tiewtrade/ui/desktop.py` — composition root และ `run_desktop()`
- `src/tiewtrade/desktop_main.py` — executable module entry point
- `tests/unit/application/test_paper_session_setup.py` — application request and policy tests
- `tests/unit/integrations/sqlite/test_active_paper_sessions.py` — migration, atomicity, restart และ concurrency tests
- `tests/unit/ui/test_session_setup.py` — form, conditional fields และ validation tests
- `tests/unit/ui/test_main_window.py` — loading, success, duplicate และ unavailable states
- `tests/acceptance/test_desktop_session_setup.py` — create/restart Desktop flow
- `tests/support/paper_session_setup.py` — deterministic configured Spot/Futures Session builders ที่ tests ใช้ร่วมกัน

### Files to modify

- `pyproject.toml` — เพิ่ม PySide6, pytest-qt และบังคับ pytest-qt ใช้ PySide6
- `PRODUCT.md` — บันทึก fee-rate upper bound และ Create-vs-Start UI semantics
- `ARCHITECTURE.md` — ระบุ PySide6 Thin UI dependency boundary
- `PROJECT_PLAN.md` — บันทึก Desktop UI Session Setup prerequisite ของ DEV-96
- `src/tiewtrade/trading/session_config.py` — บังคับ `fee_rate < 1`
- `src/tiewtrade/integrations/sqlite/database.py` — schema version 3 และ Bot Session table/index
- `tests/unit/trading/test_session_config.py` — fee upper-bound regression

---

### Task 1: สร้างและบันทึก Active Paper Session แบบ Atomic

**Files:**
- Create: `src/tiewtrade/application/paper_session_setup.py`
- Create: `src/tiewtrade/integrations/sqlite/active_paper_sessions.py`
- Create: `tests/unit/application/test_paper_session_setup.py`
- Create: `tests/unit/integrations/sqlite/test_active_paper_sessions.py`
- Create: `tests/support/paper_session_setup.py`
- Modify: `src/tiewtrade/trading/session_config.py`
- Modify: `src/tiewtrade/integrations/sqlite/database.py`
- Modify: `tests/unit/trading/test_session_config.py`
- Modify: `PRODUCT.md`
- Modify: `ARCHITECTURE.md`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Produces: `PaperSessionSetupValues`, `ConfiguredPaperSession`, `PaperSessionCreateOutcome`, `PaperSessionValidationError`, `PaperSessionUnavailableError`, `CreatePaperSession.execute()` และ `SQLiteActivePaperSessions.create()/get_active()`
- Consumes: `SessionConfig`, `MarketDataConfig`, `EntryPolicy`, `SpotTradingPolicy`, `FuturesTradingPolicy.v1()` และ `SQLiteDatabase`

- [ ] **Step 1: เพิ่ม failing fee validation test**

เพิ่มใน `tests/unit/trading/test_session_config.py`:

```python
def test_session_config_rejects_fee_rate_at_or_above_one() -> None:
    with pytest.raises(ValueError, match="fee_rate must be below 1"):
        make_config(fee_rate=Decimal("1"))
```

- [ ] **Step 2: รัน test และยืนยันว่า fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_session_config.py::test_session_config_rejects_fee_rate_at_or_above_one -v
```

Expected: FAIL เพราะ `SessionConfig` ยังยอมรับ `fee_rate == 1`

- [ ] **Step 3: บังคับ fee-rate boundary ใน shared configuration**

แก้ `SessionConfig.__post_init__()`:

```python
if self.fee_rate < 0:
    raise ValueError("fee_rate must not be negative")
if self.fee_rate >= 1:
    raise ValueError("fee_rate must be below 1")
```

แก้ `PRODUCT.md` ให้ระบุ Trading Fee Rate ตั้งแต่ 0 และน้อยกว่า 1 และแก้
`ARCHITECTURE.md`/`PROJECT_PLAN.md` ให้บันทึก Thin PySide6 UI boundary กับลำดับ Desktop
Session Setup ก่อน DEV-96

- [ ] **Step 4: เขียน failing application tests**

สร้าง `tests/unit/application/test_paper_session_setup.py` ด้วย tests ต่อไปนี้:

```python
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    CreatePaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
    PaperSessionValidationError,
)
from tiewtrade.trading.session_config import MarketType, TradeMode

SESSION_ID = UUID("00000000-0000-0000-0000-000000000123")
CREATED_AT = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def spot_values() -> PaperSessionSetupValues:
    return PaperSessionSetupValues(
        market_type="spot",
        symbol="BTCUSDT",
        timeframe="5m",
        available_capital="200000",
        max_entries="10",
        fee_percent="0.1",
        slippage_bps="5",
        spot_trading_capital_percent="80",
        futures_leverage=None,
    )


def test_create_spot_session_builds_immutable_configuration() -> None:
    recorded: list[ConfiguredPaperSession] = []

    def create_active(session: ConfiguredPaperSession) -> PaperSessionCreateOutcome:
        recorded.append(session)
        return PaperSessionCreateOutcome(session=session, created=True)

    use_case = CreatePaperSession(
        create_active=create_active,
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    outcome = use_case.execute(spot_values())

    assert outcome.created is True
    assert outcome.session.config.session_id == SESSION_ID
    assert outcome.session.config.trade_mode is TradeMode.PAPER
    assert outcome.session.config.market_type is MarketType.SPOT
    assert outcome.session.market_data.symbol == "BTCUSDT"
    assert outcome.session.market_data.timeframe == "5m"
    assert outcome.session.config.fee_rate == Decimal("0.001")
    assert outcome.session.config.spot_policy is not None
    assert outcome.session.config.spot_policy.trading_capital_ratio == Decimal("0.8")
    assert outcome.session.created_at_utc == CREATED_AT
    assert recorded == [outcome.session]


@pytest.mark.parametrize(
    ("field", "value"),
    [("available_capital", "0"), ("max_entries", "3"), ("fee_percent", "100")],
)
def test_invalid_input_reports_the_exact_field(field: str, value: str) -> None:
    values = replace(spot_values(), **{field: value})
    use_case = CreatePaperSession(
        create_active=lambda session: pytest.fail("must not persist"),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    with pytest.raises(PaperSessionValidationError) as caught:
        use_case.execute(values)

    assert caught.value.field == field
```

เพิ่ม Futures case แบบเจาะจง:

```python
def test_create_futures_session_builds_v1_policy() -> None:
    values = replace(
        spot_values(),
        market_type="futures",
        spot_trading_capital_percent=None,
        futures_leverage="3",
    )
    use_case = CreatePaperSession(
        create_active=lambda session: PaperSessionCreateOutcome(session, True),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    outcome = use_case.execute(values)

    policy = outcome.session.config.futures_policy
    assert outcome.session.config.market_type is MarketType.FUTURES
    assert outcome.session.config.spot_policy is None
    assert policy is not None
    assert policy.leverage == 3
    assert policy.margin_mode.value == "cross"
    assert policy.position_mode.value == "one_way"
```

สร้าง `tests/support/paper_session_setup.py` ด้วย `configured_spot_session()` และ
`configured_futures_session(leverage: int = 3)` โดยเรียก `CreatePaperSession` ด้วย
`SESSION_ID`, `CREATED_AT` และ identity `create_active` callable เดียวกัน เพื่อให้ทุก
SQLite/UI/acceptance test ใช้ fixture ที่ผ่าน application validation ชุดเดียวกัน

```python
SESSION_ID = UUID("00000000-0000-0000-0000-000000000123")
CREATED_AT = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)


def _configured(values: PaperSessionSetupValues) -> ConfiguredPaperSession:
    use_case = CreatePaperSession(
        create_active=lambda session: PaperSessionCreateOutcome(session, True),
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )
    return use_case.execute(values).session


def configured_spot_session() -> ConfiguredPaperSession:
    return _configured(
        PaperSessionSetupValues(
            market_type="spot",
            symbol="BTCUSDT",
            timeframe="5m",
            available_capital="200000",
            max_entries="10",
            fee_percent="0.1",
            slippage_bps="5",
            spot_trading_capital_percent="80",
            futures_leverage=None,
        )
    )


def configured_futures_session(leverage: int = 3) -> ConfiguredPaperSession:
    return _configured(
        PaperSessionSetupValues(
            market_type="futures",
            symbol="BTCUSDT",
            timeframe="5m",
            available_capital="200000",
            max_entries="10",
            fee_percent="0.1",
            slippage_bps="5",
            spot_trading_capital_percent=None,
            futures_leverage=str(leverage),
        )
    )
```

- [ ] **Step 5: รัน application tests และยืนยันว่า fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/application/test_paper_session_setup.py -v
```

Expected: collection FAIL เพราะ module ยังไม่มี

- [ ] **Step 6: เขียน minimal application use case**

สร้าง `src/tiewtrade/application/paper_session_setup.py` ด้วย public contract ต่อไปนี้:

```python
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TypeVar
from uuid import UUID, uuid4

from tiewtrade.market_data.config import MarketDataConfig
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.trading.entry_policy import EntryPolicy
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.session_config import MarketType, SessionConfig, TradeMode
from tiewtrade.trading.spot_policy import SpotTradingPolicy


@dataclass(frozen=True, slots=True)
class PaperSessionSetupValues:
    market_type: str
    symbol: str
    timeframe: str
    available_capital: str
    max_entries: str
    fee_percent: str
    slippage_bps: str
    spot_trading_capital_percent: str | None
    futures_leverage: str | None


@dataclass(frozen=True, slots=True)
class ConfiguredPaperSession:
    config: SessionConfig
    market_data: MarketDataConfig
    created_at_utc: datetime
    ended_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at_utc.tzinfo is None or self.created_at_utc.utcoffset() != timedelta(0):
            raise ValueError("created_at_utc must use UTC")
        if self.ended_at_utc is not None:
            raise ValueError("new Paper Session must be active")


@dataclass(frozen=True, slots=True)
class PaperSessionCreateOutcome:
    session: ConfiguredPaperSession
    created: bool


class PaperSessionValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


class PaperSessionUnavailableError(RuntimeError):
    pass


CreateActiveSession = Callable[[ConfiguredPaperSession], PaperSessionCreateOutcome]


class CreatePaperSession:
    def __init__(
        self,
        *,
        create_active: CreateActiveSession,
        session_ids: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._create_active = create_active
        self._session_ids = session_ids
        self._clock = clock

    def execute(self, values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        market_type = _market_type(values.market_type)
        available_capital = _decimal(values.available_capital, "available_capital")
        max_entries = _integer(values.max_entries, "max_entries")
        fee_percent = _decimal(values.fee_percent, "fee_percent")
        slippage_bps = _decimal(values.slippage_bps, "slippage_bps")
        if values.symbol != "BTCUSDT":
            raise PaperSessionValidationError("symbol", "Symbol must be BTCUSDT")
        if available_capital <= 0:
            raise PaperSessionValidationError(
                "available_capital", "Available Capital must be positive"
            )
        if not Decimal("0") <= fee_percent < Decimal("100"):
            raise PaperSessionValidationError("fee_percent", "Trading Fee must be below 100%")
        if not Decimal("0") <= slippage_bps < Decimal("10000"):
            raise PaperSessionValidationError(
                "slippage_bps", "Slippage must be below 10,000 bps"
            )

        spot_policy: SpotTradingPolicy | None = None
        futures_policy: FuturesTradingPolicy | None = None
        if market_type is MarketType.SPOT:
            ratio = _decimal(
                _required(values.spot_trading_capital_percent, "spot_trading_capital_percent"),
                "spot_trading_capital_percent",
            ) / Decimal("100")
            spot_policy = _field("spot_trading_capital_percent", lambda: SpotTradingPolicy(ratio))
        else:
            leverage = _integer(
                _required(values.futures_leverage, "futures_leverage"),
                "futures_leverage",
            )
            futures_policy = _field("futures_leverage", lambda: FuturesTradingPolicy.v1(leverage))

        preset = RsiStepGridPreset.v1()
        entry_policy = _field("max_entries", lambda: EntryPolicy(max_entries))
        market_data = _field(
            "timeframe",
            lambda: MarketDataConfig(symbol=values.symbol, timeframe=values.timeframe),
        )
        config = _field(
            "available_capital",
            lambda: SessionConfig(
                session_id=self._session_ids(),
                preset_version=preset.version,
                market_type=market_type,
                trade_mode=TradeMode.PAPER,
                available_capital=available_capital,
                fee_rate=fee_percent / Decimal("100"),
                slippage_bps=slippage_bps,
                entry_policy=entry_policy,
                spot_policy=spot_policy,
                futures_policy=futures_policy,
            ),
        )
        session = ConfiguredPaperSession(
            config=config,
            market_data=market_data,
            created_at_utc=self._clock(),
        )
        return self._create_active(session)
```

เพิ่ม private parsing helpers ต่อไปนี้ โดยไม่จับ `PaperSessionUnavailableError`:

```python
Parsed = TypeVar("Parsed")


def _required(value: str | None, field: str) -> str:
    if value is None or not value.strip():
        raise PaperSessionValidationError(field, "This field is required")
    return value


def _decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(_required(value, field))
    except InvalidOperation as error:
        raise PaperSessionValidationError(field, "Enter a valid number") from error


def _integer(value: str, field: str) -> int:
    try:
        return int(_required(value, field))
    except ValueError as error:
        raise PaperSessionValidationError(field, "Enter a whole number") from error


def _market_type(value: str) -> MarketType:
    try:
        return MarketType(value)
    except ValueError as error:
        raise PaperSessionValidationError(
            "market_type", "Select Spot or Futures"
        ) from error


def _field(field: str, factory: Callable[[], Parsed]) -> Parsed:
    try:
        return factory()
    except ValueError as error:
        raise PaperSessionValidationError(field, str(error)) from error
```

- [ ] **Step 7: เขียน failing SQLite migration/round-trip tests**

สร้าง `tests/unit/integrations/sqlite/test_active_paper_sessions.py` ให้พิสูจน์:

```python
def test_create_and_restart_round_trip_exact_spot_session(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    session = configured_spot_session()

    first = store.create(session)
    restarted = SQLiteActivePaperSessions(database).get_active()

    assert first == PaperSessionCreateOutcome(session=session, created=True)
    assert restarted == session


def test_second_active_session_returns_existing_record(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    existing = configured_spot_session()
    store.create(existing)

    outcome = store.create(configured_futures_session())

    assert outcome == PaperSessionCreateOutcome(session=existing, created=False)
```

เพิ่ม schema-v2 migration preservation, Futures exact round-trip, injected commit failure
rollback และสอง thread concurrent create ที่ยืนยันว่ามี Active record เดียว

- [ ] **Step 8: เพิ่ม schema version 3**

แก้ `SQLiteDatabase._SCHEMA_VERSION = 3` และเพิ่ม migration ที่สร้าง `bot_sessions` กับ
partial unique index:

```python
with connection:
    if version == 0:
        _create_schema(connection)
    elif version == 1:
        connection.execute(
            """
            ALTER TABLE basket_results
            ADD COLUMN leverage INTEGER
            CHECK (leverage IS NULL OR leverage BETWEEN 1 AND 5)
            """
        )
    if version in {0, 1, 2}:
        _create_bot_sessions_schema(connection)
    connection.execute("PRAGMA user_version = 3")
```

```sql
CREATE TABLE IF NOT EXISTS bot_sessions (
    session_id TEXT PRIMARY KEY,
    trade_mode TEXT NOT NULL CHECK (trade_mode = 'paper'),
    market_type TEXT NOT NULL CHECK (market_type IN ('spot', 'futures')),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    preset_version TEXT NOT NULL,
    available_capital TEXT NOT NULL,
    max_entries INTEGER NOT NULL CHECK (max_entries BETWEEN 2 AND 20 AND max_entries % 2 = 0),
    fee_rate TEXT NOT NULL,
    slippage_bps TEXT NOT NULL,
    spot_trading_capital_ratio TEXT,
    futures_policy_version TEXT,
    futures_leverage INTEGER,
    futures_trading_capital_ratio TEXT,
    futures_collateral_buffer_ratio TEXT,
    futures_maintenance_margin_rate TEXT,
    futures_margin_mode TEXT,
    futures_position_mode TEXT,
    created_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    CHECK (
        (market_type = 'spot' AND spot_trading_capital_ratio IS NOT NULL AND futures_policy_version IS NULL)
        OR
        (market_type = 'futures' AND spot_trading_capital_ratio IS NULL AND futures_policy_version IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS bot_sessions_single_active_idx
ON bot_sessions ((1))
WHERE ended_at_utc IS NULL;
```

- [ ] **Step 9: เขียน concrete SQLite store**

สร้าง `SQLiteActivePaperSessions` ที่:

```python
INSERT_SQL = """
INSERT INTO bot_sessions (
    session_id, trade_mode, market_type, symbol, timeframe, preset_version,
    available_capital, max_entries, fee_rate, slippage_bps,
    spot_trading_capital_ratio, futures_policy_version, futures_leverage,
    futures_trading_capital_ratio, futures_collateral_buffer_ratio,
    futures_maintenance_margin_rate, futures_margin_mode,
    futures_position_mode, created_at_utc, ended_at_utc
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class SQLiteActivePaperSessions:
    def __init__(self, database: SQLiteDatabase) -> None:
        self._database = database

    def create(self, session: ConfiguredPaperSession) -> PaperSessionCreateOutcome:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            connection.execute("BEGIN IMMEDIATE")
            existing = _find_active(connection)
            if existing is not None:
                connection.commit()
                return PaperSessionCreateOutcome(session=existing, created=False)
            connection.execute(INSERT_SQL, _session_values(session))
            connection.commit()
            return PaperSessionCreateOutcome(session=session, created=True)
        except sqlite3.Error as error:
            _rollback_if_open(connection)
            raise PaperSessionUnavailableError("Active Paper Session write failed") from error
        except BaseException:
            _rollback_if_open(connection)
            raise
        finally:
            _close_if_open(connection)

    def get_active(self) -> ConfiguredPaperSession | None:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._database.connect()
            row = connection.execute(
                "SELECT * FROM bot_sessions WHERE ended_at_utc IS NULL"
            ).fetchone()
            result = None if row is None else _session_from_row(row)
        except sqlite3.Error as error:
            raise PaperSessionUnavailableError(
                "Active Paper Session read failed"
            ) from error
        finally:
            _close_if_open(connection)
        return result
```

ใช้ `_session_from_row()` ที่สร้าง domain objects กลับจากค่าจริง:

```python
def _session_from_row(row: sqlite3.Row) -> ConfiguredPaperSession:
    market_type = MarketType(row["market_type"])
    spot_policy = (
        SpotTradingPolicy(Decimal(row["spot_trading_capital_ratio"]))
        if market_type is MarketType.SPOT
        else None
    )
    futures_policy = (
        FuturesTradingPolicy(
            version=row["futures_policy_version"],
            leverage=row["futures_leverage"],
            trading_capital_ratio=Decimal(row["futures_trading_capital_ratio"]),
            collateral_buffer_ratio=Decimal(row["futures_collateral_buffer_ratio"]),
            maintenance_margin_rate=Decimal(row["futures_maintenance_margin_rate"]),
            margin_mode=MarginMode(row["futures_margin_mode"]),
            position_mode=PositionMode(row["futures_position_mode"]),
        )
        if market_type is MarketType.FUTURES
        else None
    )
    config = SessionConfig(
        session_id=UUID(row["session_id"]),
        preset_version=row["preset_version"],
        market_type=market_type,
        trade_mode=TradeMode(row["trade_mode"]),
        available_capital=Decimal(row["available_capital"]),
        fee_rate=Decimal(row["fee_rate"]),
        slippage_bps=Decimal(row["slippage_bps"]),
        entry_policy=EntryPolicy(row["max_entries"]),
        spot_policy=spot_policy,
        futures_policy=futures_policy,
    )
    return ConfiguredPaperSession(
        config=config,
        market_data=MarketDataConfig(
            symbol=row["symbol"],
            timeframe=row["timeframe"],
        ),
        created_at_utc=datetime.fromisoformat(row["created_at_utc"]),
    )


def _find_active(
    connection: sqlite3.Connection,
) -> ConfiguredPaperSession | None:
    row = connection.execute(
        "SELECT * FROM bot_sessions WHERE ended_at_utc IS NULL"
    ).fetchone()
    return None if row is None else _session_from_row(row)


def _session_values(session: ConfiguredPaperSession) -> tuple[object, ...]:
    config = session.config
    spot = config.spot_policy
    futures = config.futures_policy
    return (
        str(config.session_id),
        config.trade_mode.value,
        config.market_type.value,
        session.market_data.symbol,
        session.market_data.timeframe,
        config.preset_version,
        str(config.available_capital),
        config.entry_policy.max_entries,
        str(config.fee_rate),
        str(config.slippage_bps),
        None if spot is None else str(spot.trading_capital_ratio),
        None if futures is None else futures.version,
        None if futures is None else futures.leverage,
        None if futures is None else str(futures.trading_capital_ratio),
        None if futures is None else str(futures.collateral_buffer_ratio),
        None if futures is None else str(futures.maintenance_margin_rate),
        None if futures is None else futures.margin_mode.value,
        None if futures is None else futures.position_mode.value,
        session.created_at_utc.isoformat(),
        None,
    )


def _rollback_if_open(connection: sqlite3.Connection | None) -> None:
    if connection is not None:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass


def _close_if_open(connection: sqlite3.Connection | None) -> None:
    if connection is not None:
        try:
            connection.close()
        except sqlite3.Error:
            pass
```

- [ ] **Step 10: รัน Task 1 tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_session_config.py tests/unit/application/test_paper_session_setup.py tests/unit/integrations/sqlite/test_active_paper_sessions.py -v
```

Expected: PASS

- [ ] **Step 11: รัน static checks และ commit**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add PRODUCT.md ARCHITECTURE.md PROJECT_PLAN.md src/tiewtrade/application/paper_session_setup.py src/tiewtrade/integrations/sqlite/active_paper_sessions.py src/tiewtrade/integrations/sqlite/database.py src/tiewtrade/trading/session_config.py tests/unit/application/test_paper_session_setup.py tests/unit/integrations/sqlite/test_active_paper_sessions.py tests/unit/trading/test_session_config.py
git commit -m "feat: persist configured Paper sessions"
```

---

### Task 2: เปิด Desktop และสร้าง Paper Spot Session

**Files:**
- Create: `src/tiewtrade/ui/__init__.py`
- Create: `src/tiewtrade/ui/session_setup.py`
- Create: `src/tiewtrade/ui/session_overview.py`
- Create: `src/tiewtrade/ui/session_tasks.py`
- Create: `src/tiewtrade/ui/main_window.py`
- Create: `src/tiewtrade/ui/theme.py`
- Create: `src/tiewtrade/ui/desktop.py`
- Create: `src/tiewtrade/desktop_main.py`
- Create: `tests/unit/ui/test_session_setup.py`
- Create: `tests/unit/ui/test_main_window.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `CreatePaperSession.execute(PaperSessionSetupValues) -> PaperSessionCreateOutcome`
- Produces: `SessionSetupWidget.values()`, `SessionOverviewWidget.show_session()`, `MainWindow` และ `run_desktop()`

- [ ] **Step 1: เพิ่ม PySide6 test dependencies**

แก้ `pyproject.toml`:

```toml
dependencies = [
  "aiohttp>=3.11,<4",
  "PySide6>=6.10,<7",
]

[project.optional-dependencies]
dev = [
  "mypy>=1.14,<2",
  "pytest>=8,<10",
  "pytest-qt>=4.5,<5",
  "ruff>=0.9,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--import-mode=importlib"]
qt_api = "pyside6"
```

ติดตั้ง dependency และยืนยัน import:

```bash
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -c "import PySide6; print(PySide6.__version__)"
```

Expected: installation exit 0 และพิมพ์ PySide6 version ในช่วง `6.10–6.x`

- [ ] **Step 2: เขียน failing Spot form tests**

ตั้ง `QT_QPA_PLATFORM=offscreen` ก่อน import PySide6 ใน test environment แล้วสร้าง
`tests/unit/ui/test_session_setup.py`:

```python
from PySide6.QtCore import Qt

from tiewtrade.ui.session_setup import SessionSetupWidget


def test_default_form_builds_paper_spot_values(qtbot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    values = widget.values()

    assert values.market_type == "spot"
    assert values.symbol == "BTCUSDT"
    assert values.timeframe == "5m"
    assert values.max_entries == "10"
    assert values.spot_trading_capital_percent == "80"
    assert values.futures_leverage is None
    assert widget.trade_mode_label.text() == "Paper"
    assert widget.symbol_field.isReadOnly()


def test_submit_emits_current_values_once(qtbot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.create_requested) as signal:
        qtbot.mouseClick(widget.create_button, Qt.MouseButton.LeftButton)

    assert signal.args == [widget.values()]
```

- [ ] **Step 3: รัน UI tests และยืนยันว่า fail**

Run:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/ui/test_session_setup.py -v
```

Expected: collection FAIL เพราะ `tiewtrade.ui` ยังไม่มี

- [ ] **Step 4: สร้าง focused Spot Session Setup widget**

สร้าง `SessionSetupWidget(QWidget)` ที่มี public attributes ตาม tests และ contract:

```python
class SessionSetupWidget(QWidget):
    create_requested = Signal(object)

    def values(self) -> PaperSessionSetupValues:
        return PaperSessionSetupValues(
            market_type=self.market_type.currentData(),
            symbol=self.symbol_field.text(),
            timeframe=self.timeframe.currentData(),
            available_capital=self.available_capital.text(),
            max_entries=str(self.max_entries.value()),
            fee_percent=self.fee_percent.text(),
            slippage_bps=self.slippage_bps.text(),
            spot_trading_capital_percent=self.spot_ratio.text(),
            futures_leverage=None,
        )

    @Slot()
    def _submit(self) -> None:
        if self.create_button.isEnabled():
            self.create_requested.emit(self.values())

    def set_loading(self, loading: bool) -> None:
        self.create_button.setDisabled(loading)
        self.create_button.setText("Creating…" if loading else "Create Paper Session")

    def show_field_error(self, field: str, message: str) -> None:
        self._field_errors[field].setText(message)
```

ใช้ `QFormLayout`, object names ที่เสถียรสำหรับ tests, read-only Paper/BTCUSDT/Preset
labels และ Advanced Settings ที่เปิดดูได้จริง ห้ามสร้าง placeholder pages

- [ ] **Step 5: เขียน failing Main Window success test**

สร้าง `tests/unit/ui/test_main_window.py`:

```python
def test_created_spot_session_replaces_form_with_durable_overview(qtbot) -> None:
    created = configured_spot_session()
    window = MainWindow(create_session=lambda values: PaperSessionCreateOutcome(created, True))
    qtbot.addWidget(window)
    window.show()

    qtbot.mouseClick(window.setup.create_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")
    assert window.current_page_name == "Session Overview"
    assert window.overview.state_value.text() == "Configured — Market Data Not Started"
    assert window.overview.market_value.text() == "Spot"
    assert window.overview.session_id_value.text() == str(created.config.session_id)
```

Test double click ต้องยืนยันว่า create callable ถูกเรียกเพียงครั้งเดียวขณะ loading

- [ ] **Step 6: สร้าง Overview, Main Window, theme และ entry point**

`SessionOverviewWidget.show_session(session)` ต้อง render durable snapshot โดยใช้ Decimal
จาก domain object ไม่สร้างค่าศูนย์ปลอม

สร้าง `SessionTask` และ `SessionTaskSignals` ใน `session_tasks.py`:

```python
class SessionTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()


class SessionTask(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation
        self.signals = SessionTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:
            self.signals.failed.emit(error)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
```

`MainWindow` ต้องประกอบ navigation ที่มี destination `Session`, setup/overview stack,
ส่ง create operation เข้า `QThreadPool` ผ่าน `SessionTask` และสลับ state จาก setup ไป
overview เฉพาะหลัง create result สำเร็จ โดยเก็บ task ไว้ใน `self._tasks` จนสัญญาณ
`finished` เพื่อตัดปัญหา worker/signals ถูก garbage collected ระหว่างทำงาน

`run_desktop()` ต้อง:

```python
def run_desktop(database_path: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    database = SQLiteDatabase(database_path or default_database_path())
    store = SQLiteActivePaperSessions(database)
    create_session = CreatePaperSession(create_active=store.create)

    def create_after_migration(
        values: PaperSessionSetupValues,
    ) -> PaperSessionCreateOutcome:
        database.migrate()
        return create_session.execute(values)

    window = MainWindow(create_session=create_after_migration)
    window.setStyleSheet(LIGHT_THEME)
    window.show()
    return app.exec()


def default_database_path() -> Path:
    directory = Path.home() / "Library" / "Application Support" / "TiewTrade"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "tiewtrade.sqlite3"
```

`desktop_main.py` เรียก `raise SystemExit(run_desktop())` ภายใต้ `if __name__ == "__main__"`

- [ ] **Step 7: รัน UI tests และ smoke import**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/ui/test_session_setup.py tests/unit/ui/test_main_window.py -v
.venv/bin/python -c "from tiewtrade.ui.desktop import run_desktop"
```

Expected: PASS และ import exit code 0

- [ ] **Step 8: รัน checks และ commit**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add pyproject.toml src/tiewtrade/ui src/tiewtrade/desktop_main.py tests/unit/ui
git commit -m "feat: create Paper Spot sessions from Desktop"
```

---

### Task 3: เพิ่ม Paper Futures Session Setup และ Policy Summary

**Files:**
- Modify: `src/tiewtrade/ui/session_setup.py`
- Modify: `src/tiewtrade/ui/session_overview.py`
- Modify: `tests/unit/ui/test_session_setup.py`
- Modify: `tests/unit/ui/test_main_window.py`

**Interfaces:**
- Consumes: `PaperSessionSetupValues.futures_leverage`, `FuturesTradingPolicy.v1()` และ `ConfiguredPaperSession`
- Produces: conditional Futures form กับ exact read-only policy summary

- [ ] **Step 1: เขียน failing Futures conditional-field tests**

```python
def test_futures_selection_shows_futures_policy_and_hides_spot_ratio(qtbot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    widget.market_type.setCurrentIndex(widget.market_type.findData("futures"))

    assert widget.spot_fields.isHidden()
    assert not widget.futures_fields.isHidden()
    assert widget.margin_mode_value.text() == "Cross Margin"
    assert widget.position_mode_value.text() == "One-way Mode"
    assert widget.trading_capital_value.text() == "50%"
    assert widget.collateral_buffer_value.text() == "50%"
    assert widget.values().spot_trading_capital_percent is None
    assert widget.values().futures_leverage == "1"


def test_switching_back_to_spot_removes_futures_input_from_request(qtbot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)
    widget.market_type.setCurrentIndex(widget.market_type.findData("futures"))
    widget.leverage.setValue(5)

    widget.market_type.setCurrentIndex(widget.market_type.findData("spot"))

    values = widget.values()
    assert values.market_type == "spot"
    assert values.futures_leverage is None
    assert values.spot_trading_capital_percent == widget.spot_ratio.text()
```

- [ ] **Step 2: รัน test และยืนยันว่า fail**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/ui/test_session_setup.py -v
```

Expected: FAIL เพราะ Futures fields ยังไม่ถูกประกอบ

- [ ] **Step 3: เพิ่ม Futures fields และ request mapping**

เชื่อม `market_type.currentIndexChanged` กับ method เดียว:

```python
@Slot()
def _sync_market_fields(self) -> None:
    futures = self.market_type.currentData() == "futures"
    self.spot_fields.setVisible(not futures)
    self.futures_fields.setVisible(futures)

def values(self) -> PaperSessionSetupValues:
    futures = self.market_type.currentData() == "futures"
    return PaperSessionSetupValues(
        market_type=self.market_type.currentData(),
        symbol="BTCUSDT",
        timeframe=self.timeframe.currentData(),
        available_capital=self.available_capital.text(),
        max_entries=str(self.max_entries.value()),
        fee_percent=self.fee_percent.text(),
        slippage_bps=self.slippage_bps.text(),
        spot_trading_capital_percent=None if futures else self.spot_ratio.text(),
        futures_leverage=str(self.leverage.value()) if futures else None,
    )
```

- [ ] **Step 4: เขียน failing Futures Overview test**

```python
def test_futures_overview_shows_immutable_policy(qtbot) -> None:
    session = configured_futures_session(leverage=3)
    overview = SessionOverviewWidget()
    qtbot.addWidget(overview)

    overview.show_session(session)

    assert overview.market_value.text() == "Futures"
    assert overview.leverage_value.text() == "3x"
    assert overview.margin_mode_value.text() == "Cross Margin"
    assert overview.position_mode_value.text() == "One-way Mode"
    assert overview.collateral_buffer_value.text() == "50%"
```

- [ ] **Step 5: Render Spot/Futures policy จาก domain snapshot**

Overview ห้ามคำนวณ policy ใหม่ ให้ branch จาก `session.config.market_type` และอ่าน
`spot_policy` หรือ `futures_policy` ที่ validate แล้ว หาก policy ที่ต้องมีหายให้แสดง
unavailable state แทนการสร้างค่า default

- [ ] **Step 6: รัน UI tests, checks และ commit**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/ui -v
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/ui/session_setup.py src/tiewtrade/ui/session_overview.py tests/unit/ui/test_session_setup.py tests/unit/ui/test_main_window.py
git commit -m "feat: configure Paper Futures from Desktop"
```

---

### Task 4: โหลด Active Session เดิมและทำ UI Failure States ให้ปลอดภัย

**Files:**
- Modify: `src/tiewtrade/ui/main_window.py`
- Modify: `src/tiewtrade/ui/desktop.py`
- Modify: `tests/unit/ui/test_main_window.py`

**Interfaces:**
- Consumes: sync callables `create_session(values)` และ `load_active()`
- Produces: `SessionTask(QRunnable)`, success/failure/finished signals และ startup loading flow

- [ ] **Step 1: เขียน failing async/restart tests**

เพิ่ม tests ต่อไปนี้:

```python
import threading


def unused_create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
    pytest.fail("create must not run")


def test_existing_active_session_opens_overview_without_create_form(qtbot) -> None:
    existing = configured_spot_session()
    window = MainWindow(
        create_session=lambda values: pytest.fail("must not create"),
        load_active=lambda: existing,
    )
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(lambda: window.current_page_name == "Session Overview")

    assert window.overview.session_id_value.text() == str(existing.config.session_id)


def test_sqlite_failure_shows_unavailable_without_fake_overview(qtbot) -> None:
    def fail_load() -> ConfiguredPaperSession | None:
        raise PaperSessionUnavailableError("Active Paper Session read failed")

    window = MainWindow(create_session=unused_create, load_active=fail_load)
    qtbot.addWidget(window)
    window.show()

    qtbot.waitUntil(window.unavailable_panel.isVisible)

    assert window.current_page_name == "Unavailable"
    assert not window.overview.isVisible()


def test_closing_window_ignores_late_worker_result(qtbot) -> None:
    release = threading.Event()

    def delayed_load() -> ConfiguredPaperSession | None:
        release.wait(timeout=1)
        return configured_spot_session()

    window = MainWindow(create_session=unused_create, load_active=delayed_load)
    qtbot.addWidget(window)
    window.show()
    window.close()

    release.set()
    qtbot.wait(50)

    assert not window.isVisible()
```

- [ ] **Step 2: รัน tests และยืนยันว่า fail**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/ui/test_main_window.py -v
```

Expected: FAIL เพราะ load/create ยังรันบน UI thread และไม่มี unavailable state

- [ ] **Step 3: ใช้ focused worker เดิมสำหรับ startup load**

ใช้ `SessionTask` จาก Task 2 กับ `load_active` โดยคง contract ต่อไปนี้:

```python
class SessionTaskSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()


class SessionTask(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation
        self.signals = SessionTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:
            self.signals.failed.emit(error)
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
```

ห้ามเปลี่ยน worker ให้จับ `BaseException` และห้ามขยายเป็น generic worker framework นอก
Session Setup scope

- [ ] **Step 4: เชื่อม startup load และ create ผ่าน QThreadPool**

Main Window ต้องเก็บ strong reference ของ task จน `finished`, ใช้ generation token หรือ
`QPointer`-equivalent guard เพื่อเพิกเฉย stale callback หลัง close และ disable repeated
submit ระหว่าง task ทำงาน

Error mapping:

```python
if isinstance(error, PaperSessionValidationError):
    self.setup.show_field_error(error.field, str(error))
    self._show_setup()
elif isinstance(error, PaperSessionUnavailableError):
    self._show_unavailable("Session storage is unavailable")
else:
    self._show_unavailable("Paper Session could not be created")
```

ห้ามแสดง raw exception, file path หรือ SQLite detail ใน UI

- [ ] **Step 5: ให้ composition root ส่ง `store.get_active`**

แก้ `run_desktop()` ให้ `MainWindow` รับ create callable เดิมและ `load_active` ต่อไปนี้
โดยไม่เรียกสอง operation นี้ใน composition thread:

```python
def load_after_migration() -> ConfiguredPaperSession | None:
    database.migrate()
    return store.get_active()


window = MainWindow(
    create_session=create_after_migration,
    load_active=load_after_migration,
)
```

- [ ] **Step 6: รัน UI tests, full tests และ commit**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/ui -v
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/ui/session_tasks.py src/tiewtrade/ui/main_window.py src/tiewtrade/ui/desktop.py tests/unit/ui/test_main_window.py
git commit -m "fix: make Desktop session startup fail closed"
```

---

### Task 5: พิสูจน์ Desktop Session Setup Acceptance Flow

**Files:**
- Create: `tests/acceptance/test_desktop_session_setup.py`
- Modify: `PROJECT_PLAN.md`
- Modify: `docs/superpowers/specs/2026-07-27-desktop-ui-session-setup-design.md` เมื่อ implementation ต่างจาก design ที่อนุมัติเท่านั้น

**Interfaces:**
- Consumes: `SQLiteDatabase`, `SQLiteActivePaperSessions`, `CreatePaperSession`, `MainWindow`
- Produces: deterministic end-to-end proof และ DEV-96 prerequisite gate

- [ ] **Step 1: เขียน failing create/restart acceptance test**

```python
def test_desktop_creates_and_restores_one_paper_session(qtbot, tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "tiewtrade.sqlite3")
    database.migrate()
    store = SQLiteActivePaperSessions(database)
    create = CreatePaperSession(
        create_active=store.create,
        session_ids=lambda: SESSION_ID,
        clock=lambda: CREATED_AT,
    )

    first = MainWindow(create_session=create.execute, load_active=store.get_active)
    qtbot.addWidget(first)
    first.show()
    qtbot.waitUntil(first.setup.isVisible)
    first.setup.available_capital.setText("200000")
    qtbot.mouseClick(first.setup.create_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(first.overview.isVisible)
    assert first.overview.session_id_value.text() == str(SESSION_ID)
    first.close()

    restarted_store = SQLiteActivePaperSessions(database)
    restarted = MainWindow(
        create_session=lambda values: pytest.fail("must not create a second Session"),
        load_active=restarted_store.get_active,
    )
    qtbot.addWidget(restarted)
    restarted.show()
    qtbot.waitUntil(restarted.overview.isVisible)

    assert restarted.overview.session_id_value.text() == str(SESSION_ID)
    assert restarted.overview.state_value.text() == "Configured — Market Data Not Started"
```

Parametrize Spot/Futures และเพิ่ม unavailable SQLite case โดยไม่มี network fixture

- [ ] **Step 2: รัน acceptance test และแก้เฉพาะ wiring ที่ทำให้ fail**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/acceptance/test_desktop_session_setup.py -v
```

Expected: PASS หลัง wiring สมบูรณ์

- [ ] **Step 3: รัน Desktop smoke launch แบบไม่เข้า event loop ถาวร**

เพิ่ม smoke test ที่สร้าง `QApplication`, compose Main Window ด้วย temporary database,
เรียก `show()`, process events หนึ่งรอบ และ `close()` Expected: ไม่มี exception และไม่มี
network call

- [ ] **Step 4: รัน quality gates ทั้งหมด**

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
npm --prefix docs-site test
npm --prefix docs-site run check:content
git diff --check
```

Expected: ทุกคำสั่ง exit 0

- [ ] **Step 5: ตรวจ safety และ commit acceptance gate**

ตรวจด้วย `rg` ว่า UI files ไม่มี `aiohttp`, Binance Private endpoint, API key, Strategy
หรือ Execution imports และยืนยันว่า UI tests ไม่เปิด network

```bash
git add PROJECT_PLAN.md tests/acceptance/test_desktop_session_setup.py
git commit -m "test: prove Desktop Paper Session setup"
```

หลัง review ผ่าน ให้ย้าย Issue acceptance gate เป็น Done และปลด blocker ของ DEV-96
โดยยังต้องรอคำยืนยันผู้ใช้แยกสำหรับ push และ merge
