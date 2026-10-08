"""Public quote stream contracts; connection epochs fence delayed callbacks."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from tiewtrade.core.realtime_prices import QuoteObservation
from tiewtrade.venues.symbols import Symbol


@dataclass(frozen=True, slots=True)
class FeedConnected:
    generation: int


@dataclass(frozen=True, slots=True)
class FeedQuote:
    generation: int
    quote: QuoteObservation


@dataclass(frozen=True, slots=True)
class FeedDisconnected:
    generation: int
    failure_code: str
    retry_after: timedelta | None = None


FeedEvent = FeedConnected | FeedQuote | FeedDisconnected


class PriceFeed(Protocol):
    async def snapshot(self, symbol: Symbol) -> QuoteObservation: ...
    def events(self, symbols: tuple[Symbol, ...]) -> AsyncIterator[FeedEvent]: ...
