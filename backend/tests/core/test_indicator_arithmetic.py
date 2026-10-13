from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import localcontext
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core.money import (
    AverageState,
    BatchAction,
    IndicatorBatchInput,
    IndicatorBatchState,
    InvalidInputTypeError,
    Money,
    OutOfRangeError,
    RoundingDirection,
    Scalar,
    advance_indicator_batch,
    divide_money,
    percentage_share,
    reset_indicator_batch,
    weighted_mean_money,
)
from tiewtrade.core.money.rounding import rounded_quotient

FLOOR = RoundingDirection.TOWARD_NEGATIVE


@pytest.mark.parametrize(
    "number,expected", [(1, "0.333333333333333333"), (-1, "-0.333333333333333334")]
)
def test_division_golden(number: int, expected: str) -> None:
    assert (
        divide_money(Money.of(number, "USDT"), 3, rounding=FLOOR).as_parts()["amount"] == expected
    )


def test_mean_share_overflow_and_context() -> None:
    with localcontext() as context:
        context.prec = 2
        mean = weighted_mean_money([(Money.of(v, "USDT"), 1) for v in (1, 2, 2)], rounding=FLOOR)
        assert mean.as_parts()["amount"] == "1.666666666666666666"
        share = percentage_share(Money.of(1, "USDT"), Money.of(2, "USDT"), rounding=FLOOR)
        assert share.as_text() == "33.333333333333333333"
        large = Money.of("90000000000000000000", "USDT")
        assert weighted_mean_money([(large, 1), (large, 1)], rounding=FLOOR) == large
        assert Scalar.of("-0").as_text() == "0"
        assert context.prec == 2
        with pytest.raises(OutOfRangeError):
            large - Money.of("-90000000000000000000", "USDT")


@given(st.integers(-(10**15), 10**15), st.integers(1, 200))
def test_ratio_against_independent_fraction(numerator: int, denominator: int) -> None:
    exact = Fraction(numerator, denominator)
    result = divide_money(Money.of(numerator, "USDT"), denominator, rounding=FLOOR)
    assert 0 <= exact - Fraction(result.amount) < Fraction(1, 10**18)


@pytest.mark.parametrize(
    "mode,positive,negative",
    [
        (RoundingDirection.TOWARD_ZERO, 0, 0),
        (RoundingDirection.AWAY_FROM_ZERO, 1, -1),
        (RoundingDirection.TOWARD_POSITIVE, 1, 0),
        (FLOOR, 0, -1),
    ],
)
def test_all_rounding_directions(mode: RoundingDirection, positive: int, negative: int) -> None:
    assert rounded_quotient(1, 3, mode) == positive
    assert rounded_quotient(-1, 3, mode) == negative


def test_bool_and_zero_share_rejected() -> None:
    with pytest.raises(InvalidInputTypeError):
        divide_money(Money.of(1, "USDT"), True, rounding=FLOOR)
    with pytest.raises(InvalidInputTypeError):
        percentage_share(Money.of(0, "USDT"), Money.of(0, "USDT"), rounding=FLOOR)


def test_batch_rejects_invalid_public_state_and_events() -> None:
    state = IndicatorBatchState("BTC", "USDT", "1m", timedelta(minutes=1))
    moment = datetime(2026, 10, 10, tzinfo=UTC)
    bad_gain = list(state.averages)
    bad_gain[3] = AverageState(value=Money.of(-1, "USDT"))
    with pytest.raises(InvalidInputTypeError):
        replace(state, last_open=moment, previous=Money.of(100, "USDT"), averages=tuple(bad_gain))
    with pytest.raises(InvalidInputTypeError):
        advance_indicator_batch(
            state,
            (
                IndicatorBatchInput(
                    moment,
                    BatchAction.ACCEPT,
                    "BTC",
                    "USDT",
                    "1m",
                    Money.of(-1, "USDT"),
                    Money.of(2, "USDT"),
                    Money.of(1, "USDT"),
                ),
            ),
            output_indices=(),
            rounding=FLOOR,
        )
    with pytest.raises(InvalidInputTypeError):
        advance_indicator_batch(
            state,
            (IndicatorBatchInput(moment, BatchAction.HOLD, "BTC", "USDT", "1m"),),
            output_indices=(True,),
            rounding=FLOOR,
        )


@pytest.mark.parametrize("batch_size", [1, 2, 16])
@pytest.mark.parametrize("populated", [False, True])
def test_all_reset_batch_exactly_clears_state(batch_size: int, populated: bool) -> None:
    span = timedelta(minutes=1)
    start = datetime(2026, 10, 10, tzinfo=UTC)
    state = IndicatorBatchState("BTC", "USDT", "1m", span)
    if populated:
        price = Money.of(100, "USDT")
        state = advance_indicator_batch(
            state,
            (
                IndicatorBatchInput(
                    start,
                    BatchAction.ACCEPT,
                    "BTC",
                    "USDT",
                    "1m",
                    price,
                    Money.of(101, "USDT"),
                    Money.of(99, "USDT"),
                ),
            ),
            output_indices=(),
            rounding=FLOOR,
        ).state
        first_reset = start + span
    else:
        first_reset = start
    inputs = tuple(
        IndicatorBatchInput(
            first_reset + index * span,
            BatchAction.RESET,
            "BTC",
            "USDT",
            "1m",
        )
        for index in range(batch_size)
    )
    output_sets = ((), (0,), tuple(range(batch_size)))
    for output_indices in output_sets:
        result = advance_indicator_batch(
            state,
            inputs,
            output_indices=output_indices,
            rounding=FLOOR,
        )
        assert result == reset_indicator_batch(
            state, tuple(i.open_at for i in inputs), output_indices=output_indices
        )
        assert result.state == IndicatorBatchState(
            "BTC",
            "USDT",
            "1m",
            span,
            last_open=inputs[-1].open_at,
        )
        assert result.outputs == tuple((index, (None,) * 5) for index in output_indices)


