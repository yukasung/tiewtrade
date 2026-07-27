from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from tiewtrade.ui.session_setup import SessionSetupWidget


def test_default_form_builds_paper_spot_values(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    values = widget.values()

    assert values.market_type == "spot"
    assert values.symbol == "BTCUSDT"
    assert values.timeframe == "5m"
    assert values.available_capital == ""
    assert values.max_entries == "10"
    assert values.fee_percent == ""
    assert values.slippage_bps == ""
    assert values.spot_trading_capital_percent == "80"
    assert values.futures_leverage is None
    assert widget.trade_mode_label.text() == "Paper"
    assert widget.market_type.currentData() == "spot"
    assert widget.market_type.count() == 1
    assert widget.symbol_field.isReadOnly()
    assert widget.preset_label.text() == "RSI Step Grid v1"


def test_timeframe_field_offers_every_supported_value(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    values = [
        widget.timeframe.itemData(index) for index in range(widget.timeframe.count())
    ]

    assert values == ["3m", "5m", "15m", "30m", "1h", "4h"]


def test_spot_reserve_ratio_updates_from_trading_capital_input(
    qtbot: QtBot,
) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    assert widget.spot_reserve_ratio.text() == "20%"

    widget.spot_ratio.setText("65.5")

    assert widget.spot_reserve_ratio.text() == "34.5%"


def test_advanced_execution_costs_can_be_revealed(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    assert widget.advanced_costs.isHidden() is True
    assert widget.advanced_toggle.text() == "Show Advanced Settings"

    qtbot.mouseClick(widget.advanced_toggle, Qt.MouseButton.LeftButton)

    assert widget.advanced_costs.isHidden() is False
    assert widget.advanced_toggle.text() == "Hide Advanced Settings"


def test_submit_emits_current_values_once(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)
    widget.available_capital.setText("200000")

    with qtbot.waitSignal(widget.create_requested) as signal:
        qtbot.mouseClick(widget.create_button, Qt.MouseButton.LeftButton)

    assert signal.args == [widget.values()]


def test_loading_disables_repeated_submit(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)
    widget.set_loading(True)

    assert widget.create_button.isEnabled() is False
    assert widget.create_button.text() == "Creating…"

    widget.set_loading(False)

    assert widget.create_button.isEnabled() is True
    assert widget.create_button.text() == "Create Paper Session"


def test_field_error_is_rendered_next_to_its_input(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    widget.show_field_error("available_capital", "Available Capital must be positive")

    assert widget.available_capital_error.text() == (
        "Available Capital must be positive"
    )
