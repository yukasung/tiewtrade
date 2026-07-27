from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from tiewtrade.execution.paper_futures import (
    PaperFuturesEntryFill,
    PaperFuturesExitFill,
)
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_futures_history import (
    PaperFuturesHistoryContext,
    PaperFuturesSQLiteHistory,
)
from tiewtrade.integrations.sqlite.trade_history import (
    SQLiteTradeHistory,
    TradeHistoryConflictError,
)
from tiewtrade.trading.basket import (
    BasketCloseReason,
    ClosedBasket,
)
from tiewtrade.trading.position import PositionSide
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import BasketStatus, FillSide

SESSION_ID = UUID("00000000-0000-0000-0000-000000000108")
BASKET_ID = UUID("00000000-0000-0000-0000-000000000109")
OPENED_AT = datetime(2026, 1, 1, tzinfo=UTC)
CLOSED_AT = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    return SQLiteTradeHistory(database)


@pytest.fixture
def history(store: SQLiteTradeHistory) -> PaperFuturesSQLiteHistory:
    return PaperFuturesSQLiteHistory(history_context(), store)


def history_context() -> PaperFuturesHistoryContext:
    return PaperFuturesHistoryContext(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
        commission_asset="USDT",
        leverage=3,
    )


@pytest.mark.parametrize("leverage", [0, 6, True, 1.5])
def test_history_context_rejects_leverage_outside_session_cap(
    leverage: object,
) -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        PaperFuturesHistoryContext(
            session_id=SESSION_ID,
            symbol="BTCUSDT",
            timeframe="5m",
            preset_version="rsi-step-grid-v1",
            commission_asset="USDT",
            leverage=leverage,  # type: ignore[arg-type]
        )


def entry_fill(
    *,
    side: PositionSide = PositionSide.LONG,
    sequence: int = 1,
) -> PaperFuturesEntryFill:
    price = Decimal("100") if sequence == 1 else Decimal("90")
    quantity = Decimal("2") if sequence == 1 else Decimal("1")
    intent_id = f"intent-{sequence}"
    order_id = f"entry:{intent_id}"
    return PaperFuturesEntryFill(
        order_id=order_id,
        fill_id=f"paper:{SESSION_ID}:{order_id}:fill",
        intent_id=intent_id,
        side=side,
        price=price,
        quantity=quantity,
        fee=price * quantity * Decimal("0.001"),
        filled_at=OPENED_AT + timedelta(hours=sequence - 1),
    )


def exit_fill(
    *,
    side: PositionSide = PositionSide.LONG,
) -> PaperFuturesExitFill:
    order_id = f"take_profit:{BASKET_ID}"
    return PaperFuturesExitFill(
        order_id=order_id,
        fill_id=f"paper:{SESSION_ID}:{order_id}:fill",
        side=side,
        close_reason=BasketCloseReason.TAKE_PROFIT,
        price=Decimal("110") if side is PositionSide.LONG else Decimal("90"),
        quantity=Decimal("2"),
        fee=Decimal("0.22") if side is PositionSide.LONG else Decimal("0.18"),
        filled_at=CLOSED_AT,
    )


def closed_basket(
    *,
    side: PositionSide = PositionSide.LONG,
) -> ClosedBasket:
    trading_fees = Decimal("0.42") if side is PositionSide.LONG else Decimal("0.38")
    gross_pnl = Decimal("20")
    return ClosedBasket(
        basket_id=BASKET_ID,
        entry_count=1,
        average_entry_price=Decimal("100"),
        exit_price=Decimal("110") if side is PositionSide.LONG else Decimal("90"),
        gross_realized_pnl=gross_pnl,
        trading_fees=trading_fees,
        funding_fee=Decimal("0"),
        net_realized_pnl=gross_pnl - trading_fees,
        closed_at=CLOSED_AT,
        position_side=side,
        close_reason=BasketCloseReason.TAKE_PROFIT,
    )


def test_long_entry_creates_futures_basket_and_buy_fill(
    history: PaperFuturesSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    fill = entry_fill()

    assert history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=fill,
    )

    basket = store.get_basket(BASKET_ID)
    fills = store.list_fills(BASKET_ID)
    assert basket is not None
    assert basket.trade_mode is TradeMode.PAPER
    assert basket.market_type is MarketType.FUTURES
    assert basket.leverage == 3
    assert basket.entry_count == 1
    assert basket.invested_notional == Decimal("200")
    assert basket.trading_fees == Decimal("0.200")
    assert basket.funding_fee == Decimal("0.00")
    assert basket.funding_fee.as_tuple().exponent == -2
    assert basket.net_realized_pnl == Decimal("-0.200")
    assert basket.status is BasketStatus.OPEN
    assert len(fills) == 1
    assert fills[0].side is FillSide.BUY
    assert fills[0].entry_number == 1
    assert fills[0].realized_pnl == Decimal("0")


def test_short_entry_maps_to_sell_fill(
    history: PaperFuturesSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(side=PositionSide.SHORT),
    )

    assert store.list_fills(BASKET_ID)[0].side is FillSide.SELL


