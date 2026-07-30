from pytestqt.qtbot import QtBot

from tests.support.paper_session_setup import configured_spot_session
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
    workspace.show()

    workspace.show_unavailable("Paper Session unavailable")
    workspace.set_bot_busy(True)

    assert workspace.unavailable_message.text() == "Paper Session unavailable"
    assert workspace.unavailable_panel.isVisible()
    assert workspace.header_runtime.text() == "Unavailable"
    assert not workspace.unavailable_retry_button.isEnabled()
    assert not workspace.setup.create_button.isEnabled()
