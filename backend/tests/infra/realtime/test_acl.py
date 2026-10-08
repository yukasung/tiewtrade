"""Actual Redis process capabilities from the Compose ACL, on test Redis only."""

import os
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from tiewtrade.infra.realtime.admission import AdmissionRedis, RedisAdmission
from tiewtrade.infra.realtime.notifications import CHANNEL


async def test_process_acls_allow_only_notifications_and_admission() -> None:
    admin_url = os.environ["TIEWTRADE_TEST_REDIS_URL"]
    admin = Redis.from_url(admin_url)
    config = Path(__file__).resolve().parents[4] / "config" / "redis.acl"
    lines = config.read_text().splitlines()
    assert "user default off" in lines
    for line in lines:
        if line.startswith("user ") and not line.startswith("user default "):
            words = line.split()
            await cast(Any, admin).execute_command("ACL", "SETUSER", words[1], "reset", *words[2:])
    parsed = urlsplit(admin_url)
    assert parsed.hostname is not None
    api = Redis(
        host=parsed.hostname, port=parsed.port or 6379, username="api", password="dev_api_redis"
    )
    market = Redis(
        host=parsed.hostname,
        port=parsed.port or 6379,
        username="market_data",
        password="dev_market_data_redis",
    )
    try:
        assert await market.publish(CHANNEL, "{}") >= 0
        with pytest.raises(ResponseError):
            await api.publish(CHANNEL, "{}")
        with pytest.raises(ResponseError):
            await market.get("market.ws.admission:global")
        with pytest.raises(ResponseError):
            await api.get("unrelated:user:data")
        with pytest.raises(ResponseError):
            await api.set("market.ws.admission:injected", "1")
        keys = await admin.keys("market.ws.admission:*")
        if keys:
            await admin.delete(*keys)
        assert await RedisAdmission(cast(AdmissionRedis, api)).admit("192.0.2.1")
        pubsub = api.pubsub()
        try:
            await pubsub.subscribe(CHANNEL)
            ack = await pubsub.get_message(ignore_subscribe_messages=False, timeout=1)
            assert ack is not None and ack["type"] == "subscribe"
        finally:
            await cast(Any, pubsub).aclose()
    finally:
        await api.aclose()
        await market.aclose()
        await admin.aclose()
