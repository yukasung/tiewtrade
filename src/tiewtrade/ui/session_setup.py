from collections.abc import Iterable
from decimal import Decimal

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from tiewtrade.application.paper_session_setup import (
    PaperSessionSetupValues,
    PaperSessionValidationError,
    spot_trading_policy_from_percent,
)
from tiewtrade.market_data.config import SUPPORTED_V1_TIMEFRAME_CHOICES
from tiewtrade.trading.futures_policy import FuturesTradingPolicy
from tiewtrade.ui.preset_display import preset_display_name


class SessionSetupWidget(QWidget):
    create_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sessionSetup")
        self._field_errors: dict[str, QLabel] = {}

        self.trade_mode_label = QLabel("Paper")
        self.trade_mode_label.setObjectName("readOnlyValue")

        self.market_type = QComboBox()
        self.market_type.setObjectName("marketType")
        self.market_type.addItem("Spot", "spot")
        self.market_type.addItem("Futures", "futures")

        self.symbol_field = QLineEdit("BTCUSDT")
        self.symbol_field.setObjectName("symbol")
        self.symbol_field.setReadOnly(True)

        self.timeframe = QComboBox()
        self.timeframe.setObjectName("timeframe")
        for timeframe in SUPPORTED_V1_TIMEFRAME_CHOICES:
            self.timeframe.addItem(timeframe, timeframe)
        self.timeframe.setCurrentIndex(self.timeframe.findData("5m"))

        self.available_capital = QLineEdit()
        self.available_capital.setObjectName("availableCapital")
        self.available_capital.setPlaceholderText("Enter available USDT")
        self.available_capital_error = self._error_label("available_capital")

        self.max_entries = QSpinBox()
        self.max_entries.setObjectName("maxEntries")
        self.max_entries.setRange(2, 20)
        self.max_entries.setSingleStep(2)
        self.max_entries.setValue(10)
        self.max_entries_error = self._error_label("max_entries")

        self.preset_label = QLabel(preset_display_name("rsi-step-grid-v1"))
        self.preset_label.setObjectName("readOnlyValue")

        self.spot_ratio = QLineEdit("80")
        self.spot_ratio.setObjectName("spotTradingCapitalPercent")
        self.spot_ratio.setPlaceholderText("Percent")
        self.spot_ratio.textChanged.connect(self._update_spot_reserve_ratio)
        self.spot_ratio_error = self._error_label("spot_trading_capital_percent")
        self.spot_reserve_ratio = QLabel("20%")
        self.spot_reserve_ratio.setObjectName("readOnlyValue")

        futures_policy = FuturesTradingPolicy.v1(
            leverage=FuturesTradingPolicy.V1_MINIMUM_LEVERAGE
        )
        self.leverage = QSpinBox()
        self.leverage.setObjectName("futuresLeverage")
        self.leverage.setRange(
            FuturesTradingPolicy.V1_MINIMUM_LEVERAGE,
            FuturesTradingPolicy.V1_MAXIMUM_LEVERAGE,
        )
        self.leverage.setValue(futures_policy.leverage)
        self.margin_mode_value = QLabel(
            f"{futures_policy.margin_mode.value.title()} Margin"
        )
        self.margin_mode_value.setObjectName("readOnlyValue")
        self.position_mode_value = QLabel(
            f"{futures_policy.position_mode.value.replace('_', '-').capitalize()} Mode"
        )
        self.position_mode_value.setObjectName("readOnlyValue")
        self.trading_capital_value = QLabel(
            _percent_text(futures_policy.trading_capital_ratio)
        )
        self.trading_capital_value.setObjectName("readOnlyValue")
        self.collateral_buffer_value = QLabel(
            _percent_text(futures_policy.collateral_buffer_ratio)
        )
        self.collateral_buffer_value.setObjectName("readOnlyValue")

        self.fee_percent = QLineEdit()
        self.fee_percent.setObjectName("feePercent")
        self.fee_percent.setPlaceholderText("Percent")
        self.fee_percent_error = self._error_label("fee_percent")

        self.slippage_bps = QLineEdit()
        self.slippage_bps.setObjectName("slippageBps")
        self.slippage_bps.setPlaceholderText("Basis points")
        self.slippage_bps_error = self._error_label("slippage_bps")

        self.symbol_error = self._error_label("symbol")
        self.timeframe_error = self._error_label("timeframe")
        self.market_type_error = self._error_label("market_type")

        self.create_button = QPushButton("Create Paper Session")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._submit)

        self.advanced_toggle = QPushButton("Show Advanced Settings")
        self.advanced_toggle.setObjectName("advancedButton")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        self.advanced_costs = self._build_advanced_costs()
        self.advanced_costs.setVisible(False)

        self._build_layout()
        self.market_type.currentIndexChanged.connect(self._sync_market_fields)
        self._sync_market_fields()

    def values(self) -> PaperSessionSetupValues:
        futures = self.market_type.currentData() == "futures"
        return PaperSessionSetupValues(
            market_type=str(self.market_type.currentData()),
            symbol=self.symbol_field.text().strip(),
            timeframe=str(self.timeframe.currentData()),
            available_capital=self.available_capital.text().strip(),
            max_entries=str(self.max_entries.value()),
            fee_percent=self.fee_percent.text().strip(),
            slippage_bps=self.slippage_bps.text().strip(),
            spot_trading_capital_percent=(
                None if futures else self.spot_ratio.text().strip()
            ),
            futures_leverage=str(self.leverage.value()) if futures else None,
        )

    @Slot()
    def _submit(self) -> None:
        if self.create_button.isEnabled():
            self.create_requested.emit(self.values())

    def set_loading(self, loading: bool) -> None:
        self.create_button.setDisabled(loading)
        self.create_button.setText("Creating…" if loading else "Create Paper Session")

    def clear_errors(self) -> None:
        for error_label in self._field_errors.values():
            error_label.clear()
            error_label.setVisible(False)

    def show_field_error(self, field: str, message: str) -> None:
        error_label = self._field_errors.get(field)
        if error_label is None:
            return
        error_label.setText(message)
        error_label.setVisible(True)

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        heading = QLabel("Create Paper Session")
        heading.setObjectName("pageTitle")
        description = QLabel(
            "Configure an immutable Paper session. Trading does not start yet."
        )
        description.setObjectName("supportingText")
        root.addWidget(heading)
        root.addWidget(description)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(20)

        identity_heading = QLabel("Session identity")
        identity_heading.setObjectName("sectionTitle")
        card_layout.addWidget(identity_heading)
        identity_form = self._form()
        self._add_row(identity_form, "Trade Mode", self.trade_mode_label)
        self._add_row(
            identity_form,
            "Market Type",
            self.market_type,
            (self.market_type_error,),
        )
        self._add_row(
            identity_form,
            "Symbol",
            self.symbol_field,
            (self.symbol_error,),
        )
        self._add_row(
            identity_form,
            "Timeframe",
            self.timeframe,
            (self.timeframe_error,),
        )
        self._add_row(identity_form, "Strategy Preset", self.preset_label)
        card_layout.addLayout(identity_form)

        capital_heading = QLabel("Capital and entry policy")
        capital_heading.setObjectName("sectionTitle")
        card_layout.addWidget(capital_heading)
        capital_form = self._form()
        self._add_row(
            capital_form,
            "Available Capital (USDT)",
            self.available_capital,
            (self.available_capital_error,),
        )
        self._add_row(
            capital_form,
            "Max Entries",
            self.max_entries,
            (self.max_entries_error,),
        )
        card_layout.addLayout(capital_form)

        self.spot_fields = self._build_spot_fields()
        card_layout.addWidget(self.spot_fields)
        self.futures_fields = self._build_futures_fields()
        card_layout.addWidget(self.futures_fields)

        card_layout.addWidget(self.advanced_toggle)
        card_layout.addWidget(self.advanced_costs)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.create_button)
        card_layout.addLayout(actions)
        root.addWidget(card)
        root.addStretch()

    @Slot(str)
    def _update_spot_reserve_ratio(self, value: str) -> None:
        try:
            policy = spot_trading_policy_from_percent(value.strip())
        except PaperSessionValidationError:
            self.spot_reserve_ratio.setText("—")
            return
        reserve_percent = policy.reserve_ratio * 100
        self.spot_reserve_ratio.setText(f"{format(reserve_percent.normalize(), 'f')}%")

    @Slot(bool)
    def _toggle_advanced(self, expanded: bool) -> None:
        self.advanced_costs.setVisible(expanded)
        self.advanced_toggle.setText(
            "Hide Advanced Settings" if expanded else "Show Advanced Settings"
        )

    def _build_advanced_costs(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        heading = QLabel("Execution costs")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        costs_form = self._form()
        self._add_row(
            costs_form,
            "Trading Fee (%)",
            self.fee_percent,
            (self.fee_percent_error,),
        )
        self._add_row(
            costs_form,
            "Slippage (bps)",
            self.slippage_bps,
            (self.slippage_bps_error,),
        )
        layout.addLayout(costs_form)
        return container

    def _build_spot_fields(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        heading = QLabel("Spot capital policy")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        form = self._form()
        self._add_row(
            form,
            "Spot Trading Capital Ratio (%)",
            self.spot_ratio,
            (self.spot_ratio_error,),
        )
        self._add_row(form, "Spot Reserve Ratio", self.spot_reserve_ratio)
        layout.addLayout(form)
        return container

    def _build_futures_fields(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        heading = QLabel("Futures policy")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        form = self._form()
        self._add_row(form, "Leverage", self.leverage)
        self._add_row(form, "Margin Mode", self.margin_mode_value)
        self._add_row(form, "Position Mode", self.position_mode_value)
        self._add_row(form, "Trading Capital", self.trading_capital_value)
        self._add_row(form, "Collateral Buffer", self.collateral_buffer_value)
        layout.addLayout(form)
        return container

    @Slot()
    def _sync_market_fields(self) -> None:
        futures = self.market_type.currentData() == "futures"
        self.spot_fields.setVisible(not futures)
        self.futures_fields.setVisible(futures)

    @staticmethod
    def _form() -> QFormLayout:
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        return form

    @staticmethod
    def _add_row(
        form: QFormLayout,
        label: str,
        field: QWidget,
        supporting: Iterable[QWidget] = (),
    ) -> None:
        field_stack = QVBoxLayout()
        field_stack.setSpacing(4)
        field_stack.addWidget(field)
        for widget in supporting:
            field_stack.addWidget(widget)
        form.addRow(label, field_stack)

    def _error_label(self, field: str) -> QLabel:
        label = QLabel()
        label.setObjectName("fieldError")
        label.setVisible(False)
        label.setWordWrap(True)
        self._field_errors[field] = label
        return label


def _percent_text(ratio: Decimal) -> str:
    return f"{format((ratio * Decimal('100')).normalize(), 'f')}%"
