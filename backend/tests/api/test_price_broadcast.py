import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from tiewtrade.infra.market_data.realtime_records import PriceSnapshot
from tiewtrade.services.api.price_broadcast import PriceBroadcaster


class Notifications:
    def __init__(self) -> None:
        self.subscribed = False
        self.changed = asyncio.Event()

    async def subscribe(self) -> None:
        self.subscribed = True

    async def events(self) -> AsyncIterator[None]:
        while True:
            await self.changed.wait()
            self.changed.clear()
            yield None

    async def close(self) -> None:
        self.subscribed = False


async def test_subscribe_precedes_snapshot_and_latest_slot_is_bounded() -> None:
    notifications = Notifications()
    reads = 0

    async def read() -> PriceSnapshot:
        nonlocal reads
        assert notifications.subscribed
        reads += 1
        return PriceSnapshot(None, (), datetime.now(UTC))

    broadcaster = PriceBroadcaster(notifications, read)
    queue = broadcaster.listen()
    task = asyncio.create_task(broadcaster.run())
    try:
        await asyncio.wait_for(queue.get(), 1)
        for _ in range(20):
            notifications.changed.set()
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.15)
        assert queue.qsize() == 1
        assert reads <= 3
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_disconnection_pushes_recovering_and_resubscribe_reads_before_connected() -> None:
    class Reconnecting(Notifications):
        def __init__(self) -> None:
            super().__init__()
            self.fail = asyncio.Event()
            self.subscriptions = 0

        async def subscribe(self) -> None:
            await super().subscribe()
            self.subscriptions += 1
            self.fail.clear()

        async def events(self) -> AsyncIterator[None]:
            await self.fail.wait()
            if self.fail.is_set():
                raise ConnectionError("redis transport failed")
            yield None

    notifications = Reconnecting()
    readings = 0

    async def read() -> PriceSnapshot:
        nonlocal readings
        readings += 1
        return PriceSnapshot(None, (), datetime.now(UTC))

    broadcaster = PriceBroadcaster(notifications, read)
    queue = broadcaster.listen()
    task = asyncio.create_task(broadcaster.run())
    try:
        _, connected = await asyncio.wait_for(queue.get(), 1)
        assert connected
        before = readings
        notifications.fail.set()
        _, connected = await asyncio.wait_for(queue.get(), 0.5)
        assert not connected
        async with asyncio.timeout(2):
            while not connected:
                _, connected = await queue.get()
        assert connected
        assert notifications.subscriptions == 2
        assert readings > before
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_redis_down_keeps_authoritative_recovering_heartbeats() -> None:
    class Offline(Notifications):
        async def subscribe(self) -> None:
            raise ConnectionError("offline")

    async def read() -> PriceSnapshot:
        return PriceSnapshot(None, (), datetime.now(UTC))

    broadcaster = PriceBroadcaster(Offline(), read)
    queue = broadcaster.listen()
    task = asyncio.create_task(broadcaster.run())
    try:
        first, connected = await asyncio.wait_for(queue.get(), 0.5)
        assert not connected
        second, connected = await asyncio.wait_for(queue.get(), 1.5)
        assert not connected
        assert second.server_time > first.server_time
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
