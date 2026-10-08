"""Deterministic subscription boundary and connection-generation regression tests."""

import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from tiewtrade.venues.binance_th import stream_transport as module
from tiewtrade.venues.binance_th.stream_mapping import subscription_ack
from tiewtrade.venues.price_streams import FeedConnected, FeedDisconnected, FeedQuote
from tiewtrade.venues.symbols import Symbol

PAIRS = (Symbol("BTC", "USDT"),)
TRADE = json.dumps(
    {
        "stream": "btcusdt@trade",
        "data": {
            "e": "trade",
            "s": "BTCUSDT",
            "t": 1,
            "p": "10",
            "T": 1791331200000,
        },
    }
)


class Clock:
    def __init__(self) -> None:
        self.now = asyncio.get_running_loop().time()

    def time(self) -> float:
        return self.now


class Socket:
    def __init__(self, clock: Clock, frames: list[tuple[float, str]]) -> None:
        self.clock = clock
        self.frames = deque(frames)
        self.started_at = clock.now
        self.sent: list[str] = []
        self.closed = False
        self.send_delay = 0.0
        self.send_error = False
        self.block_send = False
        self.cancelled_send = False

    async def send(self, value: str) -> None:
        self.sent.append(value)
        self.clock.now += self.send_delay
        if self.send_error:
            raise OSError("synthetic send failure")
        if self.block_send:
            try:
                await asyncio.Future()
            finally:
                self.cancelled_send = True

    async def recv(self) -> str:
        if not self.frames:
            raise OSError("synthetic peer closure")
        elapsed, frame = self.frames.popleft()
        self.clock.now = self.started_at + elapsed
        return frame


def install(monkeypatch: pytest.MonkeyPatch, socket: Socket) -> module.BinanceThStreamTransport:
    @asynccontextmanager
    async def connect(*args: Any, **kwargs: Any) -> Any:
        assert kwargs["open_timeout"] == 10
        assert kwargs["close_timeout"] == 5
        assert kwargs["ping_interval"] == 10
        assert kwargs["ping_timeout"] == 5
        assert kwargs["max_queue"] == 16
        try:
            yield socket
        finally:
            socket.closed = True

    monkeypatch.setattr(module, "connect", connect)
    monkeypatch.setattr(
        module,
        "asyncio",
        SimpleNamespace(
            get_running_loop=lambda: socket.clock,
            timeout_at=asyncio.timeout_at,
        ),
    )
    return module.BinanceThStreamTransport(clock=lambda: datetime(2026, 10, 7, tzinfo=UTC))


@pytest.mark.parametrize("elapsed,connected", [(4.999, True), (5.0, False), (5.001, False)])
async def test_ack_boundary_timeout_wins_without_duplicate_transition(
    monkeypatch: pytest.MonkeyPatch,
    elapsed: float,
    connected: bool,
) -> None:
    socket = Socket(Clock(), [(elapsed, '{"result":null,"id":7}')])
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    first = await anext(events)
    assert first == (
        FeedConnected(7) if connected else FeedDisconnected(7, "SUBSCRIPTION_ACK_TIMEOUT")
    )
    if connected:
        assert await anext(events) == FeedDisconnected(7, "VENUE_UNAVAILABLE")
    with pytest.raises(StopAsyncIteration):
        await anext(events)
    assert socket.closed
    assert len(socket.sent) == 1


@pytest.mark.parametrize("frame", ['{"result":null,"id":6}', TRADE])
async def test_wrong_generation_and_pre_ack_trade_do_not_extend_deadline(
    monkeypatch: pytest.MonkeyPatch,
    frame: str,
) -> None:
    socket = Socket(Clock(), [(1, frame), (4.999, frame), (5, '{"result":null,"id":7}')])
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedDisconnected(7, "SUBSCRIPTION_ACK_TIMEOUT")
    with pytest.raises(StopAsyncIteration):
        await anext(events)


async def test_send_wait_is_included_in_subscription_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = Socket(Clock(), [(5, '{"result":null,"id":7}')])
    socket.send_delay = 5
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedDisconnected(7, "SUBSCRIPTION_ACK_TIMEOUT")
    await events.aclose()
    assert socket.closed


