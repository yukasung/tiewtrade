"""R12 sources retain independent progress and fail together without orphan tasks."""

import asyncio
import json
from pathlib import Path
from time import monotonic
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.risk_limits import profile_workload as workload
from tests.infra.risk_limits.test_prices import publication as publication
from tiewtrade.infra.db import DatabaseRole, user_session


@pytest.mark.parametrize("failed", ["_publish_books", "_publish_prices"])
async def test_source_failure_cancels_and_joins_other_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: str
) -> None:
    fixture = workload.Fixture(tmp_path)
    started, joined = asyncio.Event(), asyncio.Event()
    error = RuntimeError("source failed")
    monkeypatch.setattr(f15, "acquire_sources", AsyncMock(return_value=(None, None)))

    async def blocked(*args: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            joined.set()

    async def broken(*args: object) -> None:
        await started.wait()
        raise error

    other = "_publish_books" if failed == "_publish_prices" else "_publish_prices"
    monkeypatch.setattr(fixture, other, blocked)
    monkeypatch.setattr(fixture, failed, broken)
    try:
        with pytest.raises(RuntimeError) as caught:
            await asyncio.wait_for(fixture.publish(), 2)
        assert caught.value is error
        assert joined.is_set()
    finally:
        await fixture.close()


async def test_price_fence_wait_does_not_stop_book_and_close_joins_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine_engine: AsyncEngine, owner: UUID
) -> None:
    fixture = workload.Fixture(tmp_path)
    try:
        leases = await f15.acquire_sources(fixture.market)
        monkeypatch.setattr(f15, "acquire_sources", AsyncMock(return_value=leases))
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute("SELECT risk_financial_fence()")
            fixture.publisher = asyncio.create_task(fixture.publish())
            async with asyncio.timeout(3):
                while fixture.publisher_stats.get("published", 0) < 3:
                    if fixture.publisher.done():
                        fixture.publisher.result()
                    await asyncio.sleep(0.01)
            assert fixture.publisher_stats.get("price_published", 0) == 0
            await fixture.close()
            assert fixture.publisher.done()
    finally:
        if not fixture.input_stream.closed:
            await fixture.close()


@pytest.mark.parametrize("trace_enabled", [False, True])
async def test_price_gap_keeps_ordered_book_ticks_and_resumes_frames(
    tmp_path: Path, api_engine: AsyncEngine, publication: AsyncEngine, trace_enabled: bool
) -> None:
    from tiewtrade.infra.db.session import market_data_session

    fixture = workload.Fixture(tmp_path)
    if trace_enabled:
        from tests.infra.risk_limits.profile_source_timing import SourceTimeline

        fixture.source_timeline = SourceTimeline(tmp_path, fixture.source_market)
        fixture.source_timeline.activate(monotonic())
    async with market_data_session(fixture.market) as session:
        previous_input = (
            await session.execute("SELECT coalesce(max(input_id),0) FROM market_execution_buffer")
        ).scalar_one()
    fixture.suspend_prices_until = monotonic() + 60
    fixture.publisher = asyncio.create_task(fixture.publish())
    try:
        async with asyncio.timeout(5):
            while fixture.publisher_stats.get("published", 0) < 3:
                if fixture.publisher.done():
                    fixture.publisher.result()
                await asyncio.sleep(0.01)
            assert fixture.publisher_stats.get("price_published", 0) == 0
            fixture.suspend_prices_until = 0
            while fixture.publisher_stats.get("price_published", 0) < 2:
                if fixture.publisher.done():
                    fixture.publisher.result()
                await asyncio.sleep(0.01)
        fixture.stop_market.set()
        await asyncio.wait_for(fixture.publisher, 3)
        if trace_enabled:
            trace_rows = [
                json.loads(line)
                for line in (tmp_path / "source-timeline.jsonl").read_text().splitlines()
            ]
            queries = [
                query
                for row in trace_rows
                if row["event"] == "CYCLE"
                for tx in row["transactions"]
                for query in tx["queries"]
            ]
            assert queries and all(query["label"] != "OTHER" for query in queries)
        async with market_data_session(fixture.market) as session:
            ids = list(
                (
                    await session.execute(
                        "SELECT input_id FROM market_execution_buffer "
                        "WHERE input_id>:previous ORDER BY input_id",
                        {"previous": previous_input},
                    )
                ).scalars()
            )
            assert len(ids) >= 3 and ids == list(range(ids[0], ids[-1] + 1))
            assert (
                fixture.last_frame
                == (
                    await session.execute("SELECT max(id) FROM market_risk_price_frames")
                ).scalar_one()
            )
    finally:
        await fixture.close()


async def test_normal_stop_waits_for_committed_price_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = workload.Fixture(tmp_path)
    committed, record_tail = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(f15, "acquire_sources", AsyncMock(return_value=(None, None)))

    async def books(*args: object) -> None:
        await committed.wait()
        fixture.stop_market.set()

    async def prices(*args: object) -> None:
        committed.set()
        await record_tail.wait()
        fixture.last_frame = 3

    monkeypatch.setattr(fixture, "_publish_books", books)
    monkeypatch.setattr(fixture, "_publish_prices", prices)
    fixture.publisher = asyncio.create_task(fixture.publish())
    try:
        await committed.wait()
        await fixture.stop_market.wait()
        # Let publish observe the completed book loop before releasing the recorder.
        for _ in range(3):
            await asyncio.sleep(0)
        assert not fixture.publisher.done()
        record_tail.set()
        await asyncio.wait_for(fixture.publisher, 2)
        assert fixture.last_frame == 3
    finally:
        await fixture.close()
