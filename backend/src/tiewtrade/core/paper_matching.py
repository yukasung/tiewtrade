"""Pure, replayable Paper matching; storage commits these transitions atomically."""

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from uuid import UUID

from tiewtrade.core.market_catalog import PAIRS
from tiewtrade.core.money import (
    Money,
    Quantity,
    RoundingDirection,
    money_for_quantity,
    quantity_for_budget,
)
from tiewtrade.core.order_book import BookState, MarketInput, MarketTrade, ShadowLevel
from tiewtrade.core.orders import (
    AdmissionPolicy,
    BaseSize,
    InsufficientFundsError,
    OrderConflictError,
    OrderConstraints,
    OrderError,
    OrderIntent,
    OrderScope,
    OrderState,
    OrderStatus,
    OrderType,
    QuoteBudget,
    SafetyUnavailableError,
    SimulationProfile,
    SourceUnavailableError,
    TradingMode,
    UnsupportedOrderError,
    aware,
    standard_execution_fee,
)
from tiewtrade.core.positions import ExecutionFact, ExecutionSide, PositionPair


@dataclass(frozen=True, slots=True)
class MatchingState:
    scope: OrderScope
    pair: PositionPair
    profile: SimulationProfile = field(default_factory=SimulationProfile)
    orders: tuple[OrderState, ...] = ()
    liquidity: tuple[ShadowLevel, ...] = ()
    inputs: tuple[MarketInput, ...] = ()
    input_constraints: tuple[OrderConstraints, ...] = ()
    executions: tuple[ExecutionFact, ...] = ()
    book: BookState | None = None
    execution_sequence: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.scope, OrderScope) or self.scope.mode is not TradingMode.PAPER:
            raise UnsupportedOrderError("Paper matching requires explicit Paper scope")
        if not isinstance(self.pair, PositionPair) or not isinstance(
            self.profile, SimulationProfile
        ):
            raise OrderError("pair and pinned profile required")
        if type(self.execution_sequence) is not int or self.execution_sequence < 0:
            raise OrderError("nonnegative episode execution sequence required")
        for values in (
            self.orders,
            self.liquidity,
            self.inputs,
            self.executions,
            self.input_constraints,
        ):
            if type(values) is not tuple:
                raise OrderError("immutable matching state required")
        if len(self.inputs) != len(self.input_constraints):
            raise OrderError("every consumed input needs its exact constraints")
        if any(o.intent.scope != self.scope or o.intent.pair != self.pair for o in self.orders):
            raise OrderError("order scope/pair mismatch")
        sequences = [o.sequence for o in self.orders]
        if sequences != sorted(set(sequences)):
            raise OrderError("orders must have unique durable sequence")


@dataclass(frozen=True, slots=True)
class MatchingTransition:
    state: MatchingState
    fills: tuple[ExecutionFact, ...]
    maker: bool
    rebased: bool = False
    fill_order_ids: tuple[UUID, ...] = ()


