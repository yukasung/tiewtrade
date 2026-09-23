from collections.abc import Callable
from decimal import Decimal, setcontext

import pytest

from tiewtrade_core import DECIMAL_CONTEXT
from tiewtrade_core.market import LeverageBracket, LeverageBrackets

# Expected values in tests must be computed with the same precision as the core.
setcontext(DECIMAL_CONTEXT.copy())

# margin_gap(price, quantity, entry, wallet, other_mm=0, other_upnl=0) -> Decimal
MarginGap = Callable[..., Decimal]


@pytest.fixture(scope="session")
def brackets() -> LeverageBrackets:
    """Illustrative BTCUSDT-like brackets with continuous maintenance amounts.

    Tier 4 (2.5%, cum 16,300) matches the Binance documentation example. These are
    test fixtures, not live Binance values.
    """
    d = Decimal
    return LeverageBrackets(
        (
            LeverageBracket(1, d(0), d(50_000), d("0.004"), d(0), 125),
            LeverageBracket(2, d(50_000), d(250_000), d("0.005"), d(50), 100),
            LeverageBracket(3, d(250_000), d(1_000_000), d("0.01"), d(1_300), 50),
            LeverageBracket(4, d(1_000_000), d(10_000_000), d("0.025"), d(16_300), 20),
            LeverageBracket(5, d(10_000_000), d(10) ** 12, d("0.05"), d(266_300), 10),
        )
    )


@pytest.fixture(scope="session")
def margin_gap(brackets: LeverageBrackets) -> MarginGap:
    """Margin Balance - Maintenance Margin if this position's mark price were ``price``.

    Independent restatement of calculation spec §2.4 used to check liquidation prices;
    other positions are held constant through ``other_mm`` and ``other_upnl``.
    """

    def gap(
        price: Decimal,
        quantity: Decimal,
        entry: Decimal,
        wallet: Decimal,
        other_mm: Decimal = Decimal(0),
        other_upnl: Decimal = Decimal(0),
    ) -> Decimal:
        balance = wallet + other_upnl + quantity * (price - entry)
        maintenance = other_mm + brackets.maintenance_margin(abs(quantity) * price)
        return balance - maintenance

    return gap
