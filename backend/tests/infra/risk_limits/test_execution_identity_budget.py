"""Allocation optimization retains complete matching economics and identities."""

from dataclasses import replace
from uuid import UUID

import pytest

from tests.core.test_paper_matching import (
    CATALOG,
    PAIR,
    SCOPE,
    admit,
    book,
    constraints,
    intent,
    m,
    q,
)
from tests.core.test_risk_matching import risk as risk_context
from tiewtrade.core.orders import OrderStatus, SimulationProfile
from tiewtrade.core.paper_matching import MatchingState, advance_matching
from tiewtrade.core.positions import ExecutionSide
from tiewtrade.infra.paper_orders import worker


@pytest.mark.parametrize("side", [ExecutionSide.BUY, ExecutionSide.SELL])
def test_many_fills_recompute_with_original_ids_and_exact_amounts(
    side: ExecutionSide,
) -> None:
    state = MatchingState(SCOPE, PAIR, SimulationProfile())
    for index in range(33):
        state = admit(
            state,
            intent(100 + index, side=side, limit="100" if side is ExecutionSide.BUY else None),
            sequence=index + 1,
            cash="100000",
            held="100",
        )
    market = book(ask_quantity="100")
    market = replace(market, bids=(replace(market.bids[0], quantity=q(100)), *market.bids[1:]))
    episode = UUID(int=99)
    context = risk_context(ready=False) if side is ExecutionSide.SELL else None
    prefix = f"fill:{PAIR.base}:{PAIR.quote}:{market.generation}:{market.input_id}:"
    expected = advance_matching(
        state,
        market,
        now=market.received_at,
        constraints=constraints(),
        market_constraints=constraints(),
        execution_ids=tuple(
            worker._identity(episode, prefix + str(index))
            for index in range(len(state.orders) * (len(market.bids) + len(market.asks)))
        ),
        catalog=CATALOG,
        risk=context,
    )
    result = worker._advance_matching_with_ids(
        state,
        market,
        episode_id=episode,
        now=market.received_at,
        constraints=constraints(),
        market_constraints=constraints(),
        catalog=CATALOG,
        risk=context,
    )
    assert result == expected
    assert len(result.fills) == len({fact.execution_id for fact in result.fills}) == 33
    assert sum((fact.gross_quantity for fact in result.fills), q(0)) == q(33)
    assert sum((fact.quote_amount for fact in result.fills), m(0)) == m(
        "3300" if side is ExecutionSide.BUY else "3267"
    )
    assert all(
        fact.fee is not None
        and fact.fee.amount == (q("0.001") if side is ExecutionSide.BUY else m("0.099"))
        for fact in result.fills
    )
    assert all(order.status is OrderStatus.FILLED for order in result.state.orders)
    assert not state.executions  # The exhausted pure attempt cannot modify the input.


def test_no_fill_allocates_no_ids_and_preserves_the_full_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = MatchingState(SCOPE, PAIR, SimulationProfile())
    for index in range(33):
        state = admit(state, intent(100 + index, limit="1"), sequence=index + 1)
    market = book()
    episode = UUID(int=99)
    original = worker._identity
    allocated = []

    def identity(owner_episode: UUID, value: str) -> UUID:
        allocated.append(value)
        return original(owner_episode, value)

    monkeypatch.setattr(worker, "_identity", identity)
    result = worker._advance_matching_with_ids(
        state,
        market,
        episode_id=episode,
        now=market.received_at,
        constraints=constraints(),
        market_constraints=constraints(),
        catalog=CATALOG,
        risk=None,
    )
    assert not allocated
    expected = advance_matching(
        state,
        market,
        now=market.received_at,
        constraints=constraints(),
        market_constraints=constraints(),
        execution_ids=(),
        catalog=CATALOG,
    )
    assert result == expected and not result.fills
