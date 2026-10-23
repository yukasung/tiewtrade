import random
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest

from tests.venues.binance_th.test_candle_stream_mapping import SERIES, sample
from tests.venues.binance_th.test_price_feed import FinishedError
from tiewtrade.venues.binance_th import candle_feed as module
from tiewtrade.venues.binance_th.candle_feed import BinanceThCandleFeed
from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport, StreamFrame
from tiewtrade.venues.candle_streams import FeedCandle
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected


@pytest.mark.parametrize(
    "durations,failure,retry_after,expected",
    [
        ([None] * 8, "SUBSCRIPTION_ACK_TIMEOUT", None, [1, 2, 4, 8, 16, 30, 30, 30]),
        ([0, 59.999, 60, 0], "VENUE_UNAVAILABLE", None, [1, 2, 1, 2]),
        ([None, None], "VENUE_PROTOCOL", None, [30, 30]),
        ([None], "VENUE_RATE_LIMITED", 90, [90]),
        ([None], "VENUE_RATE_LIMITED", 120, [120]),
        ([None], "VENUE_RATE_LIMITED", 0, [1]),
    ],
)
async def test_candle_reconnect_backoff_stability_protocol_and_retry_after(
    monkeypatch: pytest.MonkeyPatch,
    durations: list[float | None],
    failure: str,
    retry_after: int | None,
    expected: list[int],
) -> None:
    moment = 100.0
    generations: list[int] = []
    closed: list[int] = []
    sleeps: list[float] = []
    ceilings: list[float] = []

    class Transport:
        async def frames(
            self,
            params: tuple[str, ...],
            *,
            generation: int,
            decode: Callable[[object, datetime], object],
        ) -> AsyncGenerator[StreamFrame | FeedConnected | FeedDisconnected, None]:
            nonlocal moment
            assert params == tuple(
                f"{s.base.lower()}{s.quote.lower()}@kline_{s.timeframe.value}" for s in SERIES
            )
            duration = durations[len(generations)]
            generations.append(generation)
            try:
                if duration is not None:
                    yield FeedConnected(generation)
                    moment += duration
                yield FeedDisconnected(
                    generation,
                    failure,
                    None if retry_after is None else timedelta(seconds=retry_after),
                )
            finally:
                closed.append(generation)

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == len(expected):
            raise FinishedError

    def jitter(low: float, high: float) -> float:
        assert low == 0
        ceilings.append(high)
        return 0 if failure == "VENUE_PROTOCOL" or retry_after == 120 else high

    monkeypatch.setattr(
        module,
        "asyncio",
        SimpleNamespace(get_running_loop=lambda: SimpleNamespace(time=lambda: moment), sleep=sleep),
    )
    monkeypatch.setattr(random, "uniform", jitter)
    feed = BinanceThCandleFeed(cast(BinanceThStreamTransport, Transport()))
    with pytest.raises(FinishedError):
        async for _ in feed.events(SERIES):
            pass
    assert sleeps == expected
    assert generations == closed == list(range(1, len(expected) + 1))
    assert all(ceiling <= 30 for ceiling in ceilings)


async def test_candle_feed_decodes_frames_and_closes_transport_on_consumer_exit() -> None:
    closed = False

    class Transport:
        async def frames(
            self,
            params: tuple[str, ...],
            *,
            generation: int,
            decode: Callable[[object, datetime], object],
        ) -> AsyncGenerator[StreamFrame | FeedConnected | FeedDisconnected, None]:
            nonlocal closed
            try:
                yield FeedConnected(generation)
                yield StreamFrame(generation, decode(sample(), datetime.now(UTC)))
            finally:
                closed = True

    feed = BinanceThCandleFeed(cast(BinanceThStreamTransport, Transport()))
    async with aclosing(feed.events(SERIES)) as events:
        assert await anext(events) == FeedConnected(1)
        event = await anext(events)
        assert isinstance(event, FeedCandle)
        assert event.generation == 1
        assert event.observation.candle.base == "BTC"
        assert not closed
    assert closed
