"""Deterministic Spot protection decisions (F-17 NC-01 through NC-07).

Callers supply authoritative quantities, readiness, identities and time. A trigger
decision is an intent, never evidence that an order was accepted or filled.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from tiewtrade.core.money import Money, Quantity, RoundingDirection, money_for_quantity
from tiewtrade.core.orders import (
    BaseSize,
    OrderConflictError,
    OrderConstraints,
    OrderError,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderType,
    aware,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair


class ProtectionError(OrderError):
    """A protection request cannot be applied to the supplied facts."""

    code = "ORDER_INPUT_INVALID"


class ProtectionState(Enum):
    WAITING_ENTRY = "WAITING_ENTRY"
    ARMING = "ARMING"
    ARMED = "ARMED"
    EXITING = "EXITING"
    CLOSED = "CLOSED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


class ProtectionLeg(Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"


class SetupOutcome(Enum):
    SUCCEEDED = "SUCCEEDED"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    UNKNOWN = "UNKNOWN"


class SetupAction(Enum):
    ARM = "ARM"
    RETRY = "RETRY"
    RECONCILE = "RECONCILE"
    NOTIFY_UNPROTECTED = "NOTIFY_UNPROTECTED"
    CLOSE_AND_STOP = "CLOSE_AND_STOP"


@dataclass(frozen=True, slots=True)
class ProtectionPrices:
    pair: PositionPair
    take_profit: Money | None = None
    stop_loss: Money | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.pair, PositionPair):
            raise ProtectionError("protection pair required")
        if self.take_profit is None and self.stop_loss is None:
            raise ProtectionError("at least one protection leg required")
        for price in (self.take_profit, self.stop_loss):
            if price is not None and (
                type(price) is not Money or price.currency != self.pair.quote or price.amount <= 0
            ):
                raise ProtectionError("positive quote protection price required")
        if (
            self.take_profit is not None
            and self.stop_loss is not None
            and not self.stop_loss < self.take_profit
        ):
            raise ProtectionError("stop loss must be below take profit")

    def validate_creation(self, current: Money) -> None:
        self._validate_market_price(current)
        if self.take_profit is not None and not current < self.take_profit:
            raise ProtectionError("take profit already reached")
        if self.stop_loss is not None and not self.stop_loss < current:
            raise ProtectionError("stop loss already reached")

    def _validate_market_price(self, price: Money) -> None:
        if type(price) is not Money or price.currency != self.pair.quote or price.amount <= 0:
            raise ProtectionError("positive quote last trade required")

    def triggered_leg(self, last_trade: Money) -> ProtectionLeg | None:
        self._validate_market_price(last_trade)
        if self.take_profit is not None and not last_trade < self.take_profit:
            return ProtectionLeg.TAKE_PROFIT
        if self.stop_loss is not None and not self.stop_loss < last_trade:
            return ProtectionLeg.STOP_LOSS
        return None


@dataclass(frozen=True, slots=True)
class TriggerEvidence:
    source_id: UUID
    generation: int
    sequence: int
    price: Money
    occurred_at: datetime
    received_at: datetime
    pair: PositionPair

    def __post_init__(self) -> None:
        if type(self.source_id) is not UUID:
            raise ProtectionError("trigger source identity required")
        if any(type(value) is not int or value < 0 for value in (self.generation, self.sequence)):
            raise ProtectionError("invalid trigger source cursor")
        if not isinstance(self.pair, PositionPair):
            raise ProtectionError("trigger pair required")
        if (
            type(self.price) is not Money
            or self.price.amount <= 0
            or self.price.currency != self.pair.quote
        ):
            raise ProtectionError("positive trigger price required")
        aware(self.occurred_at)
        aware(self.received_at)


@dataclass(frozen=True, slots=True)
class EntryAllocationEvidence:
    """Remaining net entry assets, after linked sales/releases, from financial facts."""

    scope: OrderScope
    pair: PositionPair
    entry_order_id: UUID
    available: Quantity
    source_revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.scope, OrderScope) or not isinstance(self.pair, PositionPair):
            raise ProtectionError("entry allocation scope required")
        if type(self.entry_order_id) is not UUID:
            raise ProtectionError("entry identity required")
        _quantity(self.available, self.pair.base)
        if type(self.source_revision) is not int or self.source_revision < 0:
            raise ProtectionError("entry source revision required")


@dataclass(frozen=True, slots=True)
class Protection:
    protection_id: UUID
    scope: OrderScope
    origin: OrderOrigin
    prices: ProtectionPrices
    quantity: Quantity
    state: ProtectionState
    revision: int = 1
    entry_order_id: UUID | None = None
    winning_leg: ProtectionLeg | None = None
    trigger: TriggerEvidence | None = None
    conflicted: bool = False
    setup_attempt: int = 1
    setup_due_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.protection_id) is not UUID or not isinstance(self.scope, OrderScope):
            raise ProtectionError("protection identity and scope required")
        if not isinstance(self.origin, OrderOrigin) or not isinstance(self.state, ProtectionState):
            raise ProtectionError("protection origin and state required")
        if not isinstance(self.prices, ProtectionPrices):
            raise ProtectionError("protection prices required")
        _quantity(self.quantity, self.prices.pair.base)
        if type(self.revision) is not int or self.revision < 1:
            raise ProtectionError("positive protection revision required")
        if type(self.conflicted) is not bool:
            raise ProtectionError("explicit conflict readiness required")
        if type(self.setup_attempt) is not int or not 1 <= self.setup_attempt <= 4:
            raise ProtectionError("invalid setup attempt")
        if self.setup_due_at is not None:
            aware(self.setup_due_at)
        if self.entry_order_id is not None and type(self.entry_order_id) is not UUID:
            raise ProtectionError("entry order identity required")
        if self.state is ProtectionState.WAITING_ENTRY and (
            self.entry_order_id is None or self.quantity.amount != 0
        ):
            raise ProtectionError("waiting bracket must have entry and zero quantity")
        if (
            self.state in (ProtectionState.ARMING, ProtectionState.ARMED)
            and self.quantity.amount == 0
        ):
            raise ProtectionError("active protection quantity required")
        if (
            self.state in (ProtectionState.CANCELED, ProtectionState.CLOSED)
            and self.quantity.amount != 0
        ):
            raise ProtectionError("terminal protection cannot retain allocated quantity")
        if (self.winning_leg is None) != (self.trigger is None):
            raise ProtectionError("trigger evidence and winning leg must be linked")
        if self.trigger is not None:
            if not isinstance(self.trigger, TriggerEvidence):
                raise ProtectionError("invalid trigger evidence")
            if self.trigger.pair != self.prices.pair:
                raise ProtectionError("trigger pair differs from protection")
            if self.prices.triggered_leg(self.trigger.price) is not self.winning_leg:
                raise ProtectionError("trigger evidence does not prove winning leg")
            if self.state not in (
                ProtectionState.EXITING,
                ProtectionState.CLOSED,
                ProtectionState.FAILED,
            ):
                raise ProtectionError("triggered protection must be exiting or closed")
        elif self.state in (ProtectionState.EXITING, ProtectionState.CLOSED):
            raise ProtectionError("exit requires trigger evidence")


def _quantity(value: Quantity, asset: str) -> None:
    if type(value) is not Quantity or value.asset != asset or value.amount < 0:
        raise ProtectionError("nonnegative base quantity required")


def available_quantity(
    *, held: Quantity, reserved: Quantity, allocations: tuple[Quantity, ...]
) -> Quantity:
    """Allocations exclude quantities already transferred to exit reservations."""
    if type(held) is not Quantity:
        raise ProtectionError("held quantity required")
    _quantity(held, held.asset)
    _quantity(reserved, held.asset)
    allocated = reserved
    for value in allocations:
        _quantity(value, held.asset)
        allocated += value
    if allocated > held:
        raise OrderConflictError("protection allocation exceeds authoritative holdings")
    return held - allocated


def _editable(protection: Protection, expected_revision: int) -> None:
    if type(expected_revision) is not int or expected_revision != protection.revision:
        raise OrderConflictError("stale protection revision")
    if protection.state not in (
        ProtectionState.WAITING_ENTRY,
        ProtectionState.ARMING,
        ProtectionState.ARMED,
        ProtectionState.FAILED,
    ):
        raise ProtectionError("protection is no longer editable")


def replace_protection(
    protection: Protection,
    *,
    expected_revision: int,
    prices: ProtectionPrices,
    quantity: Quantity,
    current_price: Money,
    available_including_current: Quantity,
    authoritative_ready: bool,
    entry_evidence: EntryAllocationEvidence | None = None,
) -> Protection:
    _editable(protection, expected_revision)
    if authoritative_ready is not True:
        raise ProtectionError("authoritative quantity is unavailable")
    if prices.pair != protection.prices.pair:
        raise ProtectionError("protection pair is immutable")
    prices.validate_creation(current_price)
    _quantity(quantity, prices.pair.base)
    _quantity(available_including_current, prices.pair.base)
    waiting = protection.state is ProtectionState.WAITING_ENTRY
    if (quantity.amount == 0 and not waiting) or quantity > available_including_current:
        raise ProtectionError("replacement quantity unavailable")
    if waiting and quantity.amount != 0:
        raise ProtectionError("unfilled bracket cannot allocate unfilled quantity")
    if protection.entry_order_id is not None and (
        entry_evidence is None
        or entry_evidence.scope != protection.scope
        or entry_evidence.pair != prices.pair
        or entry_evidence.entry_order_id != protection.entry_order_id
        or quantity > entry_evidence.available
    ):
        raise ProtectionError("replacement exceeds proven remaining entry quantity")
    return replace(
        protection,
        prices=prices,
        quantity=quantity,
        state=ProtectionState.WAITING_ENTRY if waiting else ProtectionState.ARMING,
        revision=protection.revision + 1,
        conflicted=False,
        winning_leg=None,
        trigger=None,
        setup_attempt=1,
        setup_due_at=None,
    )


def cancel_protection(protection: Protection, *, expected_revision: int) -> Protection:
    _editable(protection, expected_revision)
    return replace(
        protection,
        quantity=Quantity.of(0, protection.prices.pair.base),
        state=ProtectionState.CANCELED,
        revision=protection.revision + 1,
        conflicted=False,
        winning_leg=None,
        trigger=None,
    )


@dataclass(frozen=True, slots=True)
class ManualSaleAllocation:
    protection_id: UUID
    expected_revision: int
    quantity: Quantity

    def __post_init__(self) -> None:
        if type(self.protection_id) is not UUID:
            raise ProtectionError("selected protection identity required")
        if type(self.expected_revision) is not int or self.expected_revision < 1:
            raise ProtectionError("positive selected protection revision required")
        if type(self.quantity) is not Quantity or self.quantity.amount <= 0:
            raise ProtectionError("positive selected protection quantity required")


def prepare_manual_sale(
    *,
    scope: OrderScope,
    pair: PositionPair,
    quantity: Quantity,
    held: Quantity,
    reserved: Quantity,
    protections: tuple[Protection, ...],
    selections: tuple[ManualSaleAllocation, ...],
    authoritative_ready: bool,
) -> tuple[Protection, ...]:
    """Preview A's permanent release; commit only with successful SELL admission.

    All active allocations for the pair must be supplied under the same writer
    lock. Terminal orders release their own reservation, never call this function
    in reverse. A failed admission must discard this pure preview entirely.
    """
    if authoritative_ready is not True:
        raise ProtectionError("authoritative quantity is unavailable")
    _quantity(quantity, pair.base)
    _quantity(held, pair.base)
    _quantity(reserved, pair.base)
    if quantity.amount == 0:
        raise ProtectionError("positive manual sale quantity required")
    by_id = {item.protection_id: item for item in protections}
    if len(by_id) != len(protections):
        raise OrderConflictError("duplicate protection identity")
    active = (
        ProtectionState.ARMING,
        ProtectionState.ARMED,
        ProtectionState.FAILED,
    )
    for item in protections:
        if item.scope != scope or item.prices.pair != pair:
            raise OrderConflictError("manual sale protection scope mismatch")
        if item.conflicted or item.state not in active:
            raise OrderConflictError("manual sale requires proven active allocations")
    free = available_quantity(
        held=held, reserved=reserved, allocations=tuple(item.quantity for item in protections)
    )
    selected = Quantity.of(0, pair.base)
    used: set[UUID] = set()
    changed = dict(by_id)
    for selection in selections:
        _quantity(selection.quantity, pair.base)
        if selection.protection_id in used:
            raise OrderConflictError("duplicate protection selection")
        used.add(selection.protection_id)
        selected_item = by_id.get(selection.protection_id)
        if selected_item is None:
            raise OrderConflictError("selected protection is unavailable")
        item = selected_item
        _editable(item, selection.expected_revision)
        if selection.quantity > item.quantity:
            raise ProtectionError("selection exceeds protected quantity")
        selected += selection.quantity
        remainder = item.quantity - selection.quantity
        changed[item.protection_id] = replace(
            item,
            quantity=remainder,
            state=ProtectionState.CANCELED if remainder.amount == 0 else item.state,
            revision=item.revision + 1,
            winning_leg=None if remainder.amount == 0 else item.winning_leg,
            trigger=None if remainder.amount == 0 else item.trigger,
        )
    # Unprotected assets are consumed first; reject excess selections instead of
    # silently choosing which protection to reduce by a smaller amount.
    required = quantity - min(quantity, free)
    if selected != required:
        raise ProtectionError("selected protection quantity must match sale shortfall")
    return tuple(changed[item.protection_id] for item in protections)


def evaluate_trigger(
    protection: Protection,
    evidence: TriggerEvidence,
    *,
    market_ready: bool,
    authoritative_ready: bool,
) -> Protection:
    """The caller must atomically persist the winning transition and exit intent."""
    if (
        market_ready is not True
        or authoritative_ready is not True
        or protection.conflicted
        or protection.quantity.amount == 0
        or protection.state not in (ProtectionState.ARMING, ProtectionState.ARMED)
    ):
        return protection
    if evidence.pair != protection.prices.pair:
        raise ProtectionError("trigger evidence belongs to another pair")
    leg = protection.prices.triggered_leg(evidence.price)
    if leg is None:
        return protection
    return replace(
        protection,
        state=ProtectionState.EXITING,
        winning_leg=leg,
        trigger=evidence,
        revision=protection.revision + 1,
    )


@dataclass(frozen=True, slots=True)
class SetupDecision:
    action: SetupAction
    next_attempt: int | None = None
    due_at: datetime | None = None


def decide_setup_result(
    *, origin: OrderOrigin, attempt: int, outcome: SetupOutcome, observed_at: datetime
) -> SetupDecision:
    aware(observed_at)
    if not isinstance(origin, OrderOrigin) or not isinstance(outcome, SetupOutcome):
        raise ProtectionError("explicit setup origin and outcome required")
    if type(attempt) is not int or not 1 <= attempt <= 4:
        raise ProtectionError("setup attempt outside approved retry budget")
    if outcome is SetupOutcome.UNKNOWN:
        return SetupDecision(SetupAction.RECONCILE)
    if outcome is SetupOutcome.SUCCEEDED:
        return SetupDecision(SetupAction.ARM)
    if outcome is SetupOutcome.TRANSIENT_FAILURE and attempt < 4:
        return SetupDecision(
            SetupAction.RETRY,
            next_attempt=attempt + 1,
            due_at=observed_at + timedelta(seconds=(1, 2, 4)[attempt - 1]),
        )
    return SetupDecision(
        SetupAction.NOTIFY_UNPROTECTED
        if origin is OrderOrigin.MANUAL
        else SetupAction.CLOSE_AND_STOP
    )


def validate_setup(
    value: Protection,
    constraints: OrderConstraints,
    evidence: TriggerEvidence,
    *,
    filter_reference_price: Money | None = None,
) -> None:
    """Use the F-15 admission filter calculation; this does not reserve or submit."""
    if evidence.pair != value.prices.pair:
        raise ProtectionError("setup price belongs to another pair")
    reference = filter_reference_price if constraints.average_price_minutes else evidence.price
    if reference is None:
        from tiewtrade.core.orders import SafetyUnavailableError

        raise SafetyUnavailableError("setup filter reference unavailable")
    intent = OrderIntent(
        value.protection_id,
        value.protection_id,
        value.scope,
        value.prices.pair,
        value.origin,
        ExecutionSide.SELL,
        OrderType.MARKET,
        BaseSize(value.quantity),
    )
    constraints.check(
        intent,
        value.quantity,
        money_for_quantity(
            reference,
            value.quantity,
            asset=value.prices.pair.base,
            rounding=RoundingDirection.AWAY_FROM_ZERO,
        ),
        filter_reference_price=reference,
    )
