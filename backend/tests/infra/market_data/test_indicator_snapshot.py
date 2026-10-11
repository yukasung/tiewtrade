from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.market_data.test_retention import insert_raw
from tiewtrade.core.market_data import CandleWindow, Timeframe, align_floor
from tiewtrade.infra.crypto.indicator_cursor import DatasetChangedError
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import indicator_read_session, market_data_session, user_session
from tiewtrade.infra.market_data.indicator_reader import read_indicators


async def test_snapshot_writer_commit_and_retention_time_do_not_mix(
    api_engine: AsyncEngine,
) -> None:
    await insert_raw("1", age=timedelta(minutes=2))
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.M1)
    window = CandleWindow(end - timedelta(minutes=3), end)
    owner = uuid4()
    writer = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with indicator_read_session(api_engine, owner) as reader:
            assert (
                await reader.execute("SHOW transaction_isolation")
            ).scalar_one() == "repeatable read"
            assert (await reader.execute("SHOW transaction_read_only")).scalar_one() == "on"
            old = await read_indicators(
                reader, "BTC", "USDT", Timeframe.M1, window, window, now, monotonic() + 30
            )
            async with market_data_session(writer) as session:
                await session.execute("UPDATE market_candles SET open=2 WHERE base='BTC'")
            same = await read_indicators(
                reader,
                "BTC",
                "USDT",
                Timeframe.M1,
                window,
                window,
                now,
                monotonic() + 30,
                old.revision,
            )
            assert same.revision == old.revision
        async with indicator_read_session(api_engine, owner) as reader:
            with pytest.raises(DatasetChangedError):
                await read_indicators(
                    reader,
                    "BTC",
                    "USDT",
                    Timeframe.M1,
                    window,
                    window,
                    now,
                    monotonic() + 30,
                    old.revision,
                )
        async with user_session(api_engine, owner) as normal:
            assert (await normal.execute("SHOW transaction_read_only")).scalar_one() == "off"
    finally:
        await writer.dispose()
