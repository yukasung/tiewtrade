# Paper Spot Core Tracer Bullet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้าง headless Paper Spot vertical slice สำหรับ BTCUSDT ที่ replay completed candle 5 นาทีผ่าน RSI Step Grid, Entry Pair, Basket Take Profit และ conservative fill ได้อย่าง deterministic

**Architecture:** ใช้ feature-first modular monolith ภายใต้ `src/tiewtrade` โดย business rules ไม่ขึ้นกับ Qt, SQLite หรือ Binance transport ในแผนนี้ แต่ละ module เปิดเผย concrete types เท่าที่ consumer ปัจจุบันต้องใช้ และเชื่อมกันใน `paper/session.py` โดยตรง การเพิ่ม persistence, recovery, Paper Futures และ Desktop UI แยกเป็น implementation plans ถัดไปหลัง core tracer bullet ผ่าน acceptance

**Tech Stack:** Python 3.12+, standard library (`dataclasses`, `datetime`, `decimal`, `hashlib`, `uuid`, `csv`, `argparse`), pytest, Ruff, mypy

## Global Constraints

- รองรับเฉพาะ BTCUSDT และ completed candle 5 นาทีในแผนนี้
- เวลา domain ทั้งหมดต้องเป็น timezone-aware UTC
- Strategy เป็น Long-only RSI Step Grid Preset version `rsi-step-grid-v1`
- ค่าเริ่มต้นคือ RSI(14), reset ต่ำกว่า 30, entry สูงกว่า 50, ATR(14) และ Basket TP เท่ากับ weighted average entry price บวก ATR คูณ 3
- Spot Trading Capital เท่ากับ 80% ของ Available Capital, Spot Reserve เท่ากับ 20% และแบ่ง Trading Capital เป็น 10 Entries เท่ากัน
- สูงสุด 10 Entries ต่อ Basket และใช้ Entry Pair/Cooldown Month ตาม `PRODUCT.md`
- Paper Entry จาก signal candle `N` ต้อง Fill ที่ราคาเปิดของ candle `N+1` พร้อม fee/slippage; Take Profit ห้าม Fill ใน candle เดียวกับ Entry Fill
- ใช้ `Decimal` สำหรับราคา จำนวน ทุน fee และ PnL ห้ามใช้ binary float ใน financial calculations
- ห้ามสร้าง generic base class, strategy registry, factory หรือ catch-all `models.py`, `interfaces.py`, `utils.py`
- ใช้ fake/in-memory data เท่านั้น ห้ามเรียก Binance private API หรือส่ง Live order
- ทุก task ใช้ TDD: failing test → minimal implementation → refactor → verification → commit

## Scope Boundary

แผนนี้ส่งมอบ Paper Spot core ที่เรียกผ่าน CLI และ automated acceptance test ได้ แต่ยังไม่ถือว่า “Paper Trading Complete” ตาม `PRODUCT.md` สิ่งต่อไปนี้อยู่ในแผนถัดไป:

1. SQLite durability, audit trail, restart recovery และ multi-profile active-session enforcement
2. Paper Futures, leverage, collateral buffer และ funding
3. Binance public market-data adapter, reconnect/backfill runtime
4. PySide6 Desktop UI และ final Paper acceptance

## File Map

```text
pyproject.toml
README.md
src/tiewtrade/
├── __init__.py
├── market_data/
│   ├── __init__.py
│   ├── candle.py
│   └── completed_candle_stream.py
├── strategies/
│   ├── __init__.py
│   └── rsi_step_grid/
│       ├── __init__.py
│       ├── indicators.py
│       ├── preset.py
│       └── strategy.py
├── trading/
│   ├── __init__.py
│   ├── basket.py
│   ├── capital.py
│   ├── entry_pair.py
│   └── symbol_rules.py
├── paper/
│   ├── __init__.py
│   ├── session_config.py
│   ├── session.py
│   └── replay.py
└── paper_replay_main.py
tests/
├── acceptance/test_paper_spot_replay.py
├── fixtures/btcusdt_5m_tracer.csv
└── unit/
    ├── market_data/test_completed_candle_stream.py
    ├── paper/test_session_config.py
    ├── paper/test_paper_spot_session.py
    ├── strategies/test_rsi_step_grid_indicators.py
    ├── strategies/test_rsi_step_grid_strategy.py
    ├── trading/test_basket.py
    ├── trading/test_capital.py
    └── trading/test_entry_pair.py
```

---

### Task 1: Project foundation and immutable Paper Spot session configuration

**Files:**
- Create: `pyproject.toml`
- Create: `src/tiewtrade/__init__.py`
- Create: `src/tiewtrade/paper/__init__.py`
- Create: `src/tiewtrade/paper/session_config.py`
- Create: `tests/unit/paper/test_session_config.py`

**Interfaces:**
- Consumes: ไม่มี เป็น foundation task
- Produces: `PaperSpotSessionConfig` ซึ่ง task ถัดไปใช้อ้างอิง Session, Account Profile ownership และค่าจำลองที่ immutable

- [ ] **Step 1: สร้าง failing tests สำหรับ identity และ immutable configuration**

```python
# tests/unit/paper/test_session_config.py
from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.paper.session_config import PaperSpotSessionConfig


def test_paper_session_configuration_is_immutable() -> None:
    config = PaperSpotSessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000010"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("2"),
    )

    with pytest.raises(FrozenInstanceError):
        config.available_capital = Decimal("2000")  # type: ignore[misc]


@pytest.mark.parametrize("field_value", [Decimal("0"), Decimal("-1")])
def test_paper_session_requires_positive_capital(field_value: Decimal) -> None:
    with pytest.raises(ValueError, match="available_capital"):
        PaperSpotSessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000010"),
            account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
            preset_version="rsi-step-grid-v1",
            available_capital=field_value,
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("2"),
        )


@pytest.mark.parametrize(
    ("fee_rate", "slippage_bps"),
    [(Decimal("-0.001"), Decimal("0")), (Decimal("0"), Decimal("-1"))],
)
def test_paper_session_rejects_negative_execution_costs(
    fee_rate: Decimal, slippage_bps: Decimal
) -> None:
    with pytest.raises(ValueError):
        PaperSpotSessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000010"),
            account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
            preset_version="rsi-step-grid-v1",
            available_capital=Decimal("1000"),
            fee_rate=fee_rate,
            slippage_bps=slippage_bps,
        )
```

- [ ] **Step 2: Run tests เพื่อยืนยันว่า fail เพราะ package ยังไม่มี**

Run: `python -m pytest tests/unit/paper/test_session_config.py -q`

Expected: FAIL ด้วย `ModuleNotFoundError: No module named 'tiewtrade'`

