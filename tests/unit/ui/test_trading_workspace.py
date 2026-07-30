from functools import partial

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
from tests.support.qt_interactions import click
from tiewtrade.ui.trading_workspace import TradingWorkspace


def test_workspace_places_existing_features_in_one_screen(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    assert workspace.header_symbol.text() == "No Session"
    assert workspace.chart_state.text() == "Chart is not available yet"
    assert workspace.tabs.tabText(0) == "Open Orders"
    assert workspace.tabs.tabText(1) == "Position / Basket"
    assert workspace.tabs.tabText(2) == "Trade History"
    assert workspace.orders_state.text() == "No open orders"
    assert workspace.position_state.text() == "No open Position or Basket"
    assert workspace.setup.isVisible()


def test_bot_control_is_docked_at_wide_width(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    qtbot.waitUntil(lambda: not workspace.compact_mode)

    assert workspace.bot_control.isVisible()
    assert not workspace.bot_control_button.isVisible()
    assert not workspace.bot_control_close_button.isVisible()


def test_bot_control_uses_drawer_below_breakpoint(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1199, 700)
    workspace.show()
    workspace.activateWindow()

    qtbot.waitUntil(workspace.isActiveWindow)

    qtbot.waitUntil(lambda: workspace.compact_mode)
    assert not workspace.bot_control.isVisible()
    assert workspace.bot_control_button.isVisible()

    click(workspace.bot_control_button)

    assert workspace.bot_control.isVisible()
    assert workspace.bot_control.geometry().right() == workspace.rect().right()
    assert workspace.bot_control_close_button.isVisible()

    click(workspace.bot_control_close_button)

    assert not workspace.bot_control.isVisible()
    assert workspace.bot_control_button.hasFocus()


def test_escape_closes_compact_bot_control_and_restores_trigger_focus(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1024, 700)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)
    qtbot.waitUntil(lambda: workspace.compact_mode)

    click(workspace.bot_control_button)
    workspace.bot_control.setFocus()
    QTest.keyClick(workspace.bot_control, Qt.Key.Key_Escape)

    qtbot.waitUntil(lambda: not workspace.bot_control.isVisible())
    assert workspace.bot_control_button.hasFocus()


def test_resize_transitions_do_not_duplicate_drawer_close_connection(
    qtbot: QtBot,
) -> None:
    class CountingWorkspace(TradingWorkspace):
        def __init__(self) -> None:
            self.close_calls = 0
            super().__init__()

        def close_bot_control(self) -> None:
            self.close_calls += 1
            super().close_bot_control()

    workspace = CountingWorkspace()
    qtbot.addWidget(workspace)
    workspace.show()

    for width in (1200, 1024, 1200, 1024):
        workspace.resize(width, 700)
        expected_compact = width < 1200
        qtbot.waitUntil(partial(_has_compact_mode, workspace, expected_compact))

    click(workspace.bot_control_button)
    click(workspace.bot_control_close_button)

    assert workspace.close_calls == 1


def test_resizing_keeps_the_same_bot_control_and_workspace_state(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    session = configured_spot_session()
    bot_instances = (
        workspace.bot_control,
        workspace._bot_pages,
        workspace.setup,
        workspace.overview,
        workspace.unavailable_panel,
    )

    workspace.show_configured_session(session)
    workspace.tabs.setCurrentWidget(workspace.trade_history)
    workspace.resize(1199, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)
    workspace.resize(1200, 700)
    qtbot.waitUntil(lambda: not workspace.compact_mode)

    assert (
        workspace.bot_control,
        workspace._bot_pages,
        workspace.setup,
        workspace.overview,
        workspace.unavailable_panel,
    ) == bot_instances
    assert workspace.overview.isVisible()
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.tabs.currentWidget() is workspace.trade_history
    assert workspace.bot_control.isVisible()


def test_configured_session_updates_header_and_bot_control(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    session = configured_spot_session()

    workspace.show_configured_session(session)

    assert workspace.header_symbol.text() == session.market_data.symbol
    assert workspace.header_timeframe.text() == session.market_data.timeframe
    assert workspace.header_mode.text() == "Paper · Spot"
    assert workspace.header_runtime.text() == "Configured"
    assert workspace.header_freshness.text() == "Market data not started"
    assert workspace.overview.isVisible()


def test_compact_bot_control_trigger_exposes_current_state(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)

    assert workspace.bot_control_button.text() == "Bot Control · No Session"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: No Session"

    workspace.show_configured_session(configured_spot_session())

    assert workspace.bot_control_button.text() == "Bot Control · Configured"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: Configured"

    workspace.show_unavailable("Session storage is unavailable")

    assert workspace.bot_control_button.text() == "Bot Control · Unavailable"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: Unavailable"

    workspace.show_setup()

    assert workspace.bot_control_button.text() == "Bot Control · No Session"
    assert workspace.bot_control_button.accessibleName() == "Bot Control: No Session"


@pytest.mark.parametrize("content", ["spot", "futures", "advanced"])
def test_bot_control_content_is_scrollable_at_minimum_window_size(
    qtbot: QtBot,
    content: str,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.setFixedSize(1024, 700)
    workspace.show()
    assert (workspace.width(), workspace.height()) == (1024, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)

    target: QWidget = workspace.setup.spot_ratio
    if content == "futures":
        workspace.setup.market_type.setCurrentIndex(
            workspace.setup.market_type.findData("futures")
        )
        target = workspace.setup.leverage
    elif content == "advanced":
        workspace.setup.market_type.setCurrentIndex(
            workspace.setup.market_type.findData("futures")
        )
        click(workspace.setup.advanced_toggle)
        target = workspace.setup.fee_percent

    scroll_bar = workspace.bot_control_scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: scroll_bar.maximum() > 0)

    workspace.bot_control_scroll.ensureWidgetVisible(target)
    qtbot.waitUntil(
        lambda: (
            workspace.bot_control_scroll.viewport()
            .rect()
            .contains(
                _widget_rect_in_viewport(
                    target, workspace.bot_control_scroll.viewport()
                )
            )
        )
    )

    assert scroll_bar.maximum() > 0
    assert workspace.bot_control_scroll.widget() is workspace._bot_pages


def test_trade_history_signal_is_emitted_when_tab_is_opened(qtbot: QtBot) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)

    with qtbot.waitSignal(workspace.trade_history_activated):
        workspace.tabs.setCurrentWidget(workspace.trade_history)


def test_unavailable_state_and_busy_control_are_scoped_to_bot_control(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()

    workspace.show_unavailable("Paper Session unavailable")
    workspace.set_bot_busy(True)

    assert workspace.unavailable_message.text() == "Paper Session unavailable"
    assert workspace.unavailable_panel.isVisible()
    assert workspace.header_runtime.text() == "Unavailable"
    assert not workspace.unavailable_retry_button.isEnabled()
    assert not workspace.setup.create_button.isEnabled()


def _widget_rect_in_viewport(widget: QWidget, viewport: QWidget) -> QRect:
    return QRect(widget.mapTo(viewport, QPoint(0, 0)), widget.size())


def _has_compact_mode(workspace: TradingWorkspace, expected: bool) -> bool:
    return workspace.compact_mode is expected
