from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import CandleWindow, Timeframe
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.claims import claim_next, lock_claim
from tiewtrade.infra.market_data.records import StaleClaimError
from tiewtrade.infra.market_data.storage import database_now, enqueue


async def test_expired_worker_cannot_lock(api_engine: AsyncEngine) -> None:
    async with user_session(api_engine, uuid4()) as session:
        now = await database_now(session)
        await enqueue(
            session, "ETH", "USDT", Timeframe.M5, CandleWindow(now - timedelta(minutes=10), now)
        )
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            claim = await claim_next(session, "old")
            assert claim is not None
            await session.execute(
                "UPDATE market_candle_demand SET lease_until=clock_timestamp() WHERE token=:token",
                {"token": claim.token},
            )
        with pytest.raises(StaleClaimError):
            async with market_data_session(engine) as session:
                await lock_claim(session, claim)
    finally:
        await engine.dispose()
