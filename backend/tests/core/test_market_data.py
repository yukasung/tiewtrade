from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiewtrade.core import market_data
from tiewtrade.core.money import Money, Quantity


def test_candle_contract_and_missing_half_open_slots() -> None:
    start = datetime(2026, 10, 7, tzinfo=UTC)
    tf = market_data.Timeframe.M1
    window = market_data.CandleWindow(start, start + 3 * tf.span)
    candle = market_data.Candle(
        base="BTC",
        quote="USDT",
        timeframe=tf,
        open_at=start,
        end_at=start + tf.span,
        open=Money.of("2", "USDT"),
        high=Money.of("3", "USDT"),
        low=Money.of("1", "USDT"),
        close=Money.of("2", "USDT"),
        volume=Quantity.of("0", "BTC"),
        finality=market_data.CandleFinality.UNCONFIRMED,
        observed_at=start,
    )
    assert candle.finality.value == "UNCONFIRMED"
    assert market_data.missing_windows(window, tf, [start]) == (
        market_data.CandleWindow(start + tf.span, window.end),
    )
    assert market_data.align_ceil(start + timedelta(seconds=1), tf) == start + tf.span


def test_window_rejects_naive_time() -> None:
    with pytest.raises(ValueError):
        market_data.CandleWindow(datetime(2026, 1, 1), datetime(2026, 1, 2))


@pytest.mark.parametrize("tf", list(market_data.Timeframe))
def test_initial_window_is_bounded_and_contains_current_slot(tf: market_data.Timeframe) -> None:
    now = datetime(2026, 10, 7, 10, 20, 15, tzinfo=UTC)
    window = market_data.initial_window(tf, now)
    slots = tuple(market_data.expected_opens(window, tf))
    assert 0 < len(slots) <= 1000
    assert slots[-1] == market_data.align_floor(now, tf)
    assert window.start >= now - timedelta(days=365)
    retained = market_data.retention_window(window, now)
    assert retained is not None
    assert retained.end == now


@pytest.mark.parametrize("finality", list(market_data.CandleFinality))
def test_units_decimal_precision_and_finality_are_preserved(
    finality: market_data.CandleFinality,
) -> None:
    now = datetime(2026, 10, 7, tzinfo=UTC)
    exact = Money.of("9007199254740993.12345678", "usdt")
    candle = market_data.Candle(
        "btc",
        "usdt",
        market_data.Timeframe.M1,
        now,
        now + timedelta(minutes=1),
        exact,
        exact,
        exact,
        exact,
        Quantity.of("0.12345678", "btc"),
        finality,
        now,
    )
    assert candle.base == "BTC"
    assert candle.quote == "USDT"
    assert candle.open == exact
    assert candle.finality is finality


def test_retention_uses_fixed_365_days_across_leap_year() -> None:
    now = datetime(2025, 2, 28, 12, tzinfo=UTC)
    window = market_data.CandleWindow(datetime(2024, 2, 28, tzinfo=UTC), now)
    retained = market_data.retention_window(window, now)
    assert retained is not None
    assert retained.start == datetime(2024, 2, 29, 12, tzinfo=UTC)
    assert retained.end - retained.start == timedelta(days=365)


@given(
    moment=st.datetimes(
        min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1), timezones=st.just(UTC)
    ),
    timeframe=st.sampled_from(list(market_data.Timeframe)),
)
def test_alignment_is_idempotent_and_contains_moment(
    moment: datetime, timeframe: market_data.Timeframe
) -> None:
    floor = market_data.align_floor(moment, timeframe)
    assert floor <= moment < floor + timeframe.span
    assert market_data.align_floor(floor, timeframe) == floor
    assert market_data.align_ceil(moment, timeframe) in (floor, floor + timeframe.span)


@given(timeframe=st.sampled_from(list(market_data.Timeframe)), slots=st.integers(1, 1000))
def test_expected_slots_exclude_right_boundary(
    timeframe: market_data.Timeframe, slots: int
) -> None:
    start = datetime(2026, 10, 7, tzinfo=UTC)
    end = start + slots * timeframe.span
    values = tuple(market_data.expected_opens(market_data.CandleWindow(start, end), timeframe))
    assert len(values) == slots
    assert values[0] == start and values[-1] + timeframe.span == end
    assert end not in values


@given(
    timeframe=st.sampled_from(list(market_data.Timeframe)),
    presence=st.lists(st.booleans(), min_size=1, max_size=40),
)
def test_gap_merge_is_exact_and_duplicate_presence_is_idempotent(
    timeframe: market_data.Timeframe, presence: list[bool]
) -> None:
    start = datetime(2026, 10, 7, tzinfo=UTC)
    window = market_data.CandleWindow(start, start + len(presence) * timeframe.span)
    present = [start + index * timeframe.span for index, value in enumerate(presence) if value]
    missing = {start + index * timeframe.span for index, value in enumerate(presence) if not value}
    gaps = market_data.missing_windows(window, timeframe, present)
    actual = {moment for gap in gaps for moment in market_data.expected_opens(gap, timeframe)}
    assert actual == missing
    assert market_data.missing_windows(window, timeframe, present + present) == gaps


def test_bounded_windows_preserve_unaligned_boundaries_and_slot_limit() -> None:
    origin = datetime(2026, 10, 7, tzinfo=UTC)
    start = origin + timedelta(seconds=1)
    end = origin + timedelta(minutes=2001, seconds=2)
    window = market_data.CandleWindow(start, end)
    chunks = tuple(market_data.bounded_windows(window, market_data.Timeframe.M1))
    assert chunks == (
        market_data.CandleWindow(start, origin + timedelta(minutes=1001)),
        market_data.CandleWindow(
            origin + timedelta(minutes=1001), origin + timedelta(minutes=2001)
        ),
        market_data.CandleWindow(origin + timedelta(minutes=2001), end),
    )
    assert all(
        len(tuple(market_data.expected_opens(chunk, market_data.Timeframe.M1))) <= 1000
        for chunk in chunks
    )


@pytest.mark.parametrize("timeframe", list(market_data.Timeframe))
def test_slot_count_matches_unaligned_half_open_iteration(
    timeframe: market_data.Timeframe,
) -> None:
    start = datetime(2026, 10, 7, tzinfo=UTC) + timedelta(microseconds=1)
    for end in (
        start + timedelta(microseconds=1),
        start + timeframe.span,
        start + 1001 * timeframe.span,
    ):
        window = market_data.CandleWindow(start, end)
        assert market_data.slot_count(window, timeframe) == len(
            tuple(market_data.expected_opens(window, timeframe))
        )


def test_retention_cutoff_normalizes_dst_reference_to_fixed_utc_duration() -> None:
    reference = datetime(2024, 3, 10, 8, tzinfo=ZoneInfo("America/New_York"))
    cutoff = market_data.retention_cutoff(reference)
    assert cutoff == datetime(2023, 3, 11, 12, tzinfo=UTC)
    assert reference.astimezone(UTC) - cutoff == timedelta(days=365)
