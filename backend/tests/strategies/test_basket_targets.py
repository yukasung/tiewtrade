"""Independent precision boundaries for weighted shared targets; no floats."""

from collections.abc import Sequence

import pytest

from tiewtrade.core.money import Money, MoneyError, Quantity, basket_take_profit


def m(value: str, currency: str = "USDT") -> Money:
    return Money.of(value, currency)


def q(value: str, asset: str = "BTC") -> Quantity:
    return Quantity.of(value, asset)


@pytest.mark.parametrize("size", ["0.000000000000000001", "10000000000000000000"])
def test_weighted_products_do_not_round_or_overflow_before_final_target(size: str) -> None:
    assert basket_take_profit(((m("100"), q(size)),), m("2"), m("0.01")) == m("106")


def test_fractional_atr_tick_floor_and_partial_split_preserve_the_same_target() -> None:
    whole = ((m("100.01"), q("0.1")), (m("100.03"), q("0.2")))
    split = ((m("100.01"), q("0.1")), (m("100.03"), q("0.1")), (m("100.03"), q("0.1")))
    for entries in (whole, split):
        assert basket_take_profit(entries, m("0.333333333333333333"), m("0.01")) == m("101.02")
        assert basket_take_profit(entries, m("0.333333333333333333"), m("0.05")) == m("101")
        assert basket_take_profit(
            entries, m("0.333333333333333333"), m("0.01"), held=m("99.99")
        ) == m("99.99")


@pytest.mark.parametrize(
    "entries,atr,tick,held",
    [
        ((), m("2"), m("0.01"), None),
        (((m("0"), q("1")),), m("2"), m("0.01"), None),
        (((m("100"), q("0")),), m("2"), m("0.01"), None),
        (((m("100"), q("1")),), m("-1"), m("0.01"), None),
        (((m("100"), q("1")),), m("2"), m("0"), None),
        (((m("100"), q("1")),), m("2"), m("0.01"), m("0")),
        (((m("100", "USD"), q("1")),), m("2"), m("0.01"), None),
        (((m("100"), q("1")),), m("2", "USD"), m("0.01"), None),
        (((m("100"), q("1")),), m("2"), m("0.01"), m("100", "USD")),
        (((m("100"), q("1")), (m("100"), q("1", "ETH"))), m("2"), m("0.01"), None),
        (((m("0.1"), q("1")),), m("0"), m("1"), None),
        (((m("99999999999999999999"), q("1")),), m("1"), m("1"), None),
    ],
)
def test_invalid_units_zero_values_and_final_storage_overflow_fail_closed(
    entries: Sequence[tuple[Money, Quantity]],
    atr: Money,
    tick: Money,
    held: Money | None,
) -> None:
    with pytest.raises(MoneyError):
        basket_take_profit(entries, atr, tick, held=held)


def test_execution_cost_ratios_survive_partial_fills_fees_and_reduction() -> None:
    # First order fills 1 at 66.66 and 2 at 66.67; second fills 1 at
    # 33.34 and 2 at 33.33. Per-entry averages repeat, but combined cost is 50.
    entries = ((m("66.666666666666666666"), q("3")), (m("33.333333333333333333"), q("3")))
    costs = ((m("200"), q("3")), (m("100"), q("3")))
    assert basket_take_profit(entries, m("1"), m("0.01"), held=m("69.66"), entry_costs=costs) == m(
        "53"
    )
    net = tuple((price, q("2.997")) for price, _ in entries)
    assert basket_take_profit(net, m("1"), m("0.01"), entry_costs=costs) == m("53")
    reduced = ((entries[0][0], q("1.5")), entries[1])
    assert basket_take_profit(reduced, m("1"), m("0.01"), entry_costs=costs) == m("47.44")
    assert basket_take_profit(entries, m("1"), m("0.01"), held=m("52.99"), entry_costs=costs) == m(
        "52.99"
    )


@pytest.mark.parametrize(
    "costs",
    [
        (),
        ((m("0"), q("3")),),
        ((m("100"), q("0")),),
        ((m("100", "USD"), q("3")),),
        ((m("100"), q("3", "ETH")),),
    ],
)
def test_invalid_execution_cost_basis_is_rejected(costs: Sequence[tuple[Money, Quantity]]) -> None:
    with pytest.raises(MoneyError):
        basket_take_profit(((m("33"), q("3")),), m("1"), m("0.01"), entry_costs=costs)
