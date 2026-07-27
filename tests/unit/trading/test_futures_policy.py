from dataclasses import replace
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


def test_v1_exposes_supported_leverage_bounds() -> None:
    assert FuturesTradingPolicy.V1_MINIMUM_LEVERAGE == 1
    assert FuturesTradingPolicy.V1_MAXIMUM_LEVERAGE == 5
    assert FuturesTradingPolicy.v1(leverage=1).leverage == 1
    assert FuturesTradingPolicy.v1(leverage=5).leverage == 5


@pytest.mark.parametrize(
    "leverage",
    [
        FuturesTradingPolicy.V1_MINIMUM_LEVERAGE - 1,
        FuturesTradingPolicy.V1_MAXIMUM_LEVERAGE + 1,
        1.5,
        True,
    ],
)
def test_v1_futures_policy_rejects_invalid_leverage(leverage: object) -> None:
    with pytest.raises(ValueError, match="leverage"):
        FuturesTradingPolicy.v1(leverage=leverage)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "field_name"),
    [
        ({"version": "paper-futures-v2"}, "version"),
        (
            {
                "trading_capital_ratio": Decimal("0.4"),
                "collateral_buffer_ratio": Decimal("0.6"),
            },
            "trading_capital_ratio",
        ),
        ({"maintenance_margin_rate": Decimal("0.006")}, "maintenance_margin_rate"),
    ],
)
def test_direct_constructor_rejects_altered_v1_system_policy(
    overrides: dict[str, object], field_name: str
) -> None:
    values: dict[str, object] = {
        "version": "paper-futures-v1",
        "leverage": 3,
        "trading_capital_ratio": Decimal("0.5"),
        "collateral_buffer_ratio": Decimal("0.5"),
        "maintenance_margin_rate": Decimal("0.005"),
        "margin_mode": MarginMode.CROSS,
        "position_mode": PositionMode.ONE_WAY,
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=field_name):
        FuturesTradingPolicy(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "field_name"),
    [
        ({"version": "paper-futures-v2"}, "version"),
        (
            {
                "trading_capital_ratio": Decimal("0.4"),
                "collateral_buffer_ratio": Decimal("0.6"),
            },
            "trading_capital_ratio",
        ),
        ({"maintenance_margin_rate": Decimal("0.006")}, "maintenance_margin_rate"),
    ],
)
def test_replace_rejects_altered_v1_system_policy(
    changes: dict[str, object], field_name: str
) -> None:
    policy = FuturesTradingPolicy.v1(leverage=3)

    with pytest.raises(ValueError, match=field_name):
        replace(policy, **changes)  # type: ignore[arg-type]