- [ ] **Step 3: สร้าง package configuration และ immutable domain records**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "tiewtrade"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = [
  "mypy>=1.14,<2",
  "pytest>=8,<10",
  "pytest-cov>=6,<8",
  "ruff>=0.9,<1",
]

[project.scripts]
tiewtrade-paper-replay = "tiewtrade.paper_replay_main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/tiewtrade"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["tiewtrade"]
```

```python
# src/tiewtrade/paper/session_config.py
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PaperSpotSessionConfig:
    session_id: UUID
    account_profile_id: UUID
    preset_version: str
    available_capital: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal

    def __post_init__(self) -> None:
        if self.available_capital <= 0:
            raise ValueError("available_capital must be positive")
        if self.fee_rate < 0:
            raise ValueError("fee_rate must not be negative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must not be negative")
```

สร้าง `__init__.py` ทุกไฟล์เป็นไฟล์ว่าง ห้าม re-export symbols จนกว่าจะมี consumer ต้องการ public package API

- [ ] **Step 4: Run focused tests และ quality checks**

Run: `python -m pip install -e ".[dev]"`

Expected: ติดตั้ง `tiewtrade` แบบ editable และ development tools สำเร็จ

Run: `python -m pytest tests/unit/paper/test_session_config.py -q`

Expected: `5 passed`

Run: `python -m ruff check .`

Expected: `All checks passed!`

Run: `python -m mypy src`

Expected: `Success: no issues found`

- [ ] **Step 5: Commit foundation**

```bash
git add pyproject.toml src/tiewtrade/__init__.py src/tiewtrade/paper tests/unit/paper/test_session_config.py
git commit -m "build: add paper core project foundation"
```

---

### Task 2: Completed BTCUSDT 5-minute candle boundary

**Files:**
- Create: `src/tiewtrade/market_data/__init__.py`
- Create: `src/tiewtrade/market_data/candle.py`
- Create: `src/tiewtrade/market_data/completed_candle_stream.py`
- Create: `tests/unit/market_data/test_completed_candle_stream.py`

**Interfaces:**
- Consumes: ไม่มี dependency จาก Task 1
- Produces: `Candle`, `CompletedCandleStream.accept(candle, received_at) -> bool`, `CandleGapError`

- [ ] **Step 1: เขียน failing tests สำหรับ incomplete, duplicate, gap และ UTC**

```python
# tests/unit/market_data/test_completed_candle_stream.py
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import (
    CandleGapError,
    CompletedCandleStream,
)


def candle_at(minute: int) -> Candle:
    opened = datetime(2026, 1, 1, 0, minute, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        open_time=opened,
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("10"),
    )


def test_accepts_only_closed_candles_and_deduplicates() -> None:
    stream = CompletedCandleStream()
    first = candle_at(0)

    assert not stream.accept(first, datetime(2026, 1, 1, 0, 4, 59, tzinfo=UTC))
    assert stream.accept(first, datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    assert not stream.accept(first, datetime(2026, 1, 1, 0, 6, tzinfo=UTC))


def test_rejects_a_gap_until_backfill_supplies_missing_candle() -> None:
    stream = CompletedCandleStream()
    assert stream.accept(candle_at(0), datetime(2026, 1, 1, 0, 5, tzinfo=UTC))

    with pytest.raises(CandleGapError, match="2026-01-01T00:05:00"):
        stream.accept(candle_at(10), datetime(2026, 1, 1, 0, 15, tzinfo=UTC))

    assert stream.accept(candle_at(5), datetime(2026, 1, 1, 0, 10, tzinfo=UTC))
    assert stream.accept(candle_at(10), datetime(2026, 1, 1, 0, 15, tzinfo=UTC))


def test_candle_requires_utc_and_valid_ohlc() -> None:
    with pytest.raises(ValueError, match="UTC"):
        Candle(
            symbol="BTCUSDT",
            open_time=datetime(2026, 1, 1),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("10"),
        )
```

- [ ] **Step 2: Run focused test เพื่อยืนยัน failure**

Run: `python -m pytest tests/unit/market_data/test_completed_candle_stream.py -q`

Expected: FAIL ด้วย `ModuleNotFoundError` สำหรับ `tiewtrade.market_data`

- [ ] **Step 3: Implement immutable candle และ completed stream**

```python
# src/tiewtrade/market_data/candle.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

CANDLE_INTERVAL = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.symbol != "BTCUSDT":
            raise ValueError("symbol must be BTCUSDT")
        if self.open_time.tzinfo is None or self.open_time.utcoffset() != timedelta(0):
            raise ValueError("open_time must use UTC")
        if self.open_time.second or self.open_time.microsecond:
            raise ValueError("open_time must align to a minute")
        if self.open_time.minute % 5:
            raise ValueError("open_time must align to a 5-minute boundary")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.high < max(self.open, self.close) or self.low > min(
            self.open, self.close
        ):
            raise ValueError("OHLC range is invalid")
        if self.volume < 0:
            raise ValueError("volume must not be negative")

    @property
    def close_time(self) -> datetime:
        return self.open_time + CANDLE_INTERVAL
```

```python
# src/tiewtrade/market_data/completed_candle_stream.py
from datetime import datetime, timedelta

from tiewtrade.market_data.candle import CANDLE_INTERVAL, Candle


class CandleGapError(ValueError):
    pass


class CompletedCandleStream:
    def __init__(self) -> None:
        self._last_open_time: datetime | None = None

    def accept(self, candle: Candle, received_at: datetime) -> bool:
        if received_at.tzinfo is None or received_at.utcoffset() != timedelta(0):
            raise ValueError("received_at must use UTC")
        if received_at < candle.close_time:
            return False
        if self._last_open_time is not None:
            if candle.open_time <= self._last_open_time:
                return False
            expected = self._last_open_time + CANDLE_INTERVAL
            if candle.open_time != expected:
                raise CandleGapError(
                    f"missing candle beginning {expected.isoformat()}"
                )
        self._last_open_time = candle.open_time
        return True
```

- [ ] **Step 4: Run focused tests and static checks**

Run: `python -m pytest tests/unit/market_data/test_completed_candle_stream.py -q`

Expected: `3 passed`

Run: `python -m ruff check src/tiewtrade/market_data tests/unit/market_data`

Expected: `All checks passed!`

- [ ] **Step 5: Commit candle boundary**

```bash
git add src/tiewtrade/market_data tests/unit/market_data
git commit -m "feat: enforce completed five minute candles"
```

---

### Task 3: Immutable preset and Wilder RSI/ATR indicators

**Files:**
- Create: `src/tiewtrade/strategies/__init__.py`
- Create: `src/tiewtrade/strategies/rsi_step_grid/__init__.py`
- Create: `src/tiewtrade/strategies/rsi_step_grid/preset.py`
- Create: `src/tiewtrade/strategies/rsi_step_grid/indicators.py`
- Create: `tests/unit/strategies/test_rsi_step_grid_indicators.py`

**Interfaces:**
- Consumes: `Candle`
- Produces: `RsiStepGridPreset.v1()`, `IndicatorSnapshot`, `WilderIndicators.update(candle) -> IndicatorSnapshot | None`

- [ ] **Step 1: เขียน failing tests สำหรับ preset และ Wilder warm-up**

```python
# tests/unit/strategies/test_rsi_step_grid_indicators.py
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import WilderIndicators
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


def rising_candle(index: int) -> Candle:
    close = Decimal("100") + index
    return Candle(
        symbol="BTCUSDT",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index),
        open=close - Decimal("0.5"),
        high=close + Decimal("1"),
        low=close - Decimal("1"),
        close=close,
        volume=Decimal("1"),
    )


