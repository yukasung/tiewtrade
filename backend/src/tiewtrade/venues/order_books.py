"""Public execution-feed contracts; venue fields remain inside their adapter."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.order_book import BookLevel
from tiewtrade.core.orders import OrderConstraints, OrderType
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected
from tiewtrade.venues.symbols import Symbol


@dataclass(frozen=True, slots=True)
class DepthSnapshot:
    symbol: Symbol
    last_update_id: int
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    received_at: datetime


@dataclass(frozen=True, slots=True)
class DepthUpdate:
    symbol: Symbol
    first_update_id: int
    last_update_id: int
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    event_at: datetime
    received_at: datetime


@dataclass(frozen=True, slots=True)
class TradeObservation:
    symbol: Symbol
    trade_id: int
    resting_side: ExecutionSide
    price: Money
    quantity: Quantity
    occurred_at: datetime
    event_at: datetime
    received_at: datetime


@dataclass(frozen=True, slots=True)
class TradeSample:
    symbol: Symbol
    aggregate_id: int
    first_trade_id: int
    last_trade_id: int
    price: Money
    quantity: Quantity
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionCapability:
    symbol: Symbol
    version: str
    observed_at: datetime
    market: OrderConstraints
    limit: OrderConstraints
    source_document: str

    def constraints(self, kind: OrderType) -> OrderConstraints:
        return self.market if kind is OrderType.MARKET else self.limit


@dataclass(frozen=True, slots=True)
class ExecutionFeedData:
    generation: int
    observation: DepthUpdate | TradeObservation


type ExecutionFeedEvent = FeedConnected | FeedDisconnected | ExecutionFeedData


class ExecutionFeed(Protocol):
    async def snapshot(self, symbol: Symbol) -> DepthSnapshot: ...
    async def capability(self, symbol: Symbol) -> ExecutionCapability: ...
    async def trade_history(
        self, symbol: Symbol, *, started_at: datetime, ended_at: datetime
    ) -> tuple[TradeSample, ...]: ...
    def events(
        self, symbols: tuple[Symbol, ...], *, generation: int
    ) -> AsyncGenerator[ExecutionFeedEvent, None]: ...
    async def close(self) -> None: ...


class ExecutionCapabilitySource(Protocol):
    """Read-only venue capability used before a catalog pair may prepare."""

    async def capability(self, symbol: Symbol) -> ExecutionCapability: ...
    async def close(self) -> None: ...
