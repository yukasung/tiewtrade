from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import UUID

import pytest

from tiewtrade.paper.session_config import PaperSpotSessionConfig

SESSION_ID = UUID("00000000-0000-0000-0000-000000000010")
ACCOUNT_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_config(**overrides: object) -> PaperSpotSessionConfig:
    values: dict[str, object] = {
        "session_id": SESSION_ID,
        "account_profile_id": ACCOUNT_PROFILE_ID,
        "preset_version": "rsi-step-grid-v1",
        "available_capital": Decimal("1000"),
        "fee_rate": Decimal("0.001"),
        "slippage_bps": Decimal("2"),
    }
    values.update(overrides)
    return PaperSpotSessionConfig(**values)  # type: ignore[arg-type]


def test_paper_session_configuration_is_immutable() -> None:
    config = make_config()

    with pytest.raises(FrozenInstanceError):
        config.available_capital = Decimal("2000")  # type: ignore[misc]


@pytest.mark.parametrize("capital", [Decimal("0"), Decimal("-1")])
def test_paper_session_requires_positive_capital(capital: Decimal) -> None:
    with pytest.raises(ValueError, match="available_capital"):
        make_config(available_capital=capital)


@pytest.mark.parametrize(
    ("fee_rate", "slippage_bps"),
    [(Decimal("-0.001"), Decimal("0")), (Decimal("0"), Decimal("-1"))],
)
def test_paper_session_rejects_negative_execution_costs(
    fee_rate: Decimal, slippage_bps: Decimal
) -> None:
    with pytest.raises(ValueError):
        make_config(fee_rate=fee_rate, slippage_bps=slippage_bps)
