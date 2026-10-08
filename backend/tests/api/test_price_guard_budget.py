"""Actual ASGI guard rejects overflow before admission and session lookup."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.types import Message, Scope

from tiewtrade.services.api.price_admission import ProcessBudget
from tiewtrade.services.api.price_guard import PriceScopeGuard


@pytest.mark.parametrize("physical,pending", [(100, 0), (16, 16)])
async def test_overflow_guard_does_not_admit_or_lookup(
    monkeypatch: pytest.MonkeyPatch, physical: int, pending: int
) -> None:
    budget = ProcessBudget(physical=physical, pending=pending)
    admit = AsyncMock()
    lookup = Mock(side_effect=AssertionError("overflow reached database"))
    downstream = AsyncMock()
    monkeypatch.setattr("tiewtrade.services.api.price_guard.presented_session", lookup)
    scope: Scope = {
        "type": "websocket",
        "path": "/market-data/prices/stream",
        "headers": [],
        "app": SimpleNamespace(
            state=SimpleNamespace(price_budget=budget, price_admission=SimpleNamespace(admit=admit))
        ),
    }
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    await PriceScopeGuard(downstream)(scope, AsyncMock(), send)
    assert sent == [{"type": "websocket.close", "code": 1008, "reason": ""}]
    admit.assert_not_called()
    lookup.assert_not_called()
    downstream.assert_not_called()
    assert (budget.physical, budget.pending) == (physical, pending)


async def test_sixteen_actual_pending_guards_reject_seventeenth_without_queue() -> None:
    budget = ProcessBudget()
    ready = asyncio.Event()
    release = asyncio.Event()
    entered = 0

    async def admit(_: str | None) -> bool:
        nonlocal entered
        entered += 1
        if entered == 16:
            ready.set()
        await release.wait()
        return False

    scope: Scope = {
        "type": "websocket",
        "path": "/market-data/prices/stream",
        "headers": [],
        "client": ("127.0.0.1", 1000),
        "app": SimpleNamespace(
            state=SimpleNamespace(price_budget=budget, price_admission=SimpleNamespace(admit=admit))
        ),
    }
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    guard = PriceScopeGuard(AsyncMock())
    tasks = [asyncio.create_task(guard(scope, AsyncMock(), send)) for _ in range(16)]
    try:
        await asyncio.wait_for(ready.wait(), 1)
        assert (budget.physical, budget.pending) == (16, 16)
        await asyncio.wait_for(guard(scope, AsyncMock(), send), 0.1)
        assert entered == 16
        assert len(sent) == 1 and sent[0]["code"] == 1008
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert len(sent) == 17
    assert (budget.physical, budget.pending) == (0, 0)


@pytest.mark.parametrize("limit", ["ip", "global"])
async def test_real_redis_overflow_does_not_lookup_session(
    monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    import os
    from typing import cast

    from redis.asyncio import Redis

    from tiewtrade.infra.realtime.admission import AdmissionRedis, RedisAdmission

    # This test owns only the explicitly configured disposable Redis database.
    url = os.environ.get("TIEWTRADE_TEST_REDIS_URL")
    if url is None:
        pytest.skip("isolated Redis test URL required")
    redis = Redis.from_url(url)
    await redis.flushdb()
    admission = RedisAdmission(cast(AdmissionRedis, redis))
    lookup = Mock(side_effect=AssertionError("rejected admission reached database"))
    monkeypatch.setattr("tiewtrade.services.api.price_guard.presented_session", lookup)
    try:
        count = 30 if limit == "ip" else 200
        for index in range(count):
            assert await admission.admit("192.0.2.1" if limit == "ip" else f"peer-{index}")
        scope: Scope = {
            "type": "websocket",
            "path": "/market-data/prices/stream",
            "client": ("192.0.2.1", 1234),
            "headers": [
                (b"origin", b"http://localhost:5173"),
                (b"cookie", b"tiewtrade_session=unused-presented-token"),
                (b"x-forwarded-for", b"198.51.100.1"),
            ],
            "app": SimpleNamespace(
                state=SimpleNamespace(price_budget=ProcessBudget(), price_admission=admission)
            ),
        }
        sent: list[Message] = []

        async def send(message: Message) -> None:
            sent.append(message)

        await PriceScopeGuard(AsyncMock())(scope, AsyncMock(), send)
        assert len(sent) == 1 and sent[0]["code"] == 1008
        lookup.assert_not_called()
    finally:
        await redis.flushdb()
        await redis.aclose()
