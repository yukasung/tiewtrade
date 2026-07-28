from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from tiewtrade.application.paper_spot_session import PaperSpotSessionIdentity
from tiewtrade.execution.paper_spot import PaperSpotEntryFill, PaperSpotExitFill
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.paper_spot_history import (
    PaperSpotHistoryContext,
    PaperSpotSQLiteHistory,
)
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.basket import ClosedBasket
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
OPENED_AT = datetime(2026, 1, 1, tzinfo=UTC)
CLOSED_AT = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    return SQLiteTradeHistory(database)


@pytest.fixture
def history(store: SQLiteTradeHistory) -> PaperSpotSQLiteHistory:
    return PaperSpotSQLiteHistory(
        PaperSpotHistoryContext(
            session_id=SESSION_ID,
            symbol="BTCUSDT",
            timeframe="5m",
            preset_version="rsi-step-grid-v1",
            commission_asset="USDT",
        ),
        store,
    )


def test_history_exposes_session_identity(
    history: PaperSpotSQLiteHistory,
) -> None:
    assert history.session_identity == PaperSpotSessionIdentity(
        session_id=SESSION_ID,
        symbol="BTCUSDT",
        timeframe="5m",
        preset_version="rsi-step-grid-v1",
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


def test_entry_fill_creates_exact_open_basket_and_buy_fill(
    history: PaperSpotSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    fill = entry_fill()

    result = history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=fill,
    )

    assert result is True
    assert store.get_basket(BASKET_ID) == BasketResult(
        basket_id=BASKET_ID,
        session_id=SESSION_ID,
        trade_mode=TradeMode.PAPER,
        market_type=MarketType.SPOT,
        symbol="BTCUSDT",
        timeframe="5m",
        strategy_preset_version="rsi-step-grid-v1",
        opened_at_utc=OPENED_AT,
        closed_at_utc=None,
        entry_count=1,
        invested_notional=Decimal("200"),
        gross_realized_pnl=Decimal("0"),
        trading_fees=Decimal("0.2"),
        funding_fee=Decimal("0"),
        net_realized_pnl=Decimal("-0.2"),
        status=BasketStatus.OPEN,
    )
    assert store.list_fills(BASKET_ID) == (
        TradeFill(
            fill_id=fill.fill_id,
            basket_id=BASKET_ID,
            session_id=SESSION_ID,
            order_id=fill.order_id,
            exchange_trade_id=None,
            side=FillSide.BUY,
            entry_number=1,
            filled_at_utc=OPENED_AT,
            price=Decimal("100"),
            quantity=Decimal("2"),
            notional=Decimal("200"),
            commission=Decimal("0.2"),
            commission_asset="USDT",
            realized_pnl=Decimal("0"),
            source=FillSource.PAPER_EXECUTOR,
        ),
    )


def test_second_entry_replaces_open_aggregate_and_records_another_buy_fill(
    history: PaperSpotSQLiteHistory,
    store: SQLiteTradeHistory,
) -> None:
    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=1,
        fill=entry_fill(),
    )
    second_fill = PaperSpotEntryFill(
        intent_id="intent-2",
        order_id="entry:intent-2",
        fill_id=f"paper:{SESSION_ID}:entry:intent-2:fill",
        price=Decimal("90"),
        quantity=Decimal("1"),
        fee=Decimal("0.09"),
        filled_at=OPENED_AT + timedelta(hours=1),
    )

    history.record_entry(
        basket_id=BASKET_ID,
        entry_number=2,
        fill=second_fill,
    )

    basket = store.get_basket(BASKET_ID)
    fills = store.list_fills(BASKET_ID)
    assert basket is not None
    assert basket.opened_at_utc == OPENED_AT
    assert basket.entry_count == 2
    assert basket.invested_notional == Decimal("290")
    assert basket.trading_fees == Decimal("0.29")
    assert basket.net_realized_pnl == Decimal("-0.29")
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.BUY]
    assert fills[1].entry_number == 2
    assert fills[1].notional == Decimal("90")
    assert fills[1].commission == Decimal("0.09")


def test_close_records_exact_closed_basket_and_sell_fill(
    history: PaperSpotSQLiteHistory,
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

    basket = store.get_basket(BASKET_ID)
    fills = store.list_fills(BASKET_ID)
    assert basket is not None
    assert basket.status is BasketStatus.CLOSED
    assert basket.opened_at_utc == OPENED_AT
    assert basket.closed_at_utc == CLOSED_AT
    assert basket.invested_notional == Decimal("200")
    assert basket.gross_realized_pnl == Decimal("20")
    assert basket.trading_fees == Decimal("0.42")
    assert basket.funding_fee == Decimal("0")
    assert basket.net_realized_pnl == Decimal("19.58")
    assert [fill.side for fill in fills] == [FillSide.BUY, FillSide.SELL]
    assert fills[1] == TradeFill(
        fill_id=exit_fill().fill_id,
        basket_id=BASKET_ID,
        session_id=SESSION_ID,
        order_id=exit_fill().order_id,
        exchange_trade_id=None,
        side=FillSide.SELL,
        entry_number=None,
        filled_at_utc=CLOSED_AT,
        price=Decimal("110"),
        quantity=Decimal("2"),
        notional=Decimal("220"),
        commission=Decimal("0.22"),
        commission_asset="USDT",
        realized_pnl=Decimal("19.58"),
        source=FillSource.PAPER_EXECUTOR,
    )


def test_mapper_propagates_duplicate_write_result(
    history: PaperSpotSQLiteHistory,
) -> None:
    fill = entry_fill()

    assert (
        history.record_entry(
            basket_id=BASKET_ID,
            entry_number=1,
            fill=fill,
        )
        is True
    )
    assert (
        history.record_entry(
            basket_id=BASKET_ID,
            entry_number=1,
            fill=fill,
        )
        is False
    )
