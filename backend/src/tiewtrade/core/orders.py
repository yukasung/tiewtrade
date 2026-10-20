"""Immutable shared order contracts; F-15 requirements and approved plan section 3."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol
from uuid import UUID

from tiewtrade.core.money import Money, Quantity, RoundingDirection, money_for_quantity
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, FeeEffect, PositionPair
from tiewtrade.core.trading_limits import ConstraintViolation, unmet_constraints


class OrderError(ValueError):
    code = "ORDER_INPUT_INVALID"


class OrderConflictError(OrderError):
    code = "ORDER_CONFLICT"


class SourceUnavailableError(OrderError):
    code = "ORDER_SOURCE_UNAVAILABLE"


class InsufficientFundsError(OrderError):
    code = "ORDER_INSUFFICIENT_FUNDS"


class SafetyUnavailableError(OrderError):
    code = "ORDER_SAFETY_UNAVAILABLE"


class UnsupportedOrderError(OrderError):
    code = "ORDER_UNSUPPORTED"


def standard_execution_fee(side: ExecutionSide, quantity: Quantity, quote: Money) -> FeeEffect:
    """Received-asset fee for the approved PAPER_STANDARD_V1 profile."""
    received = quantity if side is ExecutionSide.BUY else quote
    fee = received.times("0.001", rounding=RoundingDirection.AWAY_FROM_ZERO)
    if side is ExecutionSide.BUY and not fee < quantity:
        raise OrderError("received quantity cannot represent net fee")
    return FeeEffect(fee)


class TradingMode(Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class OrderOrigin(Enum):
    MANUAL = "MANUAL"
    BOT = "BOT"


class OrderEventType(Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FILL = "FILL"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    QUEUE_REBASED = "QUEUE_REBASED"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TimeInForce(Enum):
    GTC = "GTC"


class OrderStatus(Enum):
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"

    @property
    def terminal(self) -> bool:
        return self in (self.FILLED, self.CANCELED, self.EXPIRED, self.REJECTED)


def aware(value: datetime) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise OrderError("timezone-aware time required")


@dataclass(frozen=True, slots=True)
class OrderScope:
    owner_id: UUID
    episode_id: UUID
    mode: TradingMode

    def __post_init__(self) -> None:
        if type(self.owner_id) is not UUID or type(self.episode_id) is not UUID:
            raise OrderError("owner and episode identities required")
        if not isinstance(self.mode, TradingMode):
            raise OrderError("explicit trading mode required")


@dataclass(frozen=True, slots=True)
class QuoteBudget:
    amount: Money

    def __post_init__(self) -> None:
        if type(self.amount) is not Money or self.amount.amount <= 0:
            raise OrderError("positive Money budget required")


@dataclass(frozen=True, slots=True)
class BaseSize:
    quantity: Quantity

    def __post_init__(self) -> None:
        if type(self.quantity) is not Quantity or self.quantity.amount <= 0:
            raise OrderError("positive Quantity size required")


@dataclass(frozen=True, slots=True)
class OrderIntent:
    order_id: UUID
    idempotency_key: UUID
    scope: OrderScope
    pair: PositionPair
    origin: OrderOrigin
    side: ExecutionSide
    kind: OrderType
    size: QuoteBudget | BaseSize
    limit_price: Money | None = None
    time_in_force: TimeInForce | None = None

    def __post_init__(self) -> None:
        if type(self.order_id) is not UUID or type(self.idempotency_key) is not UUID:
            raise OrderError("order and idempotency identities required")
        if not isinstance(self.scope, OrderScope) or not isinstance(self.pair, PositionPair):
            raise OrderError("scope and pair required")
        if not isinstance(self.origin, OrderOrigin) or not isinstance(self.side, ExecutionSide):
            raise OrderError("explicit origin and side required")
        if not isinstance(self.kind, OrderType):
            raise UnsupportedOrderError("unsupported order type")
        if self.kind is OrderType.MARKET:
            if self.time_in_force is not None or self.limit_price is not None:
                raise UnsupportedOrderError("MARKET has no limit price or time in force")
            expected = QuoteBudget if self.side is ExecutionSide.BUY else BaseSize
            if type(self.size) is not expected:
                raise UnsupportedOrderError("unsupported MARKET size convention")
        elif (
            type(self.size) is not BaseSize
            or type(self.limit_price) is not Money
            or self.time_in_force is not TimeInForce.GTC
        ):
            raise UnsupportedOrderError("LIMIT requires base size, price and GTC")
        if isinstance(self.size, QuoteBudget):
            if self.size.amount.currency != self.pair.quote:
                raise OrderError("budget currency mismatch")
        elif isinstance(self.size, BaseSize):
            if self.size.quantity.asset != self.pair.base:
                raise OrderError("size asset mismatch")
        else:
            raise OrderError("discriminated order size required")
        if self.limit_price is not None and (
            self.limit_price.currency != self.pair.quote or self.limit_price.amount <= 0
        ):
            raise OrderError("positive quote limit price required")


@dataclass(frozen=True, slots=True)
class SimulationProfile:
    fee_version: str = "PAPER_STANDARD_V1"
    liquidity_version: str = "PAPER_DEPTH_SHADOW_V1"

    def __post_init__(self) -> None:
        if (self.fee_version, self.liquidity_version) != (
            "PAPER_STANDARD_V1",
            "PAPER_DEPTH_SHADOW_V1",
        ):
            raise UnsupportedOrderError("unapproved simulation profile")


@dataclass(frozen=True, slots=True)
class OrderConstraints:
    pair: PositionPair
    version: str
    minimum_quantity: Quantity
    quantity_step: Quantity
    minimum_notional: Money
    price_tick: Money
    maximum_quantity: Quantity | None = None
    maximum_notional: Money | None = None
    minimum_price: Money | None = None
    maximum_price: Money | None = None
    supported_types: tuple[OrderType, ...] = (OrderType.MARKET, OrderType.LIMIT)
    unsupported_rules: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pair, PositionPair)
            or type(self.version) is not str
            or not self.version
        ):
            raise OrderError("versioned pair constraints required")
        if any(
            type(value) is not Quantity for value in (self.minimum_quantity, self.quantity_step)
        ):
            raise OrderError("required quantity constraints missing")
        if any(type(value) is not Money for value in (self.minimum_notional, self.price_tick)):
            raise OrderError("required quote constraints missing")
        for quantity in (self.minimum_quantity, self.quantity_step, self.maximum_quantity):
            if quantity is not None and (
                type(quantity) is not Quantity
                or quantity.asset != self.pair.base
                or quantity.amount <= 0
            ):
                raise OrderError("invalid quantity constraint")
        for value in (
            self.minimum_notional,
            self.price_tick,
            self.maximum_notional,
            self.minimum_price,
            self.maximum_price,
        ):
            if value is not None and (
                type(value) is not Money or value.currency != self.pair.quote or value.amount <= 0
            ):
                raise OrderError("invalid price/notional constraint")
        if (
            type(self.supported_types) is not tuple
            or not all(isinstance(kind, OrderType) for kind in self.supported_types)
            or type(self.unsupported_rules) is not tuple
        ):
            raise OrderError("immutable capabilities required")
        if self.maximum_quantity is not None and self.maximum_quantity < self.minimum_quantity:
            raise OrderError("inverted quantity bounds")
        if self.maximum_notional is not None and self.maximum_notional < self.minimum_notional:
            raise OrderError("inverted notional bounds")
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and (self.minimum_price > self.maximum_price)
        ):
            raise OrderError("inverted price bounds")

    def check(self, intent: OrderIntent, quantity: Quantity, notional: Money) -> None:
        if (
            intent.pair != self.pair
            or self.unsupported_rules
            or intent.kind not in self.supported_types
        ):
            raise UnsupportedOrderError("unsupported execution capability")
        violations = unmet_constraints(
            quantity=quantity,
            notional=notional,
            minimum_quantity=self.minimum_quantity,
            quantity_step=self.quantity_step,
            minimum_notional=self.minimum_notional,
            maximum_quantity=self.maximum_quantity,
            maximum_notional=self.maximum_notional,
            price=intent.limit_price,
            price_tick=self.price_tick,
            minimum_price=self.minimum_price,
            maximum_price=self.maximum_price,
        )
        if violations:
            raise OrderConstraintError(violations)


class OrderConstraintError(OrderError):
    code = "ORDER_CONSTRAINT_VIOLATION"

    def __init__(self, violations: tuple[ConstraintViolation, ...]) -> None:
        super().__init__(self.code)
        self.violations = violations


class AdmissionPolicy(Protocol):
    """Server composition supplies shared safety policy; no production READY factory."""

    def check(self, intent: OrderIntent) -> None: ...


@dataclass(frozen=True, slots=True)
class OrderEvent:
    """Append-only facts; event sequence and identity belong to the financial writer."""

    scope: OrderScope
    order_id: UUID
    sequence: int
    occurred_at: datetime
    kind: OrderEventType
    execution: ExecutionFact | None = None
    input_id: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        aware(self.occurred_at)
        if not isinstance(self.scope, OrderScope) or type(self.order_id) is not UUID:
            raise OrderError("event ownership and order identity required")
        if type(self.sequence) is not int or self.sequence <= 0:
            raise OrderError("positive event sequence required")
        if not isinstance(self.kind, OrderEventType):
            raise OrderError("explicit event kind required")
        if (self.kind is OrderEventType.FILL) != isinstance(self.execution, ExecutionFact):
            raise OrderError("execution fact belongs only to a fill event")
        if self.input_id is not None and (type(self.input_id) is not int or self.input_id <= 0):
            raise OrderError("invalid event input identity")
        if (
            self.kind in (OrderEventType.FILL, OrderEventType.QUEUE_REBASED)
            and self.input_id is None
        ):
            raise OrderError("market-driven event requires replay evidence")
        if self.kind is OrderEventType.REJECTED and not self.reason:
            raise OrderError("rejection reason required")


@dataclass(frozen=True, slots=True)
class Reservation:
    quote: Money
    base: Quantity

    def __post_init__(self) -> None:
        if type(self.quote) is not Money or type(self.base) is not Quantity:
            raise OrderError("reservation requires Money and Quantity")
        if self.quote.amount < 0 or self.base.amount < 0:
            raise OrderError("negative reservation")


@dataclass(frozen=True, slots=True)
class OrderState:
    intent: OrderIntent
    sequence: int
    accepted_at: datetime
    status: OrderStatus
    filled: Quantity
    spent: Money
    admission_constraints: OrderConstraints
    resting: bool = False
    queue_ahead: Quantity | None = None

    def __post_init__(self) -> None:
        aware(self.accepted_at)
        if (
            not isinstance(self.intent, OrderIntent)
            or type(self.filled) is not Quantity
            or type(self.spent) is not Money
            or not isinstance(self.admission_constraints, OrderConstraints)
            or self.admission_constraints.pair != self.intent.pair
        ):
            raise OrderError("invalid typed order state")
        if type(self.sequence) is not int or self.sequence <= 0:
            raise OrderError("positive durable order sequence required")
        if not isinstance(self.status, OrderStatus) or type(self.resting) is not bool:
            raise OrderError("invalid order state")
        if (
            self.filled.asset != self.intent.pair.base
            or self.spent.currency != self.intent.pair.quote
        ):
            raise OrderError("order state unit mismatch")
        if self.filled.amount < 0 or self.spent.amount < 0:
            raise OrderError("negative cumulative execution")
        if isinstance(self.intent.size, BaseSize) and self.filled > self.intent.size.quantity:
            raise OrderError("execution exceeds quantity")
        if isinstance(self.intent.size, QuoteBudget) and self.spent > self.intent.size.amount:
            raise OrderError("execution exceeds budget")
        complete = (
            self.filled == self.intent.size.quantity
            if isinstance(self.intent.size, BaseSize)
            else self.spent == self.intent.size.amount
        )
        if (self.status is OrderStatus.FILLED) != complete:
            raise OrderError("completion status disagrees with executed size")
        if self.status in (OrderStatus.ACCEPTED, OrderStatus.REJECTED) and self.filled.amount != 0:
            raise OrderError("unfilled lifecycle status has executions")
        if self.status is OrderStatus.PARTIALLY_FILLED and self.filled.amount == 0:
            raise OrderError("partial status requires an execution")
        if self.resting and (self.intent.kind is not OrderType.LIMIT or self.queue_ahead is None):
            raise OrderError("resting LIMIT queue required")
        if self.queue_ahead is not None and (
            type(self.queue_ahead) is not Quantity
            or self.queue_ahead.asset != self.intent.pair.base
            or self.queue_ahead.amount < 0
        ):
            raise OrderError("invalid queue quantity")

    @property
    def eligible_at(self) -> datetime:
        return self.accepted_at + timedelta(milliseconds=100)

    @property
    def remaining(self) -> Quantity:
        if not isinstance(self.intent.size, BaseSize):
            raise OrderError("budget orders have no fixed remaining base quantity")
        return self.intent.size.quantity - self.filled

    @property
    def reservation(self) -> Reservation:
        quote = Money.of(0, self.intent.pair.quote)
        base = Quantity.of(0, self.intent.pair.base)
        if not self.status.terminal:
            if self.intent.side is ExecutionSide.SELL:
                base = self.remaining
            elif isinstance(self.intent.size, QuoteBudget):
                quote = self.intent.size.amount - self.spent
            elif self.intent.limit_price is not None:
                quote = money_for_quantity(
                    self.intent.limit_price,
                    self.remaining,
                    asset=base.asset,
                    rounding=RoundingDirection.AWAY_FROM_ZERO,
                )
        return Reservation(quote, base)
