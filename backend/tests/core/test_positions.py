from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.money import Money, Quantity
from tiewtrade.core.positions import (
    ExecutionFact,
    ExecutionSide,
    FeeEffect,
    InsufficientPositionError,
    InvalidPositionInputError,
    PositionPair,
    PositionSequenceError,
    PositionState,
    apply_execution,
    rebuild_correction,
    rebuild_position,
    unrealized_pnl,
)

PAIR = PositionPair("BTC", "USDT")
NOW = datetime(2026, 10, 16, tzinfo=UTC)


def _fact(
    sequence: int,
    side: ExecutionSide,
    quantity: str,
    quote: str,
    fee: Money | Quantity | None = None,
) -> ExecutionFact:
    return ExecutionFact(
        execution_id=UUID(int=sequence),
        pair=PAIR,
        side=side,
        gross_quantity=Quantity.of(quantity, "BTC"),
        quote_amount=Money.of(quote, "USDT"),
        fee=None if fee is None else FeeEffect(fee),
        source_sequence=sequence,
        occurred_at=NOW,
    )


def _amount(value: Money | Quantity) -> str:
    return value.as_parts()["amount" if type(value) is Money else "quantity"]


def test_weighted_cost_partial_sell_and_full_close_preserve_remainder() -> None:
    state = PositionState.empty(PAIR)
    first = apply_execution(state, _fact(1, ExecutionSide.BUY, "2", "200"))
    second = apply_execution(first.state, _fact(2, ExecutionSide.BUY, "1", "130"))
    partial = apply_execution(second.state, _fact(3, ExecutionSide.SELL, "1", "150"))
    closed = apply_execution(partial.state, _fact(4, ExecutionSide.SELL, "2", "180"))

    assert (_amount(partial.state.held_quantity), _amount(partial.state.total_cost)) == (
        "2",
        "220",
    )
    assert _amount(partial.state.realized_pnl) == "40"
    assert (_amount(closed.state.held_quantity), _amount(closed.state.total_cost)) == (
        "0",
        "0",
    )
    assert _amount(closed.state.realized_pnl) == "0"


def test_void_rebuild_keeps_the_source_slot_and_returns_compensation() -> None:
    buy = _fact(1, ExecutionSide.BUY, "2", "200", Quantity.of("0.01", "BNB"))

    rebuilt = rebuild_position(PAIR, (buy,))
    corrected = rebuild_correction(PAIR, (buy,), (None,))

    assert rebuilt.state.last_sequence == 1
    assert corrected.state.last_sequence == 1
    assert _amount(corrected.state.held_quantity) == "0"
    assert _amount(corrected.compensating_effects.base_delta) == "-2"
    assert _amount(corrected.compensating_effects.quote_cash_delta) == "200"
    assert [
        (effect.asset, _amount(effect))
        for effect in corrected.compensating_effects.external_asset_effects
    ] == [("BNB", "0.01")]


def test_replacement_returns_each_external_asset_compensation() -> None:
    before = _fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("0.01", "BNB"))
    after = _fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("0.02", "ETH"))

    corrected = rebuild_correction(PAIR, (before,), (after,))

    assert [
        (effect.asset, _amount(effect))
        for effect in corrected.compensating_effects.external_asset_effects
    ] == [("BNB", "0.01"), ("ETH", "-0.02")]


def test_quote_rebate_can_reduce_a_buy_cost_to_zero() -> None:
    transition = apply_execution(
        PositionState.empty(PAIR),
        _fact(1, ExecutionSide.BUY, "1", "100", Money.of("-100", "USDT")),
    )

    assert transition.state.held_quantity == Quantity.of("1", "BTC")
    assert transition.state.total_cost == Money.of("0", "USDT")


def test_sell_correction_rebuilds_realized_pnl_and_returns_only_the_difference() -> None:
    buy = _fact(1, ExecutionSide.BUY, "2", "200")
    original_sell = _fact(2, ExecutionSide.SELL, "1", "120")
    replacement_sell = _fact(2, ExecutionSide.SELL, "1", "130")

    corrected = rebuild_correction(
        PAIR,
        (buy, original_sell),
        (buy, replacement_sell),
    )

    assert corrected.state.realized_pnl == Money.of("30", "USDT")
    assert corrected.compensating_effects.base_delta == Quantity.of("0", "BTC")
    assert corrected.compensating_effects.quote_cash_delta == Money.of("10", "USDT")