def test_v1_preset_matches_product_definition() -> None:
    preset = RsiStepGridPreset.v1()
    assert preset.version == "rsi-step-grid-v1"
    assert preset.rsi_period == 14
    assert preset.rsi_reset_threshold == Decimal("30")
    assert preset.rsi_entry_threshold == Decimal("50")
    assert preset.atr_period == 14
    assert preset.take_profit_atr_multiplier == Decimal("3")
    assert preset.max_entries == 10


def test_wilder_indicators_emit_after_fourteen_price_changes() -> None:
    indicators = WilderIndicators(RsiStepGridPreset.v1())
    snapshots = [indicators.update(rising_candle(index)) for index in range(15)]

    assert all(snapshot is None for snapshot in snapshots[:14])
    assert snapshots[14] is not None
    assert snapshots[14].rsi == Decimal("100")
    assert snapshots[14].atr == Decimal("2")
```

- [ ] **Step 2: Run test เพื่อยืนยัน failure**

Run: `python -m pytest tests/unit/strategies/test_rsi_step_grid_indicators.py -q`

Expected: FAIL ด้วย `ModuleNotFoundError` สำหรับ `tiewtrade.strategies`

- [ ] **Step 3: Implement immutable preset และ Wilder smoothing**

```python
# src/tiewtrade/strategies/rsi_step_grid/preset.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RsiStepGridPreset:
    version: str
    rsi_period: int
    rsi_reset_threshold: Decimal
    rsi_entry_threshold: Decimal
    atr_period: int
    take_profit_atr_multiplier: Decimal
    max_entries: int

    @classmethod
    def v1(cls) -> "RsiStepGridPreset":
        return cls(
            version="rsi-step-grid-v1",
            rsi_period=14,
            rsi_reset_threshold=Decimal("30"),
            rsi_entry_threshold=Decimal("50"),
            atr_period=14,
            take_profit_atr_multiplier=Decimal("3"),
            max_entries=10,
        )
```

```python
# src/tiewtrade/strategies/rsi_step_grid/indicators.py
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    rsi: Decimal
    atr: Decimal


class WilderIndicators:
    def __init__(self, preset: RsiStepGridPreset) -> None:
        self._preset = preset
        self._previous_close: Decimal | None = None
        self._true_ranges: deque[Decimal] = deque(maxlen=preset.atr_period)
        self._gains: deque[Decimal] = deque(maxlen=preset.rsi_period)
        self._losses: deque[Decimal] = deque(maxlen=preset.rsi_period)
        self._average_gain: Decimal | None = None
        self._average_loss: Decimal | None = None
        self._atr: Decimal | None = None

    def update(self, candle: Candle) -> IndicatorSnapshot | None:
        previous = self._previous_close
        true_range = candle.high - candle.low
        if previous is not None:
            true_range = max(
                true_range,
                abs(candle.high - previous),
                abs(candle.low - previous),
            )
            change = candle.close - previous
            gain = max(change, Decimal("0"))
            loss = max(-change, Decimal("0"))
            self._update_rsi_averages(gain, loss)
        self._update_atr(true_range)
        self._previous_close = candle.close
        if self._atr is None or self._average_gain is None or self._average_loss is None:
            return None
        return IndicatorSnapshot(rsi=self._rsi(), atr=self._atr)

    def _update_atr(self, true_range: Decimal) -> None:
        period = Decimal(self._preset.atr_period)
        if self._atr is None:
            self._true_ranges.append(true_range)
            if len(self._true_ranges) == self._preset.atr_period:
                self._atr = sum(self._true_ranges) / period
            return
        self._atr = ((self._atr * (period - 1)) + true_range) / period

    def _update_rsi_averages(self, gain: Decimal, loss: Decimal) -> None:
        period = Decimal(self._preset.rsi_period)
        if self._average_gain is None or self._average_loss is None:
            self._gains.append(gain)
            self._losses.append(loss)
            if len(self._gains) == self._preset.rsi_period:
                self._average_gain = sum(self._gains) / period
                self._average_loss = sum(self._losses) / period
            return
        self._average_gain = ((self._average_gain * (period - 1)) + gain) / period
        self._average_loss = ((self._average_loss * (period - 1)) + loss) / period

    def _rsi(self) -> Decimal:
        assert self._average_gain is not None
        assert self._average_loss is not None
        if self._average_loss == 0:
            return Decimal("100")
        if self._average_gain == 0:
            return Decimal("0")
        relative_strength = self._average_gain / self._average_loss
        return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))
```

- [ ] **Step 4: Run focused and static tests**

Run: `python -m pytest tests/unit/strategies/test_rsi_step_grid_indicators.py -q`

Expected: `2 passed`

Run: `python -m ruff check src/tiewtrade/strategies tests/unit/strategies`

Expected: `All checks passed!`

- [ ] **Step 5: Commit indicators**

```bash
git add src/tiewtrade/strategies tests/unit/strategies
git commit -m "feat: calculate RSI step grid indicators"
```

---

### Task 4: Stateful RSI reset-to-entry decision

**Files:**
- Create: `src/tiewtrade/strategies/rsi_step_grid/strategy.py`
- Create: `tests/unit/strategies/test_rsi_step_grid_strategy.py`

**Interfaces:**
- Consumes: `Candle`, `IndicatorSnapshot`, `RsiStepGridPreset`
- Produces: `EntryIntent`, `RsiStepGridStrategy.evaluate(...)`, `on_entry_filled()`, `on_entry_rejected()`

- [ ] **Step 1: เขียน failing tests สำหรับ reset, bullish confirmation และ duplicate intent**

```python
# tests/unit/strategies/test_rsi_step_grid_strategy.py
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import IndicatorSnapshot
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import RsiStepGridStrategy


SESSION_ID = UUID("00000000-0000-0000-0000-000000000010")


