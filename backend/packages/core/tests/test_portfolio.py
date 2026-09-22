from decimal import Decimal as D

import pytest

from fasttrade_core.market import OrderSide
from fasttrade_core.portfolio import (
    FLAT,
    NO_HOLDING,
    FuturesPosition,
    apply_futures_fill,
    apply_spot_buy,
    apply_spot_sell,
    funding_payment,
    trading_fee,
)

BUY, SELL = OrderSide.BUY, OrderSide.SELL


def test_open_from_flat_starts_an_episode() -> None:
    result = apply_futures_fill(FLAT, BUY, D(2), D(100), new_episode_id="e1")
    assert result.position == FuturesPosition(D(2), D(100), "e1")
    assert result.opened_episode_id == "e1"
    assert result.realized_pnl == 0


def test_adding_averages_entry_and_keeps_episode() -> None:
    position = FuturesPosition(D(2), D(100), "e1")
    result = apply_futures_fill(position, BUY, D(2), D(110), new_episode_id="unused")
    assert result.position == FuturesPosition(D(4), D(105), "e1")
    assert result.opened_episode_id is None


def test_reducing_realizes_pnl_and_keeps_entry() -> None:
    position = FuturesPosition(D(4), D(105), "e1")
    result = apply_futures_fill(position, SELL, D(1), D(115), new_episode_id="unused")
    assert result.position == FuturesPosition(D(3), D(105), "e1")
    assert result.realized_pnl == D(10)
    assert result.closed_episode_id is None


def test_closing_ends_the_episode() -> None:
    position = FuturesPosition(D(-3), D(50), "e7")
    result = apply_futures_fill(position, BUY, D(3), D(40), new_episode_id="unused")
    assert result.position == FLAT
    assert result.realized_pnl == D(30)  # short profits when price falls
    assert result.closed_episode_id == "e7"


def test_flip_closes_the_episode_and_opens_a_new_one() -> None:
    position = FuturesPosition(D(1), D(100), "e1")
    result = apply_futures_fill(position, SELL, D(3), D(90), new_episode_id="e2")
    assert result.realized_pnl == D(-10)
    assert result.closed_quantity == D(1)
    assert result.opened_quantity == D(2)
    assert result.closed_episode_id == "e1"
    assert result.opened_episode_id == "e2"
    assert result.position == FuturesPosition(D(-2), D(90), "e2")


def test_position_invariants_are_enforced() -> None:
    with pytest.raises(ValueError, match="flat position"):
        FuturesPosition(D(1), None, "e1")


def test_fee_and_funding() -> None:
    assert trading_fee(D("0.5"), D(20_000), D("0.0005")) == D(5)
    # positive rate: long pays, short receives
    assert funding_payment(D(1), D(100), D("0.0001")) == D("0.01")
    assert funding_payment(D(-1), D(100), D("0.0001")) == D("-0.01")


def test_spot_fee_is_not_double_counted() -> None:
    # Review case: buy 1 @ 100 with 1% fee in base, sell all at 100 -> realized 0, fee 1.
    bought = apply_spot_buy(NO_HOLDING, D(1), D(100), D("0.01"), new_episode_id="s1")
    assert bought.received_quantity == D("0.99")
    assert bought.holding.average_cost == D(100)
    assert bought.fee_quote_value == D(1)
    sold = apply_spot_sell(bought.holding, D("0.99"), D(100), D(0))
    assert sold.realized_pnl == 0
    assert sold.holding == NO_HOLDING
    assert sold.closed_episode_id == "s1"
    net = sold.quote_received - bought.quote_spent
    assert net == sold.realized_pnl - bought.fee_quote_value - sold.fee


def test_spot_average_cost_and_partial_sell() -> None:
    first = apply_spot_buy(NO_HOLDING, D(1), D(100), D(0), new_episode_id="s1")
    second = apply_spot_buy(first.holding, D(1), D(200), D(0), new_episode_id="unused")
    assert second.holding.average_cost == D(150)
    assert second.holding.episode_id == "s1"
    sold = apply_spot_sell(second.holding, D(1), D(180), D("0.001"))
    assert sold.realized_pnl == D(30)
    assert sold.fee == D("0.18")
    assert sold.holding.quantity == D(1)
    assert sold.closed_episode_id is None


def test_cannot_sell_more_than_held() -> None:
    held = apply_spot_buy(NO_HOLDING, D(1), D(100), D(0), new_episode_id="s1").holding
    with pytest.raises(ValueError, match="more than the holding"):
        apply_spot_sell(held, D(2), D(100), D(0))