def admit_order(
    state: MatchingState,
    intent: OrderIntent,
    *,
    now: datetime,
    sequence: int,
    cash: Money,
    held: Quantity,
    constraints: OrderConstraints,
    reference_price: Money,
    policy: AdmissionPolicy | None,
) -> MatchingState:
    """Validate funds after other-pair reserves; caller applies F-14 effects before next command."""
    aware(now)
    if intent.scope != state.scope or intent.pair != state.pair:
        raise OrderConflictError("order does not belong to the active scope/pair")
    for order in state.orders:
        if (
            order.intent.order_id == intent.order_id
            or order.intent.idempotency_key == intent.idempotency_key
        ):
            if order.intent != intent:
                raise OrderConflictError("identity payload conflict")
            return state
    if type(sequence) is not int or sequence <= (state.orders[-1].sequence if state.orders else 0):
        raise OrderConflictError("nonmonotonic command sequence")
    if policy is None:
        raise SafetyUnavailableError("shared safety policy is unavailable")
    if intent.side is ExecutionSide.BUY and (intent.pair.base, intent.pair.quote) not in PAIRS:
        raise UnsupportedOrderError("opening pair is not in catalog")
    if (
        cash.currency != intent.pair.quote
        or held.asset != intent.pair.base
        or cash.amount < 0
        or held.amount < 0
    ):
        raise OrderError("invalid authoritative funds")
    if reference_price.currency != state.pair.quote or reference_price.amount <= 0:
        raise OrderError("positive quote reference price required")
    price = intent.limit_price if intent.limit_price is not None else reference_price
    quantity = (
        intent.size.quantity
        if isinstance(intent.size, BaseSize)
        else quantity_for_budget(intent.size.amount, price, constraints.quantity_step)
    )
    notional = money_for_quantity(
        price,
        quantity,
        asset=state.pair.base,
        rounding=RoundingDirection.AWAY_FROM_ZERO,
    )
    constraints.check(intent, quantity, notional)
    policy.check(intent)
    candidate = OrderState(
        intent,
        sequence,
        now,
        OrderStatus.ACCEPTED,
        Quantity.of(0, state.pair.base),
        Money.of(0, state.pair.quote),
        constraints,
    )
    reserved_quote, reserved_base = candidate.reservation.quote, candidate.reservation.base
    for order in state.orders:
        reserved_quote += order.reservation.quote
        reserved_base += order.reservation.base
    if reserved_quote > cash or reserved_base > held:
        raise InsufficientFundsError("funds already reserved or unavailable")
    return replace(state, orders=(*state.orders, candidate))


def cancel_order(state: MatchingState, order_id: UUID, *, scope: OrderScope) -> MatchingState:
    if scope != state.scope:
        raise OrderConflictError("cancel scope mismatch")
    orders = list(state.orders)
    for index, order in enumerate(orders):
        if order.intent.order_id != order_id:
            continue
        if order.status.terminal:
            return state
        orders[index] = replace(order, status=OrderStatus.CANCELED)
        if order.resting:
            for later_index in range(index + 1, len(orders)):
                later = orders[later_index]
                if (
                    later.resting
                    and not later.status.terminal
                    and later.intent.side is order.intent.side
                    and later.intent.limit_price == order.intent.limit_price
                    and later.queue_ahead is not None
                ):
                    orders[later_index] = replace(
                        later,
                        queue_ahead=later.queue_ahead - min(later.queue_ahead, order.remaining),
                    )
        return replace(state, orders=tuple(orders))
    raise OrderConflictError("unknown order")


def _sync_liquidity(state: MatchingState, book: BookState) -> tuple[ShadowLevel, ...]:
    levels: dict[tuple[ExecutionSide, Money], ShadowLevel] = {}
    for side in ExecutionSide:
        for level in book.levels(side):
            levels[side, level.price] = ShadowLevel(
                side, level.price, level.quantity, Quantity.of(0, book.pair.base)
            )
    for prior in state.liquidity:
        try:
            reported = book.reported(prior.side, prior.price)
        except SourceUnavailableError:
            if prior.consumed.amount > 0:
                raise
            continue  # Outside coverage is discarded only when there is no shadow debt.
        levels[prior.side, prior.price] = prior.update(reported)
    return tuple(levels.values())


def _queue(order: OrderState, older: list[OrderState], book: BookState) -> OrderState:
    price = order.intent.limit_price
    if price is None:
        raise OrderError("LIMIT price required for queue placement")
    ahead = book.reported(order.intent.side, price)
    for prior in older:
        if (
            prior.resting
            and not prior.status.terminal
            and prior.intent.side is order.intent.side
            and prior.intent.limit_price == price
        ):
            ahead += prior.remaining
    return replace(order, resting=True, queue_ahead=ahead)


