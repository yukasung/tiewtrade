"""Real wire checks: forbidden messages keep the bounded decoder and close1008."""

import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import pytest
import uvicorn
from starlette.types import Receive, Scope, Send
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State

from tiewtrade.services.api.price_protocol import _PushOnlyServerProtocol


@asynccontextmanager
async def server(received: list[object]) -> AsyncIterator[int]:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        await receive()
        await send({"type": "websocket.accept"})
        event = await receive()
        if event["type"] == "websocket.receive":
            received.append(event)
            await send({"type": "websocket.close", "code": 1008})

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    runtime = uvicorn.Server(
        uvicorn.Config(
            app,
            ws="tiewtrade.services.api.price_protocol:PriceWebSocketProtocol",
            lifespan="off",
            log_level="critical",
        )
    )
    task = asyncio.create_task(runtime.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(2):
            while not runtime.started:
                if task.done():
                    task.result()
                await asyncio.sleep(0.001)
        yield port
    finally:
        runtime.should_exit = True
        await asyncio.wait_for(task, timeout=3)
        listener.close()


@pytest.mark.parametrize("compression", [None, "deflate"])
@pytest.mark.parametrize(
    "message, reaches_app",
    [
        ("x" * 256, True),
        ("x" * 257, False),
        (b"x" * 257, False),
        ("ก" * 86, False),  # UTF-8 bytes, not character count:258bytes.
        (["x" * 128, "x" * 129], False),  # Cumulative message size across fragments.
        ("x" * 65536, False),  # A compressed message still has a bounded decoded size.
    ],
    ids=["text-limit", "text-oversize", "binary-oversize", "utf8-bytes", "fragments", "large"],
)
async def test_forbidden_messages_close_1008_without_delivering_oversized_data(
    message: str | bytes | list[str],
    reaches_app: bool,
    compression: str | None,
) -> None:
    received: list[object] = []
    async with (
        server(received) as port,
        connect(
            f"ws://127.0.0.1:{port}/market-data/prices/stream", compression=compression
        ) as peer,
    ):
        with suppress(ConnectionClosed):
            await peer.send(message)
        with pytest.raises(ConnectionClosed) as error:
            await asyncio.wait_for(peer.recv(), timeout=2)
        assert error.value.rcvd is not None
        assert error.value.rcvd.code == 1008
    assert bool(received) is reaches_app


async def test_native_ping_pong_remains_allowed() -> None:
    received: list[object] = []
    async with (
        server(received) as port,
        connect(f"ws://127.0.0.1:{port}/market-data/prices/stream") as peer,
    ):
        pong = await peer.ping()
        await asyncio.wait_for(pong, timeout=1)
        assert peer.close_code is None
    assert received == []


@pytest.mark.parametrize("code", [1002, 1007, 1011])
def test_other_protocol_failures_keep_their_codes(code: int) -> None:
    protocol = _PushOnlyServerProtocol(state=State.OPEN)
    protocol.fail(code, "test failure")
    assert protocol.close_sent is not None
    assert protocol.close_sent.code == code
