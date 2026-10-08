from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.db.test_migrations import _alembic, _failed_upgrade_or_downgrade, _snapshot
from tests.infra.market_data.test_retention import insert_raw
from tiewtrade.core.market_data import CandleWindow, Timeframe
from tiewtrade.infra.db import user_session
from tiewtrade.infra.market_data.storage import enqueue


@pytest.mark.parametrize("table", ["market_candles", "market_candle_demand"])
async def test_populated_candle_downgrade_refuses_atomically(
    migrator_engine: AsyncEngine, api_engine: AsyncEngine, table: str
) -> None:
    # F-09 tests its own migration boundary; later migrations may downgrade separately.
    _alembic("downgrade", "0013")
    try:
        if table == "market_candles":
            await insert_raw("1")
        else:
            now = datetime.now(UTC)
            async with user_session(api_engine, uuid4()) as session:
                await enqueue(
                    session,
                    "BTC",
                    "USDT",
                    Timeframe.M1,
                    CandleWindow(now - timedelta(minutes=1), now),
                )
        before = await _snapshot(migrator_engine)
        failure = _failed_upgrade_or_downgrade("downgrade", "0012")
        assert "market data populated; downgrade refused" in failure.stderr
        async with migrator_engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one() == "0013"
            assert (
                await connection.execute(text(f"SELECT count(*) FROM {table}"))
            ).scalar_one() == 1
        assert await _snapshot(migrator_engine) == before
    finally:
        _alembic("upgrade", "head")


async def test_empty_upgrade_downgrade_replays_market_schema(migrator_engine: AsyncEngine) -> None:
    _alembic("downgrade", "0013")
    try:
        before = await _snapshot(migrator_engine)
        _alembic("downgrade", "0012")
        async with migrator_engine.connect() as connection:
            assert (
                await connection.execute(text("SELECT to_regclass('market_candles')"))
            ).scalar_one() is None
        _alembic("upgrade", "0013")
        assert await _snapshot(migrator_engine) == before
    finally:
        _alembic("upgrade", "head")
