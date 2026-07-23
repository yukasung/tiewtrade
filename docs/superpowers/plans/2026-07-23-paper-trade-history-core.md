# Paper Trade History Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every Bot-owned Paper Spot BUY/SELL Fill and its Basket-level
Net Realized PnL in SQLite, then expose deterministic paginated queries that a
future Desktop UI can display.

**Architecture:** Trading owns immutable history records and PnL values without
knowing SQLite. A focused SQLite adapter owns schema migration, atomic writes,
idempotency, and read queries. A Paper Spot history mapper converts existing
execution results into the shared records, while a persistence-enabled
application wrapper fails closed if durable recording fails.

**Tech Stack:** Python 3.12, standard-library `sqlite3`, `dataclasses`,
`Decimal`, `UUID`, pytest, Ruff, mypy strict.

## Global Constraints

- Conversation, planning, and Linear Issues use Thai; code identifiers and code
  comments use English.
- The installation uses one Binance Account and one Active Bot Session globally.
- Remove `account_profile_id`; history ownership is keyed directly by
  `session_id`.
- Phase 1 records Paper Spot only through a real producer, while the normalized
  records retain `MarketType` and `TradeMode` for Paper Futures and future Live
  consumers.
- Paper Futures integration is a separate implementation plan after the Paper
  Futures executor exists.
- Desktop UI widgets are a separate implementation plan after the PySide6
  application shell exists. This plan delivers the query API and DTOs consumed
  by that UI.
- Paper Futures persists `funding_fee = Decimal("0")` during its first phase.
- Trade history contains Bot Session records only.
- All persisted money and quantity values use canonical decimal strings; never
  SQLite `REAL` or Python binary floating point.
- All timestamps are timezone-aware UTC values serialized as ISO 8601 strings.
- Trade Fill and Basket Result writes commit or roll back in one SQLite
  transaction.
- SQLite failure blocks further Entry processing; there is no in-memory
  persistence fallback.
- Do not call Binance Private APIs, store credentials, or send Live orders.
- Follow failing test → minimal implementation → refactor for every code task.

---

## File Ownership

| File | Responsibility |
| --- | --- |
| `src/tiewtrade/trading/trade_history.py` | Immutable normalized Basket and Fill records plus validation |
| `src/tiewtrade/integrations/sqlite/database.py` | SQLite connection setup, foreign keys, migration version |
| `src/tiewtrade/integrations/sqlite/trade_history.py` | Atomic idempotent history writes and paginated reads |
| `src/tiewtrade/application/paper_spot_trade_history.py` | Map Paper Spot execution results to normalized history records |
| `src/tiewtrade/application/trade_history_query.py` | Stable application-facing history query API for future UI consumers |
| `src/tiewtrade/application/persistent_paper_spot_session.py` | Compose the Paper Spot Session with mandatory durable history and fail-closed state |
| `tests/unit/trading/test_trade_history.py` | History record invariants |
| `tests/unit/integrations/sqlite/test_trade_history.py` | Migration, atomicity, idempotency, filtering, pagination |
| `tests/unit/application/test_paper_spot_trade_history.py` | Paper Spot mapping and PnL fields |
| `tests/unit/application/test_trade_history_query.py` | Application query delegation and validation |
| `tests/unit/application/test_persistent_paper_spot_session.py` | Recording flow and fail-closed behavior |
| `tests/acceptance/test_paper_spot_trade_history.py` | End-to-end replay, restart, and durable query |

The plan does not create catch-all `models.py`, `repository.py`, `interfaces.py`,
or `utils.py` files.

---

### Task 1: Align Source of Truth and Remove Account Profile Identity

**Files:**

- Modify: `PRODUCT.md`
- Modify: `CONTEXT.md`
- Modify: `ARCHITECTURE.md`
- Modify: `PROJECT_PLAN.md`
- Modify: `docs-site/content/product.mdx`
- Modify: `docs-site/content/domain.mdx`
- Modify: `docs-site/content/architecture.mdx`
- Modify: `docs-site/content/delivery.mdx`
- Modify: `src/tiewtrade/trading/session_config.py`
- Modify: `src/tiewtrade/paper_replay_main.py`
- Modify: all tests constructing `SessionConfig`
- Test: `tests/unit/trading/test_session_config.py`

**Interfaces:**

- Produces:

```python
@dataclass(frozen=True, slots=True)
class SessionConfig:
    session_id: UUID
    preset_version: str
    market_type: MarketType
    trade_mode: TradeMode
    available_capital: Decimal
    fee_rate: Decimal
    slippage_bps: Decimal
    entry_policy: EntryPolicy
    spot_policy: SpotTradingPolicy | None
```

- [ ] **Step 1: Add a failing single-account configuration test**

Add to `tests/unit/trading/test_session_config.py`:

```python
from dataclasses import fields


def test_session_config_is_owned_directly_by_the_session() -> None:
    field_names = {field.name for field in fields(SessionConfig)}

    assert "session_id" in field_names
    assert "account_profile_id" not in field_names
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/trading/test_session_config.py::test_session_config_is_owned_directly_by_the_session \
  -q
```

Expected: FAIL because `account_profile_id` is still a `SessionConfig` field.

- [ ] **Step 3: Remove Account Profile from code and fixtures**

Delete `account_profile_id` from `SessionConfig`, delete
`_ACCOUNT_PROFILE_ID` from `paper_replay_main.py`, and remove the keyword from
every constructor:

```python
session = SessionConfig(
    session_id=_SESSION_ID,
    preset_version=preset.version,
    market_type=MarketType.SPOT,
    trade_mode=TradeMode.PAPER,
    available_capital=arguments.available_capital,
    fee_rate=Decimal("0.001"),
    slippage_bps=Decimal("2"),
    entry_policy=EntryPolicy(max_entries=arguments.max_entries),
    spot_policy=SpotTradingPolicy(
        trading_capital_ratio=arguments.trading_capital_ratio
    ),
)
```

- [ ] **Step 4: Rewrite the conflicting Source-of-Truth clauses**

Apply these exact product rules across the four root documents:

