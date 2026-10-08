import random
from datetime import UTC, datetime

import pytest

from tests.venues.binance_th.conftest import replying, transport_for
from tiewtrade.venues.binance_th.price_feed import BinanceThPriceFeed
from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport
from tiewtrade.venues.symbols import Symbol


@pytest.mark.asyncio
async def test_recovery_preserves_rest_trade_id_and_last_array_member() -> None:
    feed = BinanceThPriceFeed(
        transport_for(
            replying(
                '[{"id":99,"price":"1","time":1791331200000},'
                '{"id":1,"price":"2","time":1791331200001}]'
            )
        ),
        BinanceThStreamTransport(clock=lambda: datetime.now(UTC)),
    )
    quote = await feed.snapshot(Symbol("BTC", "USDT"))
    assert quote.trade_id == 1
    assert quote.trade_time.microsecond == 1000


class FinishedError(Exception):
    """Stop an otherwise infinite reconnect supervisor after the observed sleeps."""


@pytest.mark.parametrize(
    "durations,failures,expected",
    [
        ([None] * 8, ["SUBSCRIPTION_ACK_TIMEOUT"] * 8, [1, 2, 4, 8, 16, 30, 30, 30]),
        ([0, 59.999, 60, 0], ["VENUE_UNAVAILABLE"] * 4, [1, 2, 1, 2]),
        ([None, None], ["VENUE_PROTOCOL"] * 2, [30, 30]),
    ],
)
async def test_reconnect_jitter_cap_stability_reset_and_protocol_pause(
    monkeypatch: pytest.MonkeyPatch,
    durations: list[float | None],
    failures: list[str],
    expected: list[int],
) -> None:
    from types import SimpleNamespace

    from tiewtrade.venues.binance_th import price_feed as module
    from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected

    moment = 100.0
    generations: list[int] = []
    sleeps: list[float] = []
    ceilings: list[float] = []

    class Stream:
        async def connection(self, symbols: object, *, generation: int):  # type: ignore[no-untyped-def]
            nonlocal moment
            index = len(generations)
            generations.append(generation)
            duration = durations[index]
            if duration is not None:
                yield FeedConnected(generation)
                moment += duration
            yield FeedDisconnected(generation, failures[index])

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == len(expected):
            raise FinishedError

    def jitter(low: float, high: float) -> float:
        assert low == 0
        ceilings.append(high)
        return 0 if failures[len(sleeps)] == "VENUE_PROTOCOL" else high

    monkeypatch.setattr(
        module,
        "asyncio",
        SimpleNamespace(
            get_running_loop=lambda: SimpleNamespace(time=lambda: moment),
            sleep=sleep,
        ),
    )
    monkeypatch.setattr(random, "uniform", jitter)
    feed = BinanceThPriceFeed(transport_for(replying("[]")), Stream())  # type: ignore[arg-type]
    with pytest.raises(FinishedError):
        async for _ in feed.events((Symbol("BTC", "USDT"),)):
            pass
    assert sleeps == expected
    assert generations == list(range(1, len(expected) + 1))
    assert all(ceiling <= 30 for ceiling in ceilings)


@pytest.mark.parametrize("minimum,jitter,expected", [(90, 1, 90), (120, 0, 120), (0, 1, 1)])
async def test_reconnect_waits_for_handshake_retry_after_minimum(
    monkeypatch: pytest.MonkeyPatch, minimum: int, jitter: int, expected: int
) -> None:
    from datetime import timedelta
    from types import SimpleNamespace

    from tiewtrade.venues.binance_th import price_feed as module
    from tiewtrade.venues.price_streams import FeedDisconnected

    sleeps: list[float] = []

    class Stream:
        async def connection(self, symbols: object, *, generation: int):  # type: ignore[no-untyped-def]
            yield FeedDisconnected(generation, "VENUE_RATE_LIMITED", timedelta(seconds=minimum))

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        raise FinishedError

    monkeypatch.setattr(module, "asyncio", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(random, "uniform", lambda low, high: jitter)
    feed = BinanceThPriceFeed(transport_for(replying("[]")), Stream())  # type: ignore[arg-type]
    with pytest.raises(FinishedError):
        async for _ in feed.events((Symbol("BTC", "USDT"),)):
            pass
    assert sleeps == [expected]
