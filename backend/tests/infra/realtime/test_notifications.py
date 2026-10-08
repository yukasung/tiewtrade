import asyncio
from collections.abc import AsyncIterator
from typing import Any

from tiewtrade.infra.realtime.notifications import RedisNotifications


class PubSub:
    def __init__(self) -> None:
        self.ack = asyncio.Event()

    async def subscribe(self, channel: str) -> None:
        pass

    async def get_message(self, **kwargs: Any) -> dict[str, str] | None:
        await self.ack.wait()
        return {"type": "subscribe", "channel": "market.prices.changed"}


class Redis:
    def __init__(self, pubsub: PubSub) -> None:
        self.subscription = pubsub

    def pubsub(self) -> PubSub:
        return self.subscription


async def test_subscribe_waits_for_server_acknowledgement() -> None:
    pubsub = PubSub()
    notifications = RedisNotifications(Redis(pubsub))
    subscribing = asyncio.create_task(notifications.subscribe())
    await asyncio.sleep(0.01)
    assert not subscribing.done()
    pubsub.ack.set()
    await asyncio.wait_for(subscribing, 0.5)


class SilentPubSub(PubSub):
    async def listen(self) -> AsyncIterator[dict[str, str]]:
        await asyncio.sleep(10)
        yield {}

    async def ping(self) -> None:
        pass

    async def get_message(self, **kwargs: Any) -> dict[str, str] | None:
        await asyncio.sleep(0.02)
        return None


async def test_subscriber_requires_redis_pong_when_channel_is_idle() -> None:
    import pytest

    notifications = RedisNotifications(Redis(SilentPubSub()))
    notifications._pubsub = SilentPubSub()
    started = asyncio.get_running_loop().time()
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(2):
            await anext(notifications.events())
    assert asyncio.get_running_loop().time() - started < 1.8


async def test_actual_redis_ack_idle_pong_and_public_invalidation() -> None:
    import os

    import pytest
    from redis.asyncio import Redis as RedisClient

    url = os.environ.get("TIEWTRADE_TEST_REDIS_URL")
    if not url:
        pytest.skip("isolated Redis required")
    client = RedisClient.from_url(url)
    notifications = RedisNotifications(client)
    try:
        await notifications.subscribe()

        async def next_event() -> None:
            return await anext(notifications.events())

        event = asyncio.create_task(next_event())
        await asyncio.sleep(1.6)
        assert not event.done()  # pong kept the idle subscription alive
        assert await notifications.publish("primary_spot", 123)
        await asyncio.wait_for(event, 0.5)
        assert event.done() and not event.cancelled()
    finally:
        await notifications.close()
        await client.aclose()
