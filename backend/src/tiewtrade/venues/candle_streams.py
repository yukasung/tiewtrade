"""Public candle preview feed; generation fences connection callbacks."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Protocol

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import CandleSeries
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected


@dataclass(frozen=True, slots=True)
class FeedCandle:
    generation: int
    observation: CandleObservation


CandleFeedEvent = FeedConnected | FeedDisconnected | FeedCandle


class CandleFeed(Protocol):
    def events(self, series: tuple[CandleSeries, ...]) -> AsyncGenerator[CandleFeedEvent, None]: ...
