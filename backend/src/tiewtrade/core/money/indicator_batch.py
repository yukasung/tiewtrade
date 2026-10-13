"""Bounded financial transitions with private scratch arithmetic (F-11 NC-34)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import InvalidInputTypeError, InvalidUnitError, UnitMismatchError
from tiewtrade.core.money.indicator_arithmetic import Scalar, _coefficient, _ratio
from tiewtrade.core.money.limits import STORED_SCALE
from tiewtrade.core.money.rounding import RoundingDirection
from tiewtrade.core.money.types import Money, Quantity
from tiewtrade.core.money.validation import ensure_canonical_unit, ensure_in_range

FORMULA_VERSION = "indicators-v2"
# NC-30 transition parameters; the single-step entry point uses this same kernel.
_AVERAGES = (
    (20, 19, 2),
    (50, 49, 2),
    (200, 199, 2),
    (14, 13, 1),
    (14, 13, 1),
    (14, 13, 1),
)


class BatchAction(StrEnum):
    ACCEPT = "ACCEPT"
    RESET = "RESET"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class AverageState:
    pending: tuple[Money, ...] = ()
    value: Money | None = None


@dataclass(frozen=True, slots=True)
class IndicatorBatchState:
    base: str
    quote: str
    timeframe: str
    span: timedelta
    formula_version: str = FORMULA_VERSION
    last_open: datetime | None = None
    previous: Money | None = None
    averages: tuple[AverageState, ...] = (AverageState(),) * len(_AVERAGES)
    # Number of ACCEPT events since the latest RESET; HOLD does not advance it.
    accepted_count: int = 0

    @guarded
    def __post_init__(self) -> None:
        ensure_canonical_unit(self.base)
        ensure_canonical_unit(self.quote)
        if self.base == self.quote or self.formula_version != FORMULA_VERSION:
            raise InvalidInputTypeError("invalid indicator identity")
        spans = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        if self.timeframe not in spans or self.span != timedelta(seconds=spans[self.timeframe]):
            raise InvalidInputTypeError("invalid indicator timeframe")
        if self.last_open is not None and (
            not isinstance(self.last_open, datetime) or self.last_open.tzinfo is None
        ):
            raise InvalidInputTypeError("aware state time required")
        if type(self.averages) is not tuple or len(self.averages) != len(_AVERAGES):
            raise InvalidInputTypeError("invalid average state")
        if type(self.accepted_count) is not int or self.accepted_count < 0:
            raise InvalidInputTypeError("invalid accepted input count")
        if (self.previous is not None) != (self.accepted_count > 0):
            raise InvalidInputTypeError("previous close and accepted count disagree")
        if self.previous is not None:
            _unit(self.previous, self.quote)
            if self.previous.amount <= 0 or self.last_open is None:
                raise InvalidInputTypeError("invalid previous close state")
        for index, (state, (period, _, _)) in enumerate(zip(self.averages, _AVERAGES, strict=True)):
            if type(state) is not AverageState or type(state.pending) is not tuple:
                raise InvalidInputTypeError("invalid average state")
            if len(state.pending) >= period or (state.value is not None and state.pending):
                raise InvalidInputTypeError("invalid warm-up state")
            count = (
                self.accepted_count
                if index < 3
                else max(0, self.accepted_count - 1)
            )
            if len(state.pending) != (count if count < period else 0) or (
                (state.value is not None) != (count >= period)
            ):
                raise InvalidInputTypeError("average state and accepted count disagree")
            for value in state.pending:
                _average_value(value, self.quote, index)
            if state.value is not None:
                _average_value(state.value, self.quote, index)
            if self.previous is None and (state.pending or state.value is not None):
                raise InvalidInputTypeError("average state without previous close")
        warm_prices = [state.pending for state in self.averages[:3] if state.pending]
        if warm_prices and (
            any(pending != warm_prices[0] for pending in warm_prices)
            or warm_prices[0][-1] != self.previous
        ):
            raise InvalidInputTypeError("inconsistent warm-up close history")
        if 1 < self.accepted_count <= 14:
            # Before Wilder seeding, gain/loss buffers contain raw ACCEPT deltas.
            # EMA200 retains all those closes, including across HOLD events.
            closes = self.averages[2].pending
            zero = Money.of(0, self.quote)
            for before, after, gain, loss, true_range in zip(
                closes[:-1],
                closes[1:],
                self.averages[3].pending,
                self.averages[4].pending,
                self.averages[5].pending,
                strict=True,
            ):
                if gain > zero and loss > zero:
                    raise InvalidInputTypeError("warm-up gain and loss cannot both be positive")
                delta = after - before
                expected_gain = delta if delta > zero else zero
                expected_loss = zero - delta if delta < zero else zero
                if gain != expected_gain or loss != expected_loss:
                    raise InvalidInputTypeError("gain/loss buffers disagree with close history")
                if true_range < gain + loss:
                    raise InvalidInputTypeError("warm-up true range is below gain plus loss")
        if self.accepted_count >= 15:
            average_gain, average_loss, average_atr = (
                self.averages[index].value for index in (3, 4, 5)
            )
            assert average_gain is not None and average_loss is not None and average_atr is not None
            # All three use the same Wilder seed/weights and floor rounding.
            # Compare against ATR - loss to avoid overflowing a damaged gain + loss.
            if average_loss > average_atr or average_gain > average_atr - average_loss:
                raise InvalidInputTypeError("mature ATR is below average gain plus average loss")


@dataclass(frozen=True, slots=True)
class IndicatorBatchInput:
    open_at: datetime
    action: BatchAction
    base: str
    quote: str
    timeframe: str
    close: Money | None = None
    high: Money | None = None
    low: Money | None = None


@dataclass(frozen=True, slots=True)
class IndicatorBatchResult:
    state: IndicatorBatchState
    # Values follow core.indicators.NAMES. Only selected indices have output objects.
    outputs: tuple[tuple[int, tuple[Money | Scalar | None, ...]], ...]


def _reset_result(
    state: IndicatorBatchState,
    opens: tuple[datetime, ...],
    output_indices: tuple[int, ...],
) -> IndicatorBatchResult:
    return IndicatorBatchResult(
        IndicatorBatchState(
            state.base,
            state.quote,
            state.timeframe,
            state.span,
            state.formula_version,
            opens[-1],
        ),
        tuple((index, (None,) * 5) for index in output_indices),
    )


@guarded
def reset_indicator_batch(
    state: IndicatorBatchState,
    opens: tuple[datetime, ...],
    *,
    output_indices: tuple[int, ...],
) -> IndicatorBatchResult:
    if (
        type(state) is not IndicatorBatchState
        or type(opens) is not tuple
        or not 1 <= len(opens) <= 16
    ):
        raise InvalidInputTypeError("bounded indicator reset required")
    if type(output_indices) is not tuple or any(type(i) is not int for i in output_indices):
        raise InvalidInputTypeError("invalid output indices")
    if tuple(sorted(set(output_indices))) != output_indices or any(
        not 0 <= i < len(opens) for i in output_indices
    ):
        raise InvalidInputTypeError("invalid output indices")
    previous = state.last_open
    for moment in opens:
        if (
            not isinstance(moment, datetime)
            or moment.tzinfo is None
            or (previous is not None and moment != previous + state.span)
        ):
            raise InvalidInputTypeError("unordered indicator resets")
        previous = moment
    return _reset_result(state, opens, output_indices)


def _unit(value: Money, quote: str) -> None:
    if type(value) is not Money:
        raise InvalidInputTypeError("Money state required")
    if value.currency != quote:
        raise UnitMismatchError("different indicator currency")


def _average_value(value: Money, quote: str, index: int) -> None:
    _unit(value, quote)
    if (index < 3 and value.amount <= 0) or (index >= 3 and value.amount < 0):
        raise InvalidInputTypeError("invalid indicator average state")


@guarded
def validate_ohlcv(
    open_price: Money,
    high: Money,
    low: Money,
    close: Money,
    volume: Quantity,
    *,
    base: str,
    quote: str,
) -> None:
    """Shared Candle validation within one money context; values remain checked objects."""
    if type(volume) is not Quantity or volume.asset != base:
        raise InvalidUnitError("candle base and volume must agree")
    for price in (open_price, high, low, close):
        if type(price) is not Money or price.currency != quote:
            raise InvalidUnitError("candle prices must use quote")
        if not price.amount > 0:
            raise ValueError("candle prices must be positive")
    if volume.amount < 0:
        raise ValueError("volume must not be negative")
    if (
        low.amount > min(open_price.amount, close.amount)
        or max(open_price.amount, close.amount) > high.amount
    ):
        raise ValueError("inconsistent OHLC")


def _amount(value: int) -> Decimal:
    return Decimal(value).scaleb(-STORED_SCALE)


def _difference(left: int, right: int) -> int:
    result = left - right
    ensure_in_range(_amount(result))
    return result


class _Average:
    def __init__(self, state: AverageState, parameters: tuple[int, int, int]) -> None:
        self.period, self.previous_weight, self.input_weight = parameters
        self.pending = [_coefficient(value.amount) for value in state.pending]
        self.value = _coefficient(state.value.amount) if state.value is not None else None

    def feed(self, value: int, rounding: RoundingDirection) -> int | None:
        if self.value is None:
            self.pending.append(value)
            if len(self.pending) == self.period:
                self.value = _coefficient(_ratio(sum(self.pending), self.period, rounding))
                self.pending.clear()
        else:
            self.value = _coefficient(
                _ratio(
                    self.value * self.previous_weight + value * self.input_weight,
                    self.previous_weight + self.input_weight,
                    rounding,
                )
            )
        return self.value

    def state(self, quote: str) -> AverageState:
        return AverageState(
            tuple(Money(_amount(value), quote) for value in self.pending),
            Money(_amount(self.value), quote) if self.value is not None else None,
        )


@guarded
def advance_indicator_batch(
    state: IndicatorBatchState,
    inputs: tuple[IndicatorBatchInput, ...],
    *,
    output_indices: tuple[int, ...],
    rounding: RoundingDirection,
) -> IndicatorBatchResult:
    if (
        type(state) is not IndicatorBatchState
        or type(inputs) is not tuple
        or not 1 <= len(inputs) <= 16
    ):
        raise InvalidInputTypeError("bounded indicator inputs required")
    if rounding is not RoundingDirection.TOWARD_NEGATIVE:
        raise InvalidInputTypeError("indicator rounding policy")
    if type(output_indices) is not tuple or any(type(i) is not int for i in output_indices):
        raise InvalidInputTypeError("invalid output indices")
    if tuple(sorted(set(output_indices))) != output_indices or any(
        not 0 <= i < len(inputs) for i in output_indices
    ):
        raise InvalidInputTypeError("invalid output indices")
    previous_open = state.last_open
    all_reset = True
    for item in inputs:
        if type(item) is not IndicatorBatchInput or type(item.action) is not BatchAction:
            raise InvalidInputTypeError("invalid indicator event")
        if (item.base, item.quote, item.timeframe) != (state.base, state.quote, state.timeframe):
            raise InvalidInputTypeError("different indicator series")
        if (
            not isinstance(item.open_at, datetime)
            or item.open_at.tzinfo is None
            or (previous_open is not None and item.open_at != previous_open + state.span)
        ):
            raise InvalidInputTypeError("unordered indicator events")
        previous_open = item.open_at
        if item.action is BatchAction.ACCEPT:
            all_reset = False
            for value in (item.close, item.high, item.low):
                if value is None:
                    raise InvalidInputTypeError("missing indicator prices")
                _unit(value, state.quote)
            assert item.close is not None and item.high is not None and item.low is not None
            if not 0 < item.low.amount <= item.close.amount <= item.high.amount:
                raise InvalidInputTypeError("invalid indicator price event")
        else:
            all_reset &= item.action is BatchAction.RESET
            if item.close is not None or item.high is not None or item.low is not None:
                raise InvalidInputTypeError("prices on control event")
    if all_reset:
        return _reset_result(state, tuple(item.open_at for item in inputs), output_indices)
    averages = [
        _Average(value, parameters)
        for value, parameters in zip(state.averages, _AVERAGES, strict=True)
    ]
    previous = _coefficient(state.previous.amount) if state.previous is not None else None
    previous_money = state.previous
    accepted_count = state.accepted_count
    outputs: list[tuple[int, tuple[Money | Scalar | None, ...]]] = []
    for index, item in enumerate(inputs):
        if item.action is BatchAction.RESET:
            averages = [_Average(AverageState(), parameters) for parameters in _AVERAGES]
            previous = previous_money = None
            accepted_count = 0
        if item.action is not BatchAction.ACCEPT:
            if index in output_indices:
                outputs.append((index, (None,) * 5))
            continue
        assert item.close is not None and item.high is not None and item.low is not None
        accepted_count += 1
        close, high, low = (
            _coefficient(value.amount) for value in (item.close, item.high, item.low)
        )
        ema = [average.feed(close, rounding) for average in averages[:3]]
        rsi: Decimal | None = None
        atr: int | None = None
        if previous is not None:
            delta = _difference(close, previous)
            gain = averages[3].feed(max(delta, 0), rounding)
            loss = averages[4].feed(_difference(0, min(delta, 0)), rounding)
            high_delta, low_delta = _difference(high, previous), _difference(low, previous)
            tr = max(
                _difference(high, low),
                max(high_delta, _difference(0, high_delta)),
                max(low_delta, _difference(0, low_delta)),
            )
            atr = averages[5].feed(tr, rounding)
            if gain is not None and loss is not None:
                if gain == 0 or loss == 0:
                    rsi = Decimal(50 if gain == loss == 0 else 100 if loss == 0 else 0)
                else:
                    rsi = _ratio(100 * gain * _coefficient(Decimal(1)), gain + loss, rounding)
        previous, previous_money = close, item.close
        if index in output_indices:
            money_values = (*ema, atr)
            values = [
                Money(_amount(value), state.quote) if value is not None else None
                for value in money_values
            ]
            outputs.append(
                (
                    index,
                    (
                        values[0],
                        values[1],
                        values[2],
                        Scalar(rsi) if rsi is not None else None,
                        values[3],
                    ),
                )
            )
    next_state = IndicatorBatchState(
        state.base,
        state.quote,
        state.timeframe,
        state.span,
        state.formula_version,
        inputs[-1].open_at,
        previous_money,
        tuple(average.state(state.quote) for average in averages),
        accepted_count,
    )
    return IndicatorBatchResult(next_state, tuple(outputs))
