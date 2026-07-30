from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from tiewtrade.application.trade_history import PageRequest, TradeHistoryFilter
from tiewtrade.integrations.sqlite.database import SQLiteDatabase
from tiewtrade.integrations.sqlite.trade_history import SQLiteTradeHistory
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import (
    BasketResult,
    BasketStatus,
    FillSide,
    FillSource,
    TradeFill,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000201")
LOW_ID = UUID("00000000-0000-0000-0000-000000000211")
HIGH_ID = UUID("00000000-0000-0000-0000-000000000212")
OLD_ID = UUID("00000000-0000-0000-0000-000000000213")


@pytest.fixture
def history(tmp_path: Path) -> SQLiteTradeHistory:
    database = SQLiteDatabase(tmp_path / "history.sqlite3")
    database.migrate()
    return SQLiteTradeHistory(database)


def basket(
    basket_id: UUID,
    *,
    opened_at_utc: datetime,
    symbol: str = "BTCUSDT",
    timeframe: str = "5m",
    market_type: MarketType = MarketType.SPOT,
    trade_mode: TradeMode = TradeMode.PAPER,
    status: BasketStatus = BasketStatus.CLOSED,
    net_realized_pnl: Decimal = Decimal("0"),
) -> BasketResult:
    closed = status is BasketStatus.CLOSED
    return BasketResult(
        basket_id=basket_id,
        session_id=SESSION_ID,
        trade_mode=trade_mode,
        market_type=market_type,
        symbol=symbol,
        timeframe=timeframe,
        strategy_preset_version="rsi-step-grid-v1",
        opened_at_utc=opened_at_utc,
        closed_at_utc=opened_at_utc + timedelta(hours=1) if closed else None,
        entry_count=1,
        invested_notional=Decimal("100"),
        gross_realized_pnl=net_realized_pnl if closed else Decimal("0"),
        trading_fees=Decimal("0"),
        funding_fee=Decimal("0"),
        net_realized_pnl=net_realized_pnl if closed else Decimal("0"),
        status=status,
        leverage=3 if market_type is MarketType.FUTURES else None,
    )


def fill(
    basket_result: BasketResult,
    *,
    fill_id: str,
    side: FillSide,
    filled_at_utc: datetime,
) -> TradeFill:
    return TradeFill(
        fill_id=fill_id,
        basket_id=basket_result.basket_id,
        session_id=basket_result.session_id,
        order_id=f"order-{fill_id}",
        exchange_trade_id=None,
        side=side,
        entry_number=1 if side is FillSide.BUY else None,
        filled_at_utc=filled_at_utc,
        price=Decimal("100"),
        quantity=Decimal("1"),
        notional=Decimal("100"),
        commission=Decimal("0"),
        commission_asset="USDT",
        realized_pnl=(
            basket_result.net_realized_pnl if side is FillSide.SELL else Decimal("0")
        ),
        source=FillSource.PAPER_EXECUTOR,
    )


def record(history: SQLiteTradeHistory, result: BasketResult) -> None:
    opened = replace(
        result,
        closed_at_utc=None,
        gross_realized_pnl=Decimal("0"),
        net_realized_pnl=Decimal("0"),
        status=BasketStatus.OPEN,
    )
    history.record_open_basket(
        opened,
        fill(
            opened,
            fill_id=f"{result.basket_id}-buy",
            side=FillSide.BUY,
            filled_at_utc=result.opened_at_utc,
        ),
    )
    if result.status is BasketStatus.CLOSED:
        assert result.closed_at_utc is not None
        history.record_closed_basket(
            result,
            fill(
                result,
                fill_id=f"{result.basket_id}-sell",
                side=FillSide.SELL,
                filled_at_utc=result.closed_at_utc,
            ),
        )


def test_list_baskets_returns_latest_deterministic_page_total_and_exact_summary(
    history: SQLiteTradeHistory,
) -> None:
    latest = datetime(2026, 2, 1, tzinfo=UTC)
    records = (
        basket(
            LOW_ID,
            opened_at_utc=latest,
            net_realized_pnl=Decimal("9999999999999999999999999999"),
        ),
        basket(
            HIGH_ID,
            opened_at_utc=latest,
            net_realized_pnl=Decimal("0.1"),
        ),
        basket(
            OLD_ID,
            opened_at_utc=latest - timedelta(days=1),
            net_realized_pnl=Decimal("0.000000000000000001"),
        ),
    )
    for result in records:
        record(history, result)

    first_page = history.list_baskets(
        TradeHistoryFilter(),
        PageRequest(page=1, page_size=2),
    )
    second_page = history.list_baskets(
        TradeHistoryFilter(),
        PageRequest(page=2, page_size=2),
    )

    assert [item.basket_id for item in first_page.items] == [HIGH_ID, LOW_ID]
    assert first_page.total_items == 3
    assert first_page.net_realized_pnl == Decimal(
        "9999999999999999999999999999.100000000000000001"
    )
    assert [item.basket_id for item in second_page.items] == [OLD_ID]
    assert second_page.total_items == 3
    assert second_page.net_realized_pnl == first_page.net_realized_pnl


def test_list_baskets_filters_every_supported_dimension(
    history: SQLiteTradeHistory,
) -> None:
    boundary = datetime(2026, 2, 1, tzinfo=UTC)
    target = basket(
        HIGH_ID,
        opened_at_utc=boundary,
        net_realized_pnl=Decimal("5.123"),
    )
    alternatives = (
        basket(
            LOW_ID,
            opened_at_utc=boundary - timedelta(microseconds=1),
            net_realized_pnl=Decimal("2.5"),
        ),
        basket(
            OLD_ID,
            opened_at_utc=boundary,
            symbol="ETHUSDT",
            timeframe="15m",
            market_type=MarketType.FUTURES,
            trade_mode=TradeMode.LIVE,
            status=BasketStatus.OPEN,
        ),
    )
    for result in (target, *alternatives):
        record(history, result)

    cases = (
        (
            TradeHistoryFilter(symbol="BTCUSDT"),
            (target, alternatives[0]),
            Decimal("7.623"),
        ),
        (
            TradeHistoryFilter(timeframe="5m"),
            (target, alternatives[0]),
            Decimal("7.623"),
        ),
        (
            TradeHistoryFilter(market_type=MarketType.SPOT),
            (target, alternatives[0]),
            Decimal("7.623"),
        ),
        (
            TradeHistoryFilter(trade_mode=TradeMode.PAPER),
            (target, alternatives[0]),
            Decimal("7.623"),
        ),
        (
            TradeHistoryFilter(status=BasketStatus.CLOSED),
            (target, alternatives[0]),
            Decimal("7.623"),
        ),
        (
            TradeHistoryFilter(opened_from_utc=boundary),
            (alternatives[1], target),
            Decimal("5.123"),
        ),
        (
            TradeHistoryFilter(opened_before_utc=boundary),
            (alternatives[0],),
            Decimal("2.5"),
        ),
    )

    for filters, expected, expected_net_realized_pnl in cases:
        page = history.list_baskets(filters, PageRequest(page=1, page_size=20))
        assert page.items == expected
        assert page.net_realized_pnl == expected_net_realized_pnl

    exact = history.list_baskets(
        TradeHistoryFilter(
            symbol="BTCUSDT",
            timeframe="5m",
            market_type=MarketType.SPOT,
            trade_mode=TradeMode.PAPER,
            status=BasketStatus.CLOSED,
            opened_from_utc=boundary,
            opened_before_utc=boundary + timedelta(microseconds=1),
        ),
        PageRequest(page=1, page_size=20),
    )

    assert exact.items == (target,)
    assert exact.total_items == 1
    assert exact.net_realized_pnl == Decimal("5.123")


def test_open_filter_has_zero_closed_basket_summary(
    history: SQLiteTradeHistory,
) -> None:
    opened = basket(
        HIGH_ID,
        opened_at_utc=datetime(2026, 2, 1, tzinfo=UTC),
        status=BasketStatus.OPEN,
    )
    record(history, opened)

    result = history.list_baskets(
        TradeHistoryFilter(status=BasketStatus.OPEN),
        PageRequest(),
    )

    assert result.items == (opened,)
    assert result.total_items == 1
    assert result.net_realized_pnl == Decimal("0")


def test_list_baskets_returns_empty_page_beyond_results(
    history: SQLiteTradeHistory,
) -> None:
    record(
        history,
        basket(HIGH_ID, opened_at_utc=datetime(2026, 2, 1, tzinfo=UTC)),
    )

    result = history.list_baskets(
        TradeHistoryFilter(),
        PageRequest(page=2, page_size=10),
    )

    assert result.items == ()
    assert result.total_items == 1
    assert result.net_realized_pnl == Decimal("0")


def test_list_fills_uses_execution_time_then_fill_id(
    history: SQLiteTradeHistory,
) -> None:
    timestamp = datetime(2026, 2, 1, tzinfo=UTC)
    opened = basket(HIGH_ID, opened_at_utc=timestamp, status=BasketStatus.OPEN)
    fill_z = fill(
        opened,
        fill_id="fill-z",
        side=FillSide.BUY,
        filled_at_utc=timestamp,
    )
    history.record_open_basket(opened, fill_z)
    fill_a = replace(
        fill_z,
        fill_id="fill-a",
    )
    history.record_entry_fill(opened, fill_a)

    assert history.list_fills(HIGH_ID) == (fill_a, fill_z)