def rebase_order_queues(state: MatchingState, book: BookState) -> MatchingState:
    """Rebuild active LIMIT queue-ahead from a current verified book and older orders."""
    if book.pair != state.pair or not book.rebase:
        raise OrderConflictError("explicit pair rebase book required")
    orders: list[OrderState] = []
    for order in state.orders:
        if order.resting and not order.status.terminal:
            order = _queue(order, orders, book)
        orders.append(order)
    return replace(state, orders=tuple(orders), liquidity=_sync_liquidity(state, book), book=book)


def _fill(
    order: OrderState,
    quantity: Quantity,
    price: Money,
    execution_id: UUID,
    sequence: int,
    at: datetime,
) -> tuple[OrderState, ExecutionFact]:
    quote = money_for_quantity(
        price,
        quantity,
        asset=order.intent.pair.base,
        rounding=(
            RoundingDirection.AWAY_FROM_ZERO
            if order.intent.side is ExecutionSide.BUY
            else RoundingDirection.TOWARD_ZERO
        ),
    )
    fact = ExecutionFact(
        execution_id,
        order.intent.pair,
        order.intent.side,
        quantity,
        quote,
        standard_execution_fee(order.intent.side, quantity, quote),
        sequence,
        at,
    )
    filled = order.filled + quantity
    spent = order.spent + quote
    complete = (
        filled == order.intent.size.quantity
        if isinstance(order.intent.size, BaseSize)
        else spent == order.intent.size.amount
    )
    updated = replace(
        order,
        filled=filled,
        spent=spent,
        status=OrderStatus.FILLED if complete else OrderStatus.PARTIALLY_FILLED,
    )
    if (
        order.intent.side is ExecutionSide.BUY
        and quote + updated.reservation.quote > order.reservation.quote
    ):
        raise OrderError("split fill/reserve cannot represent the approved liability")
    return updated, fact


