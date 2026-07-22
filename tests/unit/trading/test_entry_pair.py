from datetime import UTC, datetime

import pytest

from tiewtrade.trading.entry_pair import EntryPairLifecycle


def test_one_entry_may_cross_month_to_complete_its_pair() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)
    lifecycle.record_fill(datetime(2026, 1, 31, 23, 55, tzinfo=UTC))

    assert lifecycle.can_enter(datetime(2026, 2, 1, tzinfo=UTC))


def test_completed_pair_blocks_remainder_then_cooldown_month() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)
    lifecycle.record_fill(datetime(2026, 1, 10, tzinfo=UTC))
    lifecycle.record_fill(datetime(2026, 1, 20, tzinfo=UTC))

    assert not lifecycle.can_enter(datetime(2026, 1, 25, tzinfo=UTC))
    assert not lifecycle.can_enter(datetime(2026, 2, 15, tzinfo=UTC))
    assert lifecycle.can_enter(datetime(2026, 3, 1, tzinfo=UTC))


def test_entry_pair_stops_at_ten_entries() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)
    for pair_start_month in (1, 3, 5, 7, 9):
        lifecycle.record_fill(datetime(2026, pair_start_month, 1, tzinfo=UTC))
        lifecycle.record_fill(datetime(2026, pair_start_month, 2, tzinfo=UTC))

    assert not lifecycle.can_enter(datetime(2026, 11, 1, tzinfo=UTC))


def test_entry_pair_configuration_cannot_exceed_ten_entries() -> None:
    with pytest.raises(ValueError, match="maximum entries"):
        EntryPairLifecycle(max_entries=11)


def test_entry_pair_requires_utc_timestamp() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)

    with pytest.raises(ValueError, match="UTC"):
        lifecycle.can_enter(datetime(2026, 1, 1))


def test_entry_pair_resets_after_basket_closes() -> None:
    lifecycle = EntryPairLifecycle(max_entries=10)
    lifecycle.record_fill(datetime(2026, 1, 10, tzinfo=UTC))
    lifecycle.record_fill(datetime(2026, 1, 20, tzinfo=UTC))

    lifecycle.reset()

    assert lifecycle.entry_count == 0
    assert lifecycle.can_enter(datetime(2026, 1, 25, tzinfo=UTC))
