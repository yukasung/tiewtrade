"""W4 refreshes only restored market state before legacy recovery."""

import asyncio
import os
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.engine import make_url

from tests.infra.execution_market import profile_internal_restore as subject
from tests.infra.execution_market import profile_workload
from tiewtrade.infra.db import DatabaseRole


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
async def test_restored_publisher_target_lifecycle_and_primary(
    monkeypatch: pytest.MonkeyPatch, failure: type[BaseException] | None
) -> None:
    source = "postgresql+asyncpg://market:unused@localhost/source"
    monkeypatch.setenv(DatabaseRole.MARKET_DATA.url_variable, source)
    market = Mock(dispose=AsyncMock())
    factory = Mock(return_value=market)
    monkeypatch.setattr(subject, "create_async_engine", factory)
    running = asyncio.Event()
    stopped = asyncio.Event()

    async def publish(engine: object, stop: asyncio.Event, stats: object, **kwargs: object) -> None:
        assert engine is market
        running.set()
        try:
            await stop.wait()
        finally:
            stopped.set()

    async def ready(task: asyncio.Task[None], stats: object) -> None:
        await running.wait()

    error = failure() if failure else None

    async def recover(*args: object) -> dict[str, int]:
        assert running.is_set() and not stopped.is_set()
        if error is not None:
            raise error
        return {"expired_before": 1, "expired_after": 0, "rounds": 1}

    monkeypatch.setattr(profile_workload, "market_publisher", publish)
    monkeypatch.setattr(profile_workload, "wait_publisher_ready", ready)
    original = AsyncMock(side_effect=recover)
    monkeypatch.setattr(subject, "_recover_legacy_claims", original)
    target = Mock(
        url=make_url("postgresql+asyncpg://engine@localhost/tiewtrade_internal20_test_target")
    )
    if error is not None:
        with pytest.raises(type(error)) as caught:
            await subject.recover_legacy_claims(Mock(), target, Mock())
        assert caught.value is error
    else:
        assert (await subject.recover_legacy_claims(Mock(), target, Mock()))["expired_after"] == 0
    assert make_url(factory.call_args.args[0]).database == target.url.database
    assert os.environ[DatabaseRole.MARKET_DATA.url_variable] == source
    assert stopped.is_set()
    original.assert_awaited_once()
    market.dispose.assert_awaited_once()


async def test_restore_rejects_nonisolated_target() -> None:
    target = Mock(url=make_url("postgresql+asyncpg://engine@localhost/production"))
    with pytest.raises(ValueError, match="isolated restore"):
        await subject.recover_legacy_claims(Mock(), target, Mock())
