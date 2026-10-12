from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.candle_preview import CandleObservation
from tiewtrade.core.market_data import Candle, CandleFinality, Timeframe, align_floor
from tiewtrade.core.money import Money, Quantity
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.candle_preview import (
    PreviewLeaseLostError,
    acquire,
    connection,
    enqueue_ended,
    flush,
)


def observation() -> CandleObservation:
    now = datetime.now(UTC)
    opened = align_floor(now, Timeframe.H1)
    candle = Candle(
        "BTC",
        "USDT",
        Timeframe.H1,
        opened,
        opened + timedelta(hours=1),
        Money.of("100.000000000000000001", "USDT"),
        Money.of(101, "USDT"),
        Money.of(99, "USDT"),
        Money.of(100, "USDT"),
        Quantity.of(1, "BTC"),
        CandleFinality.OPEN,
        now,
    )
    return CandleObservation(candle, now, now, 1, 1, 1, False)


@pytest_asyncio.fixture
async def market_data_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        yield engine
    finally:
        await engine.dispose()


async def test_single_owner_fencing_and_two_slot_cap(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    async with market_data_session(market_data_engine) as s:
        assert await acquire(s, uuid4()) is None
        active = await connection(s, lease, True)
    with pytest.raises(PreviewLeaseLostError):
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((observation(), 1),))
    initial = observation()
    for number in range(3):
        candle = replace(
            initial.candle,
            open_at=initial.candle.open_at + number * timedelta(hours=1),
            end_at=initial.candle.end_at + number * timedelta(hours=1),
        )
        async with market_data_session(market_data_engine) as s:
            await flush(s, active, ((replace(initial, candle=candle), number + 1),))
    async with market_data_session(market_data_engine) as s:
        rows = (await s.execute("SELECT open_at FROM market_candle_preview ORDER BY open_at")).all()
        assert len(rows) == 2 and rows[0][0] == initial.candle.open_at + timedelta(hours=1)


async def test_failed_preview_transaction_rolls_back_and_old_owner_cannot_publish(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    with pytest.raises(RuntimeError, match="rollback"):
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((observation(), 1),))
            raise RuntimeError("rollback")
    async with migrator_engine.begin() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_preview"))
        ).scalar_one() == 0
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
    async with market_data_session(market_data_engine) as s:
        successor = await acquire(s, uuid4())
        assert successor is not None and successor.epoch > lease.epoch
        await flush(s, successor, ((observation(), 1),))
    with pytest.raises(PreviewLeaseLostError):
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, ((observation(), 2),))
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT epoch FROM market_candle_preview"))
        ).scalar_one() == successor.epoch


async def test_thirty_series_never_store_more_than_two_slots_each(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))
        await c.execute(text("DELETE FROM market_candle_preview"))
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    now = datetime.now(UTC)
    for slot in range(3):
        batch = []
        for base in ("BTC", "ETH", "SOL", "XRP", "DOGE"):
            for tf in Timeframe:
                opened = align_floor(now, tf) + slot * tf.span
                original = observation()
                candle = replace(
                    original.candle,
                    base=base,
                    timeframe=tf,
                    open_at=opened,
                    end_at=opened + tf.span,
                    volume=Quantity.of(1, base),
                )
                batch.append((replace(original, candle=candle), slot + 1))
        async with market_data_session(market_data_engine) as s:
            await flush(s, lease, tuple(batch))
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_preview"))
        ).scalar_one() == 60
        counts = [
            int(row[0])
            for row in (
                await c.execute(
                    text("SELECT count(*) FROM market_candle_preview GROUP BY base,quote,timeframe")
                )
            ).all()
        ]
        assert len(counts) == 30 and set(counts) == {2}


async def test_ended_demand_is_transactional_and_never_resets_a_worker_claim(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    from tiewtrade.core.market_data import CandleWindow

    async with migrator_engine.begin() as c:
        await c.execute(
            text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp(),metadata='{}'")
        )
    async with market_data_session(market_data_engine) as s:
        lease = await acquire(s, uuid4())
        assert lease is not None
    now = datetime.now(UTC)
    end = align_floor(now, Timeframe.H1)
    window = CandleWindow(end - Timeframe.H1.span, end)
    demands = {("BTC", "USDT", Timeframe.H1): window}
    with pytest.raises(RuntimeError, match="rollback"):
        async with market_data_session(market_data_engine) as s:
            await enqueue_ended(s, lease, demands)
            raise RuntimeError("rollback")
    async with migrator_engine.connect() as c:
        assert (
            await c.execute(text("SELECT count(*) FROM market_candle_demand"))
        ).scalar_one() == 0
        assert (
            await c.execute(text("SELECT metadata FROM market_candle_feed_state"))
        ).scalar_one() == {}
    async with market_data_session(market_data_engine) as s:
        await enqueue_ended(s, lease, demands)
    from tiewtrade.infra.market_data.claims import claim_next, update_claim

    async with market_data_session(market_data_engine) as s:
        claim = await claim_next(s, "f12-active-fetch")
        assert claim is not None
        await update_claim(
            s,
            claim,
            attemptcount=2,
            fetch_unit_id=uuid4(),
            fetch_start=window.start,
            fetch_end=window.end,
            next_attempt_at=now + timedelta(minutes=1),
        )
        before = (await s.execute("SELECT * FROM market_candle_demand")).mappings().one()
        await enqueue_ended(s, lease, demands)
        after = (await s.execute("SELECT * FROM market_candle_demand")).mappings().one()
        assert dict(before) == dict(after)


async def test_competing_owners_have_exactly_one_winner(
    market_data_engine: AsyncEngine,
    migrator_engine: AsyncEngine,
) -> None:
    import asyncio

    async with migrator_engine.begin() as c:
        await c.execute(text("UPDATE market_candle_feed_state SET lease_until=clock_timestamp()"))

    async def claim() -> object:
        async with market_data_session(market_data_engine) as s:
            return await acquire(s, uuid4())

    results = await asyncio.gather(claim(), claim())
    assert sum(result is not None for result in results) == 1
