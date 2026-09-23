from collections.abc import Callable
from decimal import Context, Inexact, Rounded, localcontext
from decimal import Decimal as D

import pytest

from tiewtrade_core.execution import (
    BracketLeg,
    TopOfBook,
    closing_side,
    is_marketable,
    limit_fill_on_submit,
    market_fill,
    resting_limit_fill,
    resting_limit_fills,
    stop_loss_triggered,
    take_profit_triggered,
    triggered_leg,
)
from tiewtrade_core.market import LiquidityRole, OrderSide

BUY, SELL = OrderSide.BUY, OrderSide.SELL
MAKER, TAKER = LiquidityRole.MAKER, LiquidityRole.TAKER

TICK = D("0.1")
S = D("0.0002")  # the 0.02% default of FR-ORD-07

LONG, SHORT = D("0.5"), D("-0.5")


def book(bid: str, ask: str) -> TopOfBook:
    return TopOfBook(best_bid=D(bid), best_ask=D(ask))


# Most cases only care about one price, so bid and ask sit on the same touch.
TOUCH = book("60000.1", "60000.1")


# --- TopOfBook ----------------------------------------------------------


def test_normal_book_is_neither_crossed_nor_locked() -> None:
    quotes = book("60000.0", "60000.1")

    assert not quotes.is_crossed
    assert not quotes.is_locked
    assert not quotes.is_abnormal


def test_locked_book_is_abnormal_but_not_crossed() -> None:
    """bid == ask must be caught by is_abnormal; is_crossed alone would miss it."""
    quotes = book("60000.1", "60000.1")

    assert not quotes.is_crossed
    assert quotes.is_locked
    assert quotes.is_abnormal


def test_crossed_book_is_abnormal() -> None:
    quotes = book("60000.2", "60000.1")

    assert quotes.is_crossed
    assert not quotes.is_locked
    assert quotes.is_abnormal


@pytest.mark.parametrize(("bid", "ask"), [("0", "60000.1"), ("60000.0", "0"), ("-1", "60000.1")])
def test_non_positive_quote_is_rejected(bid: str, ask: str) -> None:
    with pytest.raises(ValueError, match="positive"):
        book(bid, ask)


# --- §4.1 Market Order --------------------------------------------------


@pytest.mark.parametrize(
    ("side", "touch", "slippage", "tick", "expected"),
    [
        # lands on the grid, so rounding is a no-op
        (BUY, "60000.0", S, TICK, "60012.0"),
        # 60000.1 * 1.0002 = 60012.10002 -> rounded UP, against the buyer
        (BUY, "60000.1", S, TICK, "60012.2"),
        # 60000.1 * 0.9998 = 59988.09998 -> rounded DOWN, against the seller
        (SELL, "60000.1", S, TICK, "59988.0"),
        # a tick that is not a power of ten
        (BUY, "101.5", D("0.001"), D("0.5"), "102.0"),
        (SELL, "101.5", D("0.001"), D("0.5"), "101.0"),
        # zero slippage is a legal admin setting: the touch itself
        (BUY, "60000.1", D(0), TICK, "60000.1"),
        (SELL, "60000.1", D(0), TICK, "60000.1"),
    ],
)
def test_market_fill_rounds_against_the_user(
    side: OrderSide, touch: str, slippage: D, tick: D, expected: str
) -> None:
    fill = market_fill(side, book(touch, touch), slippage_rate=slippage, tick_size=tick)

    assert fill.price == D(expected)
    assert fill.liquidity is TAKER


def test_market_buy_reads_the_ask_and_sell_reads_the_bid() -> None:
    quotes = book("59000.0", "61000.0")

    buy = market_fill(BUY, quotes, slippage_rate=S, tick_size=TICK)
    sell = market_fill(SELL, quotes, slippage_rate=S, tick_size=TICK)

    assert buy.price >= quotes.best_ask
    assert sell.price <= quotes.best_bid


@pytest.mark.parametrize("slippage", [D("-0.0001"), D(1), D("1.5")])
def test_slippage_outside_the_allowed_range_is_rejected(slippage: D) -> None:
    with pytest.raises(ValueError, match="slippage rate"):
        market_fill(BUY, book("60000.0", "60000.1"), slippage_rate=slippage, tick_size=TICK)


