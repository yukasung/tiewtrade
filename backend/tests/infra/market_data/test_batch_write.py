from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.market_data import Candle, CandleFinality, CandleWindow, Timeframe, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.claims import Claim, claim_next, write_candles
from tiewtrade.infra.market_data.storage import enqueue


def candle_at(
    opened: datetime,
    observed: datetime,
    amount: str = "1",
    finality: CandleFinality = CandleFinality.UNCONFIRMED,
) -> Candle:
    price = Money.of(amount, "USDT")
    return Candle(
        "BTC",
        "USDT",
        Timeframe.M1,
        opened,
        opened + Timeframe.M1.span,
        price,
        price,
        price,
        price,
        Quantity.of("1", "BTC"),
        finality,
        observed,
    )


async def claim_window(api_engine: AsyncEngine, engine: AsyncEngine, window: CandleWindow) -> Claim:
    async with user_session(api_engine, uuid4()) as api_session:
        await enqueue(api_session, "BTC", "USDT", Timeframe.M1, window)
    async with market_data_session(engine) as market_session:
        claim = await claim_next(market_session, "batch-fixture")
        assert claim is not None
        return claim


async def test_thousand_candles_write_with_five_sql_calls_and_exact_values(
    api_engine: AsyncEngine,
) -> None:
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.M1) + Timeframe.M1.span
    start = end - timedelta(minutes=1000)
    window = CandleWindow(start, end)
    exact = Money.of("123.000000000000000001", "USDT")
    volume = Quantity.of("0.000000000000000001", "BTC")
    candles = tuple(
        Candle(
            "BTC",
            "USDT",
            Timeframe.M1,
            start + index * Timeframe.M1.span,
            start + (index + 1) * Timeframe.M1.span,
            exact,
            exact,
            exact,
            exact,
            volume,
            CandleFinality.UNCONFIRMED,
            now,
        )
        for index in range(1000)
    )
    async with user_session(api_engine, uuid4()) as api_session:
        await enqueue(api_session, "BTC", "USDT", Timeframe.M1, window)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as market_session:
            claim = await claim_next(market_session, "batch-test")
            assert claim is not None
        calls: list[str] = []

        def before_execute(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            calls.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", before_execute)
        try:
            async with market_data_session(engine) as market_session:
                calls.clear()
                await write_candles(market_session, claim, candles, now)
            assert len(calls) == 5
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", before_execute)
        async with user_session(api_engine, uuid4()) as api_session:
            rows = (
                await api_session.execute("SELECT open::text,volume::text FROM market_candles")
            ).all()
        assert len(rows) == 1000
        assert all(row == ("123.000000000000000001", "0.000000000000000001") for row in rows)
    finally:
        await engine.dispose()


async def test_batch_preserves_ordered_versions_of_the_same_open(api_engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    opened = align_floor(now, Timeframe.M1) - Timeframe.M1.span
    window = CandleWindow(opened, opened + Timeframe.M1.span)
    one = Money.of("1", "USDT")
    first = Candle(
        "BTC",
        "USDT",
        Timeframe.M1,
        opened,
        window.end,
        one,
        one,
        one,
        one,
        Quantity.of("1", "BTC"),
        CandleFinality.UNCONFIRMED,
        now - timedelta(seconds=30),
    )
    two = Money.of("2", "USDT")
    newer = replace(first, open=two, high=two, low=two, close=two, observed_at=now)
    async with user_session(api_engine, uuid4()) as api_session:
        await enqueue(api_session, "BTC", "USDT", Timeframe.M1, window)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with market_data_session(engine) as market_session:
            claim = await claim_next(market_session, "ordered-batch")
            assert claim is not None
            await write_candles(market_session, claim, (first, newer, first, newer), now)
        async with user_session(api_engine, uuid4()) as api_session:
            rows = (
                await api_session.execute("SELECT open::text,observed_at FROM market_candles")
            ).all()
        assert [tuple(row) for row in rows] == [("2", now)]
    finally:
        await engine.dispose()


async def test_batch_preserves_closed_and_newer_observations(api_engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    start = align_floor(now, Timeframe.M1) - timedelta(minutes=2)
    closed = candle_at(start, now - timedelta(seconds=30), finality=CandleFinality.CLOSED)
    current = candle_at(start + Timeframe.M1.span, now, "2")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        claim = await claim_window(api_engine, engine, CandleWindow(start, current.end_at))
        async with market_data_session(engine) as market_session:
            await write_candles(market_session, claim, (closed, current), now)
        later_open = candle_at(start, now, "3")
        older = candle_at(current.open_at, now - timedelta(seconds=1), "3")
        async with market_data_session(engine) as market_session:
            await write_candles(market_session, claim, (later_open, older), now)
        async with user_session(api_engine, uuid4()) as api_session:
            rows = (
                await api_session.execute(
                    "SELECT open::text,finality,observed_at FROM market_candles ORDER BY open_at"
                )
            ).all()
        assert [tuple(row) for row in rows] == [
            ("1", "CLOSED", closed.observed_at),
            ("2", "UNCONFIRMED", now),
        ]
    finally:
        await engine.dispose()


async def test_same_version_conflict_rejects_whole_batch(api_engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    start = align_floor(now, Timeframe.M1) - timedelta(minutes=2)
    original = candle_at(start, now)
    fresh = candle_at(start + Timeframe.M1.span, now)
    conflicting = candle_at(start, now, "2")
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        claim = await claim_window(api_engine, engine, CandleWindow(start, fresh.end_at))
        async with market_data_session(engine) as market_session:
            await write_candles(market_session, claim, (original,), now)
        with pytest.raises(ValueError, match="CONFLICTING_CANDLE_OBSERVATION"):
            async with market_data_session(engine) as market_session:
                await write_candles(market_session, claim, (fresh, conflicting), now)
        async with user_session(api_engine, uuid4()) as api_session:
            rows = (
                await api_session.execute("SELECT open_at,open::text FROM market_candles")
            ).all()
            assert [tuple(row) for row in rows] == [(start, "1")]
    finally:
        await engine.dispose()


async def test_batch_spanning_partitions_uses_one_partition_lookup(api_engine: AsyncEngine) -> None:
    now = datetime.now(UTC)
    boundary = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    first = candle_at(boundary - Timeframe.M1.span, now)
    second = candle_at(boundary, now)
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        claim = await claim_window(api_engine, engine, CandleWindow(first.open_at, second.end_at))
        lookups: list[str] = []

        def before_execute(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            if "to_regclass" in statement:
                lookups.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", before_execute)
        try:
            async with market_data_session(engine) as market_session:
                await write_candles(market_session, claim, (first, second), now)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", before_execute)
        assert len(lookups) == 1
        async with user_session(api_engine, uuid4()) as api_session:
            assert (
                await api_session.execute("SELECT count(*) FROM market_candles")
            ).scalar_one() == 2
    finally:
        await engine.dispose()
