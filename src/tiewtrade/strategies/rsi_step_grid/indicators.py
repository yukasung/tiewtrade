from dataclasses import dataclass
from decimal import Decimal

from tiewtrade.market_data.candle import Candle
from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    rsi: Decimal
    atr: Decimal


class WilderIndicators:
    def __init__(self, preset: RsiStepGridPreset) -> None:
        self._rsi_period = preset.rsi_period
        self._atr_period = preset.atr_period
        self._previous_close: Decimal | None = None
        self._gains: list[Decimal] = []
        self._losses: list[Decimal] = []
        self._true_ranges: list[Decimal] = []
        self._average_gain: Decimal | None = None
        self._average_loss: Decimal | None = None
        self._atr: Decimal | None = None

    def update(self, candle: Candle) -> IndicatorSnapshot | None:
        self._update_atr(candle)
        self._update_rsi(candle.close)
        self._previous_close = candle.close

        if (
            self._average_gain is None
            or self._average_loss is None
            or self._atr is None
        ):
            return None

        return IndicatorSnapshot(
            rsi=self._calculate_rsi(self._average_gain, self._average_loss),
            atr=self._atr,
        )

    def _update_rsi(self, close: Decimal) -> None:
        if self._previous_close is None:
            return

        change = close - self._previous_close
        gain = max(change, Decimal("0"))
        loss = max(-change, Decimal("0"))
        period = Decimal(self._rsi_period)

        if self._average_gain is None or self._average_loss is None:
            self._gains.append(gain)
            self._losses.append(loss)
            if len(self._gains) == self._rsi_period:
                self._average_gain = sum(self._gains, Decimal("0")) / period
                self._average_loss = sum(self._losses, Decimal("0")) / period
            return

        self._average_gain = (
            self._average_gain * (period - Decimal("1")) + gain
        ) / period
        self._average_loss = (
            self._average_loss * (period - Decimal("1")) + loss
        ) / period

    def _update_atr(self, candle: Candle) -> None:
        true_range = candle.high - candle.low
        if self._previous_close is not None:
            true_range = max(
                true_range,
                abs(candle.high - self._previous_close),
                abs(candle.low - self._previous_close),
            )

        period = Decimal(self._atr_period)
        if self._atr is None:
            self._true_ranges.append(true_range)
            if len(self._true_ranges) == self._atr_period:
                self._atr = sum(self._true_ranges, Decimal("0")) / period
            return

        self._atr = (self._atr * (period - Decimal("1")) + true_range) / period

    @staticmethod
    def _calculate_rsi(average_gain: Decimal, average_loss: Decimal) -> Decimal:
        if average_gain == 0 and average_loss == 0:
            return Decimal("50")
        if average_loss == 0:
            return Decimal("100")
        if average_gain == 0:
            return Decimal("0")

        relative_strength = average_gain / average_loss
        return Decimal("100") - Decimal("100") / (Decimal("1") + relative_strength)
