"""Lossy public invalidations. PostgreSQL remains authoritative."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

CHANNEL = "market.prices.changed"


class RedisNotifications:
    def __init__(self, client: Any, *, channel: str = CHANNEL) -> None:
        self.client = client
        self.channel = channel
        self._pubsub: Any = None

    async def publish(self, source: str, revision: int) -> bool:
        try:
            async with asyncio.timeout(0.5):
                await self.client.publish(
                    self.channel, json.dumps({"source": source, "revision": str(revision)})
                )
            return True
        except Exception:
            return False

    async def subscribe(self) -> None:
        self._pubsub = self.client.pubsub()
        async with asyncio.timeout(0.5):
            await self._pubsub.subscribe(self.channel)
            while True:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=False, timeout=0.5
                )
                if message is not None and message["type"] == "subscribe":
                    break

    async def events(self) -> AsyncIterator[None]:
        if self._pubsub is None:
            raise RuntimeError("subscribe before reading snapshot")
        loop = asyncio.get_running_loop()
        ping_at = loop.time() + 1
        while True:
            remaining = ping_at - loop.time()
            if remaining <= 0:
                async with asyncio.timeout(0.5):
                    await self._pubsub.ping()
                    while True:
                        message = await self._pubsub.get_message(
                            ignore_subscribe_messages=False, timeout=0.5
                        )
                        if message is not None and message["type"] == "pong":
                            break
                        if message is not None and message["type"] == "message":
                            yield None
                ping_at = loop.time() + 1
            else:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=False, timeout=remaining
                )
                if message is not None and message["type"] == "message":
                    yield None

    async def close(self) -> None:
        if self._pubsub is not None:
            await self._pubsub.aclose()
            self._pubsub = None
