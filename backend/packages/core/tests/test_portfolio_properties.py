from decimal import Decimal as D

from hypothesis import given
from hypothesis import strategies as st

from tiewtrade_core.market import OrderSide
from tiewtrade_core.portfolio import FLAT, apply_futures_fill

fills = st.lists(
    st.tuples(
        st.sampled_from([OrderSide.BUY, OrderSide.SELL]),
        st.decimals(min_value="0.001", max_value="50", places=3),
        st.decimals(min_value="1", max_value="100000", places=2),
    ),
    min_size=1,
    max_size=20,
)
close_prices = st.decimals(min_value="1", max_value="100000", places=2)


@given(fills, close_prices)
def test_realized_pnl_equals_cash_flow_once_flat(
    sequence: list[tuple[OrderSide, D, D]], close_price: D
) -> None:
    """Linear contract identity: when flat, total realized PnL = sells - buys (in quote)."""
    position = FLAT
    realized = D(0)
    cash = D(0)
    for number, (side, quantity, price) in enumerate(sequence):
        result = apply_futures_fill(position, side, quantity, price, new_episode_id=f"e{number}")
        position, realized = result.position, realized + result.realized_pnl
        cash -= side.sign * quantity * price
    if not position.is_flat:
        closing_side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        size = abs(position.quantity)
        result = apply_futures_fill(position, closing_side, size, close_price, new_episode_id="x")
        position, realized = result.position, realized + result.realized_pnl
        cash -= closing_side.sign * size * close_price
    assert position.is_flat
    assert abs(realized - cash) <= D("1e-30")


@given(
    st.sampled_from([OrderSide.BUY, OrderSide.SELL]),
    st.decimals(min_value="0.001", max_value="50", places=3),
    close_prices,
)
def test_round_trip_at_same_price_realizes_nothing(side: OrderSide, size: D, price: D) -> None:
    opened = apply_futures_fill(FLAT, side, size, price, new_episode_id="e1")
    opposite = OrderSide.SELL if side is OrderSide.BUY else OrderSide.BUY
    closed = apply_futures_fill(opened.position, opposite, size, price, new_episode_id="e2")
    assert closed.realized_pnl == 0
    assert closed.position.is_flat
    assert closed.closed_episode_id == opened.opened_episode_id == "e1"
