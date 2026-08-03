from datetime import UTC, datetime
from decimal import Decimal

from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.trade_history_records import trade_fill
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.chart_data import (
    ChartRange,
    ChartReadState,
    ChartSnapshot,
)
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.trade_history import FillSide
from tiewtrade.ui.bot_lifecycle_workflow import RuntimeSnapshotRelay
from tiewtrade.ui.main_window import MainWindow


def unused_create(
    values: PaperSessionSetupValues,
) -> PaperSessionCreateOutcome:
    del values
    raise AssertionError("create is not used")


def test_desktop_shows_configured_session_chart_without_manual_order_controls(
    qtbot: QtBot,
) -> None:
    session = configured_spot_session()

    async def load_chart(
        configured: ConfiguredPaperSession, chart_range: ChartRange
    ) -> ChartSnapshot:
        return ChartSnapshot(
            session=configured,
            chart_range=chart_range,
            observed_at_utc=chart_range.end,
            candles=(),
            fills=(),
            state=ChartReadState.EMPTY,
        )

    window = MainWindow(
        create_session=unused_create,
        load_active=lambda: session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        load_chart=load_chart,
        chart_clock=lambda: datetime(2026, 8, 2, 10, 3, tzinfo=UTC),
    )
    qtbot.addWidget(window)
    window.resize(1200, 700)
    window.show()

    qtbot.waitUntil(
        lambda: (
            window.workspace.chart._snapshot is not None
            and window.workspace.chart._snapshot.state is ChartReadState.EMPTY
        )
    )

    assert window.workspace.chart.isVisible()
    assert window.workspace.bot_control.isVisible()
    assert window.findChildren(QPushButton, "manualBuyButton") == []
    assert window.findChildren(QPushButton, "manualSellButton") == []


def test_runtime_completed_candle_updates_chart_and_new_durable_fill_marker(
    qtbot: QtBot,
) -> None:
    session = configured_spot_session()
    relay = RuntimeSnapshotRelay()
    relayed: list[Candle] = []
    refreshed: list[Candle] = []
    relay.completed_candle_ready.connect(
        lambda candle, _generation: relayed.append(candle)
    )

    async def load_chart(
        configured: ConfiguredPaperSession, chart_range: ChartRange
    ) -> ChartSnapshot:
        return ChartSnapshot(
            session=configured,
            chart_range=chart_range,
            observed_at_utc=chart_range.end,
            candles=(),
            fills=(),
            state=ChartReadState.EMPTY,
        )

    async def refresh_chart(
        configured: ConfiguredPaperSession,
        current: ChartSnapshot,
        completed: Candle,
    ) -> ChartSnapshot:
        refreshed.append(completed)
        duration = current.chart_range.end - current.chart_range.start
        next_range = ChartRange(completed.close_time - duration, completed.close_time)
        fill = trade_fill(
            fill_id="runtime-buy",
            side=FillSide.BUY,
            session_id=configured.config.session_id,
            filled_at_utc=completed.open_time,
        )
        return ChartSnapshot(
            session=configured,
            chart_range=next_range,
            observed_at_utc=completed.close_time,
            candles=(completed,),
            fills=(fill,),
            state=ChartReadState.READY,
        )

    window = MainWindow(
        create_session=unused_create,
        load_active=lambda: session,
        list_baskets=empty_basket_page,
        list_fills=empty_fills,
        load_chart=load_chart,
        refresh_chart=refresh_chart,
        runtime_snapshots=relay,
        chart_clock=lambda: datetime(2026, 8, 2, 10, 3, tzinfo=UTC),
    )
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.workspace.chart._snapshot is not None)
    publisher = relay.new_generation()
    completed = Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
        open=Decimal("100"),
        high=Decimal("106"),
        low=Decimal("99"),
        close=Decimal("103"),
        volume=Decimal("2"),
    )

    publisher.completed_candle(completed)

    qtbot.waitUntil(lambda: relayed == [completed])
    qtbot.waitUntil(lambda: refreshed == [completed])
    qtbot.waitUntil(lambda: window.workspace.chart.marker_labels == ("Buy",))
    snapshot = window.workspace.chart._snapshot
    assert snapshot is not None
    assert snapshot.candles == (completed,)
