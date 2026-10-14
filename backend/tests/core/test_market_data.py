from datetime import UTC, datetime, timedelta, timezone

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
    assert window.start >= market_data.retention_cutoff(now, tf)
    retained = market_data.retention_window(window, now, tf)
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
    retained = market_data.retention_window(window, now, market_data.Timeframe.M1)
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
    following = market_data.next_open(floor, timeframe)
    assert floor <= moment < following
    assert market_data.align_floor(floor, timeframe) == floor
    assert market_data.align_ceil(moment, timeframe) in (floor, following)


@given(timeframe=st.sampled_from(list(market_data.Timeframe)), slots=st.integers(1, 1000))
def test_expected_slots_exclude_right_boundary(
    timeframe: market_data.Timeframe, slots: int
) -> None:
    start = market_data.align_floor(datetime(2026, 10, 7, tzinfo=UTC), timeframe)
    end = market_data.advance(start, timeframe, slots)
    values = tuple(market_data.expected_opens(market_data.CandleWindow(start, end), timeframe))
    assert len(values) == slots
    assert values[0] == start and market_data.next_open(values[-1], timeframe) == end
    assert end not in values


@given(
    timeframe=st.sampled_from(list(market_data.Timeframe)),
    presence=st.lists(st.booleans(), min_size=1, max_size=40),
)
def test_gap_merge_is_exact_and_duplicate_presence_is_idempotent(
    timeframe: market_data.Timeframe, presence: list[bool]
) -> None:
    start = market_data.align_floor(datetime(2026, 10, 7, tzinfo=UTC), timeframe)
    window = market_data.CandleWindow(start, market_data.advance(start, timeframe, len(presence)))
    present = [
        market_data.advance(start, timeframe, index)
        for index, value in enumerate(presence)
        if value
    ]
    missing = {
        market_data.advance(start, timeframe, index)
        for index, value in enumerate(presence)
        if not value
    }
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
    floor = market_data.align_floor(start, timeframe)
    for end in (
        start + timedelta(microseconds=1),
        market_data.advance(floor, timeframe, 1) + timedelta(microseconds=1),
        market_data.advance(floor, timeframe, 1001) + timedelta(microseconds=1),
    ):
        window = market_data.CandleWindow(start, end)
        assert market_data.slot_count(window, timeframe) == len(
            tuple(market_data.expected_opens(window, timeframe))
        )


def test_retention_cutoff_normalizes_offset_reference_to_fixed_utc_duration() -> None:
    reference = datetime(2024, 3, 10, 8, tzinfo=timezone(timedelta(hours=-4)))
    cutoff = market_data.retention_cutoff(reference, market_data.Timeframe.M1)
    assert cutoff == datetime(2023, 3, 11, 12, tzinfo=UTC)
    assert reference.astimezone(UTC) - cutoff == timedelta(days=365)


def test_week_and_month_use_utc_calendar_boundaries() -> None:
    sunday = datetime(2026, 11, 1, 23, 59, tzinfo=UTC)
    assert market_data.align_floor(sunday, market_data.Timeframe.W1) == datetime(
        2026, 10, 26, tzinfo=UTC
    )
    monday = datetime(2026, 11, 2, tzinfo=UTC)
    assert market_data.align_floor(monday, market_data.Timeframe.W1) == monday

    february = datetime(2028, 2, 17, tzinfo=UTC)
    opened = market_data.align_floor(february, market_data.Timeframe.MN1)
    assert opened == datetime(2028, 2, 1, tzinfo=UTC)
    assert market_data.next_open(opened, market_data.Timeframe.MN1) == datetime(
        2028, 3, 1, tzinfo=UTC
    )
    assert market_data.previous_open(opened, market_data.Timeframe.MN1) == datetime(
        2028, 1, 1, tzinfo=UTC
    )


def test_extended_retention_clamps_leap_day_by_calendar_year() -> None:
    now = datetime(2028, 2, 29, 12, 30, tzinfo=UTC)
    expected = datetime(2023, 2, 28, 12, 30, tzinfo=UTC)
    assert market_data.retention_cutoff(now, market_data.Timeframe.W1) == expected
    assert market_data.retention_cutoff(now, market_data.Timeframe.MN1) == expected
