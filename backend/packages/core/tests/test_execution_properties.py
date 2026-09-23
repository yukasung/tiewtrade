from decimal import Decimal as D

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from tiewtrade_core.execution import (
    BracketLeg,
    TopOfBook,
    limit_fill_on_submit,
    market_fill,
    resting_limit_fill,
    resting_limit_fills,
    stop_loss_triggered,
    take_profit_triggered,
    triggered_leg,
)
from tiewtrade_core.market import LiquidityRole, OrderSide, Rounding, round_to_increment

BUY, SELL = OrderSide.BUY, OrderSide.SELL

prices = st.decimals(min_value="1", max_value="200000", places=2)
slippages = st.decimals(min_value="0", max_value="0.05", places=6)
ticks = st.sampled_from([D("0.0001"), D("0.01"), D("0.1"), D("0.5"), D(1)])
sides = st.sampled_from([BUY, SELL])
quantities = st.decimals(min_value="0.001", max_value="200", places=3)


def fillable(bid: D, slippage: D, tick: D) -> bool:
    """Whether a Market Sell still has a positive price after rounding down.

    A cheap quote with a coarse tick floors to zero, which ``market_fill`` rejects by
    design. Those inputs belong to the rejection test, not to the properties below, so
    they are assumed away rather than silently swallowed.
    """
    return round_to_increment(bid * (1 - slippage), tick, Rounding.DOWN) > 0


def on_grid(price: D, tick: D) -> D:
    return round_to_increment(price, tick, Rounding.DOWN)


# --- §4.1 Market Order --------------------------------------------------


@given(bid=prices, ask=prices, slippage=slippages, tick=ticks)
def test_market_fill_is_never_better_than_the_touch(bid: D, ask: D, slippage: D, tick: D) -> None:
    """The simulation must not beat the visible price (D-05)."""
    assume(fillable(bid, slippage, tick))
    book = TopOfBook(best_bid=bid, best_ask=ask)

    assert market_fill(BUY, book, slippage_rate=slippage, tick_size=tick).price >= ask
    assert market_fill(SELL, book, slippage_rate=slippage, tick_size=tick).price <= bid


@given(bid=prices, ask=prices, slippage=slippages, tick=ticks)
def test_rounding_moves_the_price_by_less_than_one_tick(
    bid: D, ask: D, slippage: D, tick: D
) -> None:
    assume(fillable(bid, slippage, tick))
    book = TopOfBook(best_bid=bid, best_ask=ask)

    buy = market_fill(BUY, book, slippage_rate=slippage, tick_size=tick).price
    sell = market_fill(SELL, book, slippage_rate=slippage, tick_size=tick).price

    # bounded by the slipped price on the side that hurts the user, so dropping the
    # slippage factor or rounding the wrong way both break these (C-11)
    assert ask * (1 + slippage) <= buy < ask * (1 + slippage) + tick
    assert bid * (1 - slippage) - tick < sell <= bid * (1 - slippage)


@given(bid=prices, ask=prices, slippage=slippages, tick=ticks, side=sides)
def test_every_fill_price_sits_on_the_tick_grid(
    bid: D, ask: D, slippage: D, tick: D, side: OrderSide
) -> None:
    assume(fillable(bid, slippage, tick))
    book = TopOfBook(best_bid=bid, best_ask=ask)

    price = market_fill(side, book, slippage_rate=slippage, tick_size=tick).price

    assert price % tick == 0


@given(bid=prices, ask=prices, low=slippages, high=slippages, tick=ticks)
def test_more_slippage_never_helps_the_user(bid: D, ask: D, low: D, high: D, tick: D) -> None:
    low, high = min(low, high), max(low, high)
    assume(fillable(bid, high, tick))
    book = TopOfBook(best_bid=bid, best_ask=ask)

    assert (
        market_fill(BUY, book, slippage_rate=low, tick_size=tick).price
        <= market_fill(BUY, book, slippage_rate=high, tick_size=tick).price
    )
    assert (
        market_fill(SELL, book, slippage_rate=low, tick_size=tick).price
        >= market_fill(SELL, book, slippage_rate=high, tick_size=tick).price
    )


@given(bid=prices, slippage=slippages)
def test_a_price_that_rounds_down_to_zero_is_rejected(bid: D, slippage: D) -> None:
    """The complement of the assumption above: those inputs must raise, not return 0.

    The tick is built from the quote rather than filtered for, so every example hits the
    case instead of being discarded.
    """
    tick = bid * (1 - slippage) * 2  # coarser than the slipped bid, so the floor is zero
    assume(tick > 0)
    assert not fillable(bid, slippage, tick)
    book = TopOfBook(best_bid=bid, best_ask=bid)

    with pytest.raises(ValueError, match="fill price must be positive"):
        market_fill(SELL, book, slippage_rate=slippage, tick_size=tick)


