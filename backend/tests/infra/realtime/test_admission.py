import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import cast

import pytest

from tiewtrade.infra.realtime.admission import AdmissionOutcome, AdmissionRedis, RedisAdmission


class Broken:
    async def eval(self, script: str, numkeys: int, *args: object) -> object:
        raise OSError("offline")


async def test_redis_down_fails_closed() -> None:
    assert await RedisAdmission(Broken()).admit("127.0.0.1") is False


async def test_timeout_is_unavailable_and_cancels_pending_request() -> None:
    cancelled = asyncio.Event()

    class Stalled:
        async def eval(self, script: str, numkeys: int, *args: object) -> object:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            return None

    async with asyncio.timeout(1):
        result = await RedisAdmission(Stalled(), timeout=0.01).outcome("127.0.0.1")
    assert result is AdmissionOutcome.UNAVAILABLE
    assert cancelled.is_set()


async def test_actual_redis_atomic_limits_and_bounded_keys() -> None:
    import os

    from redis.asyncio import Redis
    from redis.asyncio.connection import AbstractConnection

    url = os.environ.get("TIEWTRADE_TEST_REDIS_URL")
    if not url:
        pytest.skip("isolated Redis test URL required")
    client = Redis.from_url(url)
    try:
        # This check proves atomic quota accounting, not cold TCP/DNS capacity.
        # Reserve the burst's connections before admission starts its unchanged
        # 500ms deadline. Cold/stalled requests still fail closed in the tests above.
        connections: list[AbstractConnection] = []
        prepare = cast(
            Callable[[], Awaitable[AbstractConnection]], client.connection_pool.get_connection
        )
        try:
            async with asyncio.timeout(5):
                for _ in range(170):
                    connections.append(await prepare())
        finally:
            await asyncio.gather(*(client.connection_pool.release(c) for c in connections))
        await client.flushdb()
        admission = RedisAdmission(cast(AdmissionRedis, client))
        same = Counter(await asyncio.gather(*(admission.outcome("127.0.0.1") for _ in range(40))))
        assert same == {AdmissionOutcome.ACCEPTED: 30, AdmissionOutcome.DENIED: 10}
        varied = Counter(
            await asyncio.gather(*(admission.outcome(f"192.0.2.{i}") for i in range(170)))
        )
        assert varied == {AdmissionOutcome.ACCEPTED: 160, AdmissionOutcome.DENIED: 10}
        keys = await client.keys("market.ws.admission:*")
        assert len(keys) == 162  # global + first IP + 160 distinct accepted-window keys
        assert all(
            0 < ttl <= 120 for ttl in await asyncio.gather(*(client.ttl(key) for key in keys))
        )
        assert not await admission.admit("198.51.100.1")
        assert len(await client.keys("market.ws.admission:*")) == len(keys)
    finally:
        await client.flushdb()
        await client.aclose()
