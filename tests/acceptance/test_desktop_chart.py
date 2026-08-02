from datetime import UTC, datetime

from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.trade_history_ui import empty_basket_page, empty_fills
from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.application.paper_session_setup import (
    ConfiguredPaperSession,
    PaperSessionCreateOutcome,
    PaperSessionSetupValues,
)
from tiewtrade.ui.main_window import MainWindow


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

    def unused_create(values: PaperSessionSetupValues) -> PaperSessionCreateOutcome:
        del values
        raise AssertionError("create is not used")

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

    qtbot.waitUntil(lambda: window.workspace.chart._snapshot is not None)

    assert window.workspace.chart.isVisible()
    assert window.workspace.bot_control.isVisible()
    assert window.findChildren(QPushButton, "manualBuyButton") == []
    assert window.findChildren(QPushButton, "manualSellButton") == []
