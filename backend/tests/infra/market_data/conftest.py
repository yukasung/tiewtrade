from collections.abc import AsyncIterator

import pytest_asyncio

from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session


@pytest_asyncio.fixture(autouse=True)
async def clear_market_tables() -> AsyncIterator[None]:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        for phase in range(2):
            async with market_data_session(engine) as session:
                await session.execute("DELETE FROM market_candles")
                await session.execute("DELETE FROM market_candle_demand")
            if phase == 0:
                # Migration tests must enter downgrade with no runtime sessions,
                # including idle connections owned by this cleanup fixture.
                await engine.dispose()
                yield
    finally:
        await engine.dispose()
