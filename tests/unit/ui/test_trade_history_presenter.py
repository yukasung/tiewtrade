from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from tests.support.trade_history_records import basket_result, trade_fill
from tiewtrade.application.trade_history import TradeHistoryFilter
from tiewtrade.trading.session_config import MarketType, TradeMode
from tiewtrade.trading.trade_history import BasketStatus, FillSource
from tiewtrade.ui.trade_history_presenter import (
    PageState,
    TradeHistoryFilterValues,
    basket_rows,
    fill_rows,
    page_state,
    pnl_text,
    trade_history_filter,
)


def test_filter_values_build_inclusive_utc_date_range() -> None:
    values = TradeHistoryFilterValues(
        symbol="BTCUSDT",
        timeframe="5m",
        market_type="spot",
        trade_mode="paper",
        status="closed",
        from_date=date(2026, 1, 2),
        to_date=date(2026, 1, 3),
    )

    assert trade_history_filter(values) == TradeHistoryFilter(
        symbol="BTCUSDT",
        timeframe="5m",
        market_type=MarketType.SPOT,
        trade_mode=TradeMode.PAPER,
        status=BasketStatus.CLOSED,
        opened_from_utc=datetime(2026, 1, 2, tzinfo=UTC),
        opened_before_utc=datetime(2026, 1, 4, tzinfo=UTC),
    )


def test_filter_values_reject_from_after_to() -> None:
    values = TradeHistoryFilterValues(
        from_date=date(2026, 1, 3),
        to_date=date(2026, 1, 2),
    )

    with pytest.raises(ValueError, match="From Date must not be after To Date"):
        trade_history_filter(values)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("19.580000000000000001"), "19.580000000000000001 USDT · Profit"),
        (Decimal("-0.2"), "-0.2 USDT · Loss"),
        (Decimal("0"), "0.00 USDT · Break-even"),
    ],
)
def test_pnl_text_preserves_decimal_and_adds_semantic_label(
    value: Decimal, expected: str
) -> None:
    assert pnl_text(value) == expected


def test_basket_and_fill_rows_format_utc_and_all_columns() -> None:
    basket = basket_result()
    fill = trade_fill()

    assert basket_rows((basket,))[0].basket_id == basket.basket_id
    assert basket_rows((basket,))[0].values == (
        "2026-01-01 00:00:00 UTC",
        "Paper",
        "Spot",
        "BTCUSDT",
        "5m",
        "1",
        "200 USDT",
        "20 USDT",
        "0.42 USDT",
        "0.00 USDT",
        "19.58 USDT · Profit",
        "Closed",
    )
    assert fill_rows((fill,))[0].values == (
        "2026-01-01 00:00:00 UTC",
        "Buy",
        "1",
        "100",
        "2",
        "200 USDT",
        "0.2 USDT",
        "0.00 USDT · Break-even",
        "Paper Executor",
    )


def test_fill_rows_formats_exit_entry_and_binance_source() -> None:
    fill = trade_fill(entry_number=None, source=FillSource.BINANCE)

    assert fill_rows((fill,))[0].values[2] == "—"
    assert fill_rows((fill,))[0].values[-1] == "Binance"


@pytest.mark.parametrize(
    ("page", "page_size", "total_items", "expected"),
    [
        (1, 50, 0, PageState(1, 1, False, False)),
        (1, 50, 120, PageState(1, 3, False, True)),
        (2, 50, 120, PageState(2, 3, True, True)),
        (3, 50, 120, PageState(3, 3, True, False)),
        (99, 50, 120, PageState(3, 3, True, False)),
    ],
)
def test_page_state_bounds_previous_and_next(
    page: int, page_size: int, total_items: int, expected: PageState
) -> None:
    assert (
        page_state(page=page, page_size=page_size, total_items=total_items) == expected
    )
