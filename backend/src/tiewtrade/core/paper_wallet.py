"""Pure Paper-wallet rules for F-13."""

from __future__ import annotations

from collections.abc import Iterable

from tiewtrade.core.money import Money

PAPER_CURRENCY = "USDT"
MINIMUM_INITIAL_CAPITAL = Money.of("1000", PAPER_CURRENCY)


class InitialCapitalTooSmallError(ValueError):
    code = "INITIAL_CAPITAL_TOO_SMALL"


def initial_capital(value: str) -> Money:
    """Parse an exact amount and enforce the approved strict lower bound."""
    capital = Money.of(value, PAPER_CURRENCY)
    if not capital > MINIMUM_INITIAL_CAPITAL:
        raise InitialCapitalTooSmallError("initial capital must be greater than 1000 USDT")
    return capital


def ledger_balance(entries: Iterable[Money]) -> Money:
    """Fold an episode ledger without float or ambient Decimal arithmetic."""
    total = Money.of("0", PAPER_CURRENCY)
    for entry in entries:
        total = total + entry
    return total
