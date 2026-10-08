import json
from datetime import UTC, datetime, timedelta

import pytest
from websockets.asyncio.server import serve

from tiewtrade.venues.binance_th.stream_transport import BinanceThStreamTransport
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedQuote
from tiewtrade.venues.symbols import Symbol


@pytest.mark.asyncio
async def test_ack_gates_quotes_and_close_reports_failure() -> None:
    async def server(socket: object) -> None:
        from websockets.asyncio.server import ServerConnection

        assert isinstance(socket, ServerConnection)
        request = json.loads(await socket.recv())
        trade = json.dumps(
            {
                "stream": "btcusdt@trade",
                "data": {"e": "trade", "s": "BTCUSDT", "t": 1, "p": "10", "T": 1791331200000},
            }
        )
        await socket.send(trade)
        await socket.send(json.dumps({"result": None, "id": request["id"]}))
        await socket.send(trade)
        await socket.close()

    async with serve(server, "127.0.0.1", 0) as upstream:
        port = upstream.sockets[0].getsockname()[1]
        transport = BinanceThStreamTransport(
            clock=lambda: datetime(2026, 10, 7, tzinfo=UTC),
            endpoint=f"ws://127.0.0.1:{port}/stream",
        )
        events = transport.connection((Symbol("BTC", "USDT"),), generation=4)
        assert isinstance(await anext(events), FeedConnected)
        assert isinstance(await anext(events), FeedQuote)
        failure = await anext(events)
        assert isinstance(failure, FeedDisconnected)
        await events.aclose()


@pytest.mark.asyncio
async def test_missing_ack_times_out_without_connected_or_recovery() -> None:
    async def server(socket: object) -> None:
        from websockets.asyncio.server import ServerConnection

        assert isinstance(socket, ServerConnection)
        await socket.wait_closed()

    async with serve(server, "127.0.0.1", 0) as upstream:
        port = upstream.sockets[0].getsockname()[1]
        transport = BinanceThStreamTransport(
            clock=lambda: datetime.now(UTC),
            endpoint=f"ws://127.0.0.1:{port}/stream",
            ack_timeout=timedelta(milliseconds=20),
        )
        events = transport.connection((Symbol("BTC", "USDT"),), generation=7)
        event = await anext(events)
        assert event == FeedDisconnected(7, "SUBSCRIPTION_ACK_TIMEOUT")
        await events.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["VENUE_PROTOCOL", "SUBSCRIPTION_ACK_TIMEOUT"])
async def test_protocol_failure_invalidates_before_peer_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    import asyncio

    from tiewtrade.venues.binance_th.stream_transport import _ControlBoundConnection

    release = asyncio.Event()
    close = _ControlBoundConnection.close

    async def delayed_close(
        socket: _ControlBoundConnection, code: int = 1000, reason: str = ""
    ) -> None:
        await release.wait()
        await close(socket, code, reason)

    monkeypatch.setattr(_ControlBoundConnection, "close", delayed_close)

    async def server(socket: object) -> None:
        from websockets.asyncio.server import ServerConnection

        assert isinstance(socket, ServerConnection)
        request = json.loads(await socket.recv())
        if failure == "VENUE_PROTOCOL":
            await socket.send(json.dumps({"result": None, "id": request["id"]}))
            await socket.send("{invalid json")
        await socket.wait_closed()

    async with serve(server, "127.0.0.1", 0) as upstream:
        port = upstream.sockets[0].getsockname()[1]
        transport = BinanceThStreamTransport(
            clock=lambda: datetime.now(UTC),
            endpoint=f"ws://127.0.0.1:{port}/stream",
            ack_timeout=timedelta(milliseconds=20),
        )
        events = transport.connection((Symbol("BTC", "USDT"),), generation=7)
        if failure == "VENUE_PROTOCOL":
            assert isinstance(await anext(events), FeedConnected)
        try:
            event = await asyncio.wait_for(anext(events), timeout=0.1)
            assert event == FeedDisconnected(7, failure)
        finally:
            release.set()
            await events.aclose()


@pytest.mark.asyncio
async def test_pongs_do_not_replace_missing_subscription_ack() -> None:
    import asyncio

    from websockets.asyncio.server import ServerConnection
    from websockets.exceptions import ConnectionClosed

    pongs: list[bool] = []

    async def server(socket: ServerConnection) -> None:
        await socket.recv()
        try:
            # Automatic pongs remain serviced by the single websockets reader.
            for _ in range(3):
                waiter = await socket.ping()
                await waiter
                pongs.append(True)
                await asyncio.sleep(0.005)
            await socket.wait_closed()
        except ConnectionClosed:
            pass

    async with serve(server, "127.0.0.1", 0) as upstream:
        port = upstream.sockets[0].getsockname()[1]
        transport = BinanceThStreamTransport(
            clock=lambda: datetime.now(UTC),
            endpoint=f"ws://127.0.0.1:{port}/stream",
            ack_timeout=timedelta(milliseconds=50),
        )
        events = transport.connection((Symbol("BTC", "USDT"),), generation=9)
        assert await anext(events) == FeedDisconnected(9, "SUBSCRIPTION_ACK_TIMEOUT")
        await events.aclose()
    assert pongs == [True, True, True]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,header,code,seconds",
    [
        (429, "90", "VENUE_RATE_LIMITED", 90),
        (418, "120", "VENUE_RATE_LIMITED", 120),
        (429, None, "VENUE_RATE_LIMITED", None),
        (418, "invalid", "VENUE_RATE_LIMITED", None),
        (429, "Wed, 07 Oct 2026 00:02:00 GMT", "VENUE_RATE_LIMITED", None),
        (418, "-1", "VENUE_RATE_LIMITED", None),
        (429, "999999999999999999999", "VENUE_PROTOCOL", None),
        (503, "90", "VENUE_UNAVAILABLE", None),
    ],
)
async def test_handshake_failure_preserves_rate_limit_minimum(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    header: str | None,
    code: str,
    seconds: int | None,
) -> None:
    from websockets.datastructures import Headers
    from websockets.exceptions import InvalidStatus
    from websockets.http11 import Response

    from tiewtrade.venues.binance_th import stream_transport as module

    headers = Headers() if header is None else Headers({"Retry-After": header})

    class RejectedHandshake:
        async def __aenter__(self) -> None:
            raise InvalidStatus(Response(status, "failure", headers))

        async def __aexit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr(module, "connect", lambda *args, **kwargs: RejectedHandshake())
    transport = BinanceThStreamTransport(clock=lambda: datetime(2026, 10, 7, tzinfo=UTC))
    events = [event async for event in transport.connection((Symbol("BTC", "USDT"),), generation=8)]
    assert len(events) == 1
    failure = events[0]
    assert isinstance(failure, FeedDisconnected)
    assert failure.failure_code == code
    assert failure.retry_after == (None if seconds is None else timedelta(seconds=seconds))
