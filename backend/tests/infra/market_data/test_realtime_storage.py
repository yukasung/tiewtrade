import asyncio
from dataclasses import replace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tiewtrade.core.money import Money
from tiewtrade.core.realtime_prices import ObservationKind, QuoteObservation
from tiewtrade.infra.db import DatabaseRole, create_engine_for, user_session
from tiewtrade.infra.db.errors import SessionKindError
from tiewtrade.infra.db.session import MarketDataSession, market_data_session
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    begin_generation,
    database_now,
    read_snapshot,
    renew_writer,
    set_connected,
    write_price,
)


async def test_durable_fencing_latch_and_revision(api_engine: AsyncEngine) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        async with engine.begin() as connection:
            from sqlalchemy import text

            # Runtime role deliberately has no DELETE; clear using fresh owner takeover.
            await connection.execute(
                text(
                    "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
                )
            )
        async with market_data_session(engine) as session:
            lease = await acquire_writer(session, uuid4())
            assert lease is not None
            assert await acquire_writer(session, uuid4()) is None
            lease = await set_connected(session, lease, True)
            assert lease.connected
            renewed = await renew_writer(session, lease)
            assert renewed.generation == lease.generation
            assert renewed.lease_until > lease.lease_until
            lease = renewed
            snapshot = await read_snapshot(session)
            assert len(snapshot.rows) == 5
            now = await database_now(session)
            row = next(r for r in snapshot.rows if r.base == "BTC")
            quote = QuoteObservation(
                "primary_spot",
                "BTC",
                "USDT",
                Money.of("100", "USDT"),
                2**63 - 1,
                now,
                now,
                ObservationKind.STREAM,
            )
            dirty = replace(
                row, observation=quote, order_ambiguous_at=now, reason="ORDER_UNCONFIRMED"
            )
            assert await write_price(session, lease, dirty)
            assert not await write_price(session, lease, dirty)
            new = await begin_generation(session, lease)
            with pytest.raises(WriterLeaseLost):
                await renew_writer(session, lease)
            persisted = next(r for r in (await read_snapshot(session)).rows if r.base == "BTC")
            assert persisted.order_ambiguous_at == now
            assert persisted.observation is not None
            assert persisted.observation.trade_id == 2**63 - 1
            assert persisted.revision > row.revision
            assert new.generation == lease.generation + 1
        async with user_session(api_engine, uuid4()) as session:
            assert len((await read_snapshot(session)).rows) == 5
    finally:
        await engine.dispose()


async def test_writer_rejects_userless_wrong_session() -> None:
    with pytest.raises(SessionKindError):
        await acquire_writer(cast(MarketDataSession, object()), uuid4())


@pytest.mark.parametrize(
    ("operation", "blocked_table", "row_lock"),
    [
        ("renew", "market_price_feed", False),
        ("generation", "market_price_feed", False),
        ("connected", "market_price_feed", False),
        ("write", "market_latest_prices", False),
        ("generation", "market_latest_prices", False),
        ("connected", "market_latest_prices", False),
        ("write", "market_latest_prices", True),
    ],
)
async def test_expiry_during_sql_wait_rolls_back_writer_mutation(
    operation: str, blocked_table: str, row_lock: bool
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    task: asyncio.Task[None] | None = None
    try:
        async with market_data_session(engine) as session:
            await session.execute(
                "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
            )
            lease = await acquire_writer(session, uuid4())
            assert lease is not None
            # A short real DB-clock lease keeps this race test fast without faking clocks.
            await session.execute(
                "UPDATE market_price_feed SET lease_until=clock_timestamp()+interval '1 second'"
            )
            before = await read_snapshot(session)
            now = before.server_time
            price = next(row for row in before.rows if row.base == "BTC")
            dirty = replace(
                price,
                observation=QuoteObservation(
                    "primary_spot",
                    "BTC",
                    "USDT",
                    Money.of("101", "USDT"),
                    123,
                    now,
                    now,
                    ObservationKind.STREAM,
                ),
                reconciled_generation=lease.generation,
                effective_readiness="READY",
                reason="READY",
            )

        pid_ready: asyncio.Future[int] = asyncio.get_running_loop().create_future()

        async def mutate() -> None:
            async with market_data_session(engine) as session:
                pid_ready.set_result(
                    (await session.execute("SELECT pg_backend_pid()")).scalar_one()
                )
                if operation == "renew":
                    await renew_writer(session, lease)
                elif operation == "generation":
                    await begin_generation(session, lease)
                elif operation == "connected":
                    await set_connected(session, lease, True)
                else:
                    if row_lock:
                        # An earlier successful write must also roll back if a later
                        # price row remains locked until the lease expires.
                        eth = next(row for row in before.rows if row.base == "ETH")
                        assert dirty.observation is not None
                        await write_price(
                            session,
                            lease,
                            replace(
                                eth,
                                observation=replace(dirty.observation, base="ETH"),
                                reconciled_generation=lease.generation,
                                effective_readiness="READY",
                                reason="READY",
                            ),
                        )
                    assert await write_price(session, lease, dirty)

        async with engine.connect() as observer:
            async with engine.begin() as blocker:
                if row_lock:
                    await blocker.execute(
                        text("SELECT * FROM market_latest_prices WHERE base='BTC' FOR UPDATE")
                    )
                else:
                    # SHARE permits the initial FOR UPDATE, but blocks the later UPDATE.
                    await blocker.execute(text(f"LOCK TABLE {blocked_table} IN SHARE MODE"))
                task = asyncio.create_task(mutate())
                pid = await asyncio.wait_for(pid_ready, timeout=3)
                async with asyncio.timeout(3):
                    while True:
                        result = await observer.execute(
                            text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}
                        )
                        blocked: bool = result.scalar_one()
                        if blocked:
                            break
                        if task.done():
                            task.result()
                            pytest.fail("writer did not wait on the SQL lock")
                        await asyncio.sleep(0.01)
                    # Confirm it passed the lease check and is blocked on the mutation.
                    result = await observer.execute(
                        text("SELECT query FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}
                    )
                    query: str = result.scalar_one()
                    assert "UPDATE" in query and blocked_table in query
                    while True:
                        result = await observer.execute(
                            text("SELECT lease_until <= clock_timestamp() FROM market_price_feed")
                        )
                        expired: bool = result.scalar_one()
                        if expired:
                            break
                        await asyncio.sleep(0.01)
            with pytest.raises(WriterLeaseLost):
                await asyncio.wait_for(task, timeout=3)

        async with market_data_session(engine) as session:
            after = await read_snapshot(session)
            assert after.feed == before.feed
            assert after.rows == before.rows
            replacement = await acquire_writer(session, uuid4())
            assert replacement is not None
            assert replacement.generation == lease.generation + 1
            assert all(
                row.reconciled_generation == 0 for row in (await read_snapshot(session)).rows
            )
        with pytest.raises(WriterLeaseLost):
            async with market_data_session(engine) as session:
                await renew_writer(session, lease)
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await engine.dispose()
