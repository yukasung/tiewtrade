"""Shipped launch commands must preserve the TCP peer used by WS admission."""

import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import uvicorn
from starlette.types import Receive, Scope, Send
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def server(command: str, peers: list[str]) -> AsyncIterator[int]:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        peers.append(scope["client"][0])
        await receive()
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 1000})

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    runtime = uvicorn.Server(
        uvicorn.Config(
            app,
            ws="tiewtrade.services.api.price_protocol:PriceWebSocketProtocol",
            proxy_headers="--no-proxy-headers" not in command,
            forwarded_allow_ips="127.0.0.1,::1",
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
        yield listener.getsockname()[1]
    finally:
        runtime.should_exit = True
        await asyncio.wait_for(task, 3)
        listener.close()


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "backend/Dockerfile",
        "compose.yaml",
        "frontend/playwright.config.ts",
    ],
)
async def test_shipped_command_cannot_spoof_admission_peer(path: str) -> None:
    commands = [
        line
        for line in (ROOT / path).read_text().splitlines()
        if "uvicorn tiewtrade.services.api.app:app" in line
        or '"uvicorn", "tiewtrade.services.api.app:app"' in line
    ]
    assert len(commands) == 1
    peers: list[str] = []
    async with server(commands[0], peers) as port:
        for address in ("198.51.100.1", "198.51.100.2"):
            async with connect(
                f"ws://127.0.0.1:{port}/market-data/prices/stream",
                additional_headers={
                    "X-Forwarded-For": address,
                    "Forwarded": f"for={address}",
                    "X-Real-IP": address,
                },
            ):
                pass
    assert peers == ["127.0.0.1", "127.0.0.1"]
