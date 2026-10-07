from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Result, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import CandleWindow, Timeframe, align_floor
from tiewtrade.infra.db import DatabaseRole, ValueRejectedError, create_engine_for, user_session
from tiewtrade.infra.db.session import MarketDataSession, market_data_session
from tiewtrade.infra.market_data.claims import cleanup
from tiewtrade.infra.market_data.records import RetentionError, WindowTooLargeError
from tiewtrade.infra.market_data.storage import read_candles


async def test_reads_reject_expired_or_oversized_ranges(api_engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    async with user_session(api_engine, uuid4()) as session:
        with pytest.raises(RetentionError):
            await read_candles(
                session,
                "BTC",
                "USDT",
                Timeframe.M1,
                CandleWindow(now - timedelta(days=366), now),
                1000,
            )
        with pytest.raises(WindowTooLargeError):
            await read_candles(
                session,
                "BTC",
                "USDT",
                Timeframe.M1,
                CandleWindow(now - timedelta(minutes=1002), now),
                1000,
            )


async def insert_raw(
    value: str, *, age: timedelta = timedelta(0), base: str = "BTC", timeframe: str = "1m"
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        now = datetime.now(UTC)
        opened = align_floor(now - age, Timeframe.M1)
        async with market_data_session(engine) as session:
            await session.execute(
                """INSERT INTO market_candles
                (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
                 observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                VALUES ('primary_spot',:base,'USDT',:tf,:opened,:end,CAST(:value AS numeric),
                2,1,1,0,'UNCONFIRMED',:now,:now,:now,1)""",
                {
                    "base": base,
                    "tf": timeframe,
                    "opened": opened,
                    "end": opened + timedelta(minutes=1),
                    "now": now,
                    "value": value,
                },
            )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0", "-1", "1.0000000000000000001"])
async def test_direct_db_rejects_invalid_financial_values(value: str) -> None:
    with pytest.raises(ValueRejectedError):
        await insert_raw(value)


async def test_cleanup_removes_only_expired_observations() -> None:
    await insert_raw("1", age=timedelta(days=365, minutes=1))
    await insert_raw("1")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            assert await cleanup(session) == 1
            assert (await session.execute("SELECT count(*) FROM market_candles")).scalar_one() == 1
    finally:
        await engine.dispose()


async def test_direct_db_rejects_unsupported_series() -> None:
    with pytest.raises(ValueRejectedError):
        await insert_raw("1", base="UNSUPPORTED")


async def test_active_fetch_unit_requires_both_bounds() -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        with pytest.raises(ValueRejectedError):
            async with market_data_session(engine) as session:
                await session.execute(
                    """INSERT INTO market_candle_demand
                  (source,base,quote,timeframe,desired_start,desired_end,fetch_unit_id)
                  VALUES ('primary_spot','BTC','USDT','1m',
                  clock_timestamp()-interval '1 minute',clock_timestamp(),:unit)""",
                    {"unit": uuid4()},
                )
    finally:
        await engine.dispose()


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Europe/Paris"])
@pytest.mark.parametrize(
    "as_of", [datetime(2024, 3, 10, 12, tzinfo=UTC), datetime(2024, 11, 3, 12, tzinfo=UTC)]
)
async def test_cleanup_fixed_cutoff_across_dst(
    migrator_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    zone: str,
    as_of: datetime,
) -> None:
    cutoff = as_of - timedelta(days=365)
    month = cutoff.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1)
    partition = f"market_candles_{month:%Y%m}"
    async with migrator_engine.begin() as connection:
        existed = (
            await connection.execute(text("SELECT to_regclass(:name)"), {"name": partition})
        ).scalar_one() is not None
        if not existed:
            await connection.execute(
                text(
                    f"CREATE TABLE {partition} PARTITION OF market_candles "
                    f"FOR VALUES FROM ('{month.isoformat()}') TO ('{end.isoformat()}')"
                )
            )
            await connection.execute(
                text(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {partition} TO tiewtrade_market_data")
            )
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    original_execute = MarketDataSession.execute

    async def frozen_clock(
        session: MarketDataSession,
        statement: str,
        parameters: Mapping[str, object] | None = None,
    ) -> Result[Any]:
        if "clock_timestamp()" in statement:
            statement = statement.replace("clock_timestamp()", "CAST(:test_as_of AS timestamptz)")
            parameters = dict(parameters or {}) | {"test_as_of": as_of}
        return await original_execute(session, statement, parameters)

    try:
        async with market_data_session(engine) as session:
            for opened in (cutoff - timedelta(minutes=30), cutoff, cutoff + timedelta(minutes=30)):
                await session.execute(
                    """INSERT INTO market_candles
                    (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
                     finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                    VALUES ('primary_spot','BTC','USDT','1m',:opened,:end,1,1,1,1,0,
                      'UNCONFIRMED',:now,:now,:now,1)""",
                    {"opened": opened, "end": opened + Timeframe.M1.span, "now": as_of},
                )
        monkeypatch.setattr(MarketDataSession, "execute", frozen_clock)
        async with market_data_session(engine) as session:
            await session.execute("SELECT set_config('TimeZone',:zone,true)", {"zone": zone})
            assert await cleanup(session) == 1
            opens = (
                (await session.execute("SELECT open_at FROM market_candles ORDER BY open_at"))
                .scalars()
                .all()
            )
            assert opens == [cutoff, cutoff + timedelta(minutes=30)]
    finally:
        await engine.dispose()
        if not existed:
            async with migrator_engine.begin() as connection:
                await connection.execute(text(f"DROP TABLE {partition}"))