def advance_matching(
    state: MatchingState,
    market: MarketInput,
    *,
    now: datetime,
    constraints: OrderConstraints,
    execution_ids: tuple[UUID, ...],
) -> MatchingTransition:
    """Consume one durable input; caller supplies episode-wide sequence and fill identities."""
    aware(now)
    if market.pair != state.pair or constraints.pair != state.pair:
        raise OrderConflictError("market input scope mismatch")
    for previous, previous_constraints in zip(state.inputs, state.input_constraints, strict=True):
        if previous.input_id == market.input_id:
            if previous != market or previous_constraints != constraints:
                raise OrderConflictError("market identity payload conflict")
            return MatchingTransition(state, (), isinstance(market, MarketTrade))
    if state.inputs and market.input_id <= state.inputs[-1].input_id:
        raise SourceUnavailableError("out-of-order market input")
    if state.inputs and (
        market.received_at < state.inputs[-1].received_at
        or (
            market.input_id != state.inputs[-1].input_id + 1
            and not (isinstance(market, BookState) and market.rebase)
        )
    ):
        raise SourceUnavailableError("input gap/time reversal requires recovery")
    if constraints.unsupported_rules:
        raise UnsupportedOrderError("unsupported execution rules")
    if market.received_at > now:
        raise SourceUnavailableError("future market input")
    book = market if isinstance(market, BookState) else state.book
    if book is None:
        raise SourceUnavailableError("verified book required")
    book.require_ready(now)
    if state.book is not None and (
        market.generation < state.book.generation
        or (
            market.generation != state.book.generation
            and not (isinstance(market, BookState) and market.rebase)
        )
    ):
        raise SourceUnavailableError("generation change requires verified rebase")
    if isinstance(market, MarketTrade) and (
        not market.ordering_proven or now - market.received_at > timedelta(seconds=1)
    ):
        raise SourceUnavailableError("trade ordering/freshness cannot be proved")
    duplicate_trade = False
    newest_trade_id = 0
    if isinstance(market, MarketTrade):
        for previous in state.inputs:
            if isinstance(previous, MarketTrade) and previous.trade_id == market.trade_id:
                if (previous.resting_side, previous.price, previous.quantity) != (
                    market.resting_side,
                    market.price,
                    market.quantity,
                ):
                    raise OrderConflictError("trade identity payload conflict")
                duplicate_trade = True
            if isinstance(previous, MarketTrade):
                newest_trade_id = max(newest_trade_id, previous.trade_id)
        if not duplicate_trade and market.trade_id < newest_trade_id:
            raise SourceUnavailableError("out-of-order source trade")
    liquidity = (
        list(_sync_liquidity(state, book))
        if isinstance(market, BookState)
        else list(state.liquidity)
    )
    orders: list[OrderState] = []
    fills: list[ExecutionFact] = []
    fill_order_ids: list[UUID] = []
    available_trade = (
        market.quantity if isinstance(market, MarketTrade) else Quantity.of(0, state.pair.base)
    )
    used_ids = {fact.execution_id for fact in state.executions}

    def apply(order: OrderState, quantity: Quantity, price: Money) -> OrderState:
        if len(fills) >= len(execution_ids):
            raise OrderError("insufficient caller-supplied execution identities")
        identity = execution_ids[len(fills)]
        if type(identity) is not UUID or identity in used_ids:
            raise OrderConflictError("execution identity reused")
        updated, fact = _fill(
            order,
            quantity,
            price,
            identity,
            state.execution_sequence + len(fills) + 1,
            market.received_at,
        )
        used_ids.add(identity)
        fills.append(fact)
        fill_order_ids.append(order.intent.order_id)
        return updated

    for order in state.orders:
        if order.status.terminal or market.received_at <= order.eligible_at:
            orders.append(order)
            continue
        if isinstance(market, MarketTrade):
            if (
                not duplicate_trade
                and order.resting
                and order.intent.side is market.resting_side
                and order.intent.limit_price == market.price
                and order.queue_ahead is not None
            ):
                ahead = order.queue_ahead
                order = replace(order, queue_ahead=ahead - min(ahead, market.quantity))
                usable = market.quantity - min(market.quantity, ahead)
                quantity = min(order.remaining, usable, available_trade)
                if quantity.amount > 0:
                    order = apply(order, quantity, market.price)
                    available_trade -= quantity
        elif not order.resting:
            opposite = (
                ExecutionSide.SELL if order.intent.side is ExecutionSide.BUY else ExecutionSide.BUY
            )
            for level in book.levels(opposite):
                limit = order.intent.limit_price
                if limit is not None and (
                    (order.intent.side is ExecutionSide.BUY and level.price > limit)
                    or (order.intent.side is ExecutionSide.SELL and level.price < limit)
                ):
                    break
                index = next(
                    i
                    for i, v in enumerate(liquidity)
                    if v.side is opposite and v.price == level.price
                )
                available = liquidity[index].available
                if isinstance(order.intent.size, QuoteBudget):
                    quantity = min(
                        available,
                        quantity_for_budget(
                            order.intent.size.amount - order.spent,
                            level.price,
                            constraints.quantity_step,
                        ),
                    )
                else:
                    quantity = min(order.remaining, available)
                if quantity.amount > 0:
                    order = apply(order, quantity, level.price)
                    liquidity[index] = liquidity[index].consume(quantity)
                if order.status.terminal:
                    break
            if order.intent.kind is OrderType.MARKET and not order.status.terminal:
                order = replace(order, status=OrderStatus.EXPIRED)
            elif not order.status.terminal:
                order = _queue(order, orders, book)
        if (
            isinstance(market, BookState)
            and market.rebase
            and order.resting
            and not order.status.terminal
        ):
            order = _queue(order, orders, book)
        orders.append(order)
    return MatchingTransition(
        replace(
            state,
            orders=tuple(orders),
            liquidity=tuple(liquidity),
            book=book,
            inputs=(*state.inputs, market),
            input_constraints=(*state.input_constraints, constraints),
            executions=(*state.executions, *fills),
            execution_sequence=state.execution_sequence + len(fills),
        ),
        tuple(fills),
        isinstance(market, MarketTrade),
        isinstance(market, BookState) and market.rebase,
        tuple(fill_order_ids),
    )
