"""Independent golden, replay and safety oracles for F-15 M1 (no network or database)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Inexact, localcontext
from fractions import Fraction
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.market_catalog import CatalogSnapshot
from tiewtrade.core.money import (
    InvalidInputTypeError,
    Money,
    Quantity,
    UnitMismatchError,
    align_quantity,
    quantity_for_budget,
)
from tiewtrade.core.order_book import BookLevel, BookState, MarketTrade, ShadowLevel
from tiewtrade.core.orders import (
    BaseSize,
    InsufficientFundsError,
    OrderConflictError,
    OrderConstraintError,
    OrderConstraints,
    OrderError,
    OrderEvent,
    OrderEventType,
    OrderIntent,
    OrderOrigin,
    OrderScope,
    OrderStatus,
    OrderType,
    QuoteBudget,
    SafetyUnavailableError,
    SimulationProfile,
    SourceUnavailableError,
    TimeInForce,
    TradingMode,
    UnsupportedOrderError,
)
from tiewtrade.core.paper_matching import (
    MatchingState,
    MatchingTransition,
    admit_order,
    advance_matching,
    cancel_order,
    rebase_order_queues,
)
from tiewtrade.core.positions import ExecutionSide, PositionPair, PositionState, apply_execution
from tiewtrade.core.trading_limits import ConstraintViolation

PAIR = PositionPair("ETH", "USDT")
CATALOG = CatalogSnapshot(1, frozenset({("ETH", "USDT")}))
SCOPE = OrderScope(UUID(int=1), UUID(int=2), TradingMode.PAPER)
T0 = datetime(2026, 10, 18, tzinfo=UTC)


def q(value: str | int) -> Quantity:
    return Quantity.of(value, PAIR.base)


def m(value: str | int) -> Money:
    return Money.of(value, PAIR.quote)


class FixturePolicy:
    """Test-only composition: no production dependency can instantiate this policy."""

    def check(self, intent: OrderIntent) -> None:
        if intent.origin is not OrderOrigin.MANUAL:
            raise SafetyUnavailableError("fixture only authorizes MANUAL")


def constraints(step: str = "0.01") -> OrderConstraints:
    return OrderConstraints(PAIR, "fixture-v1", q(step), q(step), m("0.01"), m("0.01"))


def intent(
    index: int = 10,
    *,
    side: ExecutionSide = ExecutionSide.BUY,
    limit: str | None = None,
    size: str = "1",
    budget: str = "100",
) -> OrderIntent:
    return OrderIntent(
        UUID(int=index),
        UUID(int=index + 1000),
        SCOPE,
        PAIR,
        OrderOrigin.MANUAL,
        side,
        OrderType.LIMIT if limit else OrderType.MARKET,
        QuoteBudget(m(budget))
        if limit is None and side is ExecutionSide.BUY
        else BaseSize(q(size)),
        m(limit) if limit else None,
        TimeInForce.GTC if limit else None,
    )


def admit(
    state: MatchingState,
    command: OrderIntent,
    *,
    sequence: int = 1,
    cash: str = "2500",
    held: str = "10",
    step: str = "0.01",
) -> MatchingState:
    return admit_order(
        state,
        command,
        now=T0,
        sequence=sequence,
        cash=m(cash),
        held=q(held),
        constraints=constraints(step),
        reference_price=m(100),
        policy=FixturePolicy(),
        catalog=CATALOG,
    )


def book(
    input_id: int = 1,
    *,
    at_ms: int = 101,
    ask: str = "100",
    ask_quantity: str = "10",
    bid: str = "99",
    generation: int = 1,
    rebase: bool = False,
    ready: bool = True,
) -> BookState:
    at = T0 + timedelta(milliseconds=at_ms)
    return BookState(
        PAIR,
        input_id,
        generation,
        at,
        at,
        (BookLevel(m(bid), q(10)), BookLevel(m(1), q(10))),
        (BookLevel(m(ask), q(ask_quantity)), BookLevel(m(200), q(10))),
        ready,
        rebase,
    )


def advance(state: MatchingState, event: BookState | MarketTrade) -> MatchingTransition:
    return advance_matching(
        state,
        event,
        now=event.received_at,
        constraints=constraints(),
        execution_ids=tuple(UUID(int=10000 + state.execution_sequence + i) for i in range(20)),
        catalog=CATALOG,
    )


def trade(
    input_id: int,
    quantity: str,
    *,
    trade_id: int = 1,
    at_ms: int = 201,
    side: ExecutionSide = ExecutionSide.BUY,
    price: str = "99",
) -> MarketTrade:
    return MarketTrade(
        PAIR,
        input_id,
        1,
        T0 + timedelta(milliseconds=at_ms),
        trade_id,
        side,
        m(price),
        q(quantity),
        True,
    )


def test_fee_and_cash_golden_uses_existing_f14_accounting() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent())
    buy = advance(state, book(ask_quantity="1"))
    assert len(buy.fills) == 1
    assert buy.fills[0].fee is not None
    assert buy.fills[0].fee.amount == q("0.001")
    position = apply_execution(PositionState.empty(PAIR), buy.fills[0])
    assert position.state.held_quantity == q("0.999")
    assert position.state.total_cost == m(100)
    cash = m(2500) + position.quote_cash_delta
    assert cash == m(2400)
    sell_state = admit(
        buy.state,
        intent(11, side=ExecutionSide.SELL, size="0.999"),
        sequence=2,
        cash="2400",
        held="0.999",
        step="0.001",
    )
    sell = advance(sell_state, book(2, at_ms=301, bid="120", ask="121"))
    result = apply_execution(position.state, sell.fills[0])
    assert sell.fills[0].quote_amount == m("119.88")
    assert result.quote_cash_delta == m("119.76012")
    assert cash + result.quote_cash_delta == m("2519.76012")
    assert result.state.realized_pnl == m("19.76012")
    assert result.state.held_quantity == q(0)
    assert result.state.total_cost == m(0)


def test_budget_walks_depth_expires_dust_and_releases_remainder() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(budget="150"))
    event = replace(book(ask_quantity="1"), asks=(BookLevel(m(100), q(1)), BookLevel(m(110), q(1))))
    result = advance(state, event)
    assert [f.gross_quantity for f in result.fills] == [q(1), q("0.45")]
    assert [f.quote_amount for f in result.fills] == [m(100), m("49.5")]
    assert result.state.orders[0].filled == q("1.45")
    assert result.state.orders[0].spent == m("149.5")
    assert result.state.orders[0].status is OrderStatus.EXPIRED
    assert result.state.orders[0].reservation.quote == m(0)
    position = PositionState.empty(PAIR)
    for fact in result.fills:
        position = apply_execution(position, fact).state
    assert position.held_quantity == q("1.44855")


def test_shared_book_liquidity_cannot_be_used_twice() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(budget="100"))
    state = admit(state, intent(11, budget="100"), sequence=2)
    event = replace(book(ask_quantity="1"), asks=(BookLevel(m(100), q(1)),))
    result = advance(state, event)
    assert len(result.fills) == 1
    assert result.state.orders[0].status is OrderStatus.FILLED
    assert result.state.orders[1].status is OrderStatus.EXPIRED
    assert advance(result.state, event).fills == ()


def test_same_identity_replays_and_payload_conflicts() -> None:
    command = intent()
    state = admit(MatchingState(SCOPE, PAIR), command)
    assert admit(state, command) is state
    with pytest.raises(OrderConflictError):
        admit(state, replace(command, size=QuoteBudget(m(200))))
    result = advance(state, book())
    assert advance(result.state, book()).state is result.state
    with pytest.raises(OrderConflictError):
        advance(result.state, book(ask_quantity="9"))


def test_two_buys_and_two_sells_cannot_reserve_the_same_funds() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="100"), cash="150")
    assert state.orders[0].reservation.quote == m(100)
    with pytest.raises(InsufficientFundsError):
        admit(state, intent(11, limit="100"), sequence=2, cash="150")
    state = admit(MatchingState(SCOPE, PAIR), intent(side=ExecutionSide.SELL), held="1")
    with pytest.raises(InsufficientFundsError):
        admit(state, intent(11, side=ExecutionSide.SELL), sequence=2, held="1")


def test_queue_fifo_and_duplicate_trade_independent_of_depth_changes() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="99"))
    state = admit(state, intent(11, limit="99"), sequence=2)
    event = replace(book(), bids=(BookLevel(m(99), q(2)), BookLevel(m(1), q(10))))
    placed = advance(state, event).state
    assert [o.queue_ahead for o in placed.orders] == [q(2), q(3)]
    depth_only = advance(placed, replace(event, input_id=2, bids=(BookLevel(m(99), q(0)),)))
    assert depth_only.fills == ()
    result = advance(depth_only.state, trade(3, "2.5"))
    assert len(result.fills) == 1
    assert result.state.orders[0].filled == q("0.5")
    assert result.state.orders[1].filled == q(0)
    duplicate = advance(result.state, trade(4, "2.5"))
    assert duplicate.fills == ()
    second = advance(duplicate.state, trade(5, "1", trade_id=2))
    assert [f.gross_quantity for f in second.fills] == [q("0.5"), q("0.5")]
    assert all(o.queue_ahead == q(0) for o in second.state.orders)
    assert second.state.liquidity == result.state.liquidity


def test_cancel_advances_later_queue_and_releases_only_remaining() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="99"))
    state = admit(state, intent(11, limit="99"), sequence=2)
    event = replace(book(), bids=(BookLevel(m(99), q(2)),))
    state = advance(state, event).state
    state = advance(state, trade(2, "2.5")).state
    canceled = cancel_order(state, UUID(int=10), scope=SCOPE)
    assert canceled.orders[0].reservation.quote == m(0)
    assert canceled.orders[0].filled == q("0.5")
    assert canceled.orders[1].queue_ahead == q(0)
    assert cancel_order(canceled, UUID(int=10), scope=SCOPE) is canceled
    assert advance(canceled, trade(3, "0.5", trade_id=2)).state.orders[1].filled == q("0.5")
    other = replace(SCOPE, owner_id=UUID(int=3))
    with pytest.raises(OrderConflictError):
        cancel_order(state, UUID(int=10), scope=other)


def test_nc07_shadow_trace_and_rebase_preserve_consumption() -> None:
    level = ShadowLevel(ExecutionSide.SELL, m(100), q(10), q(0)).consume(q(4))
    assert level.available == q(6)
    for reported, consumed, available in [(8, 4, 4), (10, 4, 6), (2, 2, 0), (0, 0, 0), (10, 0, 10)]:
        level = level.update(q(reported))
        assert level.consumed == q(consumed)
        assert level.available == q(available)
    state = advance(admit(MatchingState(SCOPE, PAIR), intent(budget="400")), book()).state
    rebased = advance(state, book(2, at_ms=201, generation=2, rebase=True))
    assert rebased.rebased
    assert next(v for v in rebased.state.liquidity if v.price == m(100)).available == q(6)
    outside = replace(
        book(3, at_ms=301, generation=3, rebase=True),
        asks=(BookLevel(m(90), q(1)),),
        bids=(BookLevel(m(89), q(1)),),
    )
    with pytest.raises(SourceUnavailableError):
        advance(rebased.state, outside)


@pytest.mark.parametrize("milliseconds,filled", [(99, False), (100, False), (101, True)])
def test_latency_boundary(milliseconds: int, filled: bool) -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent())
    result = advance(state, book(at_ms=milliseconds))
    assert bool(result.fills) is filled


def test_book_freshness_disconnect_future_and_generation_fail_closed() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent())
    event = book()
    ok = advance_matching(
        state,
        event,
        now=event.verified_at + timedelta(seconds=1),
        constraints=constraints(),
        execution_ids=(UUID(int=50),),
        catalog=CATALOG,
    )
    assert len(ok.fills) == 1
    for bad in (replace(event, ready=False), replace(event, verified_at=T0 - timedelta(seconds=2))):
        with pytest.raises(SourceUnavailableError):
            advance(state, bad)
    with pytest.raises(SourceUnavailableError):
        advance_matching(
            state,
            event,
            now=T0,
            constraints=constraints(),
            execution_ids=(),
            catalog=CATALOG,
        )
    with pytest.raises(SourceUnavailableError):
        advance(ok.state, book(2, generation=2))
    assert cancel_order(state, UUID(int=10), scope=SCOPE).orders[0].status is OrderStatus.CANCELED


def test_limit_price_partial_maker_taker_and_sell_reservation() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="105", size="2"))
    result = advance(state, book(ask_quantity="1"))
    assert not result.maker
    assert result.state.orders[0].filled == q(1)
    assert result.state.orders[0].reservation.quote == m(105)
    assert result.state.orders[0].resting
    # A later book crossing the limit cannot itself create a maker fill.
    moved = advance(result.state, book(2, at_ms=201, ask="104"))
    assert moved.fills == ()
    maker = advance(moved.state, trade(3, "1", price="105"))
    assert maker.maker and maker.state.orders[0].status is OrderStatus.FILLED
    assert maker.fills[0].quote_amount == m(105)
    sell = admit(MatchingState(SCOPE, PAIR), intent(side=ExecutionSide.SELL, limit="110"))
    assert sell.orders[0].reservation.base == q(1)
    resting = advance(sell, book()).state
    assert advance(resting, trade(2, "1", side=ExecutionSide.SELL, price="109")).fills == ()


def test_missing_safety_origin_scope_and_live_fail_closed() -> None:
    state = MatchingState(SCOPE, PAIR)
    with pytest.raises(SafetyUnavailableError):
        admit_order(
            state,
            intent(),
            now=T0,
            sequence=1,
            cash=m(2500),
            held=q(0),
            constraints=constraints(),
            reference_price=m(100),
            policy=None,
            catalog=CATALOG,
        )
    with pytest.raises(SafetyUnavailableError):
        admit(state, replace(intent(), origin=OrderOrigin.BOT))
    with pytest.raises(OrderConflictError):
        admit(state, replace(intent(), scope=replace(SCOPE, episode_id=UUID(int=4))))
    with pytest.raises(UnsupportedOrderError):
        MatchingState(replace(SCOPE, mode=TradingMode.LIVE), PAIR)


@pytest.mark.parametrize("change", ["base_buy", "quote_sell", "market_gtc", "limit_no_gtc"])
def test_unsupported_size_or_tif_never_silently_changes(change: str) -> None:
    with pytest.raises(UnsupportedOrderError):
        if change == "base_buy":
            replace(intent(), size=BaseSize(q(1)))
        elif change == "quote_sell":
            replace(intent(), side=ExecutionSide.SELL)
        elif change == "market_gtc":
            replace(intent(), time_in_force=TimeInForce.GTC)
        else:
            replace(intent(limit="100"), time_in_force=None)


def test_constraints_have_typed_exact_violations_and_unknown_rules_reject() -> None:
    with pytest.raises(OrderConstraintError) as failure:
        admit(MatchingState(SCOPE, PAIR), intent(limit="100", size="0.015"))
    assert ConstraintViolation.QUANTITY_NOT_ON_STEP in failure.value.violations
    with pytest.raises(UnsupportedOrderError):
        replace(SimulationProfile(), fee_version="discount")
    with pytest.raises(UnsupportedOrderError):
        advance_matching(
            MatchingState(SCOPE, PAIR),
            book(),
            now=book().received_at,
            constraints=replace(constraints(), unsupported_rules=("new",)),
            execution_ids=(),
            catalog=CATALOG,
        )


def test_exact_replay_from_independent_input_sequence() -> None:
    commands = (intent(limit="99"), intent(11, limit="99"))
    events = (book(), trade(2, "11.5"), trade(3, "0.5", trade_id=2, at_ms=301))

    def replay() -> MatchingState:
        state = MatchingState(SCOPE, PAIR)
        for sequence, command in enumerate(commands, 1):
            state = admit(state, command, sequence=sequence)
        for event in events:
            state = advance(state, event).state
        return state

    first, second = replay(), replay()
    assert first == second
    assert [o.filled for o in first.orders] == [q(1), q(1)]
    assert len(first.executions) == 3
    assert all(o.status is OrderStatus.FILLED for o in first.orders)


@given(st.integers(0, 1000000), st.integers(1, 10000), st.integers(1, 100))
def test_budget_sizing_is_maximal_on_arbitrary_steps(budget: int, price: int, step: int) -> None:
    # Integer oracle is independent of the production money coefficients/rounding helpers.
    result = quantity_for_budget(m(budget), m(price), q(step))
    expected_steps = budget // (price * step)
    assert result == q(expected_steps * step)


@given(st.integers(0, 10000), st.integers(0, 10000), st.integers(0, 10000))
def test_shadow_conservation_property(initial: int, consume: int, reported: int) -> None:
    consume = min(initial, consume)
    level = ShadowLevel(ExecutionSide.SELL, m(100), q(initial), q(consume)).update(q(reported))
    assert level.consumed == q(min(consume, reported))
    assert level.available == q(reported - min(consume, reported))


def test_money_primitives_fractional_step_and_hostile_context() -> None:
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        assert quantity_for_budget(m(150), m(110), q("0.01")) == q("1.36")
        assert align_quantity(q("1.37"), q("0.03")) == q("1.35")
        assert quantity_for_budget(
            m("0.000000000000000001"), m("0.3"), q("0.000000000000000001")
        ) == q("0.000000000000000003")
    with pytest.raises(UnitMismatchError):
        quantity_for_budget(m(1), Money.of(1, "USD"), q(1))
    with pytest.raises(InvalidInputTypeError):
        quantity_for_budget(m(-1), m(1), q(1))
    with pytest.raises(InvalidInputTypeError):
        align_quantity(q(1), q(0))


def test_malformed_book_and_trade_are_rejected() -> None:
    with pytest.raises(OrderError):
        replace(book(), asks=(BookLevel(m(98), q(1)),))
    with pytest.raises(OrderError):
        replace(book(), input_id=True)
    with pytest.raises(OrderError):
        replace(book(), received_at=datetime(2026, 10, 18))
    state = advance(admit(MatchingState(SCOPE, PAIR), intent(limit="99")), book()).state
    with pytest.raises(SourceUnavailableError):
        advance(state, replace(trade(2, "1"), ordering_proven=False))
    state = advance(state, trade(2, "1")).state
    with pytest.raises(OrderConflictError):
        advance(state, trade(3, "2"))


def test_older_duplicate_trade_after_newer_trade_is_still_idempotent() -> None:
    state = advance(admit(MatchingState(SCOPE, PAIR), intent(limit="99")), book()).state
    state = advance(state, trade(2, "1", trade_id=10)).state
    state = advance(state, trade(3, "1", trade_id=11)).state
    result = advance(state, trade(4, "1", trade_id=10, at_ms=301))
    assert result.fills == ()
    assert result.state.orders == state.orders
    with pytest.raises(SourceUnavailableError):
        advance(result.state, trade(5, "1", trade_id=9, at_ms=401))


def test_input_gap_requires_explicit_rebase_and_preserves_shadow() -> None:
    state = advance(admit(MatchingState(SCOPE, PAIR), intent(budget="400")), book()).state
    with pytest.raises(SourceUnavailableError):
        advance(state, book(3, at_ms=301))
    recovered = advance(state, book(3, at_ms=301, rebase=True)).state
    assert next(v.available for v in recovered.liquidity if v.price == m(100)) == q(6)
    with pytest.raises(SourceUnavailableError):
        advance(recovered, book(4, at_ms=201))


def test_engine_absolute_depth_trace_and_independent_episodes() -> None:
    initial = admit(MatchingState(SCOPE, PAIR), intent(budget="400"))
    state = advance(initial, book()).state
    for index, (reported, consumed, available) in enumerate(
        [("8", 4, 4), ("10", 4, 6), ("2", 2, 0), ("0", 0, 0), ("10", 0, 10)], 2
    ):
        state = advance(state, book(index, at_ms=index * 100 + 1, ask_quantity=reported)).state
        level = next(v for v in state.liquidity if v.price == m(100))
        assert level.consumed == q(consumed) and level.available == q(available)
    other_scope = replace(SCOPE, owner_id=UUID(int=99))
    other = admit(MatchingState(other_scope, PAIR), replace(intent(), scope=other_scope))
    assert advance(other, book()).fills[0].gross_quantity == q(1)


def test_partial_cancel_and_terminal_order_cannot_fill_on_later_inputs() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="105", size="2"))
    first = advance(state, book(ask_quantity="1"))
    canceled = cancel_order(first.state, UUID(int=10), scope=SCOPE)
    result = advance(canceled, trade(2, "10", price="105"))
    assert result.fills == ()
    assert result.state.orders[0].filled == q(1)
    assert result.state.orders[0].reservation.quote == m(0)
    assert result.state.orders[0].status is OrderStatus.CANCELED


def test_sell_limit_never_executes_below_limit() -> None:
    command = intent(side=ExecutionSide.SELL, limit="98", size="2")
    state = admit(MatchingState(SCOPE, PAIR), command)
    event = replace(book(), bids=(BookLevel(m(99), q(1)), BookLevel(m(97), q(2))))
    result = advance(state, event)
    assert [f.quote_amount for f in result.fills] == [m(99)]
    assert result.state.orders[0].remaining == q(1)
    assert result.state.orders[0].reservation.base == q(1)


def test_rebase_queue_preserves_paper_fifo_without_gap_fills() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="99"))
    state = admit(state, intent(11, limit="99"), sequence=2)
    state = advance(state, book()).state
    state = advance(state, trade(2, "10.5")).state
    recovered = advance(state, book(5, at_ms=501, generation=2, rebase=True))
    assert recovered.fills == ()
    assert [o.queue_ahead for o in recovered.state.orders] == [q(10), q("10.5")]
    assert [o.filled for o in recovered.state.orders] == [q("0.5"), q(0)]


def test_input_replay_requires_identical_execution_constraints() -> None:
    state = advance(admit(MatchingState(SCOPE, PAIR), intent()), book()).state
    assert state.orders[0].admission_constraints == constraints()
    assert state.input_constraints == (constraints(),)
    with pytest.raises(OrderConflictError):
        advance_matching(
            state,
            book(),
            now=book().received_at,
            constraints=replace(constraints(), version="changed"),
            execution_ids=(),
            catalog=CATALOG,
        )


def test_execution_ids_cannot_be_reused_and_missing_ids_leave_original_state() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="105", size="2"))
    with pytest.raises(OrderError):
        advance_matching(
            state,
            book(),
            now=book().received_at,
            constraints=constraints(),
            execution_ids=(),
            catalog=CATALOG,
        )
    assert state.inputs == () and state.executions == ()
    first = advance(state, book(ask_quantity="1"))
    with pytest.raises(OrderConflictError):
        advance_matching(
            first.state,
            trade(2, "1", price="105"),
            now=trade(2, "1").received_at,
            constraints=constraints(),
            execution_ids=(first.fills[0].execution_id,),
            catalog=CATALOG,
        )


def test_constraint_price_maximum_and_notional_boundaries() -> None:
    rules = replace(
        constraints(),
        price_tick=m("0.1"),
        maximum_quantity=q(2),
        maximum_notional=m(200),
        minimum_price=m(10),
        maximum_price=m(100),
    )
    command = intent(limit="100", size="2")
    rules.check(command, q(2), m(200))
    with pytest.raises(OrderConstraintError) as failure:
        rules.check(replace(command, limit_price=m("100.01")), q(3), m(300))
    assert set(failure.value.violations) == {
        ConstraintViolation.PRICE_NOT_ON_TICK,
        ConstraintViolation.ABOVE_MAXIMUM_PRICE,
        ConstraintViolation.ABOVE_MAXIMUM_QUANTITY,
        ConstraintViolation.ABOVE_MAXIMUM_NOTIONAL,
    }
    with pytest.raises(OrderConstraintError) as failure:
        rules.check(replace(command, limit_price=m(9)), q(1), m(9))
    assert ConstraintViolation.BELOW_MINIMUM_PRICE in failure.value.violations


def test_withdrawn_pair_can_reduce_or_cancel_but_cannot_open() -> None:
    pair = PositionPair("WITHDRAWN", "USDT")
    rules = OrderConstraints(
        pair, "withdrawn-v1", Quantity.of(1, pair.base), Quantity.of(1, pair.base), m(1), m(1)
    )
    sell = OrderIntent(
        UUID(int=50),
        UUID(int=51),
        SCOPE,
        pair,
        OrderOrigin.MANUAL,
        ExecutionSide.SELL,
        OrderType.MARKET,
        BaseSize(Quantity.of(1, pair.base)),
    )
    state = admit_order(
        MatchingState(SCOPE, pair),
        sell,
        now=T0,
        sequence=1,
        cash=m(2500),
        held=Quantity.of(1, pair.base),
        constraints=rules,
        reference_price=m(100),
        policy=FixturePolicy(),
        catalog=CatalogSnapshot(2, frozenset()),
    )
    assert cancel_order(state, sell.order_id, scope=SCOPE).orders[0].status is OrderStatus.CANCELED
    with pytest.raises(UnsupportedOrderError):
        admit_order(
            MatchingState(SCOPE, pair),
            replace(sell, side=ExecutionSide.BUY, size=QuoteBudget(m(100))),
            now=T0,
            sequence=1,
            cash=m(2500),
            held=Quantity.of(0, pair.base),
            constraints=rules,
            reference_price=m(100),
            policy=FixturePolicy(),
            catalog=CatalogSnapshot(2, frozenset()),
        )


def test_withdrawn_pair_snapshot_blocks_opening_fill_but_allows_reduce_fill() -> None:
    active = CatalogSnapshot(1, frozenset({("ETH", "USDT")}))
    removed = CatalogSnapshot(2, frozenset())
    opening = admit(MatchingState(SCOPE, PAIR), intent(limit="105"))
    reduction = admit(
        MatchingState(SCOPE, PAIR),
        intent(20, side=ExecutionSide.SELL, limit="99"),
    )
    market = book()

    blocked = advance_matching(
        opening,
        market,
        now=market.received_at,
        constraints=constraints(),
        execution_ids=(UUID(int=900),),
        catalog=removed,
    )
    reduced = advance_matching(
        reduction,
        market,
        now=market.received_at,
        constraints=constraints(),
        execution_ids=(UUID(int=901),),
        catalog=removed,
    )

    assert blocked.fills == ()
    assert blocked.state.orders[0].status is OrderStatus.ACCEPTED
    assert len(reduced.fills) == 1
    assert reduced.fills[0].side is ExecutionSide.SELL
    assert active.supports(PAIR.base, PAIR.quote)


@given(st.integers(0, 100000), st.integers(1, 100000), st.integers(1, 1000))
def test_fractional_budget_sizing_respects_rounded_cost_and_maximal_step(
    budget_coefficient: int,
    price_coefficient: int,
    step_coefficient: int,
) -> None:
    budget = m(f"{budget_coefficient // 100}.{budget_coefficient % 100:02}")
    price = m(f"{price_coefficient // 100}.{price_coefficient % 100:02}")
    step = q(f"{step_coefficient // 1000}.{step_coefficient % 1000:03}")
    result = quantity_for_budget(budget, price, step)
    available = Fraction(budget.amount)
    cost = Fraction(price.amount)
    quantum = Fraction(step.amount)
    assert Fraction(result.amount) == (available // (cost * quantum)) * quantum
    assert Fraction(result.amount) * cost <= available
    assert (Fraction(result.amount) + quantum) * cost > available


def test_full_matching_under_hostile_decimal_context() -> None:
    command = intent(budget="150")
    event = replace(book(), asks=(BookLevel(m(100), q(1)), BookLevel(m(110), q(1))))
    normal = advance(admit(MatchingState(SCOPE, PAIR), command), event)
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        hostile = advance(admit(MatchingState(SCOPE, PAIR), command), event)
    assert normal == hostile


def test_order_event_requires_evidence_and_preserves_scope() -> None:
    result = advance(admit(MatchingState(SCOPE, PAIR), intent()), book())
    event = OrderEvent(
        SCOPE,
        UUID(int=10),
        2,
        book().received_at,
        OrderEventType.FILL,
        execution=result.fills[0],
        input_id=1,
    )
    assert event.scope == SCOPE and event.execution == result.fills[0]
    with pytest.raises(OrderError):
        replace(event, input_id=None)
    with pytest.raises(OrderError):
        replace(event, kind=OrderEventType.CANCELED)
    with pytest.raises(OrderError):
        OrderEvent(SCOPE, UUID(int=10), 1, T0, OrderEventType.REJECTED)


def test_invalid_lifecycle_snapshot_cannot_claim_filled_or_partial() -> None:
    order = admit(MatchingState(SCOPE, PAIR), intent()).orders[0]
    for status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED):
        with pytest.raises(OrderError):
            replace(order, status=status)


@given(st.integers(0, 20), st.integers(1, 10), st.integers(1, 10), st.integers(1, 50))
def test_fifo_fill_quantity_matches_independent_integer_oracle(
    external: int,
    first: int,
    second: int,
    traded: int,
) -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="99", size=str(first)), cash="10000")
    state = admit(state, intent(11, limit="99", size=str(second)), sequence=2, cash="10000")
    event = replace(book(), bids=(BookLevel(m(99), q(external)), BookLevel(m(1), q(10))))
    state = advance(state, event).state
    result = advance(state, trade(2, str(traded)))
    expected_first = min(first, max(0, traded - external))
    expected_second = min(second, max(0, traded - external - first))
    assert [o.filled for o in result.state.orders] == [q(expected_first), q(expected_second)]


def test_correction_rebase_recalculates_queue_from_current_book_and_older_orders() -> None:
    state = admit(MatchingState(SCOPE, PAIR), intent(limit="99", size="2"), cash="10000")
    state = admit(state, intent(11, limit="99", size="3"), sequence=2, cash="10000")
    initial = replace(book(), bids=(BookLevel(m(99), q(8)), BookLevel(m(1), q(10))))
    state = advance(state, initial).state
    current = replace(
        initial,
        input_id=2,
        received_at=initial.received_at + timedelta(milliseconds=1),
        verified_at=initial.verified_at + timedelta(milliseconds=1),
        bids=(BookLevel(m(99), q(5)), BookLevel(m(1), q(10))),
        rebase=True,
    )
    rebased = rebase_order_queues(state, current, constraints=constraints())
    assert [value.queue_ahead for value in rebased.orders] == [q(5), q(7)]


def test_correction_rebase_advances_durable_cursor_and_rejects_older_trade() -> None:
    from tiewtrade.infra.paper_orders.codec import state_from_payload, state_payload

    state = admit(MatchingState(SCOPE, PAIR), intent(limit="99", size="2"))
    state = advance(state, book()).state
    state = advance(state, trade(2, "10.5")).state
    current = replace(
        book(4, at_ms=401, rebase=True),
        bids=(BookLevel(m(99), q(0)), BookLevel(m(1), q(10))),
    )
    state = rebase_order_queues(state, current, constraints=constraints())
    recovered = state_from_payload(state_payload(state))
    assert recovered.inputs[-1] == current
    assert recovered.orders[0].queue_ahead == q(0)
    with pytest.raises(SourceUnavailableError):
        advance(recovered, trade(3, "1", trade_id=2, at_ms=301))
    result = advance(recovered, trade(5, "1", trade_id=3, at_ms=501))
    assert result.state.orders[0].filled == q("1.5")
    assert len(result.fills) == 1


@pytest.mark.parametrize("levels", [(("50", "2"),), (("50", "0.5"), ("60", "1"))])
def test_market_budget_cannot_exceed_cumulative_quantity_maximum(
    levels: tuple[tuple[str, str], ...],
) -> None:
    rules = replace(constraints(), maximum_quantity=q(1))
    state = admit_order(
        MatchingState(SCOPE, PAIR),
        intent(budget="100"),
        now=T0,
        sequence=1,
        cash=m(2500),
        held=q(0),
        constraints=rules,
        reference_price=m(100),
        policy=FixturePolicy(),
        catalog=CATALOG,
    )
    # Both a falling price and cumulative multi-level fills must obey maxQty.
    event = replace(book(bid="49", ask="50"), asks=tuple(BookLevel(m(p), q(v)) for p, v in levels))
    with pytest.raises(OrderConstraintError) as caught:
        advance_matching(
            state,
            event,
            now=event.received_at,
            constraints=constraints(),
            market_constraints=rules,
            execution_ids=(UUID(int=900), UUID(int=901)),
            catalog=CATALOG,
        )
    assert caught.value.violations == (ConstraintViolation.ABOVE_MAXIMUM_QUANTITY,)
    assert state.orders[0].filled == q(0)


def test_matching_uses_market_capability_and_persists_its_replay_contract() -> None:
    from tiewtrade.infra.paper_orders.codec import state_from_payload, state_payload

    state = admit(MatchingState(SCOPE, PAIR), intent(budget="150"))
    market_rules = replace(constraints("0.03"), supported_types=(OrderType.MARKET,))
    event = replace(book(ask="110", bid="109"), asks=(BookLevel(m(110), q(10)),))
    result = advance_matching(
        state,
        event,
        now=event.received_at,
        constraints=constraints(),
        market_constraints=market_rules,
        execution_ids=(UUID(int=900),),
        catalog=CATALOG,
    )
    assert result.state.orders[0].filled == q("1.35")
    recovered = state_from_payload(state_payload(result.state))
    assert recovered.input_market_constraints == (market_rules,)
    with pytest.raises(OrderConflictError):
        advance_matching(
            recovered,
            event,
            now=event.received_at,
            constraints=constraints(),
            market_constraints=replace(market_rules, version="changed"),
            execution_ids=(),
            catalog=CATALOG,
        )
    for unavailable in (
        replace(market_rules, unsupported_rules=("MARKET_RULE_UNAVAILABLE",)),
        replace(market_rules, supported_types=(OrderType.LIMIT,)),
    ):
        with pytest.raises(UnsupportedOrderError):
            advance_matching(
                state,
                event,
                now=event.received_at,
                constraints=constraints(),
                market_constraints=unavailable,
                execution_ids=(),
                catalog=CATALOG,
            )


def test_correction_rebase_keeps_cursor_when_latest_book_precedes_consumed_trade() -> None:
    state = advance(admit(MatchingState(SCOPE, PAIR), intent(limit="99", size="2")), book()).state
    state = advance(state, trade(2, "10.5")).state
    current = replace(book(), rebase=True)
    rebased = rebase_order_queues(state, current, constraints=constraints())
    assert rebased.inputs == state.inputs
    assert rebased.input_market_constraints == state.input_market_constraints
    assert rebased.orders[0].filled == q("0.5")
    assert rebased.orders[0].queue_ahead == q(10)