def candle(index: int, open_price: str, close_price: str) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 5)
    open_value = Decimal(open_price)
    close_value = Decimal(close_price)
    return Candle(
        symbol="BTCUSDT",
        open_time=opened,
        open=open_value,
        high=max(open_value, close_value) + Decimal("1"),
        low=min(open_value, close_value) - Decimal("1"),
        close=close_value,
        volume=Decimal("1"),
    )


def test_emits_one_intent_after_reset_and_bullish_confirmation() -> None:
    strategy = RsiStepGridStrategy(SESSION_ID, RsiStepGridPreset.v1())
    assert strategy.evaluate(
        candle(0, "101", "100"), IndicatorSnapshot(Decimal("29"), Decimal("2")), 1, True
    ) is None

    intent = strategy.evaluate(
        candle(1, "100", "102"), IndicatorSnapshot(Decimal("51"), Decimal("2")), 1, True
    )

    assert intent is not None
    assert intent.entry_number == 1
    assert intent.atr == Decimal("2")
    assert strategy.evaluate(
        candle(2, "102", "103"), IndicatorSnapshot(Decimal("55"), Decimal("2")), 1, True
    ) is None


def test_fill_consumes_reset_signal() -> None:
    strategy = RsiStepGridStrategy(SESSION_ID, RsiStepGridPreset.v1())
    strategy.evaluate(
        candle(0, "101", "100"), IndicatorSnapshot(Decimal("29"), Decimal("2")), 1, True
    )
    assert strategy.evaluate(
        candle(1, "100", "102"), IndicatorSnapshot(Decimal("51"), Decimal("2")), 1, True
    ) is not None

    strategy.on_entry_filled()

    assert strategy.evaluate(
        candle(2, "102", "103"), IndicatorSnapshot(Decimal("55"), Decimal("2")), 2, True
    ) is None
```

- [ ] **Step 2: Run focused tests เพื่อยืนยัน failure**

Run: `python -m pytest tests/unit/strategies/test_rsi_step_grid_strategy.py -q`

Expected: FAIL เพราะ `strategy.py` ยังไม่มี

- [ ] **Step 3: Implement intent และ state machine โดยไม่สร้าง base strategy**

```python
# src/tiewtrade/strategies/rsi_step_grid/strategy.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.indicators import IndicatorSnapshot
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


@dataclass(frozen=True, slots=True)
class EntryIntent:
    intent_id: str
    signal_open_time: datetime
    entry_number: int
    atr: Decimal


class RsiStepGridStrategy:
    def __init__(self, session_id: UUID, preset: RsiStepGridPreset) -> None:
        self._session_id = session_id
        self._preset = preset
        self._reset_close: Decimal | None = None
        self._intent_pending = False

    def evaluate(
        self,
        candle: Candle,
        indicators: IndicatorSnapshot,
        entry_number: int,
        can_enter: bool,
    ) -> EntryIntent | None:
        if indicators.rsi < self._preset.rsi_reset_threshold:
            self._reset_close = candle.close
        if self._intent_pending or not can_enter or self._reset_close is None:
            return None
        if entry_number > self._preset.max_entries:
            return None
        if not (
            indicators.rsi > self._preset.rsi_entry_threshold
            and candle.close > candle.open
            and candle.close > self._reset_close
        ):
            return None
        raw_id = (
            f"{self._session_id}:{self._preset.version}:"
            f"{candle.open_time.isoformat()}:{entry_number}"
        )
        self._intent_pending = True
        return EntryIntent(
            intent_id=sha256(raw_id.encode()).hexdigest(),
            signal_open_time=candle.open_time,
            entry_number=entry_number,
            atr=indicators.atr,
        )

    def on_entry_filled(self) -> None:
        self._reset_close = None
        self._intent_pending = False

    def on_entry_rejected(self) -> None:
        self._intent_pending = False
```

- [ ] **Step 4: Run strategy tests and full suite**

Run: `python -m pytest tests/unit/strategies/test_rsi_step_grid_strategy.py -q`

Expected: `2 passed`

Run: `python -m pytest -q`

Expected: ทุก test ผ่าน

- [ ] **Step 5: Commit strategy decision**

```bash
git add src/tiewtrade/strategies/rsi_step_grid/strategy.py tests/unit/strategies/test_rsi_step_grid_strategy.py
git commit -m "feat: create RSI step grid entry intents"
```

---

### Task 5: Spot capital, symbol quantization, Basket TP and Entry Pair lifecycle

**Files:**
- Create: `src/tiewtrade/trading/__init__.py`
- Create: `src/tiewtrade/trading/capital.py`
- Create: `src/tiewtrade/trading/symbol_rules.py`
- Create: `src/tiewtrade/trading/basket.py`
- Create: `src/tiewtrade/trading/entry_pair.py`
- Create: `tests/unit/trading/test_capital.py`
- Create: `tests/unit/trading/test_basket.py`
- Create: `tests/unit/trading/test_entry_pair.py`

**Interfaces:**
- Consumes: `Decimal`, aware UTC fill timestamps
- Produces: `SpotCapitalPlan`, `SymbolRules`, `Basket`, `ClosedBasket`, `EntryPairLifecycle.can_enter(at)`

- [ ] **Step 1: เขียน failing tests สำหรับ allocation และ quantization**

```python
# tests/unit/trading/test_capital.py
from decimal import Decimal

from tiewtrade.trading.capital import SpotCapitalPlan
from tiewtrade.trading.symbol_rules import SymbolRules


def test_spot_capital_uses_eighty_percent_and_ten_equal_entries() -> None:
    plan = SpotCapitalPlan.from_available(Decimal("1000"))
    assert plan.trading_capital == Decimal("800")
    assert plan.reserve == Decimal("200")
    assert plan.entry_notional == Decimal("80")


