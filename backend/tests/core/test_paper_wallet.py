"""Exact domain rules for F-13 Paper capital and ledger balances."""

import pytest

from tiewtrade.core.money import Money, MoneyError, UnitMismatchError
from tiewtrade.core.paper_wallet import InitialCapitalTooSmallError, initial_capital, ledger_balance


@pytest.mark.parametrize("value", ["0", "999.999999999999999999", "1000", "-1"])
def test_initial_capital_rejects_the_strict_lower_boundary(value: str) -> None:
    with pytest.raises(InitialCapitalTooSmallError):
        initial_capital(value)


@pytest.mark.parametrize("value", ["", "NaN", "Infinity", "1000.0000000000000000001"])
def test_initial_capital_uses_the_existing_money_contract(value: str) -> None:
    with pytest.raises(MoneyError):
        initial_capital(value)


def test_initial_capital_and_ledger_stay_exact() -> None:
    capital = initial_capital("1000.000000000000000001")
    assert capital.as_parts() == {"amount": "1000.000000000000000001", "currency": "USDT"}
    assert ledger_balance([capital, Money.of("0.000000000000000001", "USDT")]).as_parts() == {
        "amount": "1000.000000000000000002",
        "currency": "USDT",
    }


def test_ledger_rejects_a_different_currency() -> None:
    with pytest.raises(UnitMismatchError):
        ledger_balance([Money.of("1001", "USDT"), Money.of("1", "BTC")])