```markdown
- TiewTrade uses one Binance Account per installation.
- TiewTrade allows one Active Bot Session globally.
- A Session is the direct owner of its Basket, Order, Fill, PnL, and audit records.
- Phase 1 Paper Futures records Funding Fee as zero; funding simulation is deferred.
- Paper and Live share business and risk policies but use separate execution adapters.
```

Remove requirements for Account Profile CRUD, profile selection, five profiles,
sub-account isolation, per-profile sessions, and Account Profile metadata in
SQLite. Replace Milestone 3 steps 1–2 with:

```markdown
1. บังคับ one Active Bot Session สำหรับ installation และ Session ownership โดยตรง
2. เพิ่ม SQLite migrations, durable trade history, audit trail และ Recovery state
```

Update the four matching docs-site pages with the same rules and no Linear
references.

- [ ] **Step 5: Run source and documentation checks**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_session_config.py -q
npm --prefix docs-site test
npm --prefix docs-site run check:content
rg -n "Account Profile|sub-account|Sub-account|สูงสุด 5" \
  PRODUCT.md CONTEXT.md ARCHITECTURE.md PROJECT_PLAN.md docs-site/content
```

Expected: tests and content checks PASS; `rg` returns no obsolete product
requirements.

- [ ] **Step 6: Run the existing replay acceptance test**

Run:

```bash
.venv/bin/python -m pytest tests/acceptance/test_paper_spot_replay.py -q
```

Expected: PASS with the existing deterministic result unchanged.

- [ ] **Step 7: Commit the aligned product decision**

```bash
git add PRODUCT.md CONTEXT.md ARCHITECTURE.md PROJECT_PLAN.md \
  docs-site/content src/tiewtrade tests
git commit -m "refactor: simplify sessions to one account"
```

---

### Task 2: Expose Complete Basket Close Accounting

**Files:**

- Modify: `src/tiewtrade/trading/basket.py`
- Modify: `tests/unit/trading/test_basket.py`
- Modify: `src/tiewtrade/replay/paper_spot.py`
- Modify: `tests/unit/replay/test_paper_spot_runner.py`

**Interfaces:**

- Consumes: existing `Basket.add_entry()` and `Basket.close()`.
- Produces:

```python
@dataclass(frozen=True, slots=True)
class ClosedBasket:
    entry_count: int
    average_entry_price: Decimal
    exit_price: Decimal
    gross_realized_pnl: Decimal
    trading_fees: Decimal
    funding_fee: Decimal
    net_realized_pnl: Decimal
    closed_at: datetime

    @property
    def realized_pnl(self) -> Decimal:
        return self.net_realized_pnl
```

- [ ] **Step 1: Write a failing close-accounting test**

Add to `tests/unit/trading/test_basket.py`:

```python
def test_close_exposes_gross_fees_funding_and_net_pnl() -> None:
    basket = Basket(EntryPolicy(max_entries=2), Decimal("1"))
    basket.add_entry(
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.20"),
        filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        atr=Decimal("1"),
        tick_size=Decimal("0.01"),
    )

    closed = basket.close(
        exit_price=Decimal("110"),
        exit_fee=Decimal("0.22"),
        closed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert closed.gross_realized_pnl == Decimal("20")
    assert closed.trading_fees == Decimal("0.42")
    assert closed.funding_fee == Decimal("0")
    assert closed.net_realized_pnl == Decimal("19.58")
    assert closed.realized_pnl == closed.net_realized_pnl
```

- [ ] **Step 2: Run the test and verify the missing fields**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/trading/test_basket.py::test_close_exposes_gross_fees_funding_and_net_pnl \
  -q
```

Expected: FAIL because `ClosedBasket` lacks the accounting fields.

- [ ] **Step 3: Implement the explicit close result**

Replace the `ClosedBasket` fields and construct it in `Basket.close()`:

```python
gross_realized_pnl = sum(
    ((exit_price - entry.price) * entry.quantity for entry in self._entries),
    Decimal("0"),
)
trading_fees = (
    sum((entry.fee for entry in self._entries), Decimal("0")) + exit_fee
)
funding_fee = Decimal("0")
closed = ClosedBasket(
    entry_count=self.entry_count,
    average_entry_price=self.average_entry_price,
    exit_price=exit_price,
    gross_realized_pnl=gross_realized_pnl,
    trading_fees=trading_fees,
    funding_fee=funding_fee,
    net_realized_pnl=gross_realized_pnl - trading_fees - funding_fee,
    closed_at=closed_at,
)
```

Keep `realized_pnl` as a read-only compatibility property so the stable replay
JSON remains unchanged.

- [ ] **Step 4: Run Basket, replay, and acceptance tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/trading/test_basket.py \
  tests/unit/replay/test_paper_spot_runner.py \
  tests/acceptance/test_paper_spot_replay.py \
  -q
```

Expected: PASS; deterministic realized PnL remains `13.84062222`.

- [ ] **Step 5: Commit Basket accounting**

```bash
git add src/tiewtrade/trading/basket.py src/tiewtrade/replay/paper_spot.py \
  tests/unit/trading/test_basket.py tests/unit/replay/test_paper_spot_runner.py
git commit -m "feat: expose basket close accounting"
```

---

### Task 3: Add Normalized Trade History Records

**Files:**

- Create: `src/tiewtrade/trading/trade_history.py`
- Create: `tests/support/__init__.py`
- Create: `tests/support/trade_history_records.py`
- Create: `tests/unit/trading/test_trade_history.py`

**Interfaces:**

- Produces:

```python
class BasketStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class FillSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class FillSource(StrEnum):
    PAPER_EXECUTOR = "paper_executor"
    BINANCE = "binance"


@dataclass(frozen=True, slots=True)
class TradeFill:
    fill_id: str
    basket_id: UUID
    session_id: UUID
    order_id: str
    exchange_trade_id: str | None
    side: FillSide
    entry_number: int | None
    filled_at_utc: datetime
    price: Decimal
    quantity: Decimal
    notional: Decimal
    commission: Decimal
    commission_asset: str
    realized_pnl: Decimal
    source: FillSource


@dataclass(frozen=True, slots=True)
class BasketResult:
    basket_id: UUID
    session_id: UUID
    trade_mode: TradeMode
    market_type: MarketType
    symbol: str
    timeframe: str
    strategy_preset_version: str
    opened_at_utc: datetime
    closed_at_utc: datetime | None
    entry_count: int
    invested_notional: Decimal
    gross_realized_pnl: Decimal
    trading_fees: Decimal
    funding_fee: Decimal
    net_realized_pnl: Decimal
    status: BasketStatus
```

- [ ] **Step 1: Write failing record-invariant tests**

Put `SESSION_ID`, `BASKET_ID`, `trade_fill()`, and `basket_result()` from the
following block in `tests/support/trade_history_records.py`. Import those names
into `tests/unit/trading/test_trade_history.py`, which contains the two test
functions:

```python
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
    FillSource,
    TradeFill,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000101")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000102")


