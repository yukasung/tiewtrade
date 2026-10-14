from datetime import UTC, datetime

import pytest

from tiewtrade.core.timeframes import Timeframe, chart_display_start, retention_cutoff


@pytest.mark.parametrize(
    "now,expected",
    [
        (datetime(2024, 5, 31, 12, tzinfo=UTC), datetime(2024, 2, 29, 12, tzinfo=UTC)),
        (datetime(2025, 5, 31, 12, tzinfo=UTC), datetime(2025, 2, 28, 12, tzinfo=UTC)),
        (datetime(2026, 1, 31, 12, tzinfo=UTC), datetime(2025, 10, 31, 12, tzinfo=UTC)),
    ],
)
def test_three_calendar_months(now: datetime, expected: datetime) -> None:
    assert chart_display_start(now, Timeframe.M1) == expected
    assert retention_cutoff(now, Timeframe.M1) < expected


def test_daily_boundary_includes_intersecting_candle() -> None:
    assert chart_display_start(datetime(2026, 10, 14, 12, tzinfo=UTC), Timeframe.D1) == datetime(
        2026, 7, 14, tzinfo=UTC
    )
