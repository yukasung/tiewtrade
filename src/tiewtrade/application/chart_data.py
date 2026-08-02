from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from tiewtrade.market_data.candle import Candle
from tiewtrade.trading.trade_history import FillSide, TradeFill


class _SessionIdentity(Protocol):
    @property
    def session_id(self) -> UUID: ...

    @property
    def symbol(self) -> str: ...

    @property
    def timeframe(self) -> str: ...


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
    session: _SessionIdentity
    chart_range: ChartRange
    candles: tuple[Candle, ...]
    fills: tuple[TradeFill, ...]
    state: ChartReadState
    message: str | None = None
    markers: tuple[ChartMarker, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        if not self.session.symbol:
            raise ValueError("Session symbol must not be empty")
        if not self.session.timeframe:
            raise ValueError("Session timeframe must not be empty")
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
            if candle.symbol != self.session.symbol:
                raise ValueError("candle symbol must match Session")
            if candle.timeframe != self.session.timeframe:
                raise ValueError("candle timeframe must match Session")
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
            if fill.session_id != self.session.session_id:
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
    return replace(
        snapshot,
        candles=tuple(
            candles_by_open_time[open_time]
            for open_time in sorted(candles_by_open_time)
        ),
    )