def test_second_entry_updates_notional_fees_and_entry_count(
    history: PaperFuturesSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=2,
        fill=entry_fill(sequence=2),
    )

    basket = store.get_basket(BASKET_ID)
    assert basket is not None
    assert basket.entry_count == 2
    assert basket.invested_notional == Decimal("290")
    assert basket.trading_fees == Decimal("0.290")
    assert basket.net_realized_pnl == Decimal("-0.290")


def test_partial_fill_for_same_order_does_not_increment_entry_count(
    history: PaperFuturesSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    first = entry_fill()
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=first,
    )
    partial = PaperFuturesEntryFill(
        order_id=first.order_id,
        fill_id=f"{first.fill_id}:partial-2",
        intent_id=first.intent_id,
        side=first.side,
        price=Decimal("101"),
        quantity=Decimal("0.5"),
        fee=Decimal("0.0505"),
        filled_at=first.filled_at + timedelta(seconds=1),
    )

    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=partial,
    )

    basket = store.get_basket(BASKET_ID)
    assert basket is not None
    assert basket.entry_count == 1
    assert basket.invested_notional == Decimal("250.5")
    assert basket.trading_fees == Decimal("0.2505")
    assert len(store.list_fills(BASKET_ID)) == 2


def test_existing_basket_rejects_changed_session_leverage(
    history: PaperFuturesSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    changed_context = PaperFuturesHistoryContext(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
        commission_asset="USDT",
        leverage=4,
    )

    with pytest.raises(TradeHistoryConflictError, match="leverage"):
        PaperFuturesSQLiteHistory(changed_context, store).record_entry(
            basket_id=BASKET_ID,
            entry_number=2,
            fill=entry_fill(sequence=2),
        )


@pytest.mark.parametrize(
    ("position_side", "entry_side", "exit_side"),
    [
        (PositionSide.LONG, FillSide.BUY, FillSide.SELL),
        (PositionSide.SHORT, FillSide.SELL, FillSide.BUY),
    ],
)
def test_close_uses_shared_pnl_and_opposite_fill_side(
    tmp_path: Path,
    position_side: PositionSide,
    entry_side: FillSide,
    exit_side: FillSide,
) -> None:
    database = SQLiteDatabase(tmp_path / f"{position_side.value}.sqlite3")
    database.migrate()
    store = SQLiteTradeHistory(database)
    history = PaperFuturesSQLiteHistory(history_context(), store)
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(side=position_side),
    )
    closed = closed_basket(side=position_side)

    assert history.record_close(
        basket_id=BASKET_ID,
        fill=exit_fill(side=position_side),
        closed=closed,
    )

    basket = store.get_basket(BASKET_ID)
    fills = store.list_fills(BASKET_ID)
    assert basket is not None
    assert basket.status is BasketStatus.CLOSED
    assert basket.gross_realized_pnl == closed.gross_realized_pnl
    assert basket.trading_fees == closed.trading_fees
    assert basket.funding_fee == Decimal("0.00")
    assert basket.funding_fee.as_tuple().exponent == -2
    assert basket.net_realized_pnl == closed.net_realized_pnl
    assert [item.side for item in fills] == [entry_side, exit_side]
    assert fills[-1].realized_pnl == closed.net_realized_pnl


def test_duplicate_entry_and_close_are_idempotent(
    history: PaperFuturesSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    entry = entry_fill()
    exit = exit_fill()
    closed = closed_basket()

    assert history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry,
    )
    assert not history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry,
    )
    assert history.record_close(
        basket_id=BASKET_ID,
        fill=exit,
        closed=closed,
    )
    persisted = store.get_basket(BASKET_ID)
    assert not history.record_close(
        basket_id=BASKET_ID,
        fill=exit,
        closed=closed,
    )

    assert store.get_basket(BASKET_ID) == persisted
    assert len(store.list_fills(BASKET_ID)) == 2


def test_mapper_rejects_nonzero_paper_funding(
    history: PaperFuturesSQLiteHistory,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    invalid = closed_basket()
    invalid = ClosedBasket(
        basket_id=invalid.basket_id,
        entry_count=invalid.entry_count,
        average_entry_price=invalid.average_entry_price,
        exit_price=invalid.exit_price,
        gross_realized_pnl=invalid.gross_realized_pnl,
        trading_fees=invalid.trading_fees,
        funding_fee=Decimal("1"),
        net_realized_pnl=invalid.net_realized_pnl - Decimal("1"),
        closed_at=invalid.closed_at,
        position_side=invalid.position_side,
        close_reason=invalid.close_reason,
    )

    with pytest.raises(ValueError, match="Funding Fee must be 0.00"):
        history.record_close(
            basket_id=BASKET_ID,
            fill=exit_fill(),
            closed=invalid,
        )


@pytest.mark.parametrize(
    ("basket_id", "fill_side", "message"),
    [
        (
            UUID("00000000-0000-0000-0000-000000000999"),
            PositionSide.LONG,
            "does not match",
        ),
        (BASKET_ID, PositionSide.SHORT, "different sides"),
    ],
)
def test_mapper_rejects_inconsistent_close_ownership(
    history: PaperFuturesSQLiteHistory,
    basket_id: UUID,
    fill_side: PositionSide,
    message: str,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )

    with pytest.raises(ValueError, match=message):
        history.record_close(
            basket_id=basket_id,
            fill=exit_fill(side=fill_side),
            closed=closed_basket(),
        )
