"""Pure candle observations and half-open UTC windows."""

from collections.abc import Iterable, Iterator
from dataclasses import InitVar, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from tiewtrade.core.moments import require_aware
from tiewtrade.core.money import InvalidUnitError, Money, Quantity
from tiewtrade.core.money.indicator_batch import validate_ohlcv


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def span(self) -> timedelta:
        seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        return timedelta(seconds=seconds[self.value])


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
        if self.end_at != self.open_at + self.timeframe.span:
            raise ValueError("wrong candle span")


def align_floor(moment: datetime, timeframe: Timeframe) -> datetime:
    require_aware("moment", moment)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return epoch + ((moment - epoch) // timeframe.span) * timeframe.span


def align_ceil(moment: datetime, timeframe: Timeframe) -> datetime:
    floor = align_floor(moment, timeframe)
    return floor if floor == moment else floor + timeframe.span


def expected_opens(window: CandleWindow, timeframe: Timeframe) -> Iterator[datetime]:
    current = align_ceil(window.start, timeframe)
    while current < window.end:
        yield current
        current += timeframe.span


def slot_count(window: CandleWindow, timeframe: Timeframe) -> int:
    first = align_ceil(window.start, timeframe)
    return (window.end - first + timeframe.span - timedelta(microseconds=1)) // timeframe.span


def bounded_windows(window: CandleWindow, timeframe: Timeframe) -> Iterator[CandleWindow]:
    cursor = window.start
    while cursor < window.end:
        end = min(align_ceil(cursor, timeframe) + timeframe.span * 1000, window.end)
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
            result.append(CandleWindow(beginning, last + timeframe.span))
            beginning = None
    if beginning is not None and last is not None:
        result.append(CandleWindow(beginning, last + timeframe.span))
    return tuple(result)


def retention_cutoff(as_of: datetime) -> datetime:
    require_aware("as_of", as_of)
    return as_of.astimezone(UTC) - timedelta(days=365)


def retention_window(window: CandleWindow, as_of: datetime) -> CandleWindow | None:
    start = max(window.start, retention_cutoff(as_of))
    end = min(window.end, as_of)
    return CandleWindow(start, end) if start < end else None


def initial_window(timeframe: Timeframe, as_of: datetime) -> CandleWindow:
    end = align_floor(as_of, timeframe) + timeframe.span
    start = max(end - 1000 * timeframe.span, align_ceil(retention_cutoff(as_of), timeframe))
    return CandleWindow(start, end)
