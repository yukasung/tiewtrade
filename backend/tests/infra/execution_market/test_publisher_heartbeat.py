"""Test-only publisher liveness cannot renew stale price facts or a lost lease."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.order_book_storage import BookLease
from tiewtrade.infra.market_data.realtime_records import WriterLeaseLost
from tiewtrade.infra.market_data.realtime_storage import (
    acquire_writer,
    read_snapshot,
    renew_writer,
    write_price,
)


@pytest.mark.parametrize("heartbeat", [False, True])
@pytest.mark.parametrize("update_price", [False, True])
async def test_heartbeat_renews_once_without_manufacturing_price_freshness(
    monkeypatch: pytest.MonkeyPatch, heartbeat: bool, update_price: bool
) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        book, price = await f15.acquire_sources(engine)
        book, price = await f15.publish_market(engine, book, price, rebase=True, trade_id=1)
        async with market_data_session(engine) as session:
            before = await read_snapshot(session)
            short_expiry = (
                await session.execute(
                    """UPDATE market_price_feed
                    SET lease_until=clock_timestamp()+interval '2 seconds'
                    RETURNING lease_until"""
                )
            ).scalar_one()
        renew = AsyncMock(wraps=renew_writer)
        write = AsyncMock(wraps=write_price)
        monkeypatch.setattr(f15, "renew_writer", renew)
        monkeypatch.setattr(f15, "write_price", write)
        options: dict[str, Any] = {"heartbeat_per_book": True} if heartbeat else {}
        following_book, following_price = await f15.publish_market(
            engine, book, price, rebase=False, trade_id=2, update_price=update_price, **options
        )
        assert following_book.last_input_id == book.last_input_id + 1
        assert renew.await_count == int(heartbeat or update_price)
        assert write.await_count == int(update_price)
        async with market_data_session(engine) as session:
            after = await read_snapshot(session)
        assert after.feed is not None
        if heartbeat or update_price:
            assert after.feed.lease_until > short_expiry
            assert following_price.generation == price.generation
            assert following_price.owner == price.owner
        else:
            assert after.feed.lease_until == short_expiry
            assert following_price == price
        if not update_price:
            assert after.rows == before.rows  # All price facts/revisions/readiness stay unchanged.
        else:
            row = next(row for row in after.rows if row.base == "BTC")
            assert row.observation is not None and row.observation.trade_id == 2
    finally:
        await engine.dispose()


@pytest.mark.parametrize("stolen", [False, True])
async def test_lost_price_writer_rolls_back_book_and_propagates(stolen: bool) -> None:
    engine = create_engine_for(DatabaseRole.MARKET_DATA)
    try:
        book, price = await f15.acquire_sources(engine)
        book, price = await f15.publish_market(engine, book, price, rebase=True, trade_id=1)
        async with market_data_session(engine) as session:
            await session.execute(
                "UPDATE market_price_feed SET lease_until=clock_timestamp()-interval '1 second'"
            )
            if stolen:
                replacement = await acquire_writer(session, uuid4())
                assert replacement is not None and replacement.generation > price.generation
            before = await read_snapshot(session)
            before_book = (
                await session.execute(
                    "SELECT last_input_id,lease_until FROM market_execution_state"
                )
            ).all()
            before_buffer = (
                await session.execute("SELECT count(*) FROM market_execution_buffer")
            ).scalar_one()
        with pytest.raises(WriterLeaseLost):
            await f15.publish_market(
                engine,
                book,
                price,
                rebase=False,
                trade_id=2,
                update_price=False,
                heartbeat_per_book=True,
            )
        async with market_data_session(engine) as session:
            after = await read_snapshot(session)
            assert after.feed == before.feed and after.rows == before.rows
            assert (
                await session.execute(
                    "SELECT last_input_id,lease_until FROM market_execution_state"
                )
            ).all() == before_book
            assert (
                await session.execute("SELECT count(*) FROM market_execution_buffer")
            ).scalar_one() == before_buffer
    finally:
        await engine.dispose()


@pytest.mark.parametrize("heartbeat", [False, True])
async def test_heartbeat_option_preserves_price_tick_schedule(
    monkeypatch: pytest.MonkeyPatch, heartbeat: bool
) -> None:
    stop = asyncio.Event()
    book = BookLease(f15.PAIR, uuid4(), 1, datetime.now(UTC), 0)
    price = object()
    monkeypatch.setattr(f15, "acquire_sources", AsyncMock(return_value=(book, price)))
    calls = []

    async def publish(engine: Any, book: Any, price: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        if len(calls) == 11:
            stop.set()
        return replace(book, last_input_id=book.last_input_id + 1), price

    monkeypatch.setattr(f15, "publish_market", publish)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    await f15.market_publisher(
        cast(AsyncEngine, None), stop, {"target_hz": 10}, heartbeat_per_book=heartbeat
    )
    assert [call["trade_id"] for call in calls if call["update_price"]] == [1, 10]
    assert all(call["heartbeat_per_book"] is heartbeat for call in calls)
