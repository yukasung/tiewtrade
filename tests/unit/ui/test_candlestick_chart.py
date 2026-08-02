from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.trade_history import FillSide, TradeFill
from tiewtrade.ui.candlestick_chart import CandlestickChartWidget


def test_chart_renders_durable_buy_and_sell_markers_without_action_buttons(
    qtbot: QtBot,
) -> None:
    chart = CandlestickChartWidget()
    qtbot.addWidget(chart)
    chart.show_snapshot(ready_snapshot())
    chart.show()

    assert chart.accessibleName() == "Candlestick chart for BTCUSDT 5m"
    assert chart.marker_labels == ("Buy", "Sell")
    assert chart.findChildren(QPushButton, "manualOrderButton") == []
    assert not chart.grab().isNull()


def test_previous_and_next_range_controls_are_keyboard_accessible(qtbot: QtBot) -> None:
    chart = CandlestickChartWidget()
    qtbot.addWidget(chart)
    chart.show_snapshot(ready_snapshot())
    requests: list[ChartRange] = []
    chart.range_requested.connect(requests.append)

    chart.next_range_button.setFocus()
    cast(Any, qtbot).keyClick(chart.next_range_button, Qt.Key.Key_Space)
    chart.previous_range_button.setFocus()
    cast(Any, qtbot).keyClick(chart.previous_range_button, Qt.Key.Key_Space)

    assert chart.next_range_button.accessibleName() == "Next chart range"
    assert chart.previous_range_button.accessibleName() == "Previous chart range"
    assert requests == [
        ChartRange(
            datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 40, tzinfo=UTC),
        ),
        ChartRange(
            datetime(2025, 12, 31, 23, 40, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        ),
    ]


def ready_snapshot() -> ChartSnapshot:
    session = configured_spot_session()
    chart_range = ChartRange(
        datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
    )
    buy = fill("buy-1", FillSide.BUY, datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    sell = fill("sell-1", FillSide.SELL, datetime(2026, 1, 1, 0, 10, tzinfo=UTC))
    return ChartSnapshot(
        session=session,
        chart_range=chart_range,
        observed_at_utc=chart_range.end,
        candles=(candle(0), candle(5), candle(10)),
        fills=(buy, sell),
        state=ChartReadState.READY,
    )


def candle(minute: int) -> Candle:
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("106"),
        low=Decimal("99"),
        close=Decimal("103"),
        volume=Decimal("1"),
    )


def fill(fill_id: str, side: FillSide, filled_at_utc: datetime) -> TradeFill:
    from tests.support.trade_history_records import trade_fill

    return trade_fill(
        fill_id=fill_id,
        side=side,
        session_id=configured_spot_session().config.session_id,
        filled_at_utc=filled_at_utc,
        price=Decimal("102"),
        quantity=Decimal("2"),
        notional=Decimal("204"),
    )
