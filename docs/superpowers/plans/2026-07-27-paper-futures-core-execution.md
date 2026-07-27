# Paper Futures Core and Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ส่งมอบ headless Paper Futures Session ที่ใช้ shared side-aware business rules, deterministic Cross Margin และ Liquidation โดยไม่เรียก Binance Private API หรือส่ง Live order

**Architecture:** ขยาย shared `trading` model ให้รองรับ Position Side, Futures policy, capital และ margin calculations โดยคง Paper Spot behaviour เดิม จากนั้นเพิ่ม concrete `PaperFuturesExecutor` และ `PaperFuturesSession` แยกจาก Spot; RSI Step Grid Preset v1 ยังคงสร้างเฉพาะ Long Intent และ DEV-95 รับผิดชอบ persistence ภายหลัง

**Tech Stack:** Python 3.12, immutable dataclasses, `Decimal`, `pytest`, Ruff, mypy, Node documentation checks

## Global Constraints

- ใช้ BTCUSDT เป็น acceptance scenario แต่ห้าม hardcode symbol หรือ timeframe ใน business logic
- RSI Step Grid Preset v1 ยังสร้างเฉพาะ Long Intent; execution contracts รองรับ Long และ Short
- Paper Futures ใช้ One-way Mode, Cross Margin และ leverage จำนวนเต็ม 1x–5x
- Trading Capital และ Collateral Buffer เท่ากับ 50% ของ Available Capital อย่างละส่วน
- Versioned Paper Futures Policy v1 ใช้ `maintenance_margin_rate = Decimal("0.005")`
- Paper Futures v1 บันทึก Funding Fee เป็น `Decimal("0.00")`
- ใช้ Session `fee_rate` และ `slippage_bps` กับ Entry, Take Profit และ Liquidation
- Liquidation ใช้ completed-candle OHLC, gap-aware conservative fill และชนะ Take Profit เมื่อ intrabar กำกวม
- Basket ที่ Liquidated เป็น `CLOSED` พร้อม `close_reason = LIQUIDATION`; Session เป็น terminal `LIQUIDATED`
- Paper และ Live ใช้ shared business/risk policies แต่ใช้ execution adapters แยกกัน
- ห้ามสร้าง generic executor interface, registry หรือ factory ใน plan นี้
- ห้ามเพิ่ม SQLite persistence, Trade History mapping, Desktop UI, Recovery, API Key, Private Binance endpoint หรือ Live order
- ใช้ TDD ทุก Task: failing test → minimal implementation → refactor → focused/full verification

---

## Planned File Structure

| File | Responsibility |
| --- | --- |
| `src/tiewtrade/trading/position.py` | `PositionSide` contract |
| `src/tiewtrade/trading/futures_policy.py` | immutable/versioned Futures Session policy |
| `src/tiewtrade/trading/capital.py` | Spot และ Futures capital plans |
| `src/tiewtrade/trading/futures_margin.py` | Cross Margin equity, maintenance margin และ liquidation threshold |
| `src/tiewtrade/trading/basket.py` | shared side-aware Basket, Take Profit, close reason และ PnL |
| `src/tiewtrade/execution/paper_futures.py` | deterministic Paper Futures Entry/TP/Liquidation fills |
| `src/tiewtrade/application/paper_futures_session.py` | completed-candle orchestration และ terminal Liquidation state |
| `tests/unit/**` | business/execution/application invariants |
| `tests/acceptance/test_paper_futures_session.py` | configured deterministic acceptance scenario |

---

### Task 1: Add Futures Session Policy and Source-of-Truth Contracts

**Files:**
- Create: `src/tiewtrade/trading/futures_policy.py`
- Modify: `src/tiewtrade/trading/session_config.py`
- Modify: `tests/unit/trading/test_session_config.py`
- Modify: `tests/unit/application/test_public_market_data_runtime_composition.py`
- Create: `tests/unit/trading/test_futures_policy.py`
- Modify: `PRODUCT.md`
- Modify: `CONTEXT.md`
- Modify: `ARCHITECTURE.md`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: existing `SessionConfig`, `MarketType`, `TradeMode`
- Produces: `MarginMode`, `PositionMode`, `FuturesTradingPolicy.v1(leverage: int) -> FuturesTradingPolicy`; `SessionConfig.futures_policy`

- [ ] **Step 1: Update Source of Truth before production code**

Apply the decisions to these exact source-of-truth locations before production code:

- `PRODUCT.md` sections 7.2, 8 and 15.1: declare the 50/50 split, 1x–5x immutable
  leverage, One-way/Cross constraints, deterministic terminal Liquidation and v1
  Funding Fee `0.00`.
- `CONTEXT.md` after Market Type and under Policy Boundaries: define `Position Side`,
  `Futures Trading Policy`, `Liquidation` and `Basket Close Reason` once, using the
  vocabulary from the approved design.
- `ARCHITECTURE.md` under Shared Business Rules, Execution Adapters and Dependency
  Direction: assign side-aware PnL/margin policy to `trading`, Paper fills to
  `execution`, and completed-candle orchestration to `application`; forbid reverse
  dependencies and Binance Private API access.
- `PROJECT_PLAN.md` Milestone 3 and Module Ownership: place Paper Futures Core and
  Execution before DEV-95 and record the prerequisite relation.

Use these exact decisions without duplicating terminology:

```markdown
- Paper Futures execution contract รองรับ `LONG` และ `SHORT` แต่ RSI Step Grid Preset v1 ยังสร้างเฉพาะ `LONG`
- Internal Alpha ใช้ One-way Mode และ Cross Margin เท่านั้น
- leverage เป็นจำนวนเต็ม 1x–5x และตรึงตลอด Session
- Paper Futures Policy v1 ใช้ Maintenance Margin Rate 0.5% แบบ deterministic ไม่อ้างว่าเท่ากับ Binance Mark Price หรือ Maintenance Margin Tier จริง
- Liquidation ปิด Basket ด้วย `close_reason = LIQUIDATION`, เปลี่ยน Session เป็น terminal `LIQUIDATED` และห้ามสร้าง Entry ใหม่
```

In `PROJECT_PLAN.md`, place Paper Futures Core and Execution before DEV-95, and state that DEV-95 remains blocked until the concrete executor and shared Futures PnL policy are complete.

- [ ] **Step 2: Write failing Futures policy tests**

```python
from decimal import Decimal

import pytest

from tiewtrade.trading.futures_policy import (
    FuturesTradingPolicy,
    MarginMode,
    PositionMode,
)


def test_v1_futures_policy_uses_approved_constants() -> None:
    policy = FuturesTradingPolicy.v1(leverage=3)

    assert policy.version == "paper-futures-v1"
    assert policy.leverage == 3
    assert policy.trading_capital_ratio == Decimal("0.5")
    assert policy.collateral_buffer_ratio == Decimal("0.5")
    assert policy.maintenance_margin_rate == Decimal("0.005")
    assert policy.margin_mode is MarginMode.CROSS
    assert policy.position_mode is PositionMode.ONE_WAY


@pytest.mark.parametrize("leverage", [0, 6, 1.5, True])
def test_v1_futures_policy_rejects_invalid_leverage(leverage: object) -> None:
    with pytest.raises(ValueError, match="leverage"):
        FuturesTradingPolicy.v1(leverage=leverage)  # type: ignore[arg-type]
```

Add negative tests for both the direct constructor and `dataclasses.replace` that
reject an unknown version, altered 50/50 capital ratios, and an altered v1 Maintenance
Margin Rate. Only leverage may vary within the approved integer range 1–5x.

Append SessionConfig tests that prove Spot and Futures policies are mutually exclusive:

```python
def test_futures_session_requires_futures_policy() -> None:
    with pytest.raises(ValueError, match="futures_policy"):
        make_session(market_type=MarketType.FUTURES, spot_policy=None)


def test_futures_session_rejects_spot_policy() -> None:
    with pytest.raises(ValueError, match="spot_policy"):
        make_session(
            market_type=MarketType.FUTURES,
            spot_policy=SpotTradingPolicy(trading_capital_ratio=Decimal("0.8")),
            futures_policy=FuturesTradingPolicy.v1(leverage=3),
        )


def test_spot_session_rejects_futures_policy() -> None:
    with pytest.raises(ValueError, match="futures_policy"):
        make_session(futures_policy=FuturesTradingPolicy.v1(leverage=3))
```

Update the existing parametrized
`test_session_configuration_supports_each_mode_and_market` so Futures cases pass
`futures_policy=FuturesTradingPolicy.v1(leverage=3)` and Spot cases pass
`futures_policy=None`. Keep both Paper and Live combinations as configuration-only
tests; constructing a Live config must not start execution.

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_futures_policy.py tests/unit/trading/test_session_config.py -q
```

Expected: collection fails because `tiewtrade.trading.futures_policy` and `SessionConfig.futures_policy` do not exist.

- [ ] **Step 4: Implement the immutable Futures policy**

Create `src/tiewtrade/trading/futures_policy.py`:

```python
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class MarginMode(StrEnum):
    CROSS = "cross"


class PositionMode(StrEnum):
    ONE_WAY = "one_way"


@dataclass(frozen=True, slots=True)
class FuturesTradingPolicy:
    version: str
    leverage: int
    trading_capital_ratio: Decimal
    collateral_buffer_ratio: Decimal
    maintenance_margin_rate: Decimal
    margin_mode: MarginMode
    position_mode: PositionMode

    def __post_init__(self) -> None:
        if self.version != "paper-futures-v1":
            raise ValueError("version must be paper-futures-v1")
        if isinstance(self.leverage, bool) or not isinstance(self.leverage, int):
            raise ValueError("leverage must be an integer")
        if not 1 <= self.leverage <= 5:
            raise ValueError("leverage must be between 1 and 5")
        if self.trading_capital_ratio != Decimal("0.5"):
            raise ValueError("trading_capital_ratio must be 0.5")
        if self.collateral_buffer_ratio != Decimal("0.5"):
            raise ValueError("collateral_buffer_ratio must be 0.5")
        if self.maintenance_margin_rate != Decimal("0.005"):
            raise ValueError("maintenance_margin_rate must be 0.005")
        if self.margin_mode is not MarginMode.CROSS:
            raise ValueError("Paper Futures requires Cross Margin")
        if self.position_mode is not PositionMode.ONE_WAY:
            raise ValueError("Paper Futures requires One-way Mode")

    @classmethod
    def v1(cls, leverage: int) -> "FuturesTradingPolicy":
        return cls(
            version="paper-futures-v1",
            leverage=leverage,
            trading_capital_ratio=Decimal("0.5"),
            collateral_buffer_ratio=Decimal("0.5"),
            maintenance_margin_rate=Decimal("0.005"),
            margin_mode=MarginMode.CROSS,
            position_mode=PositionMode.ONE_WAY,
        )