def test_symbol_rules_round_quantity_and_price_down() -> None:
    rules = SymbolRules(
        tick_size=Decimal("0.10"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )
    assert rules.floor_price(Decimal("101.29")) == Decimal("101.20")
    assert rules.floor_quantity(Decimal("0.1239")) == Decimal("0.123")
```

- [ ] **Step 2: เขียน failing tests สำหรับ weighted TP, PnL และ monthly lifecycle**

```python
# tests/unit/trading/test_basket.py
from datetime import UTC, datetime
from decimal import Decimal

from tiewtrade.trading.basket import Basket


def test_basket_reprices_take_profit_after_each_equal_entry() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"), quantity=Decimal("1"), fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC), atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )
    assert basket.take_profit_price == Decimal("106.0")

    basket.add_entry(
        price=Decimal("90"), quantity=Decimal("1"), fee=Decimal("0.09"),
        filled_at=datetime(2026, 1, 2, tzinfo=UTC), atr=Decimal("3"),
        tick_size=Decimal("0.1"),
    )
    assert basket.average_entry_price == Decimal("95")
    assert basket.take_profit_price == Decimal("104.0")


def test_close_subtracts_entry_and_exit_fees() -> None:
    basket = Basket(max_entries=10, take_profit_atr_multiplier=Decimal("3"))
    basket.add_entry(
        price=Decimal("100"), quantity=Decimal("1"), fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC), atr=Decimal("2"),
        tick_size=Decimal("0.1"),
    )
    closed = basket.close(
        exit_price=Decimal("106"), exit_fee=Decimal("0.106"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert closed.realized_pnl == Decimal("5.794")
```

```python
# tests/unit/trading/test_entry_pair.py
from datetime import UTC, datetime

from tiewtrade.trading.entry_pair import EntryPairLifecycle


def test_one_entry_may_cross_month_to_complete_its_pair() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)
    lifecycle.record_fill(datetime(2026, 1, 31, 23, 55, tzinfo=UTC))
    assert lifecycle.can_enter(datetime(2026, 2, 1, tzinfo=UTC))


def test_completed_pair_blocks_remainder_then_cooldown_month() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)
    lifecycle.record_fill(datetime(2026, 1, 10, tzinfo=UTC))
    lifecycle.record_fill(datetime(2026, 1, 20, tzinfo=UTC))
    assert not lifecycle.can_enter(datetime(2026, 1, 25, tzinfo=UTC))
    assert not lifecycle.can_enter(datetime(2026, 2, 15, tzinfo=UTC))
    assert lifecycle.can_enter(datetime(2026, 3, 1, tzinfo=UTC))
```

- [ ] **Step 3: Run tests เพื่อยืนยัน failure**

Run: `python -m pytest tests/unit/trading -q`

Expected: FAIL เพราะ `tiewtrade.trading` ยังไม่มี

- [ ] **Step 4: Implement capital และ symbol rules**

```python
# src/tiewtrade/trading/capital.py
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SpotCapitalPlan:
    available_capital: Decimal
    trading_capital: Decimal
    reserve: Decimal
    entry_notional: Decimal

    @classmethod
    def from_available(cls, available: Decimal) -> "SpotCapitalPlan":
        if available <= 0:
            raise ValueError("available capital must be positive")
        trading = available * Decimal("0.80")
        return cls(
            available_capital=available,
            trading_capital=trading,
            reserve=available - trading,
            entry_notional=trading / Decimal("10"),
        )
```

```python
# src/tiewtrade/trading/symbol_rules.py
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True, slots=True)
class SymbolRules:
    tick_size: Decimal
    step_size: Decimal
    min_notional: Decimal

    def floor_price(self, value: Decimal) -> Decimal:
        return (value / self.tick_size).to_integral_value(rounding=ROUND_DOWN) * self.tick_size

    def floor_quantity(self, value: Decimal) -> Decimal:
        return (value / self.step_size).to_integral_value(rounding=ROUND_DOWN) * self.step_size
```

- [ ] **Step 5: Implement Basket และ Entry Pair lifecycle**

```python
# src/tiewtrade/trading/basket.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True, slots=True)
class BasketEntry:
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class ClosedBasket:
    entry_count: int
    average_entry_price: Decimal
    exit_price: Decimal
    realized_pnl: Decimal
    closed_at: datetime


class Basket:
    def __init__(self, max_entries: int, take_profit_atr_multiplier: Decimal) -> None:
        self._max_entries = max_entries
        self._multiplier = take_profit_atr_multiplier
        self._entries: list[BasketEntry] = []
        self.take_profit_price: Decimal | None = None

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def is_empty(self) -> bool:
        return not self._entries

    @property
    def total_quantity(self) -> Decimal:
        return sum((entry.quantity for entry in self._entries), Decimal("0"))

    @property
    def average_entry_price(self) -> Decimal:
        if self.is_empty:
            raise ValueError("basket is empty")
        notional = sum((entry.price * entry.quantity for entry in self._entries), Decimal("0"))
        return notional / self.total_quantity

    def add_entry(
        self, *, price: Decimal, quantity: Decimal, fee: Decimal,
        filled_at: datetime, atr: Decimal, tick_size: Decimal,
    ) -> None:
        if self.entry_count >= self._max_entries:
            raise ValueError("basket has reached maximum entries")
        self._entries.append(BasketEntry(price, quantity, fee, filled_at))
        raw_target = self.average_entry_price + (atr * self._multiplier)
        self.take_profit_price = (
            raw_target / tick_size
        ).to_integral_value(rounding=ROUND_DOWN) * tick_size

    def close(
        self, *, exit_price: Decimal, exit_fee: Decimal, closed_at: datetime
    ) -> ClosedBasket:
        if self.is_empty:
            raise ValueError("basket is empty")
        gross = sum(
            ((exit_price - entry.price) * entry.quantity for entry in self._entries),
            Decimal("0"),
        )
        entry_fees = sum((entry.fee for entry in self._entries), Decimal("0"))
        return ClosedBasket(
            entry_count=self.entry_count,
            average_entry_price=self.average_entry_price,
            exit_price=exit_price,
            realized_pnl=gross - entry_fees - exit_fee,
            closed_at=closed_at,
        )
```

```python
# src/tiewtrade/trading/entry_pair.py
from datetime import datetime, timedelta


def month_index(at: datetime) -> int:
    if at.tzinfo is None or at.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC")
    return (at.year * 12) + at.month


class EntryPairLifecycle:
    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._entry_count = 0
        self._completed_pair_month: int | None = None

    @property
    def entry_count(self) -> int:
        return self._entry_count

    def can_enter(self, at: datetime) -> bool:
        if self._entry_count >= self._max_entries:
            return False
        if self._entry_count % 2 == 1 or self._entry_count == 0:
            return True
        assert self._completed_pair_month is not None
        return month_index(at) >= self._completed_pair_month + 2

    def record_fill(self, at: datetime) -> None:
        if not self.can_enter(at):
            raise ValueError("entry is blocked by pair lifecycle")
        self._entry_count += 1
        if self._entry_count % 2 == 0:
            self._completed_pair_month = month_index(at)

    def reset(self) -> None:
        self._entry_count = 0
        self._completed_pair_month = None
