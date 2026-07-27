from decimal import Decimal

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.ui.preset_display import preset_display_name


class SessionOverviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sessionOverview")

        self.state_value = self._value_label()
        self.session_id_value = self._value_label()
        self.market_value = self._value_label()
        self.symbol_value = self._value_label()
        self.timeframe_value = self._value_label()
        self.preset_value = self._value_label()
        self.available_capital_value = self._value_label()
        self.max_entries_value = self._value_label()
        self.spot_ratio_value = self._value_label()
        self.spot_reserve_ratio_value = self._value_label()
        self.fee_value = self._value_label()
        self.slippage_value = self._value_label()
        self.created_at_value = self._value_label()

        self._build_layout()

    def show_session(self, session: ConfiguredPaperSession) -> None:
        config = session.config
        self.state_value.setText("Configured — Market Data Not Started")
        self.session_id_value.setText(str(config.session_id))
        self.market_value.setText(config.market_type.value.title())
        self.symbol_value.setText(session.market_data.symbol)
        self.timeframe_value.setText(session.market_data.timeframe)
        self.preset_value.setText(preset_display_name(config.preset_version))
        self.available_capital_value.setText(
            f"{_decimal_text(config.available_capital)} USDT"
        )
        self.max_entries_value.setText(str(config.entry_policy.max_entries))
        spot_policy = config.spot_policy
        reserve_ratio = None if spot_policy is None else spot_policy.reserve_ratio * 100
        self.spot_ratio_value.setText(
            "—"
            if spot_policy is None
            else f"{_decimal_text(spot_policy.trading_capital_ratio * 100)}%"
        )
        self.spot_reserve_ratio_value.setText(
            "—" if reserve_ratio is None else f"{_decimal_text(reserve_ratio)}%"
        )
        self.fee_value.setText(f"{_decimal_text(config.fee_rate * Decimal('100'))}%")
        self.slippage_value.setText(f"{_decimal_text(config.slippage_bps)} bps")
        self.created_at_value.setText(session.created_at_utc.isoformat())

    def _build_layout(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        heading = QLabel("Session Overview")
        heading.setObjectName("pageTitle")
        description = QLabel(
            "This configuration is stored. Market data and trading are not running."
        )
        description.setObjectName("supportingText")
        root.addWidget(heading)
        root.addWidget(description)

        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 16, 20, 16)
        status_label = QLabel("SESSION STATE")
        status_label.setObjectName("eyebrow")
        self.state_value.setObjectName("stateValue")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.state_value)
        root.addWidget(status_card)

        details = QFrame()
        details.setObjectName("card")
        grid = QGridLayout(details)
        grid.setContentsMargins(24, 24, 24, 24)
        grid.setHorizontalSpacing(48)
        grid.setVerticalSpacing(18)
        rows = (
            ("Session ID", self.session_id_value),
            ("Market Type", self.market_value),
            ("Symbol", self.symbol_value),
            ("Timeframe", self.timeframe_value),
            ("Strategy Preset", self.preset_value),
            ("Available Capital", self.available_capital_value),
            ("Max Entries", self.max_entries_value),
            ("Spot Trading Capital Ratio", self.spot_ratio_value),
            ("Spot Reserve Ratio", self.spot_reserve_ratio_value),
            ("Trading Fee", self.fee_value),
            ("Slippage", self.slippage_value),
            ("Created at (UTC)", self.created_at_value),
        )
        for index, (label, value) in enumerate(rows):
            column = index % 2
            row = (index // 2) * 2
            label_widget = QLabel(label)
            label_widget.setObjectName("detailLabel")
            grid.addWidget(label_widget, row, column)
            grid.addWidget(value, row + 1, column)
        root.addWidget(details)
        root.addStretch()

    @staticmethod
    def _value_label() -> QLabel:
        label = QLabel("—")
        label.setObjectName("detailValue")
        label.setTextInteractionFlags(label.textInteractionFlags())
        return label


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")
