"""R31 process boundary preserves native publication and fails closed on IPC faults."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.risk_limits.profile_publisher import SourcePublisher
from tests.infra.risk_limits.profile_publisher_process import MAX_MESSAGE, QUEUE_LIMIT, encode
from tests.infra.risk_limits.profile_workload import Fixture
from tests.infra.risk_limits.test_prices import publication as publication
from tiewtrade.core.money import Money
from tiewtrade.infra.db.session import market_data_session
from tiewtrade.infra.market_data.realtime_storage import read_snapshot


async def wait_publications(fixture: Fixture, count: int) -> None:
    async with asyncio.timeout(10):
        while fixture.publisher_stats.get("price_published", 0) < count:
            assert fixture.publisher is not None
            if fixture.publisher.done():
                await fixture.publisher
            await asyncio.sleep(0.01)


@pytest.mark.parametrize("mode", ["inline", "child"])
async def test_controls_commit_receipts_and_restart_preserve_cursor(
    tmp_path: Path, publication: AsyncEngine, mode: str
) -> None:
    fixture = Fixture(tmp_path)
    fixture.publisher_mode = mode
    try:
        fixture.publisher = asyncio.create_task(fixture.publish())
        await wait_publications(fixture, 2)
        await fixture.source_control(price="80", ask_quantity="0.5", finish_partial=True)
        await wait_publications(fixture, int(fixture.publisher_stats["price_published"]) + 2)
        async with market_data_session(publication) as session:
            snapshot = await read_snapshot(session)
        observation = next(r.observation for r in snapshot.rows if r.base == "BTC")
        assert observation is not None and observation.amount == Money.of("80", "USDT")
        assert fixture.publisher_stats["last_ask_quantity"] == "0.5"
        await fixture.source_control(suspend_prices_until=monotonic() + 0.3)
        await fixture.dispose_source_connections()
        fixture.stop_market.set()
        assert fixture.publisher is not None
        await fixture.publisher
        async with market_data_session(publication) as session:
            watermark = (
                await session.execute("SELECT max(id) FROM market_risk_price_frames")
            ).scalar_one()
        assert fixture.last_frame == watermark
        prior = fixture.last_frame
        count = fixture.publisher_stats["price_published"]
        fixture.stop_market.clear()
        fixture.publisher = asyncio.create_task(fixture.publish())
        await wait_publications(fixture, count + 2)
        fixture.stop_market.set()
        await fixture.publisher
        assert fixture.last_frame > prior
        frames = [json.loads(line) for line in (tmp_path / "inputs.jsonl").read_text().splitlines()]
        cursors = [row["cursor"] for row in frames]
        assert cursors == sorted(set(cursors))
        assert cursors[-1] == fixture.last_frame
        receipts = [
            json.loads(line)
            for line in (tmp_path / "source-commits.jsonl").read_text().splitlines()
        ]
        assert len(receipts) == len({(r["kind"], r["pair"], r["identity"]) for r in receipts})
    finally:
        await fixture.close()
    if mode == "child":
        assert fixture.publisher_link.process is not None
        assert fixture.publisher_link.process.returncode == 0
        assert fixture.publisher_link.process in fixture.sampled_processes
    pool = json.loads((tmp_path / "publisher.pools.json").read_text())
    assert pool["finalized"] and pool["pools"][0]["checked_out"] == 0
    assert pool["pools"][0]["pool_size"] == 3 and pool["pools"][0]["max_overflow"] == 0


async def test_child_death_is_not_false_success(tmp_path: Path, publication: AsyncEngine) -> None:
    fixture = Fixture(tmp_path)
    fixture.publisher_mode = "child"
    try:
        fixture.publisher = asyncio.create_task(fixture.publish())
        await wait_publications(fixture, 1)
        assert fixture.publisher_link.process is not None
        fixture.publisher_link.process.kill()
        with pytest.raises(RuntimeError, match="SOURCE_CHANNEL"):
            await asyncio.wait_for(fixture.publisher, 5)
    finally:
        await fixture.close()
    assert fixture.publisher_link.process.returncode is not None


async def test_duplicate_start_fails_without_second_writer(
    tmp_path: Path, publication: AsyncEngine
) -> None:
    fixture = Fixture(tmp_path)
    fixture.publisher_mode = "child"
    try:
        fixture.publisher = asyncio.create_task(fixture.publish())
        await wait_publications(fixture, 1)
        with pytest.raises(RuntimeError, match="SOURCE_CHANNEL"):
            await fixture.publisher_link.request("START")
        assert fixture.publisher is not None
        with pytest.raises(RuntimeError):
            await fixture.publisher
    finally:
        await fixture.close()


async def test_bounded_receipt_channel_never_silently_drops(tmp_path: Path) -> None:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_LIMIT)
    source = SourcePublisher(tmp_path, queue.put)
    source.event_timeout = 0.01
    for n in range(QUEUE_LIMIT):
        await source.source_receipt("BOOK", "BTC/USDT", str(n), datetime.now(UTC))
    with pytest.raises(TimeoutError):
        await source.source_receipt("BOOK", "BTC/USDT", "overflow", datetime.now(UTC))
    assert queue.qsize() == QUEUE_LIMIT
    with pytest.raises(RuntimeError, match="MESSAGE_LIMIT"):
        encode({"payload": "x" * MAX_MESSAGE})


async def test_control_gap_fails_closed(tmp_path: Path, publication: AsyncEngine) -> None:
    fixture = Fixture(tmp_path)
    fixture.publisher_mode = "child"
    try:
        await fixture.source_control(price="100")
        fixture.publisher_link.sequence += 1
        with pytest.raises(RuntimeError, match="SOURCE_CHANNEL"):
            await fixture.source_control(price="80")
        assert fixture.price == "100"  # no parent acknowledgement of uncertain application
    finally:
        await fixture.close()


async def test_control_timeout_is_not_acknowledged(
    tmp_path: Path, publication: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.infra.risk_limits import profile_publisher_process as protocol

    fixture = Fixture(tmp_path)
    fixture.publisher_mode = "child"
    try:
        await fixture.source_control(price="100")
        assert fixture.publisher_link.writer is not None

        async def blocked() -> None:
            await asyncio.sleep(10)

        with monkeypatch.context() as patch:
            patch.setattr(protocol, "CONTROL_TIMEOUT", 0.03)
            patch.setattr(fixture.publisher_link.writer, "drain", blocked)
            with pytest.raises(TimeoutError):
                await fixture.source_control(price="80")
        assert fixture.price == "100"
    finally:
        await fixture.close()


def test_invalid_control_batch_is_atomic(tmp_path: Path) -> None:
    source = SourcePublisher(tmp_path, lambda event: None)
    with pytest.raises(ValueError, match="CONTROL_BOOLEAN"):
        source.configure({"price": "80", "finish_partial": "yes"})
    assert source.price == "100" and not source.finish_partial


@pytest.mark.parametrize("stage", ["ACQUIRE", "BOOK", "PRICE"])
async def test_publication_failure_retains_safe_stage_and_cleans_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    from unittest.mock import AsyncMock

    from tests.infra.execution_market import profile_workload as f15

    source = SourcePublisher(tmp_path, lambda event: None)
    error = TimeoutError("secret-password SQL parameters must never appear")
    sibling_stopped = asyncio.Event()

    async def failed(*args: object) -> None:
        await asyncio.sleep(0)
        raise error

    async def waiting(*args: object) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            sibling_stopped.set()

    monkeypatch.setattr(SourcePublisher, "source_market", property(lambda self: None))
    monkeypatch.setattr(
        f15,
        "acquire_sources",
        failed if stage == "ACQUIRE" else AsyncMock(return_value=(None, None)),
    )
    monkeypatch.setattr(source, "_publish_books", failed if stage == "BOOK" else waiting)
    monkeypatch.setattr(source, "_publish_prices", failed if stage == "PRICE" else waiting)
    with pytest.raises(TimeoutError) as caught:
        await source.publish()
    assert caught.value is error
    evidence = (tmp_path / "publisher-failure.json").read_text()
    assert "secret-password" not in evidence and "SQL" not in evidence
    assert json.loads(evidence)["stage"] == stage
    assert source.failure == {"stage": stage, "category": "TimeoutError"}
    assert stage == "ACQUIRE" or sibling_stopped.is_set()
    source.record_failure(ValueError("cleanup secret"), "PUBLISH")
    assert (tmp_path / "publisher-failure.json").read_text() == evidence


def test_unknown_exception_name_and_message_are_not_recorded(tmp_path: Path) -> None:
    source = SourcePublisher(tmp_path, lambda event: None)
    error = type("secret_class_name", (Exception,), {})("secret message")
    source.record_failure(error, "secret stage")
    evidence = (tmp_path / "publisher-failure.json").read_text()
    assert "secret" not in evidence
    assert source.failure == {"category": "OTHER", "stage": "PUBLISH"}


async def test_child_failure_category_reaches_parent_and_close_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    from tests.infra.risk_limits.profile_publisher_process import PublisherLink, serve

    async def failed(source: SourcePublisher) -> None:
        source.record_failure(TimeoutError("private detail"), "PRICE")
        raise TimeoutError("private detail")

    monkeypatch.setattr(SourcePublisher, "publish", failed)
    parent, child = socket.socketpair()
    parent.setblocking(False)
    child.setblocking(False)
    reader, writer = await asyncio.open_connection(sock=parent)
    child_reader, child_writer = await asyncio.open_connection(sock=child)
    server = asyncio.create_task(serve(child_reader, child_writer, tmp_path))
    link = PublisherLink(tmp_path, lambda event: None, [])
    link.writer = writer
    link.receiver = asyncio.create_task(link.read_events(reader))

    async def connected() -> None:
        pass

    monkeypatch.setattr(link, "connect", connected)
    try:
        with pytest.raises(RuntimeError, match="F18_SOURCE_CHILD_FAILED:PRICE:TimeoutError"):
            await asyncio.wait_for(link.run(asyncio.Event()), 2)
        await asyncio.wait_for(link.request("CLOSE"), 2)
        await asyncio.wait_for(server, 2)
        assert "private" not in (tmp_path / "publisher-failure.json").read_text()
    finally:
        link.closing = True
        link.receiver.cancel()
        server.cancel()
        await asyncio.gather(link.receiver, server, return_exceptions=True)
        writer.close()
        await writer.wait_closed()


async def test_normal_publication_cancellation_does_not_record_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock

    from tests.infra.execution_market import profile_workload as f15

    source = SourcePublisher(tmp_path, lambda event: None)
    started = asyncio.Event()

    async def waiting(*args: object) -> None:
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(SourcePublisher, "source_market", property(lambda self: None))
    monkeypatch.setattr(f15, "acquire_sources", AsyncMock(return_value=(None, None)))
    monkeypatch.setattr(source, "_publish_books", waiting)
    monkeypatch.setattr(source, "_publish_prices", waiting)
    task = asyncio.create_task(source.publish())
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert source.failure is None
    assert not (tmp_path / "publisher-failure.json").exists()
