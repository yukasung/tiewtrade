import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.market_data.test_retention import insert_raw
from tiewtrade.core.market_data import CandleWindow, Timeframe, align_floor
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data import storage
from tiewtrade.infra.market_data.records import RetentionError
from tiewtrade.infra.market_data.storage import (
    enqueue,
    read_candles,
    refresh_due,
    stored_rows,
    validate_window,
    window_needs_work,
)


async def test_duplicate_requests_coalesce(api_engine: AsyncEngine) -> None:
    window = CandleWindow(datetime.now(UTC) - timedelta(minutes=5), datetime.now(UTC))
    async with user_session(api_engine, uuid4()) as session:
        first = await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        second = await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        rows = (
            await session.execute(
                "SELECT count(*) FROM market_candle_demand WHERE base='BTC' AND timeframe='1m'"
            )
        ).scalar_one()
    assert first and second and rows == 1


async def test_empty_read_reports_missing_window(api_engine: AsyncEngine) -> None:
    end = datetime.now(UTC)
    window = CandleWindow(end - timedelta(minutes=2), end)
    async with user_session(api_engine, uuid4()) as session:
        result = await read_candles(session, "ETH", "USDT", Timeframe.M1, window, 1000)
    assert result.candles == ()
    assert result.coverage == "INCOMPLETE"
    assert result.gaps


def test_future_open_is_not_in_current_window() -> None:
    now = datetime.now(UTC)
    future = align_floor(now, Timeframe.M1) + Timeframe.M1.span
    with pytest.raises(RetentionError):
        validate_window(CandleWindow(future, future + timedelta(seconds=1)), now, Timeframe.M1)


async def test_pending_refresh_in_another_window_does_not_leak(api_engine: AsyncEngine) -> None:
    await insert_raw("1", age=timedelta(hours=1))
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            now = (await session.execute("SELECT clock_timestamp()")).scalar_one()
            current = align_floor(now, Timeframe.M1)
            await session.execute(
                """INSERT INTO market_candle_demand
              (source,base,quote,timeframe,desired_start,desired_end,status,refresh_requested_at)
              VALUES ('primary_spot','BTC','USDT','1m',:start,:end,'RUNNING',:now)""",
                {"start": current, "end": current + Timeframe.M1.span, "now": now},
            )
        old = align_floor(now - timedelta(hours=1), Timeframe.M1)
        window = CandleWindow(old, old + Timeframe.M1.span)
        async with user_session(api_engine, uuid4()) as session:
            result = await read_candles(session, "BTC", "USDT", Timeframe.M1, window, 1000)
            pending = await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        assert result.coverage == "PRESENT"
        assert not result.refresh_pending
        assert not pending
    finally:
        await engine.dispose()


async def test_complete_window_does_not_create_pending_demand(api_engine: AsyncEngine) -> None:
    await insert_raw("1", age=timedelta(hours=1))
    end = align_floor(datetime.now(UTC) - timedelta(hours=1), Timeframe.M1) + Timeframe.M1.span
    async with user_session(api_engine, uuid4()) as session:
        pending = await enqueue(
            session, "BTC", "USDT", Timeframe.M1, CandleWindow(end - Timeframe.M1.span, end)
        )
        count = (await session.execute("SELECT count(*) FROM market_candle_demand")).scalar_one()
    assert not pending
    assert count == 0


async def test_concurrent_users_coalesce_one_demand(api_engine: AsyncEngine) -> None:
    end = align_floor(datetime.now(UTC), Timeframe.M1)
    window = CandleWindow(end - timedelta(minutes=3), end)

    async def request() -> bool:
        async with user_session(api_engine, uuid4()) as session:
            return await enqueue(session, "XRP", "USDT", Timeframe.M1, window)

    assert all(await asyncio.gather(request(), request(), request()))
    async with user_session(api_engine, uuid4()) as session:
        assert (
            await session.execute("SELECT count(*) FROM market_candle_demand")
        ).scalar_one() == 1


async def test_year_request_has_two_metadata_checks_without_candle_hydration(
    api_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await insert_raw("1", age=timedelta(minutes=1))
    checks: list[str] = []

    def before_execute(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if "market_candles" in statement.lower():
            checks.append(statement)

    def reject_hydration(row: object) -> None:
        pytest.fail("POST eligibility must not hydrate OHLC observations")

    monkeypatch.setattr(storage, "_stored", reject_hydration)
    event.listen(api_engine.sync_engine, "before_cursor_execute", before_execute)
    try:
        now = datetime.now(UTC)
        window = CandleWindow(now - timedelta(days=365) + timedelta(minutes=1), now)
        async with user_session(api_engine, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
        assert len(checks) == 2
        checks.clear()
        async with user_session(api_engine, uuid4()) as session:
            assert await enqueue(session, "BTC", "USDT", Timeframe.M1, window)
            assert (
                await session.execute("SELECT count(*) FROM market_candle_demand")
            ).scalar_one() == 1
        assert len(checks) == 2
    finally:
        event.remove(api_engine.sync_engine, "before_cursor_execute", before_execute)


@pytest.mark.parametrize(
    "finality,started,checked,observed,expected",
    [
        ("CLOSED", 10, 20, 100, False),
        ("UNCONFIRMED", 10, 20, 49, False),
        ("UNCONFIRMED", 10, 20, 50, True),
        ("OPEN", 10, 20, 50, True),
        ("UNCONFIRMED", 10, 59, 60, True),
        ("UNCONFIRMED", 60, 62, 300, False),
        ("UNCONFIRMED", 40, 40, 40, False),
    ],
)
async def test_metadata_refresh_matches_existing_predicate(
    api_engine: AsyncEngine,
    finality: str,
    started: int,
    checked: int,
    observed: int,
    expected: bool,
) -> None:
    opened = align_floor(datetime.now(UTC) - timedelta(hours=1), Timeframe.M1)
    window = CandleWindow(opened, opened + Timeframe.M1.span)
    as_of = opened + timedelta(seconds=observed)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as session:
            await session.execute(
                """INSERT INTO market_candles
                (source,base,quote,timeframe,open_at,end_at,open,high,low,close,volume,finality,
                 observed_at,fetch_started_at,last_checked_at,ingestion_generation)
                VALUES ('primary_spot','BTC','USDT','1m',:open_at,:end_at,1,1,1,1,0,:finality,
                  :checked,:started,:checked,1)""",
                {
                    "open_at": opened,
                    "end_at": window.end,
                    "finality": finality,
                    "started": opened + timedelta(seconds=started),
                    "checked": opened + timedelta(seconds=checked),
                },
            )
        async with user_session(api_engine, uuid4()) as session:
            rows = await stored_rows(session, "BTC", "USDT", Timeframe.M1, window)
            assert refresh_due(rows[0], as_of) == expected
            assert await window_needs_work(session, "BTC", "USDT", Timeframe.M1, window, as_of) == (
                False,
                expected,
            )
            missing = CandleWindow(opened - timedelta(minutes=1), window.end)
            assert await window_needs_work(
                session, "BTC", "USDT", Timeframe.M1, missing, as_of
            ) == (True, expected)
            empty = CandleWindow(opened + timedelta(microseconds=1), opened + timedelta(seconds=1))
            assert await window_needs_work(session, "BTC", "USDT", Timeframe.M1, empty, as_of) == (
                False,
                False,
            )
    finally:
        await engine.dispose()
