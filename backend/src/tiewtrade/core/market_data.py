"""Pure candle observations and half-open UTC windows."""

from collections.abc import Iterable, Iterator
from dataclasses import InitVar, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from tiewtrade.core.moments import require_aware
from tiewtrade.core.money import InvalidUnitError, Money, Quantity
from tiewtrade.core.money.indicator_batch import validate_ohlcv
from tiewtrade.core.timeframes import (
    Timeframe as Timeframe,
)
from tiewtrade.core.timeframes import (
    advance as advance,
)
from tiewtrade.core.timeframes import (
    align_ceil as align_ceil,
)
from tiewtrade.core.timeframes import (
    align_floor as align_floor,
)
from tiewtrade.core.timeframes import (
    next_open as next_open,
)
from tiewtrade.core.timeframes import (
    previous_open as previous_open,
)
from tiewtrade.core.timeframes import (
    retention_cutoff as retention_cutoff,
)
from tiewtrade.core.timeframes import (
    slot_count as count_slots,
)


class CandleFinality(StrEnum):
    UNCONFIRMED = "UNCONFIRMED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class CandleWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        require_aware("start", self.start)
        require_aware("end", self.end)
        object.__setattr__(self, "start", self.start.astimezone(UTC))
        object.__setattr__(self, "end", self.end.astimezone(UTC))
        if self.start >= self.end:
            raise ValueError("window must be nonempty and half-open")


@dataclass(frozen=True, slots=True)
class CandleSeries:
    base: str
    quote: str
    timeframe: Timeframe
    zero_price: Money = field(init=False)
    zero_volume: Quantity = field(init=False)

    def __post_init__(self) -> None:
        price = Money.of(0, self.quote)
        volume = Quantity.of(0, self.base)
        if not isinstance(self.timeframe, Timeframe):
            raise ValueError("unsupported timeframe")
        if price.currency == volume.asset:
            raise InvalidUnitError("invalid candle series")
        object.__setattr__(self, "base", volume.asset)
        object.__setattr__(self, "quote", price.currency)
        object.__setattr__(self, "zero_price", price)
        object.__setattr__(self, "zero_volume", volume)


@dataclass(frozen=True, slots=True)
class Candle:
    base: str
    quote: str
    timeframe: Timeframe
    open_at: datetime
    end_at: datetime
    open: Money
    high: Money
    low: Money
    close: Money
    volume: Quantity
    finality: CandleFinality
    observed_at: datetime
    series: InitVar[CandleSeries | None] = None

    def __post_init__(self, series: CandleSeries | None) -> None:
        if series is None:
            series = CandleSeries(self.base, self.quote, self.timeframe)
        elif not isinstance(series, CandleSeries) or (self.base, self.quote, self.timeframe) != (
            series.base,
            series.quote,
            series.timeframe,
        ):
            raise InvalidUnitError("different candle series")
        base, quote = series.base, series.quote
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "quote", quote)
        if not isinstance(self.timeframe, Timeframe) or not isinstance(
            self.finality, CandleFinality
        ):
            raise ValueError("unsupported timeframe or finality")
        validate_ohlcv(
            self.open, self.high, self.low, self.close, self.volume, base=base, quote=quote
        )
        for name, moment in (
            ("open_at", self.open_at),
            ("end_at", self.end_at),
            ("observed_at", self.observed_at),
        ):
            require_aware(name, moment)
            object.__setattr__(self, name, moment.astimezone(UTC))
        if align_floor(self.open_at, self.timeframe) != self.open_at:
            raise ValueError("unaligned candle open")
        if self.end_at != next_open(self.open_at, self.timeframe):
            raise ValueError("wrong candle span")


def expected_opens(window: CandleWindow, timeframe: Timeframe) -> Iterator[datetime]:
    current = align_ceil(window.start, timeframe)
    while current < window.end:
        yield current
        current = next_open(current, timeframe)


def slot_count(window: CandleWindow, timeframe: Timeframe) -> int:
    return count_slots(window.start, window.end, timeframe)


def bounded_windows(
    window: CandleWindow, timeframe: Timeframe, limit: int = 1000
) -> Iterator[CandleWindow]:
    if not 1 <= limit <= 1000:
        raise ValueError("invalid window limit")
    cursor = window.start
    while cursor < window.end:
        end = min(advance(align_ceil(cursor, timeframe), timeframe, limit), window.end)
        yield CandleWindow(cursor, end)
        cursor = end


def missing_windows(
    window: CandleWindow, timeframe: Timeframe, opens: Iterable[datetime]
) -> tuple[CandleWindow, ...]:
    present = set(opens)
    result: list[CandleWindow] = []
    beginning: datetime | None = None
    last: datetime | None = None
    for moment in expected_opens(window, timeframe):
        if moment not in present:
            if beginning is None:
                beginning = moment
            last = moment
        elif beginning is not None and last is not None:
            result.append(CandleWindow(beginning, next_open(last, timeframe)))
            beginning = None
    if beginning is not None and last is not None:
        result.append(CandleWindow(beginning, next_open(last, timeframe)))
    return tuple(result)


def retention_window(
    window: CandleWindow, as_of: datetime, timeframe: Timeframe
) -> CandleWindow | None:
    start = max(window.start, retention_cutoff(as_of, timeframe))
    end = min(window.end, as_of)
    return CandleWindow(start, end) if start < end else None


def initial_window(timeframe: Timeframe, as_of: datetime) -> CandleWindow:
    end = next_open(align_floor(as_of, timeframe), timeframe)
    start = max(
        advance(end, timeframe, -1000),
        align_ceil(retention_cutoff(as_of, timeframe), timeframe),
    )
    return CandleWindow(start, end)
