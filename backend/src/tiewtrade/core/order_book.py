"""Venue-neutral immutable verified book/trade inputs and Paper shadow liquidity."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.orders import OrderError, SourceUnavailableError, aware
from tiewtrade.core.positions import ExecutionSide, PositionPair

MAX_BOOK_AGE = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class BookLevel:
    price: Money
    quantity: Quantity

    def __post_init__(self) -> None:
        if type(self.price) is not Money or type(self.quantity) is not Quantity:
            raise OrderError("book levels require Money and Quantity")
        if self.price.amount <= 0 or self.quantity.amount < 0:
            raise OrderError("invalid book level")


@dataclass(frozen=True, slots=True)
class BookState:
    pair: PositionPair
    input_id: int
    generation: int
    received_at: datetime
    verified_at: datetime
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    ready: bool
    rebase: bool = False
    source_at: datetime | None = None
    source_first_sequence: int | None = None
    source_last_sequence: int | None = None
    snapshot_sequence: int | None = None

    def __post_init__(self) -> None:
        _identity(self.pair, self.input_id, self.generation, self.received_at)
        aware(self.verified_at)
        if self.source_at is not None:
            aware(self.source_at)
        for identity in (
            self.source_first_sequence,
            self.source_last_sequence,
            self.snapshot_sequence,
        ):
            if identity is not None and (type(identity) is not int or identity < 0):
                raise OrderError("invalid source sequence proof")
        if type(self.ready) is not bool or type(self.rebase) is not bool:
            raise OrderError("explicit book readiness/rebase required")
        for levels, reverse in ((self.bids, True), (self.asks, False)):
            if type(levels) is not tuple or not all(isinstance(v, BookLevel) for v in levels):
                raise OrderError("immutable book levels required")
            for level in levels:
                if (
                    level.price.currency != self.pair.quote
                    or level.quantity.asset != self.pair.base
                ):
                    raise OrderError("book units differ from pair")
            prices = [v.price for v in levels]
            if prices != sorted(set(prices), reverse=reverse):
                raise OrderError("book levels must be uniquely sorted")
        bids = [v.price for v in self.bids if v.quantity.amount > 0]
        asks = [v.price for v in self.asks if v.quantity.amount > 0]
        if bids and asks and not bids[0] < asks[0]:
            raise OrderError("crossed or locked book")

    def require_ready(self, now: datetime) -> None:
        aware(now)
        if (
            not self.ready
            or now < self.received_at
            or now < self.verified_at
            or now - self.verified_at > MAX_BOOK_AGE
            or (
                self.source_at is not None
                and (self.source_at > now or now - self.source_at > MAX_BOOK_AGE)
            )
        ):
            raise SourceUnavailableError("book readiness cannot be proved")

    def levels(self, side: ExecutionSide) -> tuple[BookLevel, ...]:
        return self.bids if side is ExecutionSide.BUY else self.asks

    def reported(self, side: ExecutionSide, price: Money) -> Quantity:
        levels = self.levels(side)
        for level in levels:
            if level.price == price:
                return level.quantity
        if levels and (
            (side is ExecutionSide.BUY and not price < levels[-1].price)
            or (side is ExecutionSide.SELL and not price > levels[-1].price)
        ):
            return Quantity.of(0, self.pair.base)
        raise SourceUnavailableError("price outside proven book coverage")


def _identity(pair: PositionPair, input_id: int, generation: int, received_at: datetime) -> None:
    if not isinstance(pair, PositionPair):
        raise OrderError("market pair required")
    if type(input_id) is not int or input_id <= 0 or type(generation) is not int or generation <= 0:
        raise OrderError("positive market input identity/generation required")
    aware(received_at)


@dataclass(frozen=True, slots=True)
class MarketTrade:
    pair: PositionPair
    input_id: int
    generation: int
    received_at: datetime
    trade_id: int
    resting_side: ExecutionSide
    price: Money
    quantity: Quantity
    ordering_proven: bool
    source_at: datetime | None = None
    source_event_at: datetime | None = None

    def __post_init__(self) -> None:
        _identity(self.pair, self.input_id, self.generation, self.received_at)
        if self.source_at is not None:
            aware(self.source_at)
        if self.source_event_at is not None:
            aware(self.source_event_at)
        if type(self.trade_id) is not int or self.trade_id <= 0:
            raise OrderError("positive source trade identity required")
        if (
            not isinstance(self.resting_side, ExecutionSide)
            or type(self.ordering_proven) is not bool
        ):
            raise OrderError("explicit resting side and ordering proof required")
        if type(self.price) is not Money or type(self.quantity) is not Quantity:
            raise OrderError("trade amounts require Money and Quantity")
        if (
            self.price.currency != self.pair.quote
            or self.quantity.asset != self.pair.base
            or self.price.amount <= 0
            or self.quantity.amount <= 0
        ):
            raise OrderError("invalid trade amount/units")


type MarketInput = BookState | MarketTrade


@dataclass(frozen=True, slots=True)
class ShadowLevel:
    side: ExecutionSide
    price: Money
    reported: Quantity
    consumed: Quantity

    def __post_init__(self) -> None:
        if not isinstance(self.side, ExecutionSide) or type(self.price) is not Money:
            raise OrderError("invalid shadow level identity")
        if self.price.amount <= 0 or self.reported.amount < 0 or self.consumed.amount < 0:
            raise OrderError("invalid shadow level amounts")
        if self.consumed > self.reported:
            raise OrderError("shadow consumption exceeds reported quantity")

    @property
    def available(self) -> Quantity:
        return self.reported - self.consumed

    def update(self, reported: Quantity) -> "ShadowLevel":
        if reported.amount < 0:
            raise OrderError("negative reported quantity")
        return replace(self, reported=reported, consumed=min(self.consumed, reported))

    def consume(self, quantity: Quantity) -> "ShadowLevel":
        if quantity.amount <= 0 or quantity > self.available:
            raise OrderError("unproven liquidity consumption")
        return replace(self, consumed=self.consumed + quantity)