# --- §4.2 Limit Order ---------------------------------------------------


@given(bid=prices, ask=prices, limit=prices, slippage=slippages, tick=ticks, side=sides)
def test_a_marketable_limit_never_fills_worse_than_its_limit(
    bid: D, ask: D, limit: D, slippage: D, tick: D, side: OrderSide
) -> None:
    assume(fillable(bid, slippage, tick))
    book = TopOfBook(best_bid=bid, best_ask=ask)
    limit = on_grid(limit, tick)
    assume(limit > 0)

    fill = limit_fill_on_submit(side, limit, book, slippage_rate=slippage, tick_size=tick)
    assume(fill is not None)
    assert fill is not None

    if side is BUY:
        assert fill.price <= limit
    else:
        assert fill.price >= limit
    assert fill.liquidity is LiquidityRole.TAKER


@given(bid=prices, ask=prices, slippage=slippages, tick=ticks, side=sides)
def test_a_deeply_marketable_limit_is_just_a_market_order(
    bid: D, ask: D, slippage: D, tick: D, side: OrderSide
) -> None:
    """With the cap far away, §4.2 must reduce exactly to §4.1."""
    assume(fillable(bid, slippage, tick))
    book = TopOfBook(best_bid=bid, best_ask=ask)
    market = market_fill(side, book, slippage_rate=slippage, tick_size=tick)
    limit = on_grid(market.price * 2, tick) if side is BUY else on_grid(market.price / 2, tick)
    assume(limit > 0)

    fill = limit_fill_on_submit(side, limit, book, slippage_rate=slippage, tick_size=tick)

    assert fill == market


@given(limit=prices, side=sides)
def test_touching_a_resting_limit_never_fills(limit: D, side: OrderSide) -> None:
    assert resting_limit_fills(side, limit, limit) is False
    assert resting_limit_fill(side, limit, limit) is None


@given(limit=prices, last=prices, side=sides)
def test_a_resting_fill_is_always_maker_at_the_limit_price(
    limit: D, last: D, side: OrderSide
) -> None:
    fill = resting_limit_fill(side, limit, last)
    assume(fill is not None)
    assert fill is not None

    assert fill.price == limit
    assert fill.liquidity is LiquidityRole.MAKER


@given(limit=prices, last=prices, lower=prices)
def test_a_buy_that_fills_also_fills_at_any_lower_price(limit: D, last: D, lower: D) -> None:
    lower = min(lower, last)
    assume(resting_limit_fills(BUY, limit, last))

    assert resting_limit_fills(BUY, limit, lower)


# --- §4.3 TP / SL triggers ----------------------------------------------


@given(quantity=quantities, last=prices, trigger=prices)
def test_long_and_short_triggers_mirror_each_other(quantity: D, last: D, trigger: D) -> None:
    assert stop_loss_triggered(quantity, last, trigger) == take_profit_triggered(
        -quantity, last, trigger
    )
    assert take_profit_triggered(quantity, last, trigger) == stop_loss_triggered(
        -quantity, last, trigger
    )


@given(quantity=quantities, last=prices, lower=prices, stop=prices)
def test_a_long_stop_that_fires_also_fires_lower(quantity: D, last: D, lower: D, stop: D) -> None:
    lower = min(lower, last)
    assume(stop_loss_triggered(quantity, last, stop))

    assert stop_loss_triggered(quantity, lower, stop)


@given(quantity=quantities, last=prices, stop=prices, target=prices)
def test_a_well_formed_long_bracket_can_only_fire_one_leg(
    quantity: D, last: D, stop: D, target: D
) -> None:
    """With SL below TP the two conditions are mutually exclusive, so precedence never binds."""
    stop, target = min(stop, target), max(stop, target)
    assume(stop != target)

    leg = triggered_leg(quantity, last, stop_loss_price=stop, take_profit_price=target)

    fired = {
        BracketLeg.STOP_LOSS: stop_loss_triggered(quantity, last, stop),
        BracketLeg.TAKE_PROFIT: take_profit_triggered(quantity, last, target),
    }
    # never both, and the reported leg is exactly the one that fired -- asserted for the
    # None case too, so the test cannot pass vacuously
    assert not (fired[BracketLeg.STOP_LOSS] and fired[BracketLeg.TAKE_PROFIT])
    assert leg == next((k for k, v in fired.items() if v), None)
