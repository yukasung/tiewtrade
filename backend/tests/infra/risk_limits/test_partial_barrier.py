"""Single-delivery IPC and bounded failure semantics for NC17."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.infra.risk_limits.profile_partial_barrier import PartialBarrier, consumer_barrier
from tests.infra.risk_limits.profile_publisher_process import encode, receive
from tiewtrade.core.money import Quantity
from tiewtrade.core.orders import TradingMode
from tiewtrade.core.paper_matching import MatchingState
from tiewtrade.infra.db.session import UserSession
from tiewtrade.infra.paper_orders import worker
from tiewtrade.services.engine import paper_order


def identity() -> dict[str, Any]:
    return {
        **{k: str(uuid4()) for k in ("run", "key", "owner", "wallet", "episode", "order")},
        "base": "BTC",
        "quote": "USDT",
        "generation": 1,
    }


async def connect(barrier: PartialBarrier) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    async with asyncio.timeout(1):
        while not barrier.control.exists():
            await asyncio.sleep(0)
    endpoint = json.loads(barrier.control.read_text())["endpoint"]
    return await asyncio.open_unix_connection(endpoint)


@pytest.mark.asyncio
async def test_single_delivery_and_following_read_ack(tmp_path: Path) -> None:
    barrier = PartialBarrier(tmp_path)
    value = identity()
    receipt = {"key": value["key"], "generation": 1, "input_id": 12}
    publish = AsyncMock(return_value=receipt)
    task = asyncio.create_task(barrier.deliver(value, publish, deadline=monotonic() + 2))
    reader, writer = await connect(barrier)
    writer.write(encode({"stage": "READY", "identity": value, "generation": 1, "book_input": 10}))
    await writer.drain()
    committed = await receive(reader)
    assert committed["receipt"] == receipt
    writer.write(encode({"stage": "CONSUMED", "identity": value, "inputs": [10, 11, 12]}))
    await writer.drain()
    assert await task == receipt
    writer.close()
    await writer.wait_closed()
    publish.assert_awaited_once()
    assert not barrier.control.exists() and not barrier.handlers and barrier.server is None
    assert [json.loads(line)["stage"] for line in barrier.journal.read_text().splitlines()] == [
        "ARMED",
        "READY",
        "PUBLICATION_REQUESTED",
        "COMMITTED",
        "CONSUMED",
        "CLOSED",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    ["identity", "generation", "unknown_commit", "missing_input", "disconnect", "duplicate"],
)
async def test_failure_never_republishes(tmp_path: Path, fault: str) -> None:
    barrier = PartialBarrier(tmp_path)
    value = identity()
    publish = AsyncMock(return_value={"key": value["key"], "generation": 1, "input_id": 12})
    if fault == "unknown_commit":
        publish.side_effect = ConnectionError("TEST_ONLY_DO_NOT_LOG")
    task = asyncio.create_task(barrier.deliver(value, publish, deadline=monotonic() + 2))
    reader, writer = await connect(barrier)
    ready = {"stage": "READY", "identity": value, "generation": 1, "book_input": 10}
    if fault == "identity":
        ready["identity"] = {**value, "owner": str(uuid4())}
    if fault == "generation":
        ready["generation"] = 2
    writer.write(encode(ready))
    await writer.drain()
    if fault in {"missing_input", "disconnect", "duplicate"}:
        await receive(reader)
        if fault == "missing_input":
            writer.write(encode({"stage": "CONSUMED", "identity": value, "inputs": [11]}))
            await writer.drain()
        elif fault == "duplicate":
            other_reader, other_writer = await connect(barrier)
            other_writer.write(encode(ready))
            await other_writer.drain()
            await other_reader.read()
            other_writer.close()
            await other_writer.wait_closed()
        else:
            writer.close()
    with pytest.raises(RuntimeError, match="F19_BARRIER_DELIVERY_FAILED"):
        await task
    writer.close()
    await writer.wait_closed()
    assert publish.await_count == (0 if fault in {"identity", "generation"} else 1)
    assert not barrier.control.exists() and not barrier.handlers
    assert "TEST_ONLY_DO_NOT_LOG" not in barrier.journal.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_no_ready_or_parent_cancel_has_bounded_cleanup(tmp_path: Path, cancel: bool) -> None:
    barrier = PartialBarrier(tmp_path)
    publish = AsyncMock()
    task = asyncio.create_task(barrier.deliver(identity(), publish, deadline=monotonic() + 0.05))
    if cancel:
        while not barrier.control.exists():
            await asyncio.sleep(0)
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    assert not barrier.control.exists() and not barrier.handlers and barrier.server is None
    publish.assert_not_called()


def test_worker_patches_restore_even_on_error(tmp_path: Path) -> None:
    original = (
        worker._recovery_inputs,
        vars(worker)["read_latest_book"],
        vars(paper_order)["process_claimed_order"],
    )
    with pytest.raises(RuntimeError, match="test"), consumer_barrier(tmp_path / "absent.json"):
        assert worker._recovery_inputs is not original[0]
        raise RuntimeError("test")
    assert (
        worker._recovery_inputs,
        vars(worker)["read_latest_book"],
        vars(paper_order)["process_claimed_order"],
    ) == original


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["unarmed", "other_owner", "stale"])
async def test_wrapper_preserves_untargeted_reads_and_rejects_stale_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    value = identity()
    control = tmp_path / "control.json"
    if kind != "unarmed":
        control.write_text(json.dumps({"identity": value, "endpoint": "must-not-connect"}))
    now = datetime.now(UTC)
    record = SimpleNamespace(market=SimpleNamespace(received_at=now - timedelta(seconds=2)))
    book = AsyncMock(return_value=record)

    async def original_recovery(session: object, state: object) -> object:
        typed_state = cast(MatchingState, state)
        return await vars(worker)["read_latest_book"](session, typed_state.pair)

    async def original_process(session: object, claim: object) -> object:
        return await worker._recovery_inputs(cast(UserSession, session), cast(MatchingState, state))

    monkeypatch.setattr(worker, "read_latest_book", book)
    monkeypatch.setattr(worker, "_recovery_inputs", original_recovery)
    monkeypatch.setattr(paper_order, "process_claimed_order", original_process)
    session = SimpleNamespace(
        user_id=value["owner"] if kind != "other_owner" else str(uuid4()),
        execute=AsyncMock(
            return_value=SimpleNamespace(
                one=lambda: SimpleNamespace(wallet_id=value["wallet"], now=now)
            )
        ),
    )
    state = SimpleNamespace(
        scope=SimpleNamespace(episode_id=value["episode"], mode=TradingMode.PAPER),
        pair=SimpleNamespace(base="BTC", quote="USDT"),
        orders=[
            SimpleNamespace(
                intent=SimpleNamespace(order_id=value["order"]),
                resting=True,
                status=SimpleNamespace(terminal=False),
                queue_ahead=Quantity.of(0, "BTC"),
            )
        ],
    )
    with consumer_barrier(control):
        if kind == "stale":
            with pytest.raises(TimeoutError, match="CAPTURED_BOOK_STALE"):
                await vars(paper_order)["process_claimed_order"](session, object())
        else:
            assert await vars(paper_order)["process_claimed_order"](session, object()) is record
            session.execute.assert_not_called()
