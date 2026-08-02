from dataclasses import InitVar, dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from tiewtrade.application.paper_session_setup import ConfiguredPaperSession
from tiewtrade.market_data.candle import Candle
from tiewtrade.market_data.config import timeframe_to_interval
from tiewtrade.trading.trade_history import FillSide, TradeFill

_UTC_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_DEFAULT_VISIBLE_CANDLE_COUNT = 120


@runtime_checkable
class CompletedCandleFacts(Protocol):
    @property
    def symbol(self) -> str: ...

    @property
    def timeframe(self) -> str: ...

    @property
    def open_time(self) -> datetime: ...

    @property
    def close_time(self) -> datetime: ...


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")


@dataclass(frozen=True, slots=True)
class ChartRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        _require_utc(self.start, "start")
        _require_utc(self.end, "end")
        if self.start >= self.end:
            raise ValueError("start must be before end")

    def contains(self, value: datetime) -> bool:
        return self.start <= value < self.end


def latest_completed_boundary(
    timeframe: str,
    observed_at_utc: datetime,
) -> datetime:
    _require_utc(observed_at_utc, "observed_at_utc")
    interval = timeframe_to_interval(timeframe)
    return _UTC_EPOCH + ((observed_at_utc - _UTC_EPOCH) // interval) * interval


def default_chart_range(
    session: ConfiguredPaperSession,
    observed_at_utc: datetime,
) -> ChartRange:
    interval = timeframe_to_interval(session.market_data.timeframe)
    completed_end = latest_completed_boundary(
        session.market_data.timeframe,
        observed_at_utc,
    )
    return ChartRange(
        start=completed_end - interval * _DEFAULT_VISIBLE_CANDLE_COUNT,
        end=completed_end,
    )


@dataclass(frozen=True, slots=True)
class ChartMarker:
    fill_id: str
    side: FillSide
    price: Decimal
    filled_at_utc: datetime

    @classmethod
    def from_fill(cls, fill: TradeFill) -> "ChartMarker":
        return cls(
            fill_id=fill.fill_id,
            side=fill.side,
            price=fill.price,
            filled_at_utc=fill.filled_at_utc,
        )

    def __post_init__(self) -> None:
        if not self.fill_id:
            raise ValueError("fill_id must not be empty")
        _require_utc(self.filled_at_utc, "filled_at_utc")


class ChartReadState(StrEnum):
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ChartSnapshot:
    chart_range: ChartRange
    observed_at_utc: datetime
    candles: tuple[Candle, ...]
    fills: tuple[TradeFill, ...]
    state: ChartReadState
    message: str | None = None
    session: InitVar[ConfiguredPaperSession | None] = None
    _session_facts: InitVar[tuple[UUID, str, str] | None] = None
    session_id: UUID = field(init=False)
    symbol: str = field(init=False)
    timeframe: str = field(init=False)
    markers: tuple[ChartMarker, ...] = field(init=False, default=())

    def __post_init__(
        self,
        session: ConfiguredPaperSession | None,
        _session_facts: tuple[UUID, str, str] | None,
    ) -> None:
        if session is not None and _session_facts is not None:
            raise ValueError("ChartSnapshot accepts one Session source")
        if session is not None:
            session_id = session.config.session_id
            symbol = session.market_data.symbol
            timeframe = session.market_data.timeframe
        elif _session_facts is not None:
            session_id, symbol, timeframe = _session_facts
        else:
            raise ValueError("ChartSnapshot requires a ConfiguredPaperSession")
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "timeframe", timeframe)

        if not self.symbol:
            raise ValueError("Session symbol must not be empty")
        if not self.timeframe:
            raise ValueError("Session timeframe must not be empty")
        _require_utc(self.observed_at_utc, "observed_at_utc")
        if self.chart_range.end > self.observed_at_utc:
            raise ValueError("ChartRange end must not be after observed_at_utc")
        if not isinstance(self.state, ChartReadState):
            raise ValueError("state must be a ChartReadState")
        if self.message is not None and self.state is not ChartReadState.UNAVAILABLE:
            raise ValueError("message is only valid for unavailable ChartSnapshot")
        if self.state is ChartReadState.UNAVAILABLE and not self.message:
            raise ValueError("unavailable ChartSnapshot requires a message")
        if self.state in {ChartReadState.LOADING, ChartReadState.UNAVAILABLE} and (
            self.candles or self.fills
        ):
            raise ValueError("loading or unavailable ChartSnapshot cannot contain data")
        if self.state is ChartReadState.EMPTY and self.candles:
            raise ValueError("empty ChartSnapshot cannot contain candles")

        previous_open_time: datetime | None = None
        for candle in self.candles:
            if candle.symbol != self.symbol:
                raise ValueError("candle symbol must match Session")
            if candle.timeframe != self.timeframe:
                raise ValueError("candle timeframe must match Session")
            if candle.close_time > self.observed_at_utc:
                raise ValueError("candle must be completed by observed_at_utc")
            if (
                candle.open_time < self.chart_range.start
                or candle.close_time > self.chart_range.end
            ):
                raise ValueError("candle must be completed inside ChartRange")
            if (
                previous_open_time is not None
                and candle.open_time <= previous_open_time
            ):
                raise ValueError("candles must have ascending unique open_time values")
            previous_open_time = candle.open_time

        markers: list[ChartMarker] = []
        fill_ids: set[str] = set()
        for fill in self.fills:
            if fill.session_id != self.session_id:
                raise ValueError("fill session must match Session")
            if not self.chart_range.contains(fill.filled_at_utc):
                raise ValueError("fill must be inside ChartRange")
            if fill.fill_id in fill_ids:
                raise ValueError("fills must have unique fill_id values")
            fill_ids.add(fill.fill_id)
            markers.append(ChartMarker.from_fill(fill))
        object.__setattr__(self, "markers", tuple(markers))


def append_completed_candle(snapshot: ChartSnapshot, candle: Candle) -> ChartSnapshot:
    if snapshot.state is not ChartReadState.READY:
        raise ValueError("completed candles require a ready ChartSnapshot")
    candles_by_open_time = {item.open_time: item for item in snapshot.candles}
    candles_by_open_time[candle.open_time] = candle
    return ChartSnapshot(
        candles=tuple(
            candles_by_open_time[open_time]
            for open_time in sorted(candles_by_open_time)
        ),
        chart_range=snapshot.chart_range,
        observed_at_utc=snapshot.observed_at_utc,
        fills=snapshot.fills,
        state=snapshot.state,
        message=snapshot.message,
        _session_facts=(snapshot.session_id, snapshot.symbol, snapshot.timeframe),
    )
