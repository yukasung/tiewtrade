from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

import tiewtrade.ui.candlestick_chart as chart_module
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
    assert chart._facts.text() == "BTCUSDT · 5m · Paper"
    assert chart.marker_labels == ("Buy", "Sell")
    assert chart.findChildren(QPushButton, "manualOrderButton") == []
    assert not chart.grab().isNull()


def test_painter_model_contains_buy_sell_triangles_and_scaled_volume_geometry() -> None:
    snapshot = ready_snapshot(
        candles=(
            candle(0, volume="1", open_price="100", close_price="103"),
            candle(5, volume="3", open_price="103", close_price="101"),
            candle(10, volume="2", open_price="101", close_price="104"),
        )
    )

    model = chart_module._build_painter_model(snapshot, QRectF(0, 0, 300, 200))

    assert len(model.candles) == 3
    assert [round(glyph.volume_bar.height(), 2) for glyph in model.candles] == [
        20.0,
        60.0,
        40.0,
    ]
    buy, sell = model.markers
    assert buy.label == "Buy"
    assert buy.triangle[0].y() < buy.triangle[1].y()
    assert sell.label == "Sell"
    assert sell.triangle[0].y() > sell.triangle[1].y()
    assert all(glyph.body.width() > 0 for glyph in model.candles)


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
            datetime(2025, 12, 31, 23, 40, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        ),
    ]


def test_next_range_is_disabled_at_latest_completed_boundary(qtbot: QtBot) -> None:
    chart = CandlestickChartWidget()
    qtbot.addWidget(chart)
    snapshot = ready_snapshot()
    chart.show_snapshot(snapshot)
    requests: list[ChartRange] = []
    chart.range_requested.connect(requests.append)

    assert snapshot.chart_range.end == snapshot.observed_at_utc
    assert not chart.next_range_button.isEnabled()
    chart.next_range_button.click()
    assert requests == []


def test_next_range_is_limited_to_latest_completed_boundary(qtbot: QtBot) -> None:
    chart = CandlestickChartWidget()
    qtbot.addWidget(chart)
    session = configured_spot_session()
    selected_range = ChartRange(
        datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 0, 15, tzinfo=UTC),
    )
    chart.show_snapshot(
        ChartSnapshot(
            session=session,
            chart_range=selected_range,
            observed_at_utc=datetime(2026, 1, 1, 0, 23, tzinfo=UTC),
            candles=(),
            fills=(),
            state=ChartReadState.EMPTY,
        )
    )
    requests: list[ChartRange] = []
    chart.range_requested.connect(requests.append)

    chart.next_range_button.click()

    assert requests == [
        ChartRange(
            datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
            datetime(2026, 1, 1, 0, 20, tzinfo=UTC),
        )
    ]


def test_unavailable_chart_exposes_chart_specific_retry(qtbot: QtBot) -> None:
    chart = CandlestickChartWidget()
    qtbot.addWidget(chart)
    snapshot = ready_snapshot()
    chart.show_snapshot(
        ChartSnapshot(
            _session_facts=(snapshot.session_id, snapshot.symbol, snapshot.timeframe),
            chart_range=snapshot.chart_range,
            observed_at_utc=snapshot.observed_at_utc,
            candles=(),
            fills=(),
            state=ChartReadState.UNAVAILABLE,
            message="Chart is unavailable",
        )
    )
    retries: list[bool] = []
    chart.retry_requested.connect(lambda: retries.append(True))

    assert chart.retry_button.isVisibleTo(chart)
    assert chart.retry_button.accessibleName() == "Retry chart"
    chart.retry_button.click()

    assert retries == [True]


def ready_snapshot(*, candles: tuple[Candle, ...] | None = None) -> ChartSnapshot:
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
        candles=candles or (candle(0), candle(5), candle(10)),
        fills=(buy, sell),
        state=ChartReadState.READY,
    )


def candle(
    minute: int,
    *,
    volume: str = "1",
    open_price: str = "100",
    close_price: str = "103",
) -> Candle:
    open_value = Decimal(open_price)
    close_value = Decimal(close_price)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=UTC),
        open=open_value,
        high=max(open_value, close_value) + Decimal("3"),
        low=Decimal("99"),
        close=close_value,
        volume=Decimal(volume),
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
