from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.trading.session_config import (
    MarketType,
    SessionConfig,
    TradeMode,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000010")
ACCOUNT_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_config(**overrides: object) -> SessionConfig:
    values: dict[str, object] = {
        "session_id": SESSION_ID,
        "account_profile_id": ACCOUNT_PROFILE_ID,
        "preset_version": "rsi-step-grid-v1",
        "market_type": MarketType.SPOT,
        "trade_mode": TradeMode.PAPER,
        "available_capital": Decimal("1000"),
        "fee_rate": Decimal("0.001"),
        "slippage_bps": Decimal("2"),
    }
    values.update(overrides)
    return SessionConfig(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("trade_mode", [TradeMode.PAPER, TradeMode.LIVE])
@pytest.mark.parametrize("market_type", [MarketType.SPOT, MarketType.FUTURES])
def test_session_configuration_supports_each_mode_and_market(
    trade_mode: TradeMode, market_type: MarketType
) -> None:
    config = make_config(trade_mode=trade_mode, market_type=market_type)

    assert config.trade_mode is trade_mode
    assert config.market_type is market_type


def test_session_configuration_is_immutable() -> None:
    config = make_config()

    with pytest.raises(FrozenInstanceError):
        config.available_capital = Decimal("2000")  # type: ignore[misc]


@pytest.mark.parametrize("capital", [Decimal("0"), Decimal("-1")])
def test_session_requires_positive_capital(capital: Decimal) -> None:
    with pytest.raises(ValueError, match="available_capital"):
        make_config(available_capital=capital)


@pytest.mark.parametrize(
    ("fee_rate", "slippage_bps"),
    [(Decimal("-0.001"), Decimal("0")), (Decimal("0"), Decimal("-1"))],
)
def test_session_rejects_negative_execution_costs(
    fee_rate: Decimal, slippage_bps: Decimal
) -> None:
    with pytest.raises(ValueError):
        make_config(fee_rate=fee_rate, slippage_bps=slippage_bps)


def test_live_configuration_is_only_data_and_does_not_start_execution() -> None:
    config = make_config(trade_mode=TradeMode.LIVE)

    assert config.trade_mode is TradeMode.LIVE
