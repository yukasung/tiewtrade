from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import Candle, CandleFinality, CandleWindow, Timeframe, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.storage import enqueue
from tiewtrade.services.market_data.ingestion import run_round
from tiewtrade.venues import FakeVenue, Symbol
from tiewtrade.venues.candles import CandlePage


async def test_missing_partition_fails_without_candle_or_cursor_commit(
    api_engine: AsyncEngine, migrator_engine: AsyncEngine
) -> None:
    now = datetime.now(UTC)
    opened = align_floor(now, Timeframe.M1)
    window = CandleWindow(opened, opened + Timeframe.M1.span)
    month = opened.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1)
    partition = f"market_candles_{month:%Y%m}"
    async with user_session(api_engine, uuid4()) as session:
        await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
    async with migrator_engine.begin() as connection:
        await connection.execute(text(f"ALTER TABLE market_candles DETACH PARTITION {partition}"))
        await connection.execute(text(f"DROP TABLE {partition}"))
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        source = FakeVenue()
        candle = Candle(
            "BTC",
            "USDT",
            Timeframe.M1,
            opened,
            window.end,
            Money.of("1", "USDT"),
            Money.of("2", "USDT"),
            Money.of("1", "USDT"),
            Money.of("2", "USDT"),
            Quantity.of("1", "BTC"),
            CandleFinality.UNCONFIRMED,
            now,
        )
        source.queue_candle_pages(
            [CandlePage(Symbol("BTC", "USDT"), Timeframe.M1, window, (candle,), now)]
        )
        await run_round(engine, source, "partition-test", now)
        async with market_data_session(engine) as session:
            row = (
                (
                    await session.execute(
                        "SELECT * FROM market_candle_demand WHERE base='BTC' AND timeframe='1m'"
                    )
                )
                .mappings()
                .one()
            )
            assert row["status"] == "FAILED"
            assert row["failure_code"] == "PARTITION_UNAVAILABLE"
            assert row["cursor"] == window.start
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == 0
    finally:
        await engine.dispose()
        async with migrator_engine.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE TABLE {partition} PARTITION OF market_candles "
                    f"FOR VALUES FROM ('{month.isoformat()}') TO ('{end.isoformat()}')"
                )
            )
            await connection.execute(text(f"GRANT SELECT ON {partition} TO tiewtrade_api"))
            await connection.execute(
                text(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {partition} TO tiewtrade_market_data")
            )
