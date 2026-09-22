from decimal import Decimal, setcontext

import pytest

from fasttrade_core import DECIMAL_CONTEXT
from fasttrade_core.market import LeverageBracket, LeverageBrackets

# Expected values in tests must be computed with the same precision as the core.
setcontext(DECIMAL_CONTEXT.copy())


def make_brackets() -> LeverageBrackets:
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
def brackets() -> LeverageBrackets:
    return make_brackets()