def test_trade_fill_requires_utc_and_exact_notional() -> None:
    fill = trade_fill()

    assert fill.notional == fill.price * fill.quantity
    with pytest.raises(ValueError, match="filled_at_utc must use UTC"):
        replace(fill, filled_at_utc=datetime(2026, 1, 1))


def test_closed_basket_requires_close_time_and_balanced_net_pnl() -> None:
    basket = basket_result()

    assert basket.status is BasketStatus.CLOSED
    with pytest.raises(ValueError, match="net_realized_pnl"):
        replace(basket, net_realized_pnl=Decimal("99"))


def trade_fill() -> TradeFill:
    return TradeFill(
        fill_id="fill-1",
        basket_id=BASKET_ID,
        session_id=SESSION_ID,
        order_id="order-1",
        exchange_trade_id=None,
        side=FillSide.BUY,
        entry_number=1,
        filled_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        price=Decimal("100"),
        quantity=Decimal("2"),
        notional=Decimal("200"),
        commission=Decimal("0.2"),
        commission_asset="USDT",
        realized_pnl=Decimal("0"),
        source=FillSource.PAPER_EXECUTOR,
    )


def basket_result() -> BasketResult:
    return BasketResult(
        basket_id=BASKET_ID,
        session_id=SESSION_ID,
        trade_mode=TradeMode.PAPER,
        market_type=MarketType.SPOT,
        symbol="BTCUSDT",
        timeframe="5m",
        strategy_preset_version="rsi-step-grid-v1",
        opened_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        closed_at_utc=datetime(2026, 1, 2, tzinfo=UTC),
        entry_count=1,
        invested_notional=Decimal("200"),
        gross_realized_pnl=Decimal("20"),
        trading_fees=Decimal("0.42"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("19.58"),
        status=BasketStatus.CLOSED,
    )
```

Create an empty `tests/support/__init__.py` so every later task imports the
factories with:

```python
from tests.support.trade_history_records import (
    BASKET_ID,
    SESSION_ID,
    basket_result,
    trade_fill,
)
```

- [ ] **Step 2: Run the new module test**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_trade_history.py -q
```

Expected: collection FAIL because `tiewtrade.trading.trade_history` does not
exist.

- [ ] **Step 3: Implement immutable records and validation**

Create `src/tiewtrade/trading/trade_history.py` with the declared types and
these exact invariants:

```python
def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")


def _require_non_negative(value: Decimal, field: str) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{field} must be a finite non-negative decimal")


def _require_finite(value: Decimal, field: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field} must be finite")
```

`TradeFill.__post_init__()` must require non-empty IDs, positive finite price
and quantity, `notional == price * quantity`, non-negative commission, UTC
time, and positive `entry_number` when present.

`BasketResult.__post_init__()` must require non-empty market identity, UTC
times, non-negative invested notional and trading fees, finite signed gross PnL,
Funding Fee, and Net PnL, `entry_count >= 1`, and:

```python
expected_net = (
    self.gross_realized_pnl - self.trading_fees - self.funding_fee
)
if self.net_realized_pnl != expected_net:
    raise ValueError("net_realized_pnl does not match gross minus costs")
if self.status is BasketStatus.OPEN and self.closed_at_utc is not None:
    raise ValueError("open Basket must not have closed_at_utc")
if self.status is BasketStatus.CLOSED and self.closed_at_utc is None:
    raise ValueError("closed Basket requires closed_at_utc")
```

- [ ] **Step 4: Run history-record and type checks**

Run:

```bash
.venv/bin/python -m pytest tests/unit/trading/test_trade_history.py -q
.venv/bin/python -m mypy src/tiewtrade/trading
```

Expected: PASS.

- [ ] **Step 5: Commit normalized records**

```bash
git add src/tiewtrade/trading/trade_history.py \
  tests/support tests/unit/trading/test_trade_history.py
git commit -m "feat: define durable trade history records"
```

---

### Task 4: Add SQLite Migration and Atomic History Store

**Files:**

- Create: `src/tiewtrade/integrations/__init__.py`
- Create: `src/tiewtrade/integrations/sqlite/__init__.py`
- Create: `src/tiewtrade/integrations/sqlite/database.py`
- Create: `src/tiewtrade/integrations/sqlite/trade_history.py`
- Create: `tests/unit/integrations/sqlite/test_trade_history.py`

**Interfaces:**

- Consumes: `BasketResult`, `TradeFill`.
- Produces:

```python
class SQLiteDatabase:
    def __init__(self, path: Path) -> None: ...
    def connect(self) -> sqlite3.Connection: ...
    def migrate(self) -> None: ...


@dataclass(frozen=True, slots=True)
class TradeHistoryFilter:
    symbol: str | None = None
    timeframe: str | None = None
    market_type: MarketType | None = None
    trade_mode: TradeMode | None = None
    status: BasketStatus | None = None
    opened_from_utc: datetime | None = None
    opened_to_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class BasketHistoryPage:
    items: tuple[BasketResult, ...]
    total_items: int
    closed_net_pnl: Decimal
    page: int
    page_size: int


class TradeHistoryUnavailableError(RuntimeError):
    pass


class SQLiteTradeHistory:
    def record_open_basket(
        self, basket: BasketResult, fill: TradeFill
    ) -> bool: ...
    def record_entry_fill(
        self, basket: BasketResult, fill: TradeFill
    ) -> bool: ...
    def record_closed_basket(
        self, basket: BasketResult, fill: TradeFill
    ) -> bool: ...
    def list_baskets(
        self,
        filters: TradeHistoryFilter,
        *,
        page: int,
        page_size: int,
    ) -> BasketHistoryPage: ...
    def get_basket(self, basket_id: UUID) -> BasketResult | None: ...
    def list_fills(self, basket_id: UUID) -> tuple[TradeFill, ...]: ...
```

- [ ] **Step 1: Write failing migration and persistence tests**

Create `tests/unit/integrations/sqlite/test_trade_history.py`. Import the Task 3
factories from `tests.support.trade_history_records` and add:

```python
@pytest.fixture
def history(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    return SQLiteTradeHistory(database)


def open_basket_result() -> BasketResult:
    return replace(
        basket_result(),
        closed_at_utc=None,
        gross_realized_pnl=Decimal("0"),
        trading_fees=Decimal("0.2"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("-0.2"),
        status=BasketStatus.OPEN,
    )


def buy_fill() -> TradeFill:
    return trade_fill()


def sell_fill() -> TradeFill:
    return replace(
        trade_fill(),
        fill_id="fill-2",
        order_id="order-2",
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=datetime(2026, 1, 2, tzinfo=UTC),
        price=Decimal("110"),
        notional=Decimal("220"),
        commission=Decimal("0.22"),
        realized_pnl=Decimal("19.58"),
    )


def closed_basket_result() -> BasketResult:
    return basket_result()


def test_migration_creates_version_one_schema(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()

    with database.connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert version == 1
    assert {"basket_results", "trade_fills"} <= tables


def test_duplicate_fill_does_not_change_basket_totals(
    history: SQLiteTradeHistory,
) -> None:
    basket = open_basket_result()
    fill = buy_fill()

    assert history.record_open_basket(basket, fill) is True
    assert history.record_open_basket(basket, fill) is False
    assert history.list_fills(basket.basket_id) == (fill,)


def test_closed_basket_and_sell_fill_are_atomic(
    history: SQLiteTradeHistory,
) -> None:
    history.record_open_basket(open_basket_result(), buy_fill())

    assert history.record_closed_basket(closed_basket_result(), sell_fill())

    page = history.list_baskets(TradeHistoryFilter(), page=1, page_size=20)
    assert page.items == (closed_basket_result(),)
    assert page.closed_net_pnl == Decimal("19.58")
```

Add these exact failure and query tests:

```python
def test_close_rejects_an_unknown_basket(
    history: SQLiteTradeHistory,
) -> None:
    with pytest.raises(ValueError, match="Basket does not exist"):
        history.record_closed_basket(closed_basket_result(), sell_fill())


def test_fill_rejects_a_different_session(
    history: SQLiteTradeHistory,
) -> None:
    history.record_open_basket(open_basket_result(), buy_fill())
    wrong_session_fill = replace(
        sell_fill(),
        session_id=UUID("00000000-0000-0000-0000-000000000999"),
    )

    with pytest.raises(ValueError, match="Session"):
        history.record_closed_basket(
            closed_basket_result(),
            wrong_session_fill,
        )


def test_closed_basket_rejects_another_fill(
    history: SQLiteTradeHistory,
) -> None:
    history.record_open_basket(open_basket_result(), buy_fill())
    history.record_closed_basket(closed_basket_result(), sell_fill())

    with pytest.raises(ValueError, match="closed"):
        history.record_entry_fill(
            closed_basket_result(),
            replace(buy_fill(), fill_id="fill-3", order_id="order-3"),
        )


def test_reopened_store_reads_the_same_history(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    SQLiteTradeHistory(database).record_open_basket(
        open_basket_result(),
        buy_fill(),
    )

    reopened = SQLiteTradeHistory(database)

    assert reopened.get_basket(BASKET_ID) == open_basket_result()
    assert reopened.list_fills(BASKET_ID) == (buy_fill(),)


def test_history_filters_orders_and_paginates(
    history: SQLiteTradeHistory,
) -> None:
    first = open_basket_result()
    second_id = UUID("00000000-0000-0000-0000-000000000202")
    second = replace(
        first,
        basket_id=second_id,
        symbol="ETHUSDT",
        opened_at_utc=datetime(2026, 2, 1, tzinfo=UTC),
    )
    history.record_open_basket(first, buy_fill())
    history.record_open_basket(
        second,
        replace(
            buy_fill(),
            fill_id="fill-eth",
            basket_id=second_id,
            order_id="order-eth",
            filled_at_utc=second.opened_at_utc,
        ),
    )

    filtered = history.list_baskets(
        TradeHistoryFilter(symbol="ETHUSDT"),
        page=1,
        page_size=1,
    )

    assert filtered.total_items == 1
    assert filtered.items == (second,)
    assert history.list_baskets(
        TradeHistoryFilter(), page=1, page_size=1
    ).items == (second,)
    assert history.list_baskets(
        TradeHistoryFilter(), page=2, page_size=1
    ).items == (first,)


def test_fills_are_returned_in_execution_order(
    history: SQLiteTradeHistory,
) -> None:
    history.record_open_basket(open_basket_result(), buy_fill())
    history.record_closed_basket(closed_basket_result(), sell_fill())

    assert history.list_fills(BASKET_ID) == (buy_fill(), sell_fill())
```

Extend `test_history_filters_orders_and_paginates` with one assertion for each
remaining filter using `replace()` to create matching records:

```python
assert history.list_baskets(
    TradeHistoryFilter(timeframe="5m"), page=1, page_size=20
).total_items == 2
assert history.list_baskets(
    TradeHistoryFilter(market_type=MarketType.SPOT), page=1, page_size=20
).total_items == 2
assert history.list_baskets(
    TradeHistoryFilter(trade_mode=TradeMode.PAPER), page=1, page_size=20
).total_items == 2
assert history.list_baskets(
    TradeHistoryFilter(status=BasketStatus.OPEN), page=1, page_size=20
).total_items == 2
assert history.list_baskets(
    TradeHistoryFilter(
        opened_from_utc=datetime(2026, 2, 1, tzinfo=UTC),
        opened_to_utc=datetime(2026, 2, 28, tzinfo=UTC),
    ),
    page=1,
    page_size=20,
).items == (second,)
```

- [ ] **Step 2: Run SQLite tests and verify import failure**

Run:

```bash
.venv/bin/python -m pytest tests/unit/integrations/sqlite/test_trade_history.py -q
```

Expected: collection FAIL because the SQLite modules do not exist.

- [ ] **Step 3: Implement the version-one migration**

`SQLiteDatabase.connect()` must set:

```python
connection = sqlite3.connect(self._path)
connection.row_factory = sqlite3.Row
connection.execute("PRAGMA foreign_keys = ON")
return connection
```

`migrate()` must run one transaction that creates:

```sql
CREATE TABLE basket_results (
    basket_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    trade_mode TEXT NOT NULL,
    market_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy_preset_version TEXT NOT NULL,
    opened_at_utc TEXT NOT NULL,
    closed_at_utc TEXT,
    entry_count INTEGER NOT NULL CHECK (entry_count > 0),
    invested_notional TEXT NOT NULL,
    gross_realized_pnl TEXT NOT NULL,
    trading_fees TEXT NOT NULL,
    funding_fee TEXT NOT NULL,
    net_realized_pnl TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed'))
);

CREATE TABLE trade_fills (
    fill_id TEXT PRIMARY KEY,
    basket_id TEXT NOT NULL REFERENCES basket_results(basket_id),
    session_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    exchange_trade_id TEXT,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    entry_number INTEGER,
    filled_at_utc TEXT NOT NULL,
    price TEXT NOT NULL,
    quantity TEXT NOT NULL,
    notional TEXT NOT NULL,
    commission TEXT NOT NULL,
    commission_asset TEXT NOT NULL,
    realized_pnl TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('paper_executor', 'binance')),
    UNIQUE (source, order_id, exchange_trade_id)
);

CREATE INDEX basket_results_history_idx
ON basket_results (opened_at_utc DESC, basket_id DESC);

CREATE INDEX trade_fills_basket_time_idx
ON trade_fills (basket_id, filled_at_utc, fill_id);
```

Set `PRAGMA user_version = 1`. Reject a database with a schema version greater
than one.

- [ ] **Step 4: Implement canonical serialization**

In `trade_history.py`, use focused private conversion functions:

```python
def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _utc_text(value: datetime) -> str:
    return value.isoformat()
```

Read values with `Decimal(row["price"])`,
`datetime.fromisoformat(row["filled_at_utc"])`, and enum constructors. Do not
use JSON blobs or pickle.

- [ ] **Step 5: Implement atomic idempotent write methods**

Each public write method must use:

```python
with self._database.connect() as connection:
    connection.execute("BEGIN IMMEDIATE")
    inserted = connection.execute(
        "INSERT OR IGNORE INTO trade_fills (...) VALUES (...)",
        fill_parameters,
    ).rowcount == 1
    if not inserted:
        return False
    # Insert or update the validated BasketResult in this same transaction.
```

`record_open_basket()` inserts the Basket before its first Fill because of the
foreign key. It must remove the just-created Basket if the Fill conflicts.
`record_entry_fill()` requires an existing open Basket.
`record_closed_basket()` requires an existing open Basket and changes it to
closed in the same transaction as the SELL Fill. Validate Basket/Session
identity before mutation.

- [ ] **Step 6: Implement filtered paginated reads**

Build parameterized WHERE clauses only from the declared
`TradeHistoryFilter`. Require `page >= 1` and `1 <= page_size <= 100`.

Use the same WHERE clause for the count, item, and closed-Net-PnL queries.
Count rows without casting monetary values:

```sql
SELECT COUNT(*) AS total_items
FROM basket_results
WHERE ...
```

Read matching closed PnL values as canonical text:

```sql
SELECT net_realized_pnl
FROM basket_results
WHERE ... AND status = 'closed'
```

Calculate the filtered total without SQLite numeric coercion:

```python
closed_net_pnl = sum(
    (Decimal(row["net_realized_pnl"]) for row in pnl_rows),
    Decimal("0"),
)
```

Use this item query:

```sql
SELECT *
FROM basket_results
WHERE ...
ORDER BY opened_at_utc DESC, basket_id DESC
LIMIT ? OFFSET ?
```

`get_basket()` performs a primary-key lookup and returns `None` when the Basket
does not exist. Individual values must round-trip from canonical text columns.

Catch `sqlite3.Error` at the public adapter boundary and raise
`TradeHistoryUnavailableError` with the original exception as its cause. Domain
validation errors remain unchanged.

- [ ] **Step 7: Run SQLite tests, lint, and mypy**

Run:

```bash
.venv/bin/python -m pytest tests/unit/integrations/sqlite/test_trade_history.py -q
.venv/bin/python -m ruff check \
  src/tiewtrade/integrations tests/unit/integrations
.venv/bin/python -m mypy src/tiewtrade/integrations
```

Expected: PASS.

- [ ] **Step 8: Commit durable SQLite history**

```bash
git add src/tiewtrade/integrations tests/unit/integrations
git commit -m "feat: persist trade history in sqlite"
```

---

### Task 5: Expose the Application Trade History Query

**Files:**

- Create: `src/tiewtrade/application/trade_history_query.py`
- Create: `tests/unit/application/test_trade_history_query.py`

**Interfaces:**

- Consumes: `SQLiteTradeHistory`, `TradeHistoryFilter`,
  `BasketHistoryPage`, `BasketResult`, and `TradeFill`.
- Produces:

```python
class TradeHistoryQuery:
    def __init__(self, history: SQLiteTradeHistory) -> None: ...

    def baskets(
        self,
        filters: TradeHistoryFilter,
        *,
        page: int,
        page_size: int,
    ) -> BasketHistoryPage: ...

    def fills(self, basket_id: UUID) -> tuple[TradeFill, ...]: ...
```

- [ ] **Step 1: Write failing application query tests**

Create `tests/unit/application/test_trade_history_query.py`:

```python
@pytest.fixture
def populated_history(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    history = SQLiteTradeHistory(database)
    closed = basket_result()
    opened = replace(
        closed,
        closed_at_utc=None,
        gross_realized_pnl=Decimal("0"),
        trading_fees=trade_fill().commission,
        funding_fee=Decimal("0"),
        net_realized_pnl=-trade_fill().commission,
        status=BasketStatus.OPEN,
    )
    sell = replace(
        trade_fill(),
        fill_id="fill-2",
        order_id="order-2",
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=closed.closed_at_utc,
        price=Decimal("110"),
        notional=Decimal("220"),
        commission=Decimal("0.22"),
        realized_pnl=closed.net_realized_pnl,
    )
    history.record_open_basket(opened, trade_fill())
    history.record_closed_basket(closed, sell)
    return history


def test_query_returns_filtered_baskets_and_selected_fills(
    populated_history: SQLiteTradeHistory,
) -> None:
    query = TradeHistoryQuery(populated_history)

    page = query.baskets(
        TradeHistoryFilter(symbol="BTCUSDT"),
        page=1,
        page_size=20,
    )
    fills = query.fills(page.items[0].basket_id)

    assert page.total_items == 1
    assert page.closed_net_pnl == Decimal("19.58")
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
```

- [ ] **Step 2: Run the query test and verify import failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/application/test_trade_history_query.py -q
```

Expected: collection FAIL because `TradeHistoryQuery` does not exist.

- [ ] **Step 3: Implement the narrow application facade**

Create `trade_history_query.py`:

```python
from uuid import UUID

from tiewtrade.integrations.sqlite.trade_history import (
    BasketHistoryPage,
    SQLiteTradeHistory,
    TradeHistoryFilter,
)
from tiewtrade.trading.trade_history import TradeFill


class TradeHistoryQuery:
    def __init__(self, history: SQLiteTradeHistory) -> None:
        self._history = history

    def baskets(
        self,
        filters: TradeHistoryFilter,
        *,
        page: int,
        page_size: int,
    ) -> BasketHistoryPage:
        return self._history.list_baskets(
            filters,
            page=page,
            page_size=page_size,
        )

    def fills(self, basket_id: UUID) -> tuple[TradeFill, ...]:
        return self._history.list_fills(basket_id)
```

The future UI imports this application facade and does not import
`integrations.sqlite`.

- [ ] **Step 4: Run query tests and mypy**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/application/test_trade_history_query.py -q
.venv/bin/python -m mypy src/tiewtrade/application/trade_history_query.py
```

Expected: PASS.

- [ ] **Step 5: Commit the application query**

```bash
git add src/tiewtrade/application/trade_history_query.py \
  tests/unit/application/test_trade_history_query.py
git commit -m "feat: expose trade history queries"
```

---

### Task 6: Map Paper Spot Fills into Durable History

**Files:**

- Create: `src/tiewtrade/application/paper_spot_trade_history.py`
- Create: `tests/unit/application/test_paper_spot_trade_history.py`
- Modify: `src/tiewtrade/application/paper_spot_session.py`
- Modify: `src/tiewtrade/execution/paper_spot.py`
- Modify: related Paper Spot tests

**Interfaces:**

- Produces:

```python
@dataclass(frozen=True, slots=True)
class PaperSpotHistoryContext:
    session_id: UUID
    symbol: str
    timeframe: str
    preset_version: str
    commission_asset: str


class PaperSpotTradeHistory:
    def __init__(
        self,
        context: PaperSpotHistoryContext,
        store: SQLiteTradeHistory,
    ) -> None: ...

    def record_entry(
        self,
        *,
        basket_id: UUID,
        entry_number: int,
        fill: PaperSpotEntryFill,
    ) -> bool: ...

    def record_close(
        self,
        *,
        basket_id: UUID,
        fill: PaperSpotExitFill,
        closed: ClosedBasket,
    ) -> bool: ...
```

`PaperSpotEntryFill` and `PaperSpotExitFill` additionally expose:

```python
order_id: str
fill_id: str
```

`ClosedBasket` additionally exposes:

```python
basket_id: UUID
```

- [ ] **Step 1: Write failing mapping tests**

Create `tests/unit/application/test_paper_spot_trade_history.py` and assert:

```python
SESSION_ID = UUID("00000000-0000-0000-0000-000000000101")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000102")
OPENED_AT = datetime(2026, 1, 1, tzinfo=UTC)
CLOSED_AT = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    return SQLiteTradeHistory(database)


@pytest.fixture
def history(store: SQLiteTradeHistory) -> PaperSpotTradeHistory:
    return PaperSpotTradeHistory(
        PaperSpotHistoryContext(
            session_id=SESSION_ID,
            symbol="BTCUSDT",
            timeframe="5m",
            preset_version="rsi-step-grid-v1",
            commission_asset="USDT",
        ),
        store,
    )


def entry_fill() -> PaperSpotEntryFill:
    return PaperSpotEntryFill(
        intent_id="intent-1",
        order_id="entry:intent-1",
        fill_id=f"paper:{SESSION_ID}:entry:intent-1:fill",
        price=Decimal("100"),
        quantity=Decimal("2"),
        fee=Decimal("0.2"),
        filled_at=OPENED_AT,
    )


def exit_fill() -> PaperSpotExitFill:
    return PaperSpotExitFill(
        order_id=f"take-profit:{BASKET_ID}",
        fill_id=f"paper:{SESSION_ID}:take-profit:{BASKET_ID}:fill",
        price=Decimal("110"),
        quantity=Decimal("2"),
        fee=Decimal("0.22"),
        filled_at=CLOSED_AT,
    )


def closed_basket() -> ClosedBasket:
    return ClosedBasket(
        basket_id=BASKET_ID,
        entry_count=1,
        average_entry_price=Decimal("100"),
        exit_price=Decimal("110"),
        gross_realized_pnl=Decimal("20"),
        trading_fees=Decimal("0.42"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("19.58"),
        closed_at=CLOSED_AT,
    )


def test_entry_fill_creates_an_open_basket_and_buy_fill(
    history: PaperSpotTradeHistory,
    store: SQLiteTradeHistory,
) -> None:
    assert history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )

    basket = store.list_baskets(
        TradeHistoryFilter(), page=1, page_size=20
    ).items[0]
    fill = store.list_fills(BASKET_ID)[0]

    assert basket.status is BasketStatus.OPEN
    assert basket.entry_count == 1
    assert basket.invested_notional == fill.notional
    assert fill.side is FillSide.BUY
    assert fill.entry_number == 1


def test_close_records_sell_and_exact_net_realized_pnl(
    history: PaperSpotTradeHistory,
    store: SQLiteTradeHistory,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    history.record_close(
        basket_id=BASKET_ID,
        fill=exit_fill(),
        closed=closed_basket(),
    )

    basket = store.list_baskets(
        TradeHistoryFilter(), page=1, page_size=20
    ).items[0]
    assert basket.gross_realized_pnl == Decimal("20")
    assert basket.trading_fees == Decimal("0.42")
    assert basket.funding_fee == Decimal("0")
    assert basket.net_realized_pnl == Decimal("19.58")
```

- [ ] **Step 2: Run mapping tests and verify import failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_trade_history.py -q
```

Expected: collection FAIL because the mapper does not exist.

- [ ] **Step 3: Add deterministic Paper IDs**

In `PaperSpotExecutor`, construct IDs without random state:

```python
entry_order_id = f"entry:{intent.intent_id}"
entry_fill_id = f"paper:{self._session.session_id}:{entry_order_id}:fill"
```

For Take Profit:

```python
exit_order_id = f"take-profit:{basket.basket_id}"
exit_fill_id = f"paper:{self._session.session_id}:{exit_order_id}:fill"
```

In `PaperSpotSession`, create each new Basket with:

```python
basket_id = uuid5(
    self._session.session_id,
    f"basket:{self._closed_basket_count + 1}",
)
```

Pass `basket_id` into `Basket` and copy it into `ClosedBasket`.

- [ ] **Step 4: Implement the Paper Spot mapper**

`record_entry()` creates a BUY `TradeFill` and an OPEN `BasketResult`. It reads
an existing Basket through `get_basket()` for Entry 2+ and passes the new
aggregate to `record_entry_fill()`. The first Entry calls
`record_open_basket()`.

Map:

```python
TradeFill(
    fill_id=fill.fill_id,
    basket_id=basket_id,
    session_id=context.session_id,
    order_id=fill.order_id,
    exchange_trade_id=None,
    side=FillSide.BUY,
    entry_number=entry_number,
    filled_at_utc=fill.filled_at,
    price=fill.price,
    quantity=fill.quantity,
    notional=fill.price * fill.quantity,
    commission=fill.fee,
    commission_asset=context.commission_asset,
    realized_pnl=Decimal("0"),
    source=FillSource.PAPER_EXECUTOR,
)
```

For Entry 2+, create the updated OPEN result with:

```python
replace(
    existing,
    entry_count=existing.entry_count + 1,
    invested_notional=existing.invested_notional + normalized_fill.notional,
    trading_fees=existing.trading_fees + normalized_fill.commission,
    net_realized_pnl=(
        existing.gross_realized_pnl
        - existing.trading_fees
        - normalized_fill.commission
        - existing.funding_fee
    ),
)
```

`record_close()` creates a SELL Fill with `entry_number=None` and
`realized_pnl=closed.net_realized_pnl`, then supplies the final CLOSED
`BasketResult` using the accounting values from `ClosedBasket` and the
`opened_at_utc`, `invested_notional`, and identity fields from `get_basket()`.

- [ ] **Step 5: Run mapping and existing execution tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/application/test_paper_spot_trade_history.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/unit/execution/test_paper_spot.py \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit Paper Spot normalization**

```bash
git add src/tiewtrade/application src/tiewtrade/execution \
  src/tiewtrade/trading/basket.py tests/unit/application \
  tests/unit/execution tests/unit/trading
git commit -m "feat: map paper spot fills to trade history"
```

---

### Task 7: Add Persistence-Enabled Paper Spot Session

**Files:**

- Create: `src/tiewtrade/application/persistent_paper_spot_session.py`
- Create: `tests/unit/application/test_persistent_paper_spot_session.py`

**Interfaces:**

- Consumes: `PaperSpotSession`, `PaperSpotTradeHistory`.
- Produces:

```python
class PersistenceState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class SessionPersistenceBlockedError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PersistentPaperSpotSnapshot:
    session: PaperSpotSessionSnapshot
    persistence_state: PersistenceState


class PersistentPaperSpotSession:
    def __init__(
        self,
        session: PaperSpotSession,
        history: PaperSpotTradeHistory,
    ) -> None: ...

    def process_completed_candle(
        self,
        candle: Candle,
        *,
        received_at: datetime,
    ) -> PersistentPaperSpotSnapshot: ...
```

- [ ] **Step 1: Write failing orchestration tests**

Create tests that use a real temporary SQLite store:

```python
def test_entry_and_close_are_written_before_next_candle_is_allowed(
    persistent_session: PersistentPaperSpotSession,
    store: SQLiteTradeHistory,
) -> None:
    entry_snapshot = drive_until_entry(persistent_session)
    assert entry_snapshot.session.entry_fill is not None
    assert len(store.list_fills(entry_snapshot.session.basket_id)) == 1

    close_snapshot = drive_until_close(persistent_session)
    assert close_snapshot.session.closed_basket is not None
    assert len(store.list_fills(close_snapshot.session.closed_basket.basket_id)) == 2


def test_history_failure_blocks_future_candles(
    persistent_session_with_closed_database: PersistentPaperSpotSession,
) -> None:
    with pytest.raises(TradeHistoryUnavailableError):
        drive_until_entry(persistent_session_with_closed_database)

    with pytest.raises(SessionPersistenceBlockedError):
        persistent_session_with_closed_database.process_completed_candle(
            next_candle(), received_at=next_candle().close_time
        )
```

Use a deliberately invalid SQLite path or a store test double that raises the
public `TradeHistoryUnavailableError`; do not add an in-memory success store.

- [ ] **Step 2: Run the wrapper tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/application/test_persistent_paper_spot_session.py -q
```

Expected: collection FAIL because the wrapper does not exist.

- [ ] **Step 3: Expose the current Basket identity in snapshots**

Add:

```python
basket_id: UUID | None
```

to `PaperSpotSessionSnapshot`. `_snapshot()` returns the active Basket ID or
the just-closed Basket ID. This identity allows the wrapper to record the Fill
without inspecting private Session state.

- [ ] **Step 4: Implement synchronous durable recording and blocking**

The wrapper delegates one Candle, records any returned Entry Fill or closed
Basket synchronously, and changes its state to `BLOCKED` on any persistence
exception:

```python
if self._state is PersistenceState.BLOCKED:
    raise SessionPersistenceBlockedError(
        "Session is blocked because trade history is unavailable"
    )

snapshot = self._session.process_completed_candle(
    candle,
    received_at=received_at,
)
try:
    if snapshot.entry_fill is not None:
        assert snapshot.basket_id is not None
        self._history.record_entry(
            basket_id=snapshot.basket_id,
            entry_number=snapshot.basket_entry_count,
            fill=snapshot.entry_fill,
        )
    if snapshot.closed_basket is not None:
        assert snapshot.take_profit_fill is not None
        self._history.record_close(
            basket_id=snapshot.closed_basket.basket_id,
            fill=snapshot.take_profit_fill,
            closed=snapshot.closed_basket,
        )
except Exception:
    self._state = PersistenceState.BLOCKED
    raise
```

The wrapper must not swallow or replace the original persistence error on the
first failure.

- [ ] **Step 5: Run wrapper, Session, and replay tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/application/test_persistent_paper_spot_session.py \
  tests/unit/application/test_paper_spot_session.py \
  tests/acceptance/test_paper_spot_replay.py \
  -q
```

Expected: PASS; headless replay remains available as a separate deterministic
acceptance command.

- [ ] **Step 6: Commit persistent orchestration**

```bash
git add src/tiewtrade/application tests/unit/application
git commit -m "feat: fail closed on trade history failure"
```

---

### Task 8: Prove Durable History Across Restart

**Files:**

- Create: `tests/acceptance/test_paper_spot_trade_history.py`
- Modify: `README.md` if it exists; otherwise modify `PROJECT_PLAN.md` only

**Interfaces:**

- Consumes: all interfaces from Tasks 1–7.
- Produces: a deterministic acceptance scenario proving durable history and
  restart queries.

- [ ] **Step 1: Write the failing end-to-end acceptance test**

Create `tests/acceptance/test_paper_spot_trade_history.py`:

```python
def test_replay_persists_complete_trade_history_across_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "tiewtrade.sqlite3"
    first_store = migrated_history(database_path)
    session = persistent_tracer_session(first_store)

    for candle in tracer_candles():
        session.process_completed_candle(candle, received_at=candle.close_time)

    reopened_store = migrated_history(database_path)
    page = reopened_store.list_baskets(
        TradeHistoryFilter(), page=1, page_size=20
    )

    assert page.total_items == 1
    assert page.items[0].status is BasketStatus.CLOSED
    assert page.items[0].entry_count == 1
    assert page.items[0].funding_fee == Decimal("0")
    assert page.items[0].net_realized_pnl == Decimal("13.84062222")
    fills = reopened_store.list_fills(page.items[0].basket_id)
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
    assert page.closed_net_pnl == Decimal("13.84062222")
```

Build `persistent_tracer_session()` from the same fixture configuration as
`test_paper_spot_replay.py`; do not duplicate the trading algorithm.

- [ ] **Step 2: Run the acceptance test and verify the first integration gap**

Run:

```bash
.venv/bin/python -m pytest \
  tests/acceptance/test_paper_spot_trade_history.py -q
```

Expected: FAIL until the persistent Session helper and complete recording path
are wired correctly.

- [ ] **Step 3: Complete only the missing acceptance composition**

Compose:

```python
database = SQLiteDatabase(database_path)
database.migrate()
store = SQLiteTradeHistory(database)
core_session = PaperSpotSession(
    session_config,
    market_data,
    symbol_rules,
    preset,
)
history = PaperSpotTradeHistory(
    PaperSpotHistoryContext(
        session_id=session_config.session_id,
        symbol=market_data.symbol,
        timeframe=market_data.timeframe,
        preset_version=preset.version,
        commission_asset="USDT",
    ),
    store,
)
return PersistentPaperSpotSession(core_session, history)
```

Do not add a GUI, Futures executor, Binance transport, or generic runtime
factory in this task.

- [ ] **Step 4: Run the complete Python verification suite**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 5: Run documentation verification**

Run:

```bash
npm --prefix docs-site test
npm --prefix docs-site run check:content
```

Expected: PASS.

- [ ] **Step 6: Record the milestone result**

Update the Paper Trading Complete section in `PROJECT_PLAN.md` to state that
durable Paper Spot Trade History is complete and that Paper Futures production
and Desktop UI consumption remain ordered after their respective foundations.
Do not mark Paper Trading Complete itself complete.

- [ ] **Step 7: Commit the tracer-bullet acceptance**

```bash
git add tests/acceptance/test_paper_spot_trade_history.py PROJECT_PLAN.md
git commit -m "test: prove durable paper trade history"
```

---

## Follow-up Plan Boundaries

The approved design contains two deliverables that must not be scaffolded in
this plan:

1. **Paper Futures Trade History Integration** starts after a concrete Paper
   Futures executor and shared Futures PnL policy exist. It maps actual Paper
   Futures fills into the same `TradeFill` and `BasketResult` records and keeps
   Phase 1 `funding_fee` at zero.
2. **Desktop Trade History UI** starts after the PySide6 application shell and
   navigation exist. It consumes `list_baskets()` and `list_fills()` to render
   the approved connected Basket History and Trade Fills tables.

Future Live history will add a Binance-owned mapper, Bot-owned client order
identity, idempotent Binance Trade IDs, income reconciliation, and OS Keyring
credentials under the Live milestones. None of those side effects belong in
the Paper implementation.