async def test_blocked_send_is_cancelled_by_total_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = Socket(Clock(), [])
    socket.block_send = True
    transport = install(monkeypatch, socket)
    transport._ack_timeout = timedelta(milliseconds=10)
    events = transport.connection(PAIRS, generation=7)
    assert await anext(events) == FeedDisconnected(7, "SUBSCRIPTION_ACK_TIMEOUT")
    assert socket.cancelled_send
    await events.aclose()
    assert socket.closed


async def test_send_error_invalidates_once(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = Socket(Clock(), [])
    socket.send_error = True
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedDisconnected(7, "VENUE_UNAVAILABLE")
    with pytest.raises(StopAsyncIteration):
        await anext(events)


async def test_duplicate_ack_does_not_repeat_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = Socket(
        Clock(), [(1, '{"result":null,"id":7}'), (2, '{"result":null,"id":7}'), (3, TRADE)]
    )
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedConnected(7)
    assert isinstance(await anext(events), FeedQuote)
    assert await anext(events) == FeedDisconnected(7, "VENUE_UNAVAILABLE")
    with pytest.raises(StopAsyncIteration):
        await anext(events)


async def test_oversized_trade_id_invalidates_without_emitting_a_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = json.loads(TRADE)
    frame["data"]["t"] = 2**63
    socket = Socket(Clock(), [(1, '{"result":null,"id":7}'), (2, json.dumps(frame))])
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedConnected(7)
    assert await anext(events) == FeedDisconnected(7, "VENUE_PROTOCOL")
    with pytest.raises(StopAsyncIteration):
        await anext(events)
    assert socket.closed


@pytest.mark.parametrize("frame", ['{"result":null,"id":true}', '{"code":2,"id":7}', "{"])
async def test_bad_ack_uses_protocol_failure(monkeypatch: pytest.MonkeyPatch, frame: str) -> None:
    socket = Socket(Clock(), [(1, frame)])
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedDisconnected(7, "VENUE_PROTOCOL")
    await events.aclose()


async def test_rotation_does_not_emit_a_trade_received_at_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = Socket(Clock(), [(1, '{"result":null,"id":7}'), (module.ROTATION_SECONDS, TRADE)])
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    assert await anext(events) == FeedConnected(7)
    assert await anext(events) == FeedDisconnected(7, "VENUE_UNAVAILABLE")
    await events.aclose()


async def test_ack_validation_finishing_at_deadline_is_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = Socket(Clock(), [(4.999, '{"result":null,"id":7}')])
    events = install(monkeypatch, socket).connection(PAIRS, generation=7)
    original = subscription_ack

    def validate(payload: object, generation: int) -> bool:
        result = original(payload, generation)
        socket.clock.now = socket.started_at + 5
        return result

    monkeypatch.setattr(module, "subscription_ack", validate)
    assert await anext(events) == FeedDisconnected(7, "SUBSCRIPTION_ACK_TIMEOUT")
    await events.aclose()


def test_control_budget_counts_subscription_ping_and_pong_in_one_window() -> None:
    clock = SimpleNamespace(now=100.0)
    pending: list[bytes] = []
    writes: list[bytes] = []
    aborted: list[bool] = []
    # This test supplies only the I/O collaborators used by send_data.
    connection = cast(Any, object.__new__(module._ControlBoundConnection))
    connection.loop = SimpleNamespace(time=lambda: clock.now)
    connection.protocol = SimpleNamespace(data_to_send=lambda: list(pending))
    connection.transport = SimpleNamespace(write=writes.append, abort=lambda: aborted.append(True))
    # One subscription, two probes and two automatic pongs consume the budget.
    for opcode in (1, 9, 10, 9, 10):
        pending[:] = [bytes([128 | opcode, 0])]
        connection.send_data()
    pending[:] = [b"\x8a\x00"]
    with pytest.raises(ConnectionError, match="control budget exceeded"):
        connection.send_data()
    assert len(writes) == 5
    assert aborted == [True]
    clock.now += 1
    connection.send_data()
    assert len(writes) == 6