@pytest.mark.parametrize(
    ("fee", "quantity", "cost", "external"),
    [
        (Quantity.of("0.001", "BTC"), "0.999", "100", None),
        (Money.of("0.1", "USDT"), "1", "100.1", None),
        (Quantity.of("0.0002", "BNB"), "1", "100", "-0.0002"),
    ],
)
def test_buy_fee_effects_use_the_confirmed_fee_unit(
    fee: Money | Quantity,
    quantity: str,
    cost: str,
    external: str | None,
) -> None:
    result = apply_execution(
        PositionState.empty(PAIR), _fact(1, ExecutionSide.BUY, "1", "100", fee)
    )

    assert _amount(result.state.held_quantity) == quantity
    assert _amount(result.state.total_cost) == cost
    assert (
        None if result.external_asset_effect is None else _amount(result.external_asset_effect)
    ) == external


def test_quote_fee_reduces_sell_proceeds() -> None:
    opened = apply_execution(PositionState.empty(PAIR), _fact(1, ExecutionSide.BUY, "1", "100"))
    sold = apply_execution(
        opened.state,
        _fact(2, ExecutionSide.SELL, "0.5", "60", Money.of("0.06", "USDT")),
    )

    assert _amount(sold.quote_cash_delta) == "59.94"
    assert _amount(sold.released_cost) == "50"
    assert _amount(sold.realized_increment) == "9.94"


def test_rebates_reverse_the_corresponding_fee_effect() -> None:
    result = apply_execution(
        PositionState.empty(PAIR),
        _fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("-0.001", "BTC")),
    )
    assert _amount(result.state.held_quantity) == "1.001"


def test_sell_base_fee_and_third_asset_rebate_keep_their_units() -> None:
    opened = apply_execution(PositionState.empty(PAIR), _fact(1, ExecutionSide.BUY, "1.001", "100"))
    closed = apply_execution(
        opened.state,
        _fact(2, ExecutionSide.SELL, "1", "120", Quantity.of("0.001", "BTC")),
    )
    assert _amount(closed.state.held_quantity) == "0"

    external_rebate = apply_execution(
        PositionState.empty(PAIR),
        _fact(1, ExecutionSide.BUY, "1", "100", Quantity.of("-0.0002", "BNB")),
    )
    assert external_rebate.external_asset_effect is not None
    assert external_rebate.external_asset_effect.asset == "BNB"
    assert _amount(external_rebate.external_asset_effect) == "0.0002"


def test_sequence_gap_and_oversell_fail_closed() -> None:
    state = PositionState.empty(PAIR)
    with pytest.raises(PositionSequenceError):
        apply_execution(state, _fact(2, ExecutionSide.BUY, "1", "100"))
    opened = apply_execution(state, _fact(1, ExecutionSide.BUY, "1", "100"))
    with pytest.raises(InsufficientPositionError):
        apply_execution(opened.state, _fact(2, ExecutionSide.SELL, "2", "200"))


def test_invalid_units_and_fee_shapes_are_rejected() -> None:
    with pytest.raises(InvalidPositionInputError):
        PositionPair("BTC", "BTC")
    with pytest.raises(InvalidPositionInputError):
        _fact(1, ExecutionSide.BUY, "1", "100", Money.of("1", "THB"))


def test_unrealized_pnl_requires_price_only_for_an_open_position() -> None:
    empty = PositionState.empty(PAIR)
    empty_pnl = unrealized_pnl(empty, None)
    assert empty_pnl is not None and _amount(empty_pnl) == "0"
    opened = apply_execution(empty, _fact(1, ExecutionSide.BUY, "2", "200"))
    assert unrealized_pnl(opened.state, None) is None
    value = unrealized_pnl(opened.state, Money.of("130", "USDT"))
    assert value is not None and _amount(value) == "60"


@given(
    quantity=st.integers(min_value=2, max_value=10_000),
    cost=st.integers(min_value=1, max_value=10_000_000),
    sold=st.integers(min_value=1, max_value=9_999),
)
def test_partial_then_full_close_conserves_total_cost(quantity: int, cost: int, sold: int) -> None:
    sold = 1 + sold % (quantity - 1)
    opened = apply_execution(
        PositionState.empty(PAIR),
        _fact(1, ExecutionSide.BUY, str(quantity), str(cost)),
    )
    partial = apply_execution(
        opened.state,
        _fact(2, ExecutionSide.SELL, str(sold), "1"),
    )
    closed = apply_execution(
        partial.state,
        _fact(3, ExecutionSide.SELL, str(quantity - sold), "1"),
    )

    assert partial.released_cost + partial.state.total_cost == opened.state.total_cost
    assert closed.released_cost == partial.state.total_cost
    assert closed.state.held_quantity == Quantity.of(0, "BTC")
    assert closed.state.total_cost == Money.of(0, "USDT")
