"""One public reader per process; Redis is only a lossy invalidation signal."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from typing import Protocol

from tiewtrade.infra.market_data.realtime_records import PriceSnapshot


class Notifications(Protocol):
    async def subscribe(self) -> None: ...
    def events(self) -> AsyncIterator[None]: ...
    async def close(self) -> None: ...


class PriceBroadcaster:
    def __init__(
        self, notifications: Notifications, read: Callable[[], Awaitable[PriceSnapshot]]
    ) -> None:
        self.notifications = notifications
        self.read = read
        self.connected = False
        self.latest: PriceSnapshot | None = None
        self.queues: set[asyncio.Queue[tuple[PriceSnapshot, bool]]] = set()
        self.changed = asyncio.Event()

    def listen(self) -> asyncio.Queue[tuple[PriceSnapshot, bool]]:
        queue: asyncio.Queue[tuple[PriceSnapshot, bool]] = asyncio.Queue(maxsize=1)
        self.queues.add(queue)
        if self.latest is not None:
            queue.put_nowait((self.latest, self.connected))
        return queue

    def unlisten(self, queue: asyncio.Queue[tuple[PriceSnapshot, bool]]) -> None:
        self.queues.discard(queue)

    def _push(self) -> None:
        if self.latest is None:
            return
        for queue in self.queues:
            if queue.full():
                queue.get_nowait()
            queue.put_nowait((self.latest, self.connected))

    async def _events(self) -> None:
        try:
            async for _ in self.notifications.events():
                self.changed.set()
            raise ConnectionError("notification stream ended")
        finally:
            self.connected = False
            self._push()
            self.changed.set()

    async def run(self) -> None:
        listener: asyncio.Task[None] | None = None
        try:
            while True:
                try:
                    await self.notifications.subscribe()
                    listener = asyncio.create_task(self._events())
                    self.latest = await self.read()
                    if listener.done():
                        await listener
                    self.connected = True
                    self._push()
                    while True:
                        # Minimum interval limits bursts to ten database reads per second.
                        await asyncio.sleep(0.1)
                        if listener.done():
                            await listener
                        with suppress(TimeoutError):
                            async with asyncio.timeout(0.9):
                                await self.changed.wait()
                        self.changed.clear()
                        self.latest = await self.read()
                        self._push()
                except Exception:
                    was_connected = self.connected
                    self.connected = False
                    if was_connected:
                        self._push()
                    if listener is not None:
                        listener.cancel()
                        await asyncio.gather(listener, return_exceptions=True)
                    await self.notifications.close()
                    with suppress(Exception):
                        self.latest = await self.read()
                        self._push()
                    await asyncio.sleep(1)
        finally:
            self.connected = False
            if listener is not None:
                listener.cancel()
                await asyncio.gather(listener, return_exceptions=True)
            await self.notifications.close()