```

Add to `SessionConfig` after `spot_policy`:

```python
futures_policy: FuturesTradingPolicy | None = None
```

Extend `SessionConfig.__post_init__`:

```python
if self.market_type is MarketType.SPOT and self.futures_policy is not None:
    raise ValueError("futures_policy is not valid for Spot sessions")
if self.market_type is MarketType.FUTURES and self.futures_policy is None:
    raise ValueError("futures_policy is required for Futures sessions")
if self.market_type is MarketType.FUTURES and self.spot_policy is not None:
    raise ValueError("spot_policy is not valid for Futures sessions")
```

- [ ] **Step 5: Run focused and regression tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_futures_policy.py tests/unit/trading/test_session_config.py tests/acceptance/test_paper_spot_replay.py -q
```

Expected: all pass and Paper Spot replay remains unchanged.

- [ ] **Step 6: Run static checks and commit**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add PRODUCT.md CONTEXT.md ARCHITECTURE.md PROJECT_PLAN.md docs/superpowers/plans/2026-07-27-paper-futures-core-execution.md src/tiewtrade/trading/futures_policy.py src/tiewtrade/trading/session_config.py tests/unit/application/test_public_market_data_runtime_composition.py tests/unit/trading/test_futures_policy.py tests/unit/trading/test_session_config.py
git commit -m "feat: define Paper Futures session policy"
```

---

### Task 2: Make Basket and Entry Intent Side-aware

**Files:**
- Create: `src/tiewtrade/trading/position.py`
- Modify: `src/tiewtrade/trading/basket.py`
- Modify: `src/tiewtrade/strategies/rsi_step_grid/strategy.py`
- Modify: `tests/unit/trading/test_basket.py`
- Modify: `tests/unit/strategies/test_rsi_step_grid_strategy.py`
- Verify: `tests/acceptance/test_paper_spot_replay.py`

**Interfaces:**
- Consumes: `EntryPolicy`, existing `Basket`, `EntryIntent`
- Produces: `PositionSide`, `BasketCloseReason`; side-aware `Basket(..., position_side=PositionSide.LONG)`, `Basket.add_entry(..., position_side)`, `Basket.close(..., close_reason)`; `EntryIntent.side`

- [ ] **Step 1: Write failing side-aware Basket tests**

```python
from tiewtrade.trading.basket import BasketCloseReason
from tiewtrade.trading.position import PositionSide


