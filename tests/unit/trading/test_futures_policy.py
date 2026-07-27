from decimal import Decimal

import pytest

from tiewtrade.trading.futures_policy import (
    FuturesTradingPolicy,
    MarginMode,
    PositionMode,
)


def test_v1_futures_policy_uses_approved_constants() -> None:
    policy = FuturesTradingPolicy.v1(leverage=3)

    assert policy.version == "paper-futures-v1"
    assert policy.leverage == 3
    assert policy.trading_capital_ratio == Decimal("0.5")
    assert policy.collateral_buffer_ratio == Decimal("0.5")
    assert policy.maintenance_margin_rate == Decimal("0.005")
    assert policy.margin_mode is MarginMode.CROSS
    assert policy.position_mode is PositionMode.ONE_WAY


@pytest.mark.parametrize("leverage", [0, 6, 1.5, True])
def test_v1_futures_policy_rejects_invalid_leverage(leverage: object) -> None:
    with pytest.raises(ValueError, match="leverage"):
        FuturesTradingPolicy.v1(leverage=leverage)  # type: ignore[arg-type]
