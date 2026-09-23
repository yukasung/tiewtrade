from decimal import Decimal as D

import pytest

from tiewtrade_core.market import (
    FilterViolation,
    LeverageBracket,
    LeverageBrackets,
    OrderSide,
    Rounding,
    SymbolFilters,
    round_to_increment,
)


@pytest.mark.parametrize(
    ("value", "increment", "rounding", "expected"),
    [
        (D("100.37"), D("0.1"), Rounding.DOWN, D("100.3")),
        (D("100.37"), D("0.1"), Rounding.UP, D("100.4")),
        (D("100.30"), D("0.1"), Rounding.UP, D("100.3")),
        (D("101.26"), D("0.5"), Rounding.DOWN, D("101.0")),
        (D("101.26"), D("0.5"), Rounding.UP, D("101.5")),
        (D("0.0012345"), D("0.001"), Rounding.DOWN, D("0.001")),
    ],
)
def test_round_to_increment(value: D, increment: D, rounding: Rounding, expected: D) -> None:
    assert round_to_increment(value, increment, rounding) == expected


def test_round_to_increment_rejects_non_positive_increment() -> None:
    with pytest.raises(ValueError, match="positive"):
        round_to_increment(D(1), D(0), Rounding.DOWN)


FILTERS = SymbolFilters(
    tick_size=D("0.1"),
    step_size=D("0.001"),
    min_qty=D("0.001"),
    max_qty=D(1000),
    min_notional=D(100),
)


def test_valid_order_has_no_violations() -> None:
    assert FILTERS.violations(D("0.002"), D("60000.0")) == []


@pytest.mark.parametrize(
    ("quantity", "price", "expected"),
    [
        (D("0.002"), D("60000.05"), [FilterViolation.TICK]),
        (D("0.0025"), D("60000.0"), [FilterViolation.STEP]),
        (D("0.000"), D("60000.0"), [FilterViolation.MIN_QTY, FilterViolation.MIN_NOTIONAL]),
        (D("1001"), D("60000.0"), [FilterViolation.MAX_QTY]),
        (D("0.001"), D("50000.0"), [FilterViolation.MIN_NOTIONAL]),
    ],
)
def test_filter_violations(quantity: D, price: D, expected: list[FilterViolation]) -> None:
    assert FILTERS.violations(quantity, price) == expected


def test_order_side_sign() -> None:
    assert OrderSide.BUY.sign == 1
    assert OrderSide.SELL.sign == -1


def test_bracket_lookup_uses_floor_inclusive_cap_exclusive(brackets: LeverageBrackets) -> None:
    assert brackets.for_notional(D(0)).bracket == 1
    assert brackets.for_notional(D("49999.99")).bracket == 1
    assert brackets.for_notional(D(50_000)).bracket == 2
    assert brackets.for_notional(D(10) ** 15).bracket == 5  # above the last cap


def test_maintenance_margin_matches_binance_documentation_example(
    brackets: LeverageBrackets,
) -> None:
    # Binance FAQ: 3,500,032.458 x 2.50% - 16,300 = 71,200.81144. Exact arithmetic gives
    # 71,200.81145; the FAQ's notional is most likely rounded from a longer value, so the
    # last digit is confirmed only by golden tests from real account data (C-02).
    assert brackets.maintenance_margin(D("3500032.458")) == D("71200.81145")


def test_maintenance_margin_is_continuous_across_bracket_boundaries(
    brackets: LeverageBrackets,
) -> None:
    for tier in brackets.tiers[1:]:
        below = brackets.tiers[tier.bracket - 2]
        at_floor = tier.notional_floor
        from_below = at_floor * below.maintenance_margin_rate - below.maintenance_amount
        assert brackets.maintenance_margin(at_floor) == from_below


def test_brackets_must_be_contiguous() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        LeverageBrackets(
            (
                LeverageBracket(1, D(0), D(100), D("0.01"), D(0), 50),
                LeverageBracket(2, D(200), D(300), D("0.02"), D(1), 20),
            )
        )


def test_brackets_must_start_at_zero() -> None:
    with pytest.raises(ValueError, match="start at notional 0"):
        LeverageBrackets((LeverageBracket(1, D(10), D(100), D("0.01"), D(0), 50),))