```

- [ ] **Step 6: Run domain tests and refactor only after green**

Run: `python -m pytest tests/unit/trading -q`

Expected: `6 passed`

Run: `python -m ruff check src/tiewtrade/trading tests/unit/trading`

Expected: `All checks passed!`

Run: `python -m mypy src`

Expected: `Success: no issues found`

- [ ] **Step 7: Commit trading policies**

```bash
git add src/tiewtrade/trading tests/unit/trading
git commit -m "feat: add spot basket and entry pair policies"
```

---

### Task 6: Conservative Paper Spot session orchestration

**Files:**
- Create: `src/tiewtrade/paper/session.py`
- Create: `tests/unit/paper/test_paper_spot_session.py`

**Interfaces:**
- Consumes: `PaperSpotSessionConfig`, `Candle`, `CompletedCandleStream`, `WilderIndicators`, `RsiStepGridStrategy`, `SpotCapitalPlan`, `SymbolRules`, `Basket`, `EntryPairLifecycle`
- Produces: `PaperSpotSession.on_candle(candle, received_at) -> bool`, `PaperFill`, `PaperSessionSnapshot`; return `True` เฉพาะ candle ที่ผ่าน completed/dedup/gap boundary

- [ ] **Step 1: เขียน failing tests ด้วย indicator snapshots ที่ควบคุมได้ผ่าน public decision method**

เพื่อไม่สร้าง generic strategy interface ให้เพิ่ม method `on_completed_candle(candle, indicators)` ใน `PaperSpotSession` สำหรับ unit test orchestration ส่วน production `on_candle` เป็นผู้คำนวณ snapshot แล้วเรียก method เดียวกัน

```python
# tests/unit/paper/test_paper_spot_session.py
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from tiewtrade.market_data.candle import Candle
from tiewtrade.paper.session import PaperSpotSession
from tiewtrade.paper.session_config import PaperSpotSessionConfig
from tiewtrade.strategies.rsi_step_grid.indicators import IndicatorSnapshot
from tiewtrade.trading.symbol_rules import SymbolRules


def candle(index: int, open_price: str, high: str, low: str, close: str) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        open_time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index),
        open=Decimal(open_price), high=Decimal(high), low=Decimal(low),
        close=Decimal(close), volume=Decimal("1"),
    )


def session() -> PaperSpotSession:
    return PaperSpotSession.create(
        PaperSpotSessionConfig(
            session_id=UUID("00000000-0000-0000-0000-000000000010"),
            account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
            preset_version="rsi-step-grid-v1",
            available_capital=Decimal("1000"),
            fee_rate=Decimal("0.001"),
            slippage_bps=Decimal("10"),
        ),
        SymbolRules(Decimal("0.1"), Decimal("0.001"), Decimal("5")),
    )


def test_signal_fills_at_next_open_with_slippage_and_fee() -> None:
    paper = session()
    paper.on_completed_candle(
        candle(0, "101", "102", "99", "100"),
        IndicatorSnapshot(Decimal("29"), Decimal("2")),
    )
    paper.on_completed_candle(
        candle(1, "100", "103", "99", "102"),
        IndicatorSnapshot(Decimal("51"), Decimal("2")),
    )
    assert paper.snapshot().pending_entry_number == 1

    paper.on_completed_candle(
        candle(2, "110", "120", "109", "119"),
        IndicatorSnapshot(Decimal("60"), Decimal("3")),
    )

    snapshot = paper.snapshot()
    assert snapshot.entry_count == 1
    assert snapshot.last_entry_price == Decimal("110.110")
    assert snapshot.last_entry_fee > 0
    assert snapshot.closed_basket_count == 0


def test_take_profit_cannot_fill_on_entry_fill_candle() -> None:
    paper = session()
    paper.on_completed_candle(
        candle(0, "101", "102", "99", "100"),
        IndicatorSnapshot(Decimal("29"), Decimal("2")),
    )
    paper.on_completed_candle(
        candle(1, "100", "103", "99", "102"),
        IndicatorSnapshot(Decimal("51"), Decimal("2")),
    )
    paper.on_completed_candle(
        candle(2, "100", "120", "99", "119"),
        IndicatorSnapshot(Decimal("60"), Decimal("2")),
    )
    assert paper.snapshot().entry_count == 1

    paper.on_completed_candle(
        candle(3, "105", "107", "104", "106"),
        IndicatorSnapshot(Decimal("60"), Decimal("2")),
    )
    assert paper.snapshot().closed_basket_count == 1
```

- [ ] **Step 2: Run focused tests เพื่อยืนยัน failure**

Run: `python -m pytest tests/unit/paper/test_paper_spot_session.py -q`

Expected: FAIL เพราะ `paper/session.py` ยังไม่มี

- [ ] **Step 3: Implement Paper records และ orchestration ตามลำดับ event ที่แน่นอน**

```python
# src/tiewtrade/paper/session.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.completed_candle_stream import CompletedCandleStream
from tiewtrade.paper.session_config import PaperSpotSessionConfig
from tiewtrade.strategies.rsi_step_grid.indicators import IndicatorSnapshot, WilderIndicators
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset
from tiewtrade.strategies.rsi_step_grid.strategy import EntryIntent, RsiStepGridStrategy
from tiewtrade.trading.basket import Basket, ClosedBasket
from tiewtrade.trading.capital import SpotCapitalPlan
from tiewtrade.trading.entry_pair import EntryPairLifecycle
from tiewtrade.trading.symbol_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class PaperFill:
    intent_id: str
    entry_number: int
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class PaperSessionSnapshot:
    pending_entry_number: int | None
    entry_count: int
    last_entry_price: Decimal | None
    last_entry_fee: Decimal | None
    take_profit_price: Decimal | None
    closed_basket_count: int


