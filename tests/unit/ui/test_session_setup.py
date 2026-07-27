from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from tiewtrade.trading.futures_policy import FuturesTradingPolicy
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
    assert [
        widget.market_type.itemData(index)
        for index in range(widget.market_type.count())
    ] == ["spot", "futures"]
    assert widget.market_type.isEnabled()
    assert widget.symbol_field.isReadOnly()
    assert widget.preset_label.text() == "RSI Step Grid v1"


def test_futures_selection_shows_futures_policy_and_hides_spot_ratio(
    qtbot: QtBot,
) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    widget.market_type.setCurrentIndex(widget.market_type.findData("futures"))

    assert widget.spot_fields.isHidden()
    assert widget.futures_fields.isHidden() is False
    assert widget.margin_mode_value.text() == "Cross Margin"
    assert widget.position_mode_value.text() == "One-way Mode"
    assert widget.trading_capital_value.text() == "50%"
    assert widget.collateral_buffer_value.text() == "50%"
    assert widget.values().spot_trading_capital_percent is None
    assert widget.values().futures_leverage == "1"


def test_futures_leverage_input_uses_domain_bounds(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)

    assert widget.leverage.minimum() == FuturesTradingPolicy.V1_MINIMUM_LEVERAGE
    assert widget.leverage.maximum() == FuturesTradingPolicy.V1_MAXIMUM_LEVERAGE


def test_futures_request_includes_selected_leverage(qtbot: QtBot) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)
    widget.market_type.setCurrentIndex(widget.market_type.findData("futures"))

    widget.leverage.setValue(5)

    assert widget.values().futures_leverage == "5"


def test_switching_back_to_spot_removes_futures_input_from_request(
    qtbot: QtBot,
) -> None:
    widget = SessionSetupWidget()
    qtbot.addWidget(widget)
    widget.market_type.setCurrentIndex(widget.market_type.findData("futures"))
    widget.leverage.setValue(5)

    widget.market_type.setCurrentIndex(widget.market_type.findData("spot"))

    values = widget.values()

    assert values.market_type == "spot"
    assert values.futures_leverage is None
    assert values.spot_trading_capital_percent == widget.spot_ratio.text()


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