def test_sell_price_rounding_down_to_zero_is_rejected() -> None:
    """tick larger than the slipped bid floors the price to zero, which is not a fill."""
    with pytest.raises(ValueError, match="fill price must be positive"):
        market_fill(SELL, book("1", "1"), slippage_rate=D("0.02"), tick_size=D(1))


# --- §4.2 Limit Order, marketable at submission -------------------------


@pytest.mark.parametrize(
    ("side", "limit", "expected"),
    [
        (BUY, "60013.0", True),
        (BUY, "60000.1", True),  # resting exactly on the ask
        (BUY, "59000.0", False),
        (SELL, "59988.0", True),
        (SELL, "60000.1", True),  # resting exactly on the bid
        (SELL, "61000.0", False),
    ],
)
def test_is_marketable_compares_against_the_raw_book(
    side: OrderSide, limit: str, expected: bool
) -> None:
    assert is_marketable(side, D(limit), TOUCH) is expected


def test_marketable_buy_fills_at_the_market_price_when_the_cap_does_not_bind() -> None:
    fill = limit_fill_on_submit(BUY, D("60013.0"), TOUCH, slippage_rate=S, tick_size=TICK)

    assert fill is not None
    assert fill.price == D("60012.2")
    assert fill.liquidity is TAKER


def test_marketable_buy_never_fills_above_its_limit() -> None:
    """The §4.1 price is 60012.2; the limit caps it to 60012.1 (FR-ORD-08)."""
    fill = limit_fill_on_submit(BUY, D("60012.1"), TOUCH, slippage_rate=S, tick_size=TICK)

    assert fill is not None
    assert fill.price == D("60012.1")
    assert fill.liquidity is TAKER


def test_marketable_sell_never_fills_below_its_limit() -> None:
    fill = limit_fill_on_submit(SELL, D("59988.1"), TOUCH, slippage_rate=S, tick_size=TICK)

    assert fill is not None
    assert fill.price == D("59988.1")


def test_cap_rescues_a_sell_whose_market_price_would_round_to_zero() -> None:
    """The intermediate §4.1 price is 0, but §4.2 caps it to the limit, which is valid.

    Validating the intermediate value instead of the final one would reject this fill.
    """
    fill = limit_fill_on_submit(SELL, D(1), book("1", "1"), slippage_rate=D("0.02"), tick_size=D(1))

    assert fill is not None
    assert fill.price == D(1)
    assert fill.liquidity is TAKER


def test_non_marketable_limit_rests_instead_of_filling() -> None:
    assert limit_fill_on_submit(BUY, D("59000.0"), TOUCH, slippage_rate=S, tick_size=TICK) is None


# --- §4.2 Limit Order, resting ------------------------------------------


@pytest.mark.parametrize(
    ("side", "limit", "last", "fills"),
    [
        (BUY, "59000.0", "58999.9", True),  # through
        (BUY, "59000.0", "59000.0", False),  # touching is not enough
        (BUY, "59000.0", "59000.1", False),
        (SELL, "61000.0", "61000.1", True),
        (SELL, "61000.0", "61000.0", False),
        (SELL, "61000.0", "60999.9", False),
    ],
)
def test_resting_limit_needs_the_price_to_go_through(
    side: OrderSide, limit: str, last: str, fills: bool
) -> None:
    assert resting_limit_fills(side, D(limit), D(last)) is fills

    fill = resting_limit_fill(side, D(limit), D(last))
    if fills:
        assert fill is not None
        assert fill.price == D(limit)
        assert fill.liquidity is MAKER
    else:
        assert fill is None


# --- §4.3 TP / SL triggers ----------------------------------------------


@pytest.mark.parametrize(
    ("quantity", "last", "stop", "triggered"),
    [
        (LONG, "58000.0", "58000.0", True),  # touching fires, unlike a resting limit
        (LONG, "57999.9", "58000.0", True),
        (LONG, "58000.1", "58000.0", False),
        (SHORT, "62000.0", "62000.0", True),
        (SHORT, "62000.1", "62000.0", True),
        (SHORT, "61999.9", "62000.0", False),
    ],
)
def test_stop_loss_fires_on_touch(quantity: D, last: str, stop: str, triggered: bool) -> None:
    assert stop_loss_triggered(quantity, D(last), D(stop)) is triggered


