from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from tests.infra.db.test_migrations import _alembic, _failed_upgrade_or_downgrade, _snapshot
from tests.infra.market_data.test_retention import insert_raw
from tiewtrade.core.market_data import CandleWindow, Timeframe, advance, align_floor, slot_count

_INSERT_CANDLE = text(
    """INSERT INTO market_candles
    (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,
     finality,observed_at,fetch_started_at,last_checked_at,ingestion_generation)
    VALUES ('primary_spot','BTC','USDT',:timeframe,:opened,:ended,
    100.000000000000000001,101.000000000000000001,
    99.000000000000000001,100.500000000000000001,
    1.250000000000000001,'CLOSED',:observed,:observed,:observed,7)"""
)
_CANDLE_CHECKSUM = text(
    "SELECT md5(to_jsonb(c)::text) FROM market_candles c "
    "WHERE base='BTC' AND quote='USDT' AND timeframe='1h' AND open_at=:opened"
)


async def _insert_candle(
    connection: AsyncConnection, timeframe: str, opened: datetime, ended: datetime
) -> None:
    await connection.execute(
        _INSERT_CANDLE,
        {
            "timeframe": timeframe,
            "opened": opened,
            "ended": ended,
            "observed": ended + timedelta(seconds=1),
        },
    )


async def _candle_checksum(connection: AsyncConnection, opened: datetime) -> str:
    checksum: str = (await connection.execute(_CANDLE_CHECKSUM, {"opened": opened})).scalar_one()
    return checksum


@pytest.mark.parametrize("table", ["market_candles", "market_candle_demand"])
async def test_populated_candle_downgrade_refuses_atomically(
    migrator_engine: AsyncEngine, table: str
) -> None:
    # F-09 tests its own migration boundary; later migrations may downgrade separately.
    _alembic("downgrade", "0013")
    try:
        if table == "market_candles":
            await insert_raw("1")
        else:
            now = datetime.now(UTC)
            async with migrator_engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO market_candle_demand("
                        "base,quote,timeframe,desired_start,desired_end) "
                        "VALUES('BTC','USDT','1m',:start,:end)"
                    ),
                    {"start": now - timedelta(minutes=1), "end": now},
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


async def test_week_month_upgrade_preserves_existing_candle_checksum(
    migrator_engine: AsyncEngine,
) -> None:
    await migrator_engine.dispose()
    _alembic("downgrade", "0025")
    try:
        opened = align_floor(datetime.now(UTC) - timedelta(hours=2), Timeframe.H1)
        ended = advance(opened, Timeframe.H1, 1)
        async with migrator_engine.begin() as connection:
            await _insert_candle(connection, Timeframe.H1.value, opened, ended)
            before = await _candle_checksum(connection, opened)
        await migrator_engine.dispose()
        _alembic("upgrade", "0026")
        async with migrator_engine.connect() as connection:
            after = await _candle_checksum(connection, opened)
        assert after == before
    finally:
        await migrator_engine.dispose()
        _alembic("upgrade", "head")


async def test_week_month_partition_inventory_and_grants(migrator_engine: AsyncEngine) -> None:
    current_month = align_floor(datetime.now(UTC), Timeframe.MN1)
    first_month = current_month.replace(year=current_month.year - 5)
    stop = advance(current_month, Timeframe.MN1, 13)
    expected = [
        f"market_candles_{advance(first_month, Timeframe.MN1, index):%Y%m}"
        for index in range(slot_count(CandleWindow(first_month, stop), Timeframe.MN1))
    ]
    async with migrator_engine.connect() as connection:
        for partition in expected:
            relation = f"public.{partition}"
            found: str | None = (
                await connection.execute(
                    text("SELECT to_regclass(:relation)"), {"relation": relation}
                )
            ).scalar_one()
            assert found == partition
            api: bool = (
                await connection.execute(
                    text("SELECT has_table_privilege('tiewtrade_api',:relation,'SELECT')"),
                    {"relation": relation},
                )
            ).scalar_one()
            worker: bool = (
                await connection.execute(
                    text(
                        "SELECT bool_and(has_table_privilege("
                        "'tiewtrade_market_data',:relation,privilege)) "
                        "FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE']) "
                        "AS privileges(privilege)"
                    ),
                    {"relation": relation},
                )
            ).scalar_one()
            assert api is True and worker is True


@pytest.mark.parametrize(
    ("timeframe", "fault"),
    [
        ("1W", "case"),
        ("1w", "open"),
        ("1w", "end"),
        ("1M", "open"),
        ("1M", "end"),
    ],
)
async def test_week_month_constraints_reject_case_and_calendar_boundary_errors(
    migrator_engine: AsyncEngine, timeframe: str, fault: str
) -> None:
    canonical = Timeframe.W1 if timeframe in {"1W", "1w"} else Timeframe.MN1
    opened = align_floor(datetime.now(UTC), canonical)
    ended = advance(opened, canonical, 1)
    if fault == "open":
        opened += timedelta(days=1)
    elif fault == "end":
        ended -= timedelta(days=1)
    with pytest.raises(DBAPIError) as error:
        async with migrator_engine.begin() as connection:
            await _insert_candle(connection, timeframe, opened, ended)
    assert getattr(error.value.orig, "sqlstate", None) == "23514"


@pytest.mark.parametrize("timeframe", list(Timeframe))
async def test_sql_timeframe_helpers_match_python_across_calendar_edges(
    migrator_engine: AsyncEngine, timeframe: Timeframe
) -> None:
    moments = (
        datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC),
    )
    async with migrator_engine.connect() as connection:
        for moment in moments:
            opened = align_floor(moment, timeframe)
            ended = advance(opened, timeframe, 3)
            row = (
                await connection.execute(
                    text(
                        "SELECT market_timeframe_floor(:tf,:moment),"
                        "market_timeframe_advance(:tf,:opened,3),"
                        "market_timeframe_slots(:tf,:opened,:ended)"
                    ),
                    {
                        "tf": timeframe.value,
                        "moment": moment,
                        "opened": opened,
                        "ended": ended,
                    },
                )
            ).one()
            assert row == (opened, ended, slot_count(CandleWindow(opened, ended), timeframe))
