from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from typing import cast
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.infra.market_data.test_chart_preview import observation
from tiewtrade.core.candle_preview import CandleObservation, Progress, compare
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.market_data.candle_preview import PreviewLease
from tiewtrade.infra.realtime.notifications import RedisNotifications
from tiewtrade.services.market_data import candle_realtime
from tiewtrade.services.market_data.candle_realtime import (
    SERIES,
    CandleConflictError,
    CandleSupervisor,
)
from tiewtrade.venues.candle_streams import FeedCandle
from tiewtrade.venues.fake import FakeCandleFeed


def supervisor() -> CandleSupervisor:
    # These state-machine checks never invoke persistence or notification methods.
    from sqlalchemy.ext.asyncio import AsyncEngine

    result = CandleSupervisor(
        cast(AsyncEngine, None), FakeCandleFeed(()), cast(RedisNotifications, None)
    )
    result.epoch = 1
    return result


async def test_bootstrap_commits_each_series_before_marking_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = supervisor()
    state.lease = PreviewLease(uuid4(), 1)
    calls: list[object] = []
    sessions = 0
    completed = False

    class Session:
        async def execute(self, statement: str) -> None:
            assert statement.startswith("SET LOCAL")

    @asynccontextmanager
    async def session(_engine: object) -> AsyncIterator[Session]:
        nonlocal sessions
        sessions += 1
        yield Session()

    async def bootstrap(_session: object, _lease: PreviewLease, series: object) -> None:
        calls.append(series)

    async def complete(_session: object, _lease: PreviewLease) -> None:
        nonlocal completed
        completed = True

    monkeypatch.setattr(candle_realtime, "market_data_session", session)
    monkeypatch.setattr(candle_realtime, "bootstrap_series", bootstrap)
    monkeypatch.setattr(candle_realtime, "complete_bootstrap", complete)

    await state._bootstrap(1)

    assert calls == list(SERIES)
    assert sessions == len(SERIES) + 1
    assert completed is True


@given(st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=100))
def test_dominated_and_duplicate_permutations_never_replace_the_newest(counts: list[int]) -> None:
    state = supervisor()
    original = observation()
    maximum = max(counts)
    for count in counts + counts:
        incoming = replace(
            original,
            trade_count=count,
            first_trade_id=1,
            last_trade_id=count,
            candle=replace(original.candle, volume=Quantity.of(count, "BTC")),
        )
        state.observe(FeedCandle(1, incoming))
    row, revision = next(iter(state.rows.values()))
    assert row.trade_count == maximum
    assert len(state.rows) == len(state.dirty) == 1
    prior_revision = revision
    state.observe(FeedCandle(1, row))
    assert next(iter(state.rows.values()))[1] == prior_revision


def test_conflicting_prices_never_use_event_time_as_a_tiebreaker() -> None:
    state = supervisor()
    original = observation()
    state.observe(FeedCandle(1, original))
    conflicting = replace(
        original,
        event_at=original.event_at + timedelta(seconds=1),
        candle=replace(original.candle, close=Money.of(101, "USDT")),
    )
    assert compare(original, conflicting) is Progress.CONFLICT
    with pytest.raises(CandleConflictError):
        state.observe(FeedCandle(1, conflicting))
    assert next(iter(state.rows.values()))[0] == original


def test_old_epoch_and_old_candle_cannot_change_the_current_slot() -> None:
    state = supervisor()
    original = observation()
    state.observe(FeedCandle(1, original))
    state.observe(FeedCandle(0, replace(original, trade_count=2, last_trade_id=2)))
    earlier = replace(
        original.candle,
        open_at=original.candle.open_at - timedelta(hours=1),
        end_at=original.candle.end_at - timedelta(hours=1),
    )
    state.observe(FeedCandle(1, replace(original, candle=earlier)))
    assert list(state.rows.values()) == [(original, 1)]


def test_skipped_intervals_coalesce_one_ended_demand() -> None:
    state = supervisor()
    original = observation()
    state.observe(FeedCandle(1, original))
    next_candle = replace(
        original.candle,
        open_at=original.candle.open_at + timedelta(hours=3),
        end_at=original.candle.end_at + timedelta(hours=3),
    )
    state.observe(FeedCandle(1, replace(original, candle=next_candle)))
    demand = next(iter(state.demands.values()))
    assert demand.start == original.candle.open_at and demand.end == next_candle.open_at
    assert len(state.rows) == len(state.demands) == 1


def empty_observation() -> CandleObservation:
    original = observation()
    return replace(
        original,
        trade_count=0,
        first_trade_id=-1,
        last_trade_id=-1,
        candle=replace(original.candle, volume=Quantity.of(0, "BTC")),
        closed_hint=False,
    )


def test_first_trade_establishes_ohlc_and_late_empty_cannot_replace_it() -> None:
    state = supervisor()
    empty = empty_observation()
    first = replace(
        observation(),
        candle=replace(
            observation().candle,
            open=Money.of(101, "USDT"),
            high=Money.of(101, "USDT"),
            low=Money.of(101, "USDT"),
            close=Money.of(101, "USDT"),
        ),
    )
    assert compare(empty, first) is Progress.NEWER
    assert compare(first, empty) is Progress.OLDER
    state.observe(FeedCandle(1, empty))
    state.observe(FeedCandle(1, first))
    assert next(iter(state.rows.values())) == (first, 2)
    state.observe(FeedCandle(1, replace(empty, event_at=first.event_at + timedelta(seconds=2))))
    state.observe(FeedCandle(1, first))
    assert next(iter(state.rows.values())) == (first, 2)


@pytest.mark.parametrize("fault", ["first-id", "last-id", "volume", "closed"])
def test_malformed_or_closed_empty_does_not_bypass_conflict(fault: str) -> None:
    empty = empty_observation()
    if fault == "first-id":
        empty = replace(empty, first_trade_id=1)
    elif fault == "last-id":
        empty = replace(empty, last_trade_id=1)
    elif fault == "volume":
        empty = replace(empty, candle=replace(empty.candle, volume=Quantity.of(1, "BTC")))
    else:
        empty = replace(empty, closed_hint=True)
    first = observation()
    assert compare(empty, first) is Progress.CONFLICT
    assert compare(first, empty) is Progress.CONFLICT


@given(st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=80))
def test_empty_and_trade_permutations_preserve_the_cumulative_head(counts: list[int]) -> None:
    state = supervisor()
    empty = empty_observation()
    state.observe(FeedCandle(1, empty))
    for count in counts:
        incoming = (
            empty
            if count == 0
            else replace(
                observation(),
                trade_count=count,
                first_trade_id=1,
                last_trade_id=count,
                candle=replace(observation().candle, volume=Quantity.of(count, "BTC")),
            )
        )
        state.observe(FeedCandle(1, incoming))
    assert next(iter(state.rows.values()))[0].trade_count == max(counts)
