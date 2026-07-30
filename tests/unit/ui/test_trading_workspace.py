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

    workspace.close_bot_control()

    assert not workspace.bot_control.isVisible()
    assert workspace.bot_control_button.hasFocus()


def test_resizing_keeps_the_same_bot_control_and_workspace_state(
    qtbot: QtBot,
) -> None:
    workspace = TradingWorkspace()
    qtbot.addWidget(workspace)
    workspace.resize(1200, 700)
    workspace.show()
    session = configured_spot_session()
    bot_control = workspace.bot_control

    workspace.show_configured_session(session)
    workspace.tabs.setCurrentWidget(workspace.trade_history)
    workspace.resize(1199, 700)
    qtbot.waitUntil(lambda: workspace.compact_mode)
    click(workspace.bot_control_button)
    workspace.resize(1200, 700)
    qtbot.waitUntil(lambda: not workspace.compact_mode)

    assert workspace.bot_control is bot_control
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
