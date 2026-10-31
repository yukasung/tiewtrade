from dataclasses import replace
from datetime import timedelta
from uuid import UUID

import pytest

from tests.core.test_paper_matching import (
    CATALOG,
    PAIR,
    SCOPE,
    T0,
    admit,
    book,
    constraints,
    intent,
    m,
    q,
)
from tiewtrade.core.orders import OrderConflictError, OrderOrigin, OrderStatus, SimulationProfile
from tiewtrade.core.paper_matching import MatchingState, MatchingTransition, advance_matching
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.core.risk_limits import (
    RiskBook,
    RiskExecutionContext,
    RiskPrice,
    RiskScope,
    RiskSetting,
)


def risk(*, ready: bool = True) -> RiskExecutionContext:
    scope = RiskScope(SCOPE.owner_id, SCOPE.mode, UUID(int=3), SCOPE.episode_id)
    price = RiskPrice(
        PAIR,
        QuoteObservation(
            "primary_spot", PAIR.base, PAIR.quote, m(50), 1, T0, T0, ObservationKind.STREAM
        ),
        True,
        True,
        T0 + timedelta(seconds=5),
        1,
        1,
    )
    return RiskExecutionContext(
        RiskSetting(scope, 1, m(10)), RiskBook(scope, 2, ()) if ready else None, (price,), ready
    )


def unset_risk(*, ready: bool = True) -> RiskExecutionContext:
    scope = RiskScope(SCOPE.owner_id, SCOPE.mode, UUID(int=3), SCOPE.episode_id)
    return RiskExecutionContext(RiskSetting(scope, 0, None), None, (), ready)


def advance(state: MatchingState, context: RiskExecutionContext) -> MatchingTransition:
    market = book(ask_quantity="1")
    return advance_matching(
        state,
        market,
        now=market.received_at,
        constraints=constraints(),
        execution_ids=tuple(UUID(int=500 + i) for i in range(20)),
        catalog=CATALOG,
        risk=context,
    )


def test_breach_after_first_depth_fill_blocks_remaining_buy_fills_in_same_batch() -> None:
    state = MatchingState(SCOPE, PAIR, SimulationProfile())
    state = admit(state, intent(10, budget="300"))
    state = admit(state, intent(11, budget="100"), sequence=2)
    result = advance(state, risk())
    assert len(result.fills) == 1 and result.fills[0].gross_quantity == q(1)
    assert result.state.orders[0].status is OrderStatus.PARTIALLY_FILLED
    assert result.state.orders[0].filled == q(1)
    assert result.state.orders[1].status is OrderStatus.ACCEPTED
    assert result.state.orders[1].filled == q(0)


def test_unavailable_risk_does_not_consume_buy_liquidity_or_expire_the_order() -> None:
    state = admit(MatchingState(SCOPE, PAIR, SimulationProfile()), intent())
    result = advance(state, risk(ready=False))
    assert not result.fills
    assert result.state.orders[0].status is OrderStatus.ACCEPTED
    assert all(level.consumed.amount == 0 for level in result.state.liquidity)


def test_unset_paper_limit_allows_buy_only_while_global_opening_is_ready() -> None:
    state = admit(MatchingState(SCOPE, PAIR, SimulationProfile()), intent())
    allowed = advance(state, unset_risk())
    assert len(allowed.fills) == 1
    blocked = advance(state, unset_risk(ready=False))
    assert not blocked.fills
    assert blocked.state.orders[0].status is OrderStatus.ACCEPTED


def test_unset_paper_limit_never_authorizes_bot_matching() -> None:
    state = admit(MatchingState(SCOPE, PAIR, SimulationProfile()), intent())
    bot_order = replace(
        state.orders[0], intent=replace(state.orders[0].intent, origin=OrderOrigin.BOT)
    )
    state = replace(state, orders=(bot_order,))
    result = advance(state, unset_risk())
    assert not result.fills
    assert result.state.orders[0].status is OrderStatus.ACCEPTED


def test_missing_risk_book_does_not_block_existing_bounded_sell() -> None:
    state = admit(
        MatchingState(SCOPE, PAIR, SimulationProfile()), intent(side=ExecutionSide.SELL), held="1"
    )
    result = advance(state, risk(ready=False))
    assert len(result.fills) == 1 and result.fills[0].side is ExecutionSide.SELL
    assert result.state.orders[0].status is OrderStatus.FILLED


def test_cross_owner_risk_context_cannot_authorize_matching() -> None:
    state = admit(MatchingState(SCOPE, PAIR, SimulationProfile()), intent())
    context = risk(ready=False)
    other = replace(context.setting.scope, owner_id=UUID(int=999))
    with pytest.raises(OrderConflictError):
        advance(state, replace(context, setting=replace(context.setting, scope=other)))