class PaperSpotSession:
    def __init__(
        self, config: PaperSpotSessionConfig, rules: SymbolRules,
        preset: RsiStepGridPreset,
    ) -> None:
        self._config = config
        self._rules = rules
        self._preset = preset
        self._stream = CompletedCandleStream()
        self._indicators = WilderIndicators(preset)
        self._strategy = RsiStepGridStrategy(config.session_id, preset)
        self._capital = SpotCapitalPlan.from_available(config.available_capital)
        self._lifecycle = EntryPairLifecycle(preset.max_entries)
        self._basket = Basket(preset.max_entries, preset.take_profit_atr_multiplier)
        self._pending: EntryIntent | None = None
        self._fills: list[PaperFill] = []
        self._closed: list[ClosedBasket] = []
        self._last_fill_candle: datetime | None = None

    @classmethod
    def create(
        cls, config: PaperSpotSessionConfig, rules: SymbolRules
    ) -> "PaperSpotSession":
        preset = RsiStepGridPreset.v1()
        if config.preset_version != preset.version:
            raise ValueError("unsupported preset version")
        return cls(config, rules, preset)

    def on_candle(self, candle: Candle, received_at: datetime) -> bool:
        if not self._stream.accept(candle, received_at):
            return False
        snapshot = self._indicators.update(candle)
        if snapshot is not None:
            self.on_completed_candle(candle, snapshot)
        return True

    def on_completed_candle(
        self, candle: Candle, indicators: IndicatorSnapshot
    ) -> None:
        if self._pending is not None:
            self._fill_pending_at_open(candle)
        elif self._take_profit_is_fillable(candle):
            self._close_at_take_profit(candle)
        intent = self._strategy.evaluate(
            candle,
            indicators,
            self._lifecycle.entry_count + 1,
            self._lifecycle.can_enter(candle.open_time),
        )
        if intent is not None:
            self._pending = intent

    def _fill_pending_at_open(self, candle: Candle) -> None:
        assert self._pending is not None
        multiplier = Decimal("1") + (self._config.slippage_bps / Decimal("10000"))
        price = candle.open * multiplier
        quantity = self._rules.floor_quantity(self._capital.entry_notional / price)
        notional = price * quantity
        if notional < self._rules.min_notional:
            self._strategy.on_entry_rejected()
            self._pending = None
            return
        fee = notional * self._config.fee_rate
        fill = PaperFill(
            intent_id=self._pending.intent_id,
            entry_number=self._pending.entry_number,
            price=price,
            quantity=quantity,
            fee=fee,
            filled_at=candle.open_time,
        )
        self._fills.append(fill)
        self._basket.add_entry(
            price=price, quantity=quantity, fee=fee,
            filled_at=candle.open_time, atr=self._pending.atr,
            tick_size=self._rules.tick_size,
        )
        self._lifecycle.record_fill(candle.open_time)
        self._strategy.on_entry_filled()
        self._pending = None
        self._last_fill_candle = candle.open_time

    def _take_profit_is_fillable(self, candle: Candle) -> bool:
        return (
            not self._basket.is_empty
            and self._basket.take_profit_price is not None
            and self._last_fill_candle is not None
            and candle.open_time > self._last_fill_candle
            and candle.high >= self._basket.take_profit_price
        )

    def _close_at_take_profit(self, candle: Candle) -> None:
        assert self._basket.take_profit_price is not None
        exit_price = self._basket.take_profit_price
        exit_fee = exit_price * self._basket.total_quantity * self._config.fee_rate
        self._closed.append(
            self._basket.close(
                exit_price=exit_price, exit_fee=exit_fee, closed_at=candle.open_time
            )
        )
        self._basket = Basket(self._preset.max_entries, self._preset.take_profit_atr_multiplier)
        self._lifecycle.reset()
        self._last_fill_candle = None

    def snapshot(self) -> PaperSessionSnapshot:
        last = self._fills[-1] if self._fills else None
        return PaperSessionSnapshot(
            pending_entry_number=self._pending.entry_number if self._pending else None,
            entry_count=self._basket.entry_count,
            last_entry_price=last.price if last else None,
            last_entry_fee=last.fee if last else None,
            take_profit_price=self._basket.take_profit_price,
            closed_basket_count=len(self._closed),
        )

    @property
    def realized_pnl(self) -> Decimal:
        return sum(
            (closed.realized_pnl for closed in self._closed),
            Decimal("0"),
        )
```

- [ ] **Step 4: Run focused tests, then fix test prices to cross the computed TP exactly**

Run: `python -m pytest tests/unit/paper/test_paper_spot_session.py -q -vv`

Expected: `2 passed`; assertions must use the actual floor-to-tick TP from the Basket and must not weaken the same-candle prohibition

- [ ] **Step 5: Run full suite and static analysis**

Run: `python -m pytest -q`

Expected: ทุก test ผ่าน

Run: `python -m ruff check .`

Expected: `All checks passed!`

Run: `python -m mypy src`

Expected: `Success: no issues found`

- [ ] **Step 6: Commit Paper session**

```bash
git add src/tiewtrade/paper/session.py tests/unit/paper/test_paper_spot_session.py
git commit -m "feat: execute conservative paper spot sessions"
```

---

### Task 7: Deterministic CSV replay CLI and tracer-bullet acceptance

**Files:**
- Create: `src/tiewtrade/paper/replay.py`
- Create: `src/tiewtrade/paper_replay_main.py`
- Create: `tests/fixtures/btcusdt_5m_tracer.csv`
- Create: `tests/acceptance/test_paper_spot_replay.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `PaperSpotSession`, `PaperSpotSessionConfig`, `SymbolRules`, CSV rows with UTC `open_time,open,high,low,close,volume`
- Produces: `load_candles(path) -> list[Candle]`, `run_replay(candles, config, rules) -> ReplayResult`, CLI exit status 0 and deterministic JSON summary

- [ ] **Step 1: เพิ่ม fixture ที่มีช่วงขาลงสำหรับ RSI reset ช่วงฟื้นตัวสำหรับ entry และ candle ที่แตะ TP**

สร้าง `tests/fixtures/btcusdt_5m_tracer.csv` ด้วยข้อมูล 40 แถวต่อเนื่องนี้:

```csv
open_time,open,high,low,close,volume
2026-01-01T00:00:00+00:00,120,121,118,119,1
2026-01-01T00:05:00+00:00,119,120,117,118,1
2026-01-01T00:10:00+00:00,118,119,116,117,1
2026-01-01T00:15:00+00:00,117,118,115,116,1
2026-01-01T00:20:00+00:00,116,117,114,115,1
2026-01-01T00:25:00+00:00,115,116,113,114,1
2026-01-01T00:30:00+00:00,114,115,112,113,1
2026-01-01T00:35:00+00:00,113,114,111,112,1
2026-01-01T00:40:00+00:00,112,113,110,111,1
2026-01-01T00:45:00+00:00,111,112,109,110,1
2026-01-01T00:50:00+00:00,110,111,108,109,1
2026-01-01T00:55:00+00:00,109,110,107,108,1
2026-01-01T01:00:00+00:00,108,109,106,107,1
2026-01-01T01:05:00+00:00,107,108,105,106,1
2026-01-01T01:10:00+00:00,106,107,104,105,1
2026-01-01T01:15:00+00:00,105,106,103,104,1
2026-01-01T01:20:00+00:00,104,106,103,105,1
2026-01-01T01:25:00+00:00,105,107,104,106,1
2026-01-01T01:30:00+00:00,106,108,105,107,1
2026-01-01T01:35:00+00:00,107,109,106,108,1
2026-01-01T01:40:00+00:00,108,110,107,109,1
2026-01-01T01:45:00+00:00,109,111,108,110,1
2026-01-01T01:50:00+00:00,110,112,109,111,1
2026-01-01T01:55:00+00:00,111,113,110,112,1
2026-01-01T02:00:00+00:00,112,114,111,113,1
2026-01-01T02:05:00+00:00,113,115,112,114,1
2026-01-01T02:10:00+00:00,114,116,113,115,1
2026-01-01T02:15:00+00:00,115,117,114,116,1
2026-01-01T02:20:00+00:00,116,118,115,117,1
2026-01-01T02:25:00+00:00,117,119,116,118,1
2026-01-01T02:30:00+00:00,118,120,117,119,1
2026-01-01T02:35:00+00:00,119,121,118,120,1
2026-01-01T02:40:00+00:00,120,122,119,121,1
2026-01-01T02:45:00+00:00,121,123,120,122,1
2026-01-01T02:50:00+00:00,122,124,121,123,1
2026-01-01T02:55:00+00:00,123,125,122,124,1
2026-01-01T03:00:00+00:00,124,126,123,125,1
2026-01-01T03:05:00+00:00,125,127,124,126,1
2026-01-01T03:10:00+00:00,126,128,125,127,1
2026-01-01T03:15:00+00:00,127,129,126,128,1
```

