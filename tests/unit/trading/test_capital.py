from decimal import Decimal

import pytest

from tiewtrade.trading.capital import SpotCapitalPlan
from tiewtrade.trading.symbol_rules import SymbolRules


def test_spot_capital_uses_eighty_percent_and_ten_equal_entries() -> None:
    plan = SpotCapitalPlan.from_available(Decimal("1000"))

    assert plan.trading_capital == Decimal("800")
    assert plan.reserve == Decimal("200")
    assert plan.entry_notional == Decimal("80")


def test_spot_capital_requires_positive_available_capital() -> None:
    with pytest.raises(ValueError, match="available capital"):
        SpotCapitalPlan.from_available(Decimal("0"))


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
