"""Conservative cumulative observations; ambiguity never selects a price."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from tiewtrade.core.market_data import Candle
from tiewtrade.core.moments import require_aware
from tiewtrade.core.money import Quantity


@dataclass(frozen=True, slots=True)
class CandleObservation:
    candle: Candle
    event_at: datetime
    received_at: datetime
    trade_count: int
    first_trade_id: int
    last_trade_id: int
    closed_hint: bool

    def __post_init__(self) -> None:
        require_aware("event_at", self.event_at)
        require_aware("received_at", self.received_at)
        for value in (self.trade_count, self.first_trade_id, self.last_trade_id):
            if type(value) is not int:
                raise ValueError("invalid cumulative progress")
        if self.trade_count < 0 or min(self.first_trade_id, self.last_trade_id) < -1:
            raise ValueError("invalid cumulative progress")
        if self.trade_count > 0 and not 0 <= self.first_trade_id <= self.last_trade_id:
            raise ValueError("invalid cumulative progress")
        if type(self.closed_hint) is not bool:
            raise ValueError("invalid closure hint")


class Progress(StrEnum):
    DUPLICATE = "DUPLICATE"
    NEWER = "NEWER"
    OLDER = "OLDER"
    CONFLICT = "CONFLICT"


def compare(old: CandleObservation, new: CandleObservation) -> Progress:
    a, b = old.candle, new.candle
    if (a.base, a.quote, a.timeframe, a.open_at) != (b.base, b.quote, b.timeframe, b.open_at):
        raise ValueError("different candle identity")

    def empty_baseline(observation: CandleObservation) -> bool:
        return (
            observation.trade_count == 0
            and observation.first_trade_id == observation.last_trade_id == -1
            and observation.candle.volume == Quantity.of(0, observation.candle.base)
            and not observation.closed_hint
        )

    # Empty venue snapshots are provisional until the first actual trade establishes OHLC.
    # Only this sentinel state bypasses normal first-ID/open invariants, never timestamps.
    if old.trade_count == 0 and new.trade_count > 0:
        return Progress.NEWER if empty_baseline(old) else Progress.CONFLICT
    if new.trade_count == 0 and old.trade_count > 0:
        return Progress.OLDER if empty_baseline(new) else Progress.CONFLICT
    if (
        a.open,
        a.high,
        a.low,
        a.close,
        a.volume,
        old.trade_count,
        old.first_trade_id,
        old.last_trade_id,
    ) == (
        b.open,
        b.high,
        b.low,
        b.close,
        b.volume,
        new.trade_count,
        new.first_trade_id,
        new.last_trade_id,
    ):
        return Progress.DUPLICATE

    def dominates(left: CandleObservation, right: CandleObservation) -> bool:
        c, d = left.candle, right.candle
        return (
            left.trade_count > right.trade_count
            and left.first_trade_id == right.first_trade_id
            and left.last_trade_id >= right.last_trade_id
            and c.open == d.open
            and not c.high < d.high
            and not d.low < c.low
            and not c.volume < d.volume
        )

    if dominates(new, old):
        return Progress.NEWER
    if dominates(old, new):
        return Progress.OLDER
    return Progress.CONFLICT