def test_short_basket_reprices_take_profit_below_average_and_rounds_up() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.SHORT,
    )
    basket.add_entry(
        position_side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("1"),
        fee=Decimal("0.1"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("1.03"),
        tick_size=Decimal("0.1"),
    )
    assert basket.take_profit_price == Decimal("97.0")


def test_short_basket_close_calculates_directional_pnl() -> None:
    basket = short_basket_with_entry(price=Decimal("100"), quantity=Decimal("2"))
    closed = basket.close(
        exit_price=Decimal("90"),
        exit_fee=Decimal("0.18"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
        close_reason=BasketCloseReason.TAKE_PROFIT,
    )
    assert closed.position_side is PositionSide.SHORT
    assert closed.close_reason is BasketCloseReason.TAKE_PROFIT
    assert closed.gross_realized_pnl == Decimal("20")


def test_one_way_basket_rejects_opposite_side_without_mutation() -> None:
    basket = Basket(
        basket_id=basket_id(),
        policy=policy(),
        take_profit_atr_multiplier=Decimal("3"),
        position_side=PositionSide.LONG,
    )
    with pytest.raises(ValueError, match="opposite"):
        basket.add_entry(
            position_side=PositionSide.SHORT,
            price=Decimal("100"),
            quantity=Decimal("1"),
            fee=Decimal("0.1"),
            filled_at=datetime(2026, 1, 1, tzinfo=UTC),
            atr=Decimal("2"),
            tick_size=Decimal("0.1"),
        )
    assert basket.entry_count == 0
```

Append a Strategy test:

```python
def test_preset_v1_entry_intent_is_explicitly_long() -> None:
    intent = trigger_entry_intent()
    assert intent is not None
    assert intent.side is PositionSide.LONG
```

- [ ] **Step 2: Run tests to verify RED**

```bash
.venv/bin/python -m pytest tests/unit/trading/test_basket.py tests/unit/strategies/test_rsi_step_grid_strategy.py -q
```

Expected: import/constructor failures for `PositionSide`, `BasketCloseReason` and `EntryIntent.side`.

- [ ] **Step 3: Add Position Side and side-aware Basket behaviour**

Create `src/tiewtrade/trading/position.py`:

```python
from enum import StrEnum


class PositionSide(StrEnum):
    LONG = "long"
    SHORT = "short"
```

Add to `basket.py`:

```python
from enum import StrEnum
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal

from tiewtrade.trading.position import PositionSide


class BasketCloseReason(StrEnum):
    TAKE_PROFIT = "take_profit"
    LIQUIDATION = "liquidation"
```

Add backward-compatible
`position_side: PositionSide = PositionSide.LONG` and
`close_reason: BasketCloseReason = BasketCloseReason.TAKE_PROFIT` after the existing
required fields on `ClosedBasket`; existing Paper Spot persistence fixtures therefore
keep constructing the same Long/Take Profit record without edits. Add
`position_side: PositionSide = PositionSide.LONG` to `Basket.__init__`, expose a
`position_side` property, and add this property for accumulated entry fees:

```python
@property
def entry_fees(self) -> Decimal:
    return sum((entry.fee for entry in self._entries), Decimal("0"))
```

In `add_entry`, accept `position_side: PositionSide = PositionSide.LONG`, validate it
before appending, and calculate the target as follows:

```python
if position_side is not self.position_side:
    raise ValueError("opposite-side Entry is not allowed in One-way Mode")

if self.position_side is PositionSide.LONG:
    raw_target = self.average_entry_price + (
        atr * self._take_profit_atr_multiplier
    )
    rounding = ROUND_DOWN
else:
    raw_target = self.average_entry_price - (
        atr * self._take_profit_atr_multiplier
    )
    rounding = ROUND_CEILING
if raw_target <= 0:
    raise ValueError("take profit price must be positive")
self.take_profit_price = (raw_target / tick_size).to_integral_value(
    rounding=rounding
) * tick_size
```

In `close`, accept
`close_reason: BasketCloseReason = BasketCloseReason.TAKE_PROFIT` and calculate:

```python
if self.position_side is PositionSide.LONG:
    gross_realized_pnl = sum(
        ((exit_price - entry.price) * entry.quantity for entry in self._entries),
        Decimal("0"),
    )
else:
    gross_realized_pnl = sum(
        ((entry.price - exit_price) * entry.quantity for entry in self._entries),
        Decimal("0"),
    )
```

Set `position_side` and `close_reason` on the returned `ClosedBasket`.

Add `side: PositionSide = PositionSide.LONG` after `atr` on `EntryIntent`, preserving
all existing constructor call sites, and set
`side=PositionSide.LONG` when Preset v1 creates an intent. Do not add side to the v1
intent identity hash, so existing Paper Spot deterministic IDs remain unchanged.

- [ ] **Step 4: Run focused tests and Paper Spot regressions**

```bash
.venv/bin/python -m pytest tests/unit/trading/test_basket.py tests/unit/strategies/test_rsi_step_grid_strategy.py tests/unit/application/test_paper_spot_session.py tests/acceptance/test_paper_spot_replay.py -q
```

Expected: all pass and the existing stable Paper Spot summary remains byte-for-byte unchanged.

- [ ] **Step 5: Run static checks and commit**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/trading/position.py src/tiewtrade/trading/basket.py src/tiewtrade/strategies/rsi_step_grid/strategy.py tests/unit/trading/test_basket.py tests/unit/strategies/test_rsi_step_grid_strategy.py
git commit -m "feat: make Basket side-aware"
```

---

### Task 3: Add Futures Capital and Deterministic Margin Model

**Files:**
- Modify: `src/tiewtrade/trading/capital.py`
- Create: `src/tiewtrade/trading/futures_margin.py`
- Modify: `tests/unit/trading/test_capital.py`
- Create: `tests/unit/trading/test_futures_margin.py`

**Interfaces:**
- Consumes: `FuturesTradingPolicy`, `EntryPolicy`, `PositionSide`
- Produces: `FuturesCapitalPlan.from_available(available, futures_policy, entry_policy)`; `FuturesMarginModel(policy).snapshot(...)`; `FuturesMarginSnapshot`

- [ ] **Step 1: Write failing capital and margin tests**

```python
def test_futures_capital_plan_uses_half_for_trading_and_half_for_buffer() -> None:
    plan = FuturesCapitalPlan.from_available(
        Decimal("200000"),
        FuturesTradingPolicy.v1(leverage=3),
        EntryPolicy(max_entries=10),
    )
    assert plan.trading_capital == Decimal("100000.0")
    assert plan.collateral_buffer == Decimal("100000.0")
    assert plan.initial_margin_per_entry == Decimal("10000.0")
    assert plan.target_notional_per_entry == Decimal("30000.0")
```

Create margin tests with exact formulas:

```python
def test_long_liquidation_threshold_uses_cross_account_equity() -> None:
    model = FuturesMarginModel(FuturesTradingPolicy.v1(leverage=3))
    price = model.liquidation_price(
        side=PositionSide.LONG,
        average_entry_price=Decimal("100"),
        quantity=Decimal("3000"),
        available_capital=Decimal("200000"),
        accumulated_entry_fees=Decimal("30"),
    )
    expected = (
        Decimal("100") * Decimal("3000") - Decimal("199970")
    ) / (Decimal("3000") * Decimal("0.995"))
    assert price == expected


def test_short_liquidation_threshold_is_above_entry() -> None:
    model = FuturesMarginModel(FuturesTradingPolicy.v1(leverage=3))
    price = model.liquidation_price(
        side=PositionSide.SHORT,
        average_entry_price=Decimal("100"),
        quantity=Decimal("3000"),
        available_capital=Decimal("200000"),
        accumulated_entry_fees=Decimal("30"),
    )
    expected = (
        Decimal("199970") + Decimal("100") * Decimal("3000")
    ) / (Decimal("3000") * Decimal("1.005"))
    assert price == expected


def test_long_threshold_returns_none_when_equity_covers_all_positive_prices() -> None:
    model = FuturesMarginModel(FuturesTradingPolicy.v1(leverage=3))
    assert model.liquidation_price(
        side=PositionSide.LONG,
        average_entry_price=Decimal("100"),
        quantity=Decimal("1"),
        available_capital=Decimal("200000"),
        accumulated_entry_fees=Decimal("0"),
    ) is None


def test_entry_fees_reduce_account_equity() -> None:
    model = FuturesMarginModel(FuturesTradingPolicy.v1(leverage=3))
    snapshot = model.snapshot(
        side=PositionSide.LONG,
        average_entry_price=Decimal("100"),
        quantity=Decimal("3000"),
        available_capital=Decimal("200000"),
        accumulated_entry_fees=Decimal("30"),
        current_price=Decimal("90"),
    )
    assert snapshot.account_equity == Decimal("169970")
    assert snapshot.maintenance_margin == Decimal("1350.000")
    assert not snapshot.is_liquidated
```

- [ ] **Step 2: Run tests to verify RED**

```bash
.venv/bin/python -m pytest tests/unit/trading/test_capital.py tests/unit/trading/test_futures_margin.py -q
```

Expected: failures because `FuturesCapitalPlan` and `FuturesMarginModel` do not exist.

- [ ] **Step 3: Implement Futures capital allocation**

Append to `capital.py`:

```python
@dataclass(frozen=True, slots=True)
class FuturesCapitalPlan:
    available_capital: Decimal
    trading_capital: Decimal
    collateral_buffer: Decimal
    initial_margin_per_entry: Decimal
    target_notional_per_entry: Decimal

    @classmethod
    def from_available(
        cls,
        available: Decimal,
        futures_policy: FuturesTradingPolicy,
        entry_policy: EntryPolicy,
    ) -> "FuturesCapitalPlan":
        if not available.is_finite() or available <= 0:
            raise ValueError("available capital must be finite and positive")
        trading_capital = available * futures_policy.trading_capital_ratio
        collateral_buffer = available * futures_policy.collateral_buffer_ratio
        initial_margin = trading_capital / Decimal(entry_policy.max_entries)
        return cls(
            available_capital=available,
            trading_capital=trading_capital,
            collateral_buffer=collateral_buffer,
            initial_margin_per_entry=initial_margin,
            target_notional_per_entry=(
                initial_margin * Decimal(futures_policy.leverage)
            ),
        )
```

- [ ] **Step 4: Implement the deterministic margin model**

Create `futures_margin.py`:

```python
from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.trading.position import PositionSide


@dataclass(frozen=True, slots=True)
class FuturesMarginSnapshot:
    account_equity: Decimal
    maintenance_margin: Decimal
    liquidation_price: Decimal | None
    is_liquidated: bool


class FuturesMarginModel:
    def __init__(self, policy: FuturesTradingPolicy) -> None:
        self._policy = policy

    def liquidation_price(
        self,
        *,
        side: PositionSide,
        average_entry_price: Decimal,
        quantity: Decimal,
        available_capital: Decimal,
        accumulated_entry_fees: Decimal,
    ) -> Decimal | None:
        self._validate_inputs(
            average_entry_price,
            quantity,
            available_capital,
            accumulated_entry_fees,
        )
        wallet = available_capital - accumulated_entry_fees
        rate = self._policy.maintenance_margin_rate
        if side is PositionSide.LONG:
            threshold = (
                average_entry_price * quantity - wallet
            ) / (quantity * (Decimal("1") - rate))
            return threshold if threshold > 0 else None
        return (wallet + average_entry_price * quantity) / (
            quantity * (Decimal("1") + rate)
        )

    def snapshot(
        self,
        *,
        side: PositionSide,
        average_entry_price: Decimal,
        quantity: Decimal,
        available_capital: Decimal,
        accumulated_entry_fees: Decimal,
        current_price: Decimal,
    ) -> FuturesMarginSnapshot:
        if not current_price.is_finite() or current_price <= 0:
            raise ValueError("current_price must be finite and positive")
        liquidation_price = self.liquidation_price(
            side=side,
            average_entry_price=average_entry_price,
            quantity=quantity,
            available_capital=available_capital,
            accumulated_entry_fees=accumulated_entry_fees,
        )
        if side is PositionSide.LONG:
            unrealized_pnl = (current_price - average_entry_price) * quantity
        else:
            unrealized_pnl = (average_entry_price - current_price) * quantity
        account_equity = (
            available_capital - accumulated_entry_fees + unrealized_pnl
        )
        maintenance_margin = (
            current_price * quantity * self._policy.maintenance_margin_rate
        )
        return FuturesMarginSnapshot(
            account_equity=account_equity,
            maintenance_margin=maintenance_margin,
            liquidation_price=liquidation_price,
            is_liquidated=account_equity <= maintenance_margin,
        )

    @staticmethod
    def _validate_inputs(
        average_entry_price: Decimal,
        quantity: Decimal,
        available_capital: Decimal,
        accumulated_entry_fees: Decimal,
    ) -> None:
        if not average_entry_price.is_finite() or average_entry_price <= 0:
            raise ValueError("average_entry_price must be finite and positive")
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("quantity must be finite and positive")
        if not available_capital.is_finite() or available_capital <= 0:
            raise ValueError("available_capital must be finite and positive")
        if not accumulated_entry_fees.is_finite() or accumulated_entry_fees < 0:
            raise ValueError("accumulated_entry_fees must be finite and non-negative")
        if accumulated_entry_fees >= available_capital:
            raise ValueError("entry fees must remain below available capital")
```

- [ ] **Step 5: Run focused tests and static checks**

```bash
.venv/bin/python -m pytest tests/unit/trading/test_capital.py tests/unit/trading/test_futures_margin.py -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/tiewtrade/trading/capital.py src/tiewtrade/trading/futures_margin.py tests/unit/trading/test_capital.py tests/unit/trading/test_futures_margin.py
git commit -m "feat: add deterministic Futures margin model"
```

---

### Task 4: Add Deterministic Paper Futures Executor

**Files:**
- Create: `src/tiewtrade/execution/paper_futures.py`
- Create: `tests/unit/execution/test_paper_futures.py`

**Interfaces:**
- Consumes: `SessionConfig`, `FuturesCapitalPlan`, `PositionSide`, side-aware `Basket`, `SymbolRules`, `Candle`, `EntryIntent`
- Produces: `PaperFuturesEntryFill`, `PaperFuturesExitFill`; `PaperFuturesExecutor.fill_entry`, `fill_take_profit`, `fill_liquidation`

- [ ] **Step 1: Write failing executor tests**

```python
def test_long_entry_uses_next_open_adverse_slippage_and_target_notional() -> None:
    executor = make_executor(leverage=3, fee_rate="0.001", slippage_bps="10")
    fill = executor.fill_entry(long_intent(), candle(open="100"))
    assert fill is not None
    assert fill.side is PositionSide.LONG
    assert fill.price == Decimal("100.1")
    assert fill.quantity == Decimal("299.7")
    assert fill.fee == fill.price * fill.quantity * Decimal("0.001")


def test_short_entry_uses_adverse_downward_slippage() -> None:
    executor = make_executor(leverage=3, fee_rate="0.001", slippage_bps="10")
    fill = executor.fill_entry(short_intent(), candle(open="100"))
    assert fill is not None
    assert fill.side is PositionSide.SHORT
    assert fill.price == Decimal("99.9")


def test_liquidation_wins_over_take_profit_and_uses_gap_aware_price() -> None:
    executor = make_executor(slippage_bps="10")
    basket = long_basket(entry_price="100", take_profit="106")
    current = candle(open="70", high="110", low="60")
    liquidation = executor.fill_liquidation(
        basket,
        current,
        liquidation_price=Decimal("80"),
    )
    take_profit = executor.fill_take_profit(basket, current)
    assert liquidation is not None
    assert liquidation.close_reason is BasketCloseReason.LIQUIDATION
    assert liquidation.price == Decimal("69.9")
    assert take_profit is not None


def test_repeating_the_same_entry_produces_the_same_fill_identity() -> None:
    executor = make_executor(leverage=3)
    intent = long_intent()
    current = candle(open="100")
    assert executor.fill_entry(intent, current) == executor.fill_entry(intent, current)


def test_entry_below_min_notional_returns_none() -> None:
    executor = make_executor(min_notional="50000", leverage=1)
    assert executor.fill_entry(long_intent(), candle(open="100")) is None
```

The session will choose Liquidation first; the executor tests both independently.

- [ ] **Step 2: Run tests to verify RED**

```bash
.venv/bin/python -m pytest tests/unit/execution/test_paper_futures.py -q
```

Expected: import failure for `paper_futures`.

- [ ] **Step 3: Implement fill contracts and constructor validation**

Create immutable fill records:

```python
@dataclass(frozen=True, slots=True)
class PaperFuturesEntryFill:
    order_id: str
    fill_id: str
    intent_id: str
    side: PositionSide
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime


@dataclass(frozen=True, slots=True)
class PaperFuturesExitFill:
    order_id: str
    fill_id: str
    side: PositionSide
    close_reason: BasketCloseReason
    price: Decimal
    quantity: Decimal
    fee: Decimal
    filled_at: datetime
```

The constructor must require `TradeMode.PAPER`, `MarketType.FUTURES`, and a non-null
`futures_policy`, then build `FuturesCapitalPlan`.

- [ ] **Step 4: Implement side-aware Entry and Take Profit fills**

Use these exact price directions:

```python
if intent.side is PositionSide.LONG:
    raw_price = candle.open * (Decimal("1") + slippage)
    price = self._symbol_rules.ceil_price(raw_price)
else:
    raw_price = candle.open * (Decimal("1") - slippage)
    price = self._symbol_rules.floor_price(raw_price)
```

Quantity is `floor_quantity(target_notional_per_entry / price)` and a failed minimum
notional returns `None` without creating a Fill.

Take Profit triggers and adverse prices:

```python
if basket.position_side is PositionSide.LONG:
    if candle.high < basket.take_profit_price:
        return None
    price = self._symbol_rules.floor_price(
        basket.take_profit_price * (Decimal("1") - slippage)
    )
else:
    if candle.low > basket.take_profit_price:
        return None
    price = self._symbol_rules.ceil_price(
        basket.take_profit_price * (Decimal("1") + slippage)
    )
```

Return `PaperFuturesExitFill` with `close_reason=TAKE_PROFIT`.

- [ ] **Step 5: Implement gap-aware Liquidation fills**

```python
if basket.position_side is PositionSide.LONG:
    if candle.low > liquidation_price:
        return None
    raw_price = min(candle.open, liquidation_price) * (
        Decimal("1") - slippage
    )
    price = self._symbol_rules.floor_price(raw_price)
else:
    if candle.high < liquidation_price:
        return None
    raw_price = max(candle.open, liquidation_price) * (
        Decimal("1") + slippage
    )
    price = self._symbol_rules.ceil_price(raw_price)
```

Reject non-positive fill prices. Return `PaperFuturesExitFill` with
`close_reason=LIQUIDATION`. Entry, TP and Liquidation IDs must be deterministic from
Session, Intent or Basket identity and close reason. Entry fills use
`candle.open_time`; Take Profit and Liquidation fills use `candle.close_time` because
their intrabar trigger is only known after accepting the completed candle.

- [ ] **Step 6: Run focused tests, Spot executor regression and static checks**

```bash
.venv/bin/python -m pytest tests/unit/execution/test_paper_futures.py tests/unit/execution/test_paper_spot.py -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/tiewtrade/execution/paper_futures.py tests/unit/execution/test_paper_futures.py
git commit -m "feat: add Paper Futures executor"
```

---

### Task 5: Compose the Headless Paper Futures Session

**Files:**
- Create: `src/tiewtrade/application/paper_futures_session.py`
- Create: `tests/unit/application/test_paper_futures_session.py`
- Create: `tests/acceptance/test_paper_futures_session.py`

**Interfaces:**
- Consumes: completed `Candle`, `RsiStepGridPreset`, `SessionConfig`, `MarketDataConfig`, `SymbolRules`, `PaperFuturesExecutor`, `FuturesMarginModel`, shared `Basket` and `EntryPairLifecycle`
- Produces: `PaperFuturesSessionState`, `PaperFuturesFailureReason`,
  `PaperFuturesSessionError`, `PaperFuturesSessionSnapshot`,
  `PaperFuturesSession.process_completed_candle`, `warm_up_completed_candles`

- [ ] **Step 1: Write failing session-ordering tests**

```python
def test_entry_fill_can_liquidate_on_the_same_candle() -> None:
    session = make_session_with_pending_long_intent()
    snapshot = session.process_completed_candle(
        liquidation_candle_after_gap_open(),
        received_at=received_at(),
    )
    assert snapshot.entry_fill is not None
    assert snapshot.exit_fill is not None
    assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED
    assert snapshot.closed_basket is not None


def test_liquidation_wins_when_same_candle_touches_take_profit() -> None:
    session = make_session_with_open_long_basket()
    snapshot = session.process_completed_candle(
        candle_touching_take_profit_and_liquidation(),
        received_at=received_at(),
    )
    assert snapshot.exit_fill is not None
    assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
    assert snapshot.state is PaperFuturesSessionState.LIQUIDATED


def test_liquidated_session_rejects_future_candles_without_mutation() -> None:
    session = make_liquidated_session()
    before = session.snapshot
    after = session.process_completed_candle(
        next_completed_candle(),
        received_at=received_at(),
    )
    assert not after.accepted
    assert after.state is before.state
    assert after.closed_basket == before.closed_basket
    assert after.basket_id == before.basket_id
    assert after.basket_entry_count == before.basket_entry_count


def test_unexpected_execution_error_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = make_session()
    monkeypatch.setattr(session._executor, "fill_entry", raise_execution_error)
    with pytest.raises(PaperFuturesSessionError, match="execution failed"):
        session.process_completed_candle(entry_candle(), received_at=received_at())
    assert session.snapshot.state is PaperFuturesSessionState.FAILED_CLOSED
    assert (
        session.snapshot.failure_reason
        is PaperFuturesFailureReason.EXECUTION_ERROR
    )
```

Add a lifecycle test proving a newly recalculated Take Profit cannot fill on the Entry
candle and a test proving normal TP closes/reset the Basket without terminating the
Session.

- [ ] **Step 2: Run unit tests to verify RED**

```bash
.venv/bin/python -m pytest tests/unit/application/test_paper_futures_session.py -q
```

Expected: import failure for `paper_futures_session`.

- [ ] **Step 3: Implement Session state and snapshot contracts**

```python
class PaperFuturesSessionState(StrEnum):
    ACTIVE = "active"
    LIQUIDATED = "liquidated"
    FAILED_CLOSED = "failed_closed"


class PaperFuturesFailureReason(StrEnum):
    EXECUTION_ERROR = "execution_error"


class PaperFuturesSessionError(RuntimeError):
    """Paper Futures stopped because an execution invariant failed."""


@dataclass(frozen=True, slots=True)
class PaperFuturesSessionSnapshot:
    accepted: bool
    state: PaperFuturesSessionState
    pending_intent: EntryIntent | None
    entry_fill: PaperFuturesEntryFill | None
    exit_fill: PaperFuturesExitFill | None
    closed_basket: ClosedBasket | None
    basket_id: UUID | None
    basket_entry_count: int
    position_side: PositionSide | None
    take_profit_price: Decimal | None
    liquidation_price: Decimal | None
    account_equity: Decimal
    capital_plan: FuturesCapitalPlan
    failure_reason: PaperFuturesFailureReason | None
```

The constructor must require Paper/Futures configuration, matching Preset version and
non-null Futures policy. It owns concrete completed-candle stream, indicators, v1
Strategy, Entry Pair lifecycle, Basket, Executor and Margin Model.

- [ ] **Step 4: Implement the completed-candle ordering**

`process_completed_candle` must use this order and return after terminal Liquidation:

```python
if self._state is not PaperFuturesSessionState.ACTIVE:
    return self._snapshot(accepted=False)
if not self._candles.accept(candle, received_at):
    return self._snapshot(accepted=False)

basket_existed_at_open = self._basket is not None
entry_fill = self._fill_pending_intent(candle)
exit_fill = self._fill_liquidation(candle)
if exit_fill is not None:
    closed = self._close_basket(exit_fill)
    self._state = PaperFuturesSessionState.LIQUIDATED
    self._pending_intent = None
    return self._snapshot(
        accepted=True,
        entry_fill=entry_fill,
        exit_fill=exit_fill,
        closed_basket=closed,
    )

closed = None
if basket_existed_at_open and entry_fill is None:
    take_profit_fill = self._fill_take_profit(candle)
    if take_profit_fill is not None:
        closed = self._close_basket(take_profit_fill)
        self._lifecycle.reset()

indicators = self._indicators.update(candle)
self._evaluate_strategy(candle, indicators)
return self._snapshot(
    accepted=True,
    entry_fill=entry_fill,
    exit_fill=take_profit_fill,
    closed_basket=closed,
)
```

Ensure local variables such as `take_profit_fill` are initialized before conditional
branches. On normal TP, clear Basket and allow a new Basket in the same UTC month. On
Liquidation, do not reset lifecycle for reuse because the Session is terminal.

- [ ] **Step 5: Calculate margin and close Basket atomically in memory**

After every Entry, compute `liquidation_price` from current Basket average, quantity,
entry fees and Session available capital. `_fill_liquidation` returns `None` when the
Long threshold is absent. `_close_basket` must pass the Fill reason into `Basket.close`
and include the exit fee. Wrap executor and margin invariant failures in
`PaperFuturesSessionError`, set state to `FAILED_CLOSED`, set failure reason to
`PaperFuturesFailureReason.EXECUTION_ERROR`, clear the pending intent, then re-raise.
Every later candle must return `accepted=False` without changing business state.

- [ ] **Step 6: Add the configured acceptance test**

Build `SessionConfig` and policy through public constructors with:

```python
available_capital=Decimal("200000")
entry_policy=EntryPolicy(max_entries=10)
futures_policy=FuturesTradingPolicy.v1(leverage=3)
market_type=MarketType.FUTURES
trade_mode=TradeMode.PAPER
```

Use BTCUSDT 5m completed candles in two explicit scenarios.

Scenario A proves configured capital facts, a deterministic Long Entry Fill and replay
equality:

```python
assert snapshot.capital_plan.trading_capital == Decimal("100000.0")
assert snapshot.capital_plan.collateral_buffer == Decimal("100000.0")
assert snapshot.capital_plan.initial_margin_per_entry == Decimal("10000.0")
assert snapshot.capital_plan.target_notional_per_entry == Decimal("30000.0")
assert snapshot.entry_fill is not None
assert snapshot.entry_fill.side is PositionSide.LONG
assert replay(candles) == replay(candles)
```

Scenario B uses an explicit adverse completed candle after a Long Entry and proves the
terminal Liquidation outcome:

```python
snapshot = replay(configured_liquidation_candles())[-1]
assert snapshot.exit_fill is not None
assert snapshot.exit_fill.close_reason is BasketCloseReason.LIQUIDATION
assert snapshot.closed_basket is not None
assert snapshot.closed_basket.close_reason is BasketCloseReason.LIQUIDATION
assert snapshot.state is PaperFuturesSessionState.LIQUIDATED
```

- [ ] **Step 7: Run focused, acceptance and Spot regression tests**

```bash
.venv/bin/python -m pytest tests/unit/application/test_paper_futures_session.py tests/acceptance/test_paper_futures_session.py tests/unit/application/test_paper_spot_session.py tests/acceptance/test_paper_spot_replay.py -q
```

Expected: all pass and Paper Spot output remains unchanged.

- [ ] **Step 8: Run static checks and commit**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
git add src/tiewtrade/application/paper_futures_session.py tests/unit/application/test_paper_futures_session.py tests/acceptance/test_paper_futures_session.py
git commit -m "feat: compose Paper Futures session"
```

---

### Task 6: Mark the Design Verified and Run Repository Gates

**Files:**
- Modify: `docs/superpowers/specs/2026-07-27-paper-futures-core-execution-design.md`
- Verify: all `src/`, `tests/`, and `docs-site/`

**Interfaces:**
- Consumes: verified Tasks 1–5
- Produces: implemented/verified design status and complete gate evidence

- [ ] **Step 1: Run the complete Python test suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Run source quality gates**

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 3: Run documentation gates**

```bash
npm --prefix docs-site test
npm --prefix docs-site run check:content
```

Expected: documentation tests and content validation pass.

- [ ] **Step 4: Confirm scope and safety**

```bash
git diff --stat main...HEAD
rg -n "api[_-]?key|secret|private endpoint|live order" src/tiewtrade tests
```

Expected: diff contains only Paper Futures core/execution, source-of-truth docs and
tests; any safety-term matches are assertions prohibiting unsafe behaviour, not
credentials or Live execution paths.

- [ ] **Step 5: Mark the design implemented only after gates pass**

Change:

```markdown
**Status:** Approved for implementation planning
```

to:

```markdown
**Status:** Implemented and verified
```

- [ ] **Step 6: Commit verification documentation**

```bash
git add docs/superpowers/specs/2026-07-27-paper-futures-core-execution-design.md
git commit -m "docs: verify Paper Futures core execution"
```

---

## Final Review Checklist

- [ ] Review the complete range from the design commit to HEAD against the approved spec
- [ ] Confirm Paper Spot deterministic IDs and replay output did not change
- [ ] Confirm no generic execution abstraction was introduced
- [ ] Confirm no SQLite/Trade History implementation duplicated DEV-95
- [ ] Confirm no Binance Private API, credentials or Live order path exists
- [ ] Confirm Liquidation wins ambiguous candles and produces terminal Session state
- [ ] Confirm `origin/main` is not pushed or merged without separate user confirmation