@pytest.mark.parametrize(
    ("quantity", "last", "target", "triggered"),
    [
        (LONG, "62000.0", "62000.0", True),
        (LONG, "62000.1", "62000.0", True),
        (LONG, "61999.9", "62000.0", False),
        (SHORT, "58000.0", "58000.0", True),
        (SHORT, "57999.9", "58000.0", True),
        (SHORT, "58000.1", "58000.0", False),
    ],
)
def test_take_profit_fires_on_touch(quantity: D, last: str, target: str, triggered: bool) -> None:
    assert take_profit_triggered(quantity, D(last), D(target)) is triggered


def test_triggered_leg_picks_the_leg_that_fired() -> None:
    kwargs = {"stop_loss_price": D("58000.0"), "take_profit_price": D("62000.0")}

    assert triggered_leg(LONG, D("58000.0"), **kwargs) is BracketLeg.STOP_LOSS
    assert triggered_leg(LONG, D("62000.0"), **kwargs) is BracketLeg.TAKE_PROFIT
    assert triggered_leg(LONG, D("60000.0"), **kwargs) is None


def test_stop_loss_wins_when_a_mis_set_bracket_fires_both() -> None:
    """Long with SL above TP: both hold at once, and Paper takes the worse outcome."""
    leg = triggered_leg(
        LONG, D("60000.0"), stop_loss_price=D("62000.0"), take_profit_price=D("58000.0")
    )

    assert leg is BracketLeg.STOP_LOSS


def test_triggered_leg_ignores_a_missing_leg() -> None:
    assert (
        triggered_leg(LONG, D("58000.0"), stop_loss_price=None, take_profit_price=D("62000.0"))
        is None
    )
    assert (
        triggered_leg(LONG, D("58000.0"), stop_loss_price=D("58000.0"), take_profit_price=None)
        is BracketLeg.STOP_LOSS
    )


@pytest.mark.parametrize(("quantity", "side"), [(LONG, SELL), (SHORT, BUY)])
def test_closing_side_reduces_the_position(quantity: D, side: OrderSide) -> None:
    assert closing_side(quantity) is side


@pytest.mark.parametrize(
    "call",
    [
        lambda: stop_loss_triggered(D(0), D("58000.0"), D("58000.0")),
        lambda: take_profit_triggered(D(0), D("62000.0"), D("62000.0")),
        lambda: closing_side(D(0)),
        lambda: triggered_leg(D(0), D(1), stop_loss_price=D(1), take_profit_price=D(2)),
    ],
)
def test_a_flat_position_has_no_trigger(call: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="position is flat"):
        call()


# --- §4.3 end to end ----------------------------------------------------


def test_stop_loss_closes_a_long_at_the_market_price() -> None:
    """A fired SL fills as a §4.1 Market order on the closing side."""
    assert stop_loss_triggered(LONG, D("57990.0"), D("58000.0"))
    side = closing_side(LONG)

    fill = market_fill(side, book("57990.0", "57990.1"), slippage_rate=S, tick_size=TICK)

    assert side is SELL
    assert fill.price == D("57978.4")
    assert fill.liquidity is TAKER


# --- Decimal context isolation ------------------------------------------


def test_comparison_helpers_survive_a_hostile_caller_context() -> None:
    """Functions without @calc must hold no Decimal arithmetic.

    A caller may run with a small precision and traps enabled. Anything that subtracts or
    multiplies outside the core context would raise here instead of answering.
    """
    quotes = book("60000.123456789", "60000.987654321")
    last = D("60000.123456789")
    stop = D("60000.1")

    with localcontext(Context(prec=5, traps=[Inexact, Rounded])):
        assert quotes.is_crossed is False
        assert quotes.is_locked is False
        assert quotes.is_abnormal is False
        assert is_marketable(BUY, D("60000.987654321"), quotes) is True
        assert resting_limit_fills(BUY, stop, last) is False
        assert resting_limit_fill(BUY, stop, last) is None
        assert stop_loss_triggered(LONG, last, stop) is False
        assert take_profit_triggered(SHORT, last, stop) is False
        assert triggered_leg(LONG, last, stop_loss_price=stop, take_profit_price=None) is None
        assert closing_side(LONG) is SELL
