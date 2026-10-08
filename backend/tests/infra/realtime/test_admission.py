from typing import cast

import pytest

from tiewtrade.infra.realtime.admission import AdmissionRedis, RedisAdmission


class Broken:
    async def eval(self, script: str, numkeys: int, *args: object) -> object:
        raise OSError("offline")


async def test_redis_down_fails_closed() -> None:
    assert await RedisAdmission(Broken()).admit("127.0.0.1") is False


async def test_actual_redis_atomic_limits_and_bounded_keys() -> None:
    import asyncio
    import os

    from redis.asyncio import Redis

    url = os.environ.get("TIEWTRADE_TEST_REDIS_URL")
    if not url:
        pytest.skip("isolated Redis test URL required")
    client = Redis.from_url(url)
    try:
        await client.flushdb()
        admission = RedisAdmission(cast(AdmissionRedis, client))
        same = await asyncio.gather(*(admission.admit("127.0.0.1") for _ in range(40)))
        assert sum(same) == 30
        varied = await asyncio.gather(*(admission.admit(f"192.0.2.{i}") for i in range(170)))
        assert sum(varied) == 160
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
