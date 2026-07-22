from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tiewtrade.trading.entry_pair import EntryPairLifecycle
from tiewtrade.trading.spot_policy import SpotTradingPolicy


def policy(max_entries: int = 10) -> SpotTradingPolicy:
    return SpotTradingPolicy(
        trading_capital_ratio=Decimal("0.80"),
        max_entries=max_entries,
    )


def test_one_entry_may_cross_month_to_complete_its_pair() -> None:
    lifecycle = EntryPairLifecycle(policy())
    lifecycle.record_fill(datetime(2026, 1, 31, 23, 55, tzinfo=UTC))

    assert lifecycle.can_enter(datetime(2026, 2, 1, tzinfo=UTC))


def test_completed_pair_blocks_remainder_then_cooldown_month() -> None:
    lifecycle = EntryPairLifecycle(policy())
    lifecycle.record_fill(datetime(2026, 1, 10, tzinfo=UTC))
    lifecycle.record_fill(datetime(2026, 1, 20, tzinfo=UTC))

    assert not lifecycle.can_enter(datetime(2026, 1, 25, tzinfo=UTC))
    assert not lifecycle.can_enter(datetime(2026, 2, 15, tzinfo=UTC))
    assert lifecycle.can_enter(datetime(2026, 3, 1, tzinfo=UTC))


def test_entry_pair_stops_at_configured_maximum() -> None:
    lifecycle = EntryPairLifecycle(policy(4))
    for pair_start_month in (1, 3):
        lifecycle.record_fill(datetime(2026, pair_start_month, 1, tzinfo=UTC))
        lifecycle.record_fill(datetime(2026, pair_start_month, 2, tzinfo=UTC))

    assert not lifecycle.can_enter(datetime(2026, 5, 1, tzinfo=UTC))


def test_entry_pair_requires_utc_timestamp() -> None:
    lifecycle = EntryPairLifecycle(policy())

    with pytest.raises(ValueError, match="UTC"):
        lifecycle.can_enter(datetime(2026, 1, 1))


def test_entry_pair_resets_after_basket_closes() -> None:
    lifecycle = EntryPairLifecycle(policy())
    lifecycle.record_fill(datetime(2026, 1, 10, tzinfo=UTC))
    lifecycle.record_fill(datetime(2026, 1, 20, tzinfo=UTC))

    lifecycle.reset()

    assert lifecycle.entry_count == 0
    assert lifecycle.can_enter(datetime(2026, 1, 25, tzinfo=UTC))