def test_reset_batch_matches_mature_transition_and_rejects_bad_bounds() -> None:
    span = timedelta(minutes=1)
    start = datetime(2026, 10, 10, tzinfo=UTC)
    price = Money.of(100, "USDT")
    state = IndicatorBatchState("BTC", "USDT", "1m", span)
    for offset in range(0, 208, 16):
        accepted = tuple(
            IndicatorBatchInput(
                start + index * span,
                BatchAction.ACCEPT,
                "BTC",
                "USDT",
                "1m",
                price,
                Money.of(101, "USDT"),
                Money.of(99, "USDT"),
            )
            for index in range(offset, offset + 16)
        )
        state = advance_indicator_batch(state, accepted, output_indices=(), rounding=FLOOR).state
    assert state.accepted_count == 208
    opens = tuple(start + (208 + index) * span for index in range(16))
    resets = tuple(
        IndicatorBatchInput(moment, BatchAction.RESET, "BTC", "USDT", "1m") for moment in opens
    )
    expected = advance_indicator_batch(
        state,
        resets,
        output_indices=(0, 7, 15),
        rounding=FLOOR,
    )
    assert reset_indicator_batch(state, opens, output_indices=(0, 7, 15)) == expected
    invalid = (
        (),
        (*opens, opens[-1] + span),
        (opens[0], opens[0] + 2 * span),
        (opens[0].replace(tzinfo=None),),
    )
    for moments in invalid:
        with pytest.raises(InvalidInputTypeError):
            reset_indicator_batch(state, moments, output_indices=())
    with pytest.raises(InvalidInputTypeError):
        reset_indicator_batch(state, opens, output_indices=(True,))


def test_warm_gain_loss_validation_handles_up_down_flat_and_hold() -> None:
    state = IndicatorBatchState("BTC", "USDT", "1m", timedelta(minutes=1))
    start = datetime(2026, 10, 10, tzinfo=UTC)
    prices = [
        Money.of(text, "USDT")
        for text in (
            "100.000000000000000001",
            "100.000000000000000002",
            "100.000000000000000001",
            "100.000000000000000001",
        )
    ]
    inputs = tuple(
        IndicatorBatchInput(
            start + timedelta(minutes=index),
            BatchAction.ACCEPT,
            "BTC",
            "USDT",
            "1m",
            price,
            price + Money.of(1, "USDT"),
            price - Money.of(1, "USDT"),
        )
        for index, price in enumerate(prices)
    )
    state = advance_indicator_batch(state, inputs, output_indices=(), rounding=FLOOR).state
    zero, tick = Money.of(0, "USDT"), Money.of("0.000000000000000001", "USDT")
    assert state.averages[3].pending == (tick, zero, zero)
    assert state.averages[4].pending == (zero, tick, zero)
    held = advance_indicator_batch(
        state,
        (IndicatorBatchInput(start + timedelta(minutes=4), BatchAction.HOLD, "BTC", "USDT", "1m"),),
        output_indices=(),
        rounding=FLOOR,
    ).state
    assert held.accepted_count == state.accepted_count
    assert held.averages == state.averages
    invalid = list(state.averages)
    invalid[4] = AverageState(pending=(tick, tick, zero))
    with pytest.raises(InvalidInputTypeError, match="both be positive"):
        replace(state, averages=tuple(invalid))
    invalid_range = list(state.averages)
    invalid_range[5] = AverageState(pending=(zero, Money.of(2, "USDT"), Money.of(2, "USDT")))
    with pytest.raises(InvalidInputTypeError, match="true range is below gain plus loss"):
        replace(state, averages=tuple(invalid_range))


def test_mature_wilder_gain_and_loss_can_both_be_positive() -> None:
    state = IndicatorBatchState("BTC", "USDT", "1m", timedelta(minutes=1))
    start = datetime(2026, 10, 10, tzinfo=UTC)
    prices = [Money.of(100 + index % 2, "USDT") for index in range(16)]
    inputs = tuple(
        IndicatorBatchInput(
            start + timedelta(minutes=index),
            BatchAction.ACCEPT,
            "BTC",
            "USDT",
            "1m",
            price,
            price + Money.of(1, "USDT"),
            price - Money.of(1, "USDT"),
        )
        for index, price in enumerate(prices)
    )
    state = advance_indicator_batch(state, inputs, output_indices=(), rounding=FLOOR).state
    assert state.accepted_count == 16
    assert state.averages[3].value is not None and state.averages[4].value is not None
    assert state.averages[3].value > Money.of(0, "USDT")
    assert state.averages[4].value > Money.of(0, "USDT")
    lower_bound = state.averages[3].value + state.averages[4].value
    averages = list(state.averages)
    averages[5] = AverageState(value=lower_bound)
    boundary = replace(state, averages=tuple(averages))
    assert boundary.averages[5].value == lower_bound
    averages[5] = AverageState(value=lower_bound - Money.of("0.000000000000000001", "USDT"))
    with pytest.raises(InvalidInputTypeError, match="mature ATR is below"):
        replace(state, averages=tuple(averages))
    averages[3] = averages[4] = AverageState(value=Money.of("90000000000000000000", "USDT"))
    averages[5] = AverageState(value=Money.of("90000000000000000000", "USDT"))
    with pytest.raises(InvalidInputTypeError, match="mature ATR is below"):
        replace(state, averages=tuple(averages))
