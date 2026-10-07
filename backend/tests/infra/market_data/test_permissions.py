from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import DatabaseRoleError, NotPermittedError
from tiewtrade.infra.db.session import market_data_session


async def test_market_session_refuses_api_role(api_engine: AsyncEngine) -> None:
    with pytest.raises(DatabaseRoleError):
        async with market_data_session(api_engine):
            pytest.fail("wrong role accepted")


async def test_api_can_read_but_cannot_delete_market_data(api_engine: AsyncEngine) -> None:
    async with user_session(api_engine, uuid4()) as session:
        await session.execute("SELECT * FROM market_candles LIMIT 1")
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, uuid4()) as session:
            await session.execute("DELETE FROM market_candles")


async def test_worker_cannot_read_credentials() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        with pytest.raises(NotPermittedError):
            async with market_data_session(engine) as session:
                await session.execute("SELECT * FROM user_api_keys")
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE market_candles SET open=1 WHERE false",
        "UPDATE market_candle_demand SET generation=1 WHERE false",
        "UPDATE market_candle_demand SET status='COMPLETE' WHERE false",
        "INSERT INTO market_candle_demand "
        "(source,base,quote,timeframe,desired_start,desired_end,status) "
        "VALUES ('primary_spot','BTC','USDT','1m',clock_timestamp()-interval '1 minute',"
        "clock_timestamp(),'RUNNING')",
        "CREATE TABLE market_data_shortcut (id integer)",
    ],
)
async def test_api_cannot_write_worker_columns_prices_or_schema(
    api_engine: AsyncEngine, statement: str
) -> None:
    with pytest.raises(NotPermittedError):
        async with user_session(api_engine, uuid4()) as session:
            await session.execute(statement)
