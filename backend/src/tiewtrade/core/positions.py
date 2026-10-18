"""Pure Spot position accounting shared by Paper and Live execution adapters (F-14)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from tiewtrade.core.money import (
    Money,
    Quantity,
    RoundingDirection,
    allocate_money,
    money_for_quantity,
)
from tiewtrade.core.money.context import guarded
from tiewtrade.core.money.errors import MoneyError
from tiewtrade.core.money.validation import ensure_canonical_unit


class PositionError(Exception):
    """Base error for deterministic position-domain rejection."""


class InvalidPositionInputError(PositionError):
    """The execution or state violates the approved Spot contract."""


class PositionSequenceError(PositionError):
    """The execution stream is not contiguous."""


class InsufficientPositionError(PositionError):
    """A Spot sell would reduce more base asset than the position holds."""


class ExecutionSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionAvailability(Enum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, slots=True)
class PositionPair:
    base: str
    quote: str

    def __post_init__(self) -> None:
        try:
            ensure_canonical_unit(self.base)
            ensure_canonical_unit(self.quote)
        except MoneyError as cause:
            raise InvalidPositionInputError("invalid position units") from cause
        if self.base == self.quote:
            raise InvalidPositionInputError("base and quote must differ")


@dataclass(frozen=True, slots=True)
class FeeEffect:
    """A positive amount is a charge; a negative amount is a rebate."""

    amount: Money | Quantity

    def __post_init__(self) -> None:
        if type(self.amount) not in (Money, Quantity):
            raise InvalidPositionInputError("fee must be Money or Quantity")
        if self.amount.amount == 0:
            raise InvalidPositionInputError("zero fee must be omitted")


@dataclass(frozen=True, slots=True)
class ExecutionFact:
    execution_id: UUID
    pair: PositionPair
    side: ExecutionSide
    gross_quantity: Quantity
    quote_amount: Money
    fee: FeeEffect | None
    source_sequence: int
    occurred_at: datetime

    def __post_init__(self) -> None:
        if type(self.execution_id) is not UUID:
            raise InvalidPositionInputError("execution id must be UUID")
        if not isinstance(self.pair, PositionPair) or not isinstance(self.side, ExecutionSide):
            raise InvalidPositionInputError("pair and side are required")
        if type(self.gross_quantity) is not Quantity or type(self.quote_amount) is not Money:
            raise InvalidPositionInputError("execution amounts use Quantity and Money")
        if self.gross_quantity.asset != self.pair.base:
            raise InvalidPositionInputError("execution quantity does not match pair base")
        if self.quote_amount.currency != self.pair.quote:
            raise InvalidPositionInputError("execution quote does not match pair quote")
        if self.gross_quantity.amount <= 0 or self.quote_amount.amount <= 0:
            raise InvalidPositionInputError("execution amounts must be positive")
        if self.fee is not None and not isinstance(self.fee, FeeEffect):
            raise InvalidPositionInputError("invalid fee")
        if self.fee is not None:
            fee_amount = self.fee.amount
            if type(fee_amount) is Money and fee_amount.currency != self.pair.quote:
                raise InvalidPositionInputError("money fee must use the quote currency")
            if type(fee_amount) is Quantity and fee_amount.asset == self.pair.quote:
                raise InvalidPositionInputError("quote fee must use Money")
        if type(self.source_sequence) is not int or self.source_sequence <= 0:
            raise InvalidPositionInputError("source sequence must be positive")
        if not isinstance(self.occurred_at, datetime) or self.occurred_at.tzinfo is None:
            raise InvalidPositionInputError("execution time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class PositionState:
    pair: PositionPair
    held_quantity: Quantity
    total_cost: Money
    realized_pnl: Money
    last_sequence: int

    def __post_init__(self) -> None:
        if not isinstance(self.pair, PositionPair):
            raise InvalidPositionInputError("position pair required")
        if type(self.held_quantity) is not Quantity or self.held_quantity.asset != self.pair.base:
            raise InvalidPositionInputError("position quantity unit mismatch")
        if type(self.total_cost) is not Money or self.total_cost.currency != self.pair.quote:
            raise InvalidPositionInputError("position cost unit mismatch")
        if type(self.realized_pnl) is not Money or self.realized_pnl.currency != self.pair.quote:
            raise InvalidPositionInputError("position PnL unit mismatch")
        if self.held_quantity.amount < 0 or self.total_cost.amount < 0:
            raise InvalidPositionInputError("Spot quantity and cost cannot be negative")
        if self.held_quantity.amount == 0 and self.total_cost.amount != 0:
            raise InvalidPositionInputError("zero quantity must have zero cost")
        if type(self.last_sequence) is not int or self.last_sequence < 0:
            raise InvalidPositionInputError("last sequence must be nonnegative")

    @classmethod
    def empty(cls, pair: PositionPair) -> "PositionState":
        return cls(
            pair,
            Quantity.of(0, pair.base),
            Money.of(0, pair.quote),
            Money.of(0, pair.quote),
            0,
        )


@dataclass(frozen=True, slots=True)
class PositionTransition:
    state: PositionState
    base_delta: Quantity
    quote_cash_delta: Money
    released_cost: Money
    realized_increment: Money
    external_asset_effect: Quantity | None


@dataclass(frozen=True, slots=True)
class PositionEffects:
    base_delta: Quantity
    quote_cash_delta: Money
    external_asset_effects: tuple[Quantity, ...]

    def __post_init__(self) -> None:
        if type(self.base_delta) is not Quantity or type(self.quote_cash_delta) is not Money:
            raise InvalidPositionInputError("position effects require Quantity and Money")
        if type(self.external_asset_effects) is not tuple or any(
            type(effect) is not Quantity for effect in self.external_asset_effects
        ):
            raise InvalidPositionInputError("external effects must be immutable quantities")
        assets = [effect.asset for effect in self.external_asset_effects]
        if assets != sorted(set(assets)) or any(
            effect.amount == 0 for effect in self.external_asset_effects
        ):
            raise InvalidPositionInputError("external effects must be nonzero and unique by asset")


@dataclass(frozen=True, slots=True)
class PositionRebuild:
    state: PositionState
    effects: PositionEffects

    def __post_init__(self) -> None:
        if not isinstance(self.state, PositionState) or not isinstance(
            self.effects, PositionEffects
        ):
            raise InvalidPositionInputError("invalid rebuilt position")
        if (
            self.effects.base_delta.asset != self.state.pair.base
            or self.effects.quote_cash_delta.currency != self.state.pair.quote
        ):
            raise InvalidPositionInputError("rebuilt effects do not match pair")


@dataclass(frozen=True, slots=True)
class PositionCorrection:
    state: PositionState
    compensating_effects: PositionEffects

    def __post_init__(self) -> None:
        if not isinstance(self.state, PositionState) or not isinstance(
            self.compensating_effects, PositionEffects
        ):
            raise InvalidPositionInputError("invalid position correction")
        if (
            self.compensating_effects.base_delta.asset != self.state.pair.base
            or self.compensating_effects.quote_cash_delta.currency != self.state.pair.quote
        ):
            raise InvalidPositionInputError("correction effects do not match pair")


def _zero_money(pair: PositionPair) -> Money:
    return Money.of(0, pair.quote)


def _zero_quantity(pair: PositionPair) -> Quantity:
    return Quantity.of(0, pair.base)


def _combine_external(effects: list[Quantity]) -> tuple[Quantity, ...]:
    totals: dict[str, Quantity] = {}
    for effect in effects:
        prior = totals.get(effect.asset, Quantity.of(0, effect.asset))
        totals[effect.asset] = prior + effect
    return tuple(totals[asset] for asset in sorted(totals) if totals[asset].amount != 0)


def _fee_parts(
    pair: PositionPair, fee: FeeEffect | None
) -> tuple[Quantity, Money, Quantity | None]:
    base_fee, quote_fee = _zero_quantity(pair), _zero_money(pair)
    if fee is None:
        return base_fee, quote_fee, None
    amount = fee.amount
    if isinstance(amount, Money):
        if amount.currency != pair.quote:
            raise InvalidPositionInputError("money fee must use the quote currency")
        return base_fee, amount, None
    if amount.asset == pair.base:
        return amount, quote_fee, None
    if amount.asset == pair.quote:
        raise InvalidPositionInputError("quote fee must use Money")
    return base_fee, quote_fee, Quantity.of(0, amount.asset) - amount


@guarded
def apply_execution(state: PositionState, fact: ExecutionFact) -> PositionTransition:
    """Apply one confirmed execution to a Spot position without side effects."""
    if not isinstance(state, PositionState) or not isinstance(fact, ExecutionFact):
        raise InvalidPositionInputError("PositionState and ExecutionFact required")
    if state.pair != fact.pair:
        raise InvalidPositionInputError("execution pair does not match position")
    if fact.source_sequence != state.last_sequence + 1:
        raise PositionSequenceError("execution sequence is not contiguous")
    base_fee, quote_fee, external_effect = _fee_parts(state.pair, fact.fee)
    zero_quantity, zero_money = _zero_quantity(state.pair), _zero_money(state.pair)

    if fact.side is ExecutionSide.BUY:
        base_delta = fact.gross_quantity - base_fee
        adjusted_cost = fact.quote_amount + quote_fee
        if not base_delta > zero_quantity or adjusted_cost < zero_money:
            raise InvalidPositionInputError("buy fee makes execution invalid")
        new_state = PositionState(
            pair=state.pair,
            held_quantity=state.held_quantity + base_delta,
            total_cost=state.total_cost + adjusted_cost,
            realized_pnl=state.realized_pnl,
            last_sequence=fact.source_sequence,
        )
        return PositionTransition(
            new_state,
            base_delta,
            zero_money - adjusted_cost,
            zero_money,
            zero_money,
            external_effect,
        )

    base_delta = zero_quantity - fact.gross_quantity - base_fee
    sold_quantity = zero_quantity - base_delta
    proceeds = fact.quote_amount - quote_fee
    if not base_delta < zero_quantity or proceeds < zero_money:
        raise InvalidPositionInputError("sell fee makes execution invalid")
    if sold_quantity > state.held_quantity:
        raise InsufficientPositionError("sell exceeds held Spot quantity")
    released_cost = (
        state.total_cost
        if sold_quantity == state.held_quantity
        else allocate_money(
            state.total_cost,
            sold_quantity,
            state.held_quantity,
            rounding=RoundingDirection.AWAY_FROM_ZERO,
        )
    )
    remaining_quantity = state.held_quantity - sold_quantity
    remaining_cost = (
        zero_money if remaining_quantity == zero_quantity else state.total_cost - released_cost
    )
    realized_increment = proceeds - released_cost
    new_state = PositionState(
        pair=state.pair,
        held_quantity=remaining_quantity,
        total_cost=remaining_cost,
        realized_pnl=state.realized_pnl + realized_increment,
        last_sequence=fact.source_sequence,
    )
    return PositionTransition(
        new_state,
        base_delta,
        proceeds,
        released_cost,
        realized_increment,
        external_effect,
    )


@guarded
def rebuild_position(
    pair: PositionPair, slots: tuple[ExecutionFact | None, ...]
) -> PositionRebuild:
    """Fold a complete source stream; ``None`` is an explicitly voided sequence slot."""
    if not isinstance(pair, PositionPair) or type(slots) is not tuple:
        raise InvalidPositionInputError("position pair and immutable source slots required")
    state = PositionState.empty(pair)
    base_delta = _zero_quantity(pair)
    quote_delta = _zero_money(pair)
    external: list[Quantity] = []
    for sequence, fact in enumerate(slots, start=1):
        if fact is None:
            state = PositionState(
                pair=pair,
                held_quantity=state.held_quantity,
                total_cost=state.total_cost,
                realized_pnl=state.realized_pnl,
                last_sequence=sequence,
            )
            continue
        if not isinstance(fact, ExecutionFact) or fact.pair != pair:
            raise InvalidPositionInputError("source slot does not match position pair")
        if fact.source_sequence != sequence:
            raise PositionSequenceError("source slot sequence is not contiguous")
        transition = apply_execution(state, fact)
        state = transition.state
        base_delta = base_delta + transition.base_delta
        quote_delta = quote_delta + transition.quote_cash_delta
        if transition.external_asset_effect is not None:
            external.append(transition.external_asset_effect)
    return PositionRebuild(
        state,
        PositionEffects(base_delta, quote_delta, _combine_external(external)),
    )


@guarded
def rebuild_correction(
    pair: PositionPair,
    before: tuple[ExecutionFact | None, ...],
    after: tuple[ExecutionFact | None, ...],
) -> PositionCorrection:
    """Rebuild both immutable histories and return their exact net economic difference."""
    if len(before) != len(after):
        raise PositionSequenceError("correction cannot change source completeness")
    for old_fact, new_fact in zip(before, after, strict=True):
        if (
            old_fact is not None
            and new_fact is not None
            and (
                old_fact.execution_id != new_fact.execution_id
                or old_fact.source_sequence != new_fact.source_sequence
            )
        ):
            raise InvalidPositionInputError("correction changed execution identity")
    old = rebuild_position(pair, before)
    new = rebuild_position(pair, after)
    external = list(new.effects.external_asset_effects)
    external.extend(
        Quantity.of(0, effect.asset) - effect for effect in old.effects.external_asset_effects
    )
    return PositionCorrection(
        new.state,
        PositionEffects(
            new.effects.base_delta - old.effects.base_delta,
            new.effects.quote_cash_delta - old.effects.quote_cash_delta,
            _combine_external(external),
        ),
    )


@guarded
def unrealized_pnl(state: PositionState, latest_price: Money | None) -> Money | None:
    """Return exact unrealized PnL, or unavailable when a nonzero position has no price."""
    if not isinstance(state, PositionState):
        raise InvalidPositionInputError("PositionState required")
    zero = _zero_quantity(state.pair)
    if state.held_quantity == zero:
        return _zero_money(state.pair)
    if latest_price is None:
        return None
    if type(latest_price) is not Money or latest_price.currency != state.pair.quote:
        raise InvalidPositionInputError("latest price unit mismatch")
    if latest_price.amount <= 0:
        raise InvalidPositionInputError("latest price must be positive")
    value = money_for_quantity(
        latest_price,
        state.held_quantity,
        asset=state.pair.base,
        rounding=RoundingDirection.TOWARD_ZERO,
    )
    return value - state.total_cost