- [ ] **Step 2: เขียน failing acceptance test ที่ replay ซ้ำสองครั้ง**

```python
# tests/acceptance/test_paper_spot_replay.py
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from tiewtrade.paper.replay import load_candles, run_replay
from tiewtrade.paper.session_config import PaperSpotSessionConfig
from tiewtrade.trading.symbol_rules import SymbolRules


FIXTURE = Path("tests/fixtures/btcusdt_5m_tracer.csv")


def config() -> PaperSpotSessionConfig:
    return PaperSpotSessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000010"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        available_capital=Decimal("1000"),
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("2"),
    )


def test_replay_is_deterministic_and_closes_a_basket() -> None:
    candles = load_candles(FIXTURE)
    rules = SymbolRules(Decimal("0.1"), Decimal("0.001"), Decimal("5"))

    first = run_replay(candles, config(), rules)
    second = run_replay(candles, config(), rules)

    assert first == second
    assert first.accepted_candles == len(candles)
    assert first.closed_basket_count == 1
    assert first.realized_pnl != Decimal("0")
```

- [ ] **Step 3: Run acceptance test เพื่อยืนยัน failure**

Run: `python -m pytest tests/acceptance/test_paper_spot_replay.py -q`

Expected: FAIL เพราะ `paper/replay.py` ยังไม่มี

- [ ] **Step 4: Implement strict CSV loading และ replay result**

```python
# src/tiewtrade/paper/replay.py
import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from tiewtrade.market_data.candle import Candle
from tiewtrade.paper.session import PaperSpotSession
from tiewtrade.paper.session_config import PaperSpotSessionConfig
from tiewtrade.trading.symbol_rules import SymbolRules


@dataclass(frozen=True, slots=True)
class ReplayResult:
    accepted_candles: int
    entry_count: int
    closed_basket_count: int
    realized_pnl: Decimal


def load_candles(path: Path) -> list[Candle]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            Candle(
                symbol="BTCUSDT",
                open_time=datetime.fromisoformat(row["open_time"]),
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=Decimal(row["volume"]),
            )
            for row in csv.DictReader(handle)
        ]


def run_replay(
    candles: list[Candle],
    config: PaperSpotSessionConfig,
    rules: SymbolRules,
) -> ReplayResult:
    session = PaperSpotSession.create(config, rules)
    accepted = sum(
        1 for candle in candles if session.on_candle(candle, candle.close_time)
    )
    snapshot = session.snapshot()
    return ReplayResult(
        accepted_candles=accepted,
        entry_count=snapshot.entry_count,
        closed_basket_count=snapshot.closed_basket_count,
        realized_pnl=session.realized_pnl,
    )
```

- [ ] **Step 5: Implement CLI ที่พิมพ์ JSON แบบ stable**

```python
# src/tiewtrade/paper_replay_main.py
import argparse
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from tiewtrade.paper.replay import load_candles, run_replay
from tiewtrade.paper.session_config import PaperSpotSessionConfig
from tiewtrade.trading.symbol_rules import SymbolRules


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay BTCUSDT 5m Paper Spot candles")
    parser.add_argument("csv", type=Path)
    parser.add_argument("--capital", type=Decimal, default=Decimal("1000"))
    args = parser.parse_args()
    config = PaperSpotSessionConfig(
        session_id=UUID("00000000-0000-0000-0000-000000000010"),
        account_profile_id=UUID("00000000-0000-0000-0000-000000000001"),
        preset_version="rsi-step-grid-v1",
        available_capital=args.capital,
        fee_rate=Decimal("0.001"),
        slippage_bps=Decimal("2"),
    )
    result = run_replay(
        load_candles(args.csv),
        config,
        SymbolRules(Decimal("0.1"), Decimal("0.001"), Decimal("5")),
    )
    payload = {key: str(value) if isinstance(value, Decimal) else value for key, value in asdict(result).items()}
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run acceptance twice and compare stable output**

Run: `python -m pytest tests/acceptance/test_paper_spot_replay.py -q`

Expected: `1 passed`

Run: `python -m tiewtrade.paper_replay_main tests/fixtures/btcusdt_5m_tracer.csv`

Expected: JSON มี `"accepted_candles": 40`, `"closed_basket_count": 1` และ `"realized_pnl"` เป็น string decimal ที่ไม่เท่ากับ `"0"`

Run คำสั่ง CLI เดิมครั้งที่สอง

Expected: output ตรงกับครั้งแรกทุกตัวอักษร

- [ ] **Step 7: Run final verification**

Run: `python -m ruff format .`

Expected: Python files ถูก format สำเร็จ

Run: `python -m pytest --cov=tiewtrade --cov-report=term-missing -q`

Expected: ทุก test ผ่าน และไม่มี uncovered branch ใน `strategy.py`, `entry_pair.py`, `basket.py` หรือ `paper/session.py` ที่เกี่ยวกับกฎในแผนนี้

Run: `python -m ruff check .`

Expected: `All checks passed!`

Run: `python -m ruff format --check .`

Expected: files already formatted

Run: `python -m mypy src`

Expected: `Success: no issues found`

Run: `git diff --check`

Expected: ไม่มี output

- [ ] **Step 8: Document and commit tracer bullet**

````markdown
# TiewTrade V2

Binance Trading Bot แบบ Paper-first สำหรับ Internal Alpha ปัจจุบัน tracer bullet รองรับเฉพาะ deterministic BTCUSDT 5-minute Paper Spot replay โดยไม่เชื่อมบัญชี Binance และไม่ส่ง Live order

## ติดตั้ง Development Environment

```bash
python -m pip install -e ".[dev]"
```

## ตรวจสอบ

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
```

## รัน Paper Spot Replay

```bash
python -m tiewtrade.paper_replay_main tests/fixtures/btcusdt_5m_tracer.csv
```
````

จากนั้น commit:

```bash
git add README.md src/tiewtrade tests
git commit -m "feat: complete paper spot replay tracer bullet"
```

## Completion Evidence

ก่อนปิดแผน ผู้ implement ต้องรายงาน:

- commit hashes ของ Tasks 1–7
- output สรุปจาก pytest, Ruff, format check, mypy และ `git diff --check`
- JSON output จาก deterministic replay สองครั้ง
- ข้อจำกัดที่ยังเหลือตาม Scope Boundary โดยไม่เรียกงานนี้ว่า “Paper Trading Complete”
