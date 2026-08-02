from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QLineF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from tiewtrade.application.chart_data import ChartRange, ChartReadState, ChartSnapshot
from tiewtrade.trading.trade_history import FillSide


class CandlestickChartWidget(QWidget):
    """Read-only QPainter surface for a validated chart snapshot."""

    range_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("candlestickChart")
        self.setMinimumHeight(280)
        self._snapshot: ChartSnapshot | None = None

        header = QHBoxLayout()
        header.setContentsMargins(12, 10, 12, 0)
        self._facts = QLabel("Chart")
        self._facts.setObjectName("chartFacts")
        self._range = QLabel()
        self._range.setObjectName("chartRange")
        self.previous_range_button = QPushButton("Previous")
        self.previous_range_button.setObjectName("previousRangeButton")
        self.previous_range_button.setAccessibleName("Previous chart range")
        self.next_range_button = QPushButton("Next")
        self.next_range_button.setObjectName("nextRangeButton")
        self.next_range_button.setAccessibleName("Next chart range")
        self.previous_range_button.clicked.connect(self._request_previous_range)
        self.next_range_button.clicked.connect(self._request_next_range)
        header.addWidget(self._facts)
        header.addStretch()
        header.addWidget(self._range)
        header.addWidget(self.previous_range_button)
        header.addWidget(self.next_range_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addStretch()

    @property
    def marker_labels(self) -> tuple[str, ...]:
        if self._snapshot is None:
            return ()
        return tuple(
            "Buy" if marker.side is FillSide.BUY else "Sell"
            for marker in self._snapshot.markers
        )

    def show_snapshot(self, snapshot: ChartSnapshot) -> None:
        self._snapshot = snapshot
        self.setAccessibleName(
            f"Candlestick chart for {snapshot.symbol} {snapshot.timeframe}"
        )
        self._facts.setText(f"{snapshot.symbol} · {snapshot.timeframe}")
        self._range.setText(_range_text(snapshot.chart_range))
        has_range = snapshot.state in {ChartReadState.READY, ChartReadState.EMPTY}
        self.previous_range_button.setEnabled(has_range)
        self.next_range_button.setEnabled(has_range)
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#10151C"))
        snapshot = self._snapshot
        if snapshot is None:
            painter.end()
            return
        surface = QRectF(12, 54, max(1, self.width() - 24), max(1, self.height() - 66))
        if snapshot.state is ChartReadState.UNAVAILABLE:
            self._draw_message(
                painter, surface, snapshot.message or "Chart is unavailable"
            )
        elif snapshot.state is ChartReadState.LOADING:
            self._draw_message(painter, surface, "Loading chart")
        elif not snapshot.candles:
            self._draw_message(painter, surface, "No completed candles")
        else:
            self._draw_chart(painter, surface, snapshot)
        painter.end()

    def _request_previous_range(self) -> None:
        if self._snapshot is None:
            return
        chart_range = self._snapshot.chart_range
        self.range_requested.emit(
            ChartRange(
                chart_range.start - (chart_range.end - chart_range.start),
                chart_range.start,
            )
        )

    def _request_next_range(self) -> None:
        if self._snapshot is None:
            return
        chart_range = self._snapshot.chart_range
        self.range_requested.emit(
            ChartRange(
                chart_range.end,
                chart_range.end + (chart_range.end - chart_range.start),
            )
        )

    def _draw_message(self, painter: QPainter, surface: QRectF, message: str) -> None:
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(surface, 0x84, message)

    def _draw_chart(
        self, painter: QPainter, surface: QRectF, snapshot: ChartSnapshot
    ) -> None:
        prices = [
            price for candle in snapshot.candles for price in (candle.high, candle.low)
        ] + [marker.price for marker in snapshot.markers]
        low, high = min(prices), max(prices)
        if low == high:
            low -= Decimal("1")
            high += Decimal("1")
        painter.setPen(QPen(QColor("#26313F"), 1))
        for line in range(5):
            y = surface.top() + (surface.height() * line / 4)
            painter.drawLine(QLineF(surface.left(), y, surface.right(), y))
        width = max(4.0, surface.width() / max(len(snapshot.candles) * 2, 2))
        for index, candle in enumerate(snapshot.candles):
            x = surface.left() + surface.width() * (index + 0.5) / len(snapshot.candles)
            candle_color = QColor(
                "#0ECB81" if candle.close >= candle.open else "#F6465D"
            )
            painter.setPen(QPen(candle_color, 1))
            painter.drawLine(
                QLineF(
                    x,
                    _price_y(candle.high, low, high, surface),
                    x,
                    _price_y(candle.low, low, high, surface),
                )
            )
            top = _price_y(max(candle.open, candle.close), low, high, surface)
            bottom = _price_y(min(candle.open, candle.close), low, high, surface)
            painter.fillRect(
                QRectF(x - width / 2, top, width, max(1.0, bottom - top)),
                candle_color,
            )
        for marker in snapshot.markers:
            x = _marker_x(marker.filled_at_utc, snapshot.chart_range, surface)
            y = _price_y(marker.price, low, high, surface)
            color = QColor("#0ECB81" if marker.side is FillSide.BUY else "#F6465D")
            painter.setPen(QPen(color, 2))
            label = "Buy" if marker.side is FillSide.BUY else "Sell"
            painter.drawText(QRectF(x - 22, y - 20, 44, 16), 0x84, label)


def _range_text(chart_range: ChartRange) -> str:
    return f"{chart_range.start:%Y-%m-%d %H:%M}–{chart_range.end:%H:%M} UTC"


def _price_y(price: Decimal, low: Decimal, high: Decimal, surface: QRectF) -> float:
    return surface.bottom() - float((price - low) / (high - low)) * surface.height()


def _marker_x(value: datetime, chart_range: ChartRange, surface: QRectF) -> float:
    elapsed = (value - chart_range.start).total_seconds()
    duration = (chart_range.end - chart_range.start).total_seconds()
    return surface.left() + surface.width() * elapsed / duration
