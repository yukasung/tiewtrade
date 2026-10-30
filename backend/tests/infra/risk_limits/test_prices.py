import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.risk_limits import RiskUnavailableError
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import RiskProtocolError
from tiewtrade.infra.db.session import UserSession, market_data_session
from tiewtrade.infra.market_data.realtime_storage import acquire_writer, set_connected
from tiewtrade.infra.risk_limits.prices import price_watermark, read_frame, read_frames


@pytest.mark.parametrize("fault", ["missing", "checksum"])
async def test_cached_frame_cannot_mask_storage_failure(
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    owner: UUID,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    async with market_data_session(publication) as publisher:
        lease = await acquire_writer(publisher, uuid4())
        assert lease is not None
        await set_connected(publisher, lease, True)
    async with user_session(api_engine, owner) as session:
        watermark = await price_watermark(session)
        await read_frame(session, watermark)
    original = UserSession.execute

    async def failed_read(
        session: UserSession, statement: str, parameters: Mapping[str, object] | None = None
    ) -> Any:
        result = await original(session, statement, parameters)
        if "FROM market_risk_price_frames WHERE id" not in statement:
            return result
        rows = [dict(row) for row in result.mappings().all()]
        assert rows
        if fault == "missing":
            rows = []
        else:
            rows[0]["valid"] = False
        unavailable = Mock()
        unavailable.mappings.return_value.all.return_value = rows
        return unavailable

    with monkeypatch.context() as patch:
        patch.setattr(UserSession, "execute", failed_read)
        async with user_session(api_engine, owner) as session:
            with pytest.raises(RiskUnavailableError, match="incomplete"):
                await read_frame(session, watermark)


@pytest.fixture
async def publication(migrator_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with migrator_engine.begin() as connection:
        await connection.execute(text("UPDATE risk_protocol_control SET publication_enabled=true"))
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(market) as session:
            await session.execute("SELECT risk_publication_fence()")
            await session.execute(
                "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
            )
        yield market
    finally:
        await market.dispose()
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE risk_protocol_control SET admission_enabled=false,"
                    "financial_enabled=false,publication_enabled=false"
                )
            )


async def test_guard_blocks_old_publisher_and_guc_spoof(publication: AsyncEngine) -> None:
    for spoof in (False, True):
        with pytest.raises(RiskProtocolError):
            async with market_data_session(publication) as session:
                if spoof:
                    await session.execute(
                        "SELECT set_config('tiewtrade.risk_publication_version','F18_V1',true)"
                    )
                await session.execute("UPDATE market_price_feed SET connected=false")


async def test_atomic_frames_and_rollback(
    publication: AsyncEngine,
    api_engine: AsyncEngine,
    owner: UUID,
) -> None:
    async with user_session(api_engine, owner) as session:
        before = await price_watermark(session)
    with pytest.raises(RuntimeError, match="crash"):
        async with market_data_session(publication) as session:
            lease = await acquire_writer(session, uuid4())
            assert lease is not None
            await set_connected(session, lease, True)
            raise RuntimeError("crash before commit")
    async with user_session(api_engine, owner) as session:
        assert await price_watermark(session) == before
    async with market_data_session(publication) as session:
        lease = await acquire_writer(session, uuid4())
        assert lease is not None
        await set_connected(session, lease, True)
    async with user_session(api_engine, owner) as session:
        after = await price_watermark(session)
        frames = await read_frames(session, after=before, through=after)
        assert len(frames) == after - before > 1
        final = await read_frame(session, after)
        assert final == frames[-1]
        assert all(price.connected for price in final.prices)
        assert {p.pair.base for p in final.prices} >= {"BTC", "ETH"}
        with pytest.raises(RiskUnavailableError):
            await read_frame(session, after + 1)


async def test_shared_financial_fence_orders_publication_without_feed_lock(
    publication: AsyncEngine,
    engine_engine: AsyncEngine,
    owner: UUID,
) -> None:
    entered = asyncio.Event()
    published = asyncio.Event()

    async def publish() -> None:
        async with market_data_session(publication) as session:
            entered.set()
            lease = await acquire_writer(session, uuid4())
            assert lease is not None
            await set_connected(session, lease, True)
        published.set()

    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        watermark = (await session.execute("SELECT risk_financial_fence()")).scalar_one()
        task = asyncio.create_task(publish())
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            # The publisher must be waiting on the fence, rather than holding the
            # feed row and causing an owner->fence->feed inversion.
            async with market_data_session(publication) as observer:
                await observer.execute("SELECT * FROM market_price_feed FOR UPDATE NOWAIT")
            assert not published.is_set()
            assert await price_watermark(session) == watermark
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
    await asyncio.wait_for(task, timeout=3)
    assert published.is_set()


async def test_publication_disabled_creates_no_journal_history(
    api_engine: AsyncEngine,
    owner: UUID,
) -> None:
    market = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with user_session(api_engine, owner) as session:
            before = await price_watermark(session)
        async with market_data_session(market) as session:
            await session.execute("SELECT risk_publication_fence()")
            await session.execute("UPDATE market_price_feed SET connected=false")
        async with user_session(api_engine, owner) as session:
            assert await price_watermark(session) == before
    finally:
        await market.dispose()
