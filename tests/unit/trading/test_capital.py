from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from tiewtrade.trading.capital import SpotCapitalPlan
from tiewtrade.trading.spot_policy import SpotTradingPolicy
from tiewtrade.trading.symbol_rules import SymbolRules


def test_spot_capital_uses_form_policy_to_allocate_equal_entries() -> None:
    policy = SpotTradingPolicy(
        trading_capital_ratio=Decimal("0.75"),
        max_entries=12,
    )
    plan = SpotCapitalPlan.from_available(Decimal("1000"), policy)

    assert plan.trading_capital == Decimal("750")
    assert plan.reserve == Decimal("250")
    assert plan.entry_notional == Decimal("62.5")


def test_spot_trading_policy_is_immutable() -> None:
    policy = SpotTradingPolicy(
        trading_capital_ratio=Decimal("0.80"),
        max_entries=10,
    )

    with pytest.raises(FrozenInstanceError):
        policy.max_entries = 12  # type: ignore[misc]


@pytest.mark.parametrize(
    "ratio",
    [Decimal("-0.1"), Decimal("0"), Decimal("1"), Decimal("1.1")],
)
def test_spot_trading_policy_rejects_invalid_ratio(ratio: Decimal) -> None:
    with pytest.raises(ValueError, match="trading_capital_ratio"):
        SpotTradingPolicy(trading_capital_ratio=ratio, max_entries=10)


@pytest.mark.parametrize("max_entries", [1, 3, 22])
def test_spot_trading_policy_requires_even_entries_between_two_and_twenty(
    max_entries: int,
) -> None:
    with pytest.raises(ValueError, match="max_entries"):
        SpotTradingPolicy(
            trading_capital_ratio=Decimal("0.80"),
            max_entries=max_entries,
        )


def test_spot_capital_requires_positive_available_capital() -> None:
    policy = SpotTradingPolicy(
        trading_capital_ratio=Decimal("0.80"),
        max_entries=10,
    )
    with pytest.raises(ValueError, match="available capital"):
        SpotCapitalPlan.from_available(Decimal("0"), policy)


def test_symbol_rules_round_quantity_and_price_down() -> None:
    rules = SymbolRules(
        tick_size=Decimal("0.10"),
        step_size=Decimal("0.001"),
        min_notional=Decimal("5"),
    )

    assert rules.floor_price(Decimal("101.29")) == Decimal("101.20")
    assert rules.floor_quantity(Decimal("0.1239")) == Decimal("0.123")


def test_symbol_rules_require_positive_exchange_filters() -> None:
    with pytest.raises(ValueError, match="tick_size"):
        SymbolRules(
            tick_size=Decimal("0"),
            step_size=Decimal("0.001"),
            min_notional=Decimal("5"),
        )
