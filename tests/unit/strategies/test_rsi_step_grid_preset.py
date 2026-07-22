from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from tiewtrade.strategies.rsi_step_grid.preset import RsiStepGridPreset


def test_preset_v1_matches_the_approved_product_parameters() -> None:
    preset = RsiStepGridPreset.v1()

    assert preset.version == "rsi-step-grid-v1"
    assert preset.rsi_period == 14
    assert preset.rsi_reset_threshold == Decimal("30")
    assert preset.rsi_entry_threshold == Decimal("50")
    assert preset.atr_period == 14
    assert preset.take_profit_atr_multiplier == Decimal("3")


def test_preset_is_immutable() -> None:
    preset = RsiStepGridPreset.v1()

    with pytest.raises(FrozenInstanceError):
        preset.rsi_period = 7  # type: ignore[misc]


def test_preset_rejects_overlapping_rsi_thresholds() -> None:
    with pytest.raises(ValueError, match="reset threshold"):
        RsiStepGridPreset(
            version="invalid",
            rsi_period=14,
            rsi_reset_threshold=Decimal("50"),
            rsi_entry_threshold=Decimal("50"),
            atr_period=14,
            take_profit_atr_multiplier=Decimal("3"),
        )


def test_preset_version_cannot_be_reused_with_different_parameters() -> None:
    with pytest.raises(ValueError, match="rsi-step-grid-v1 parameters"):
        RsiStepGridPreset(
            version="rsi-step-grid-v1",
            rsi_period=7,
            rsi_reset_threshold=Decimal("30"),
            rsi_entry_threshold=Decimal("50"),
            atr_period=14,
            take_profit_atr_multiplier=Decimal("3"),
        )
