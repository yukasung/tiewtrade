"""NC09 preserves read correctness/deadlines and admission access to the same pool."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.infra.execution_market import profile_workload as f15
from tests.infra.execution_market.profile_parent_poll import ParentPollGate, validate_options
from tiewtrade.core.orders import OrderIntent, OrderStatus
from tiewtrade.infra.db import DatabaseRole, user_session
from tiewtrade.infra.paper_orders.dispatch import OrderCommand


def options() -> argparse.Namespace:
    return argparse.Namespace(
        parent_poll_limit=4,
        phase="SMOKE",
        diagnostics=True,
        r8_claim_budget=True,
        publisher_heartbeat_per_book=True,
        final_tail_drain=True,
        worker_only=False,
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("parent_poll_limit", 0),
        ("parent_poll_limit", 5),
        ("parent_poll_limit", True),
        ("phase", "W1"),
        ("phase", "BASELINE"),
        ("worker_only", True),
        ("diagnostics", False),
        ("r8_claim_budget", False),
        ("publisher_heartbeat_per_book", False),
        ("final_tail_drain", False),
    ],
)
async def test_invalid_profile_rejected_before_side_effects(
    monkeypatch: pytest.MonkeyPatch, key: str, value: Any
) -> None:
    args = options()
    setattr(args, key, value)
    monkeypatch.setattr(f15, "create_engine_for", lambda *a: pytest.fail("allocated engine"))
    with pytest.raises(ValueError, match="poll limit4"):
        await f15.run(args)
    with pytest.raises(ValueError, match="poll limit4"):
        await f15._run(args)


def test_default_and_exact_profile() -> None:
    validate_options(argparse.Namespace())
    validate_options(options())
    gate = ParentPollGate()
    with pytest.raises(ValueError, match="pool5"):
        gate.verify_pool(cast(AsyncEngine, SimpleNamespace(pool=object())))


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"active": 0, "peak": 0, "entered": 0, "exited": 0}

    @asynccontextmanager
    async def session(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        assert kwargs["role"] is DatabaseRole.ENGINE
        state["active"] += 1
        state["entered"] += 1
        state["peak"] = max(state["peak"], state["active"])
        try:
            yield object()
        finally:
            state["active"] -= 1
            state["exited"] += 1

    monkeypatch.setattr(f15, "user_session", session)
    return state


async def test_gate_precedes_session_and_does_not_block_submission(
    sessions: dict[str, Any],
) -> None:
    gate = ParentPollGate()
    release = asyncio.Event()
    entered = asyncio.Event()

    async def read() -> None:
        async with f15.poll_session(cast(AsyncEngine, None), uuid4(), "wait_command", gate):
            if gate.active == 4:
                entered.set()
            await release.wait()

    tasks = [asyncio.create_task(read()) for _ in range(12)]
    try:
        await entered.wait()
        await asyncio.sleep(0)
        assert sessions["active"] == gate.active == 4
        async with vars(f15)["user_session"](None, uuid4(), role=DatabaseRole.ENGINE):
            assert sessions["active"] == 5 and gate.active == 4
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert gate.peak == 4 and gate.active == sessions["active"] == 0
    assert len(gate.rows) == 12 and all(r["acquired"] for r in gate.rows)


@pytest.mark.parametrize("mode", ["deadline", "cancel"])
async def test_waiting_permit_counts_toward_deadline_and_never_opens_session(
    sessions: dict[str, Any], mode: str
) -> None:
    gate = ParentPollGate()
    for _ in range(4):
        await gate.semaphore.acquire()
    task = asyncio.create_task(
        f15.wait_command(
            cast(AsyncEngine, None),
            uuid4(),
            OrderCommand(uuid4(), "PENDING"),
            timeout=0.02,
            poll_gate=gate,
        )
    )
    try:
        if mode == "cancel":
            await asyncio.sleep(0)
            task.cancel()
        with pytest.raises(TimeoutError if mode == "deadline" else asyncio.CancelledError):
            await task
        assert sessions["entered"] == 0 and gate.active == 0
        assert len(gate.rows) == 1 and not gate.rows[0]["acquired"]
        assert gate.rows[0]["gate_wait_seconds"] >= 0
    finally:
        for _ in range(4):
            gate.semaphore.release()


@pytest.mark.parametrize("mode", ["query", "cancel", "cleanup"])
async def test_held_permit_released_on_failure(
    sessions: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    gate = ParentPollGate()
    original = RuntimeError("original failure")
    started = asyncio.Event()

    @asynccontextmanager
    async def broken(*a: Any, **kw: Any) -> AsyncIterator[Any]:
        try:
            yield object()
        finally:
            raise original

    if mode == "cleanup":
        monkeypatch.setattr(f15, "user_session", broken)

    async def operation() -> None:
        async with f15.poll_session(cast(AsyncEngine, None), uuid4(), "wait_status", gate):
            started.set()
            if mode == "query":
                raise original
            if mode == "cancel":
                await asyncio.Event().wait()

    task = asyncio.create_task(operation())
    await started.wait()
    if mode == "cancel":
        task.cancel()
    with pytest.raises(asyncio.CancelledError if mode == "cancel" else RuntimeError) as caught:
        await task
    if mode != "cancel":
        assert caught.value is original
    assert gate.active == 0 and gate.semaphore._value == 4


async def test_pending_missing_failed_command_and_sleep_outside_permit(
    sessions: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = ParentPollGate()
    identifier = uuid4()
    failed = OrderCommand(identifier, "FAILED", failure_code="TEST")
    results = iter([None, OrderCommand(identifier, "PENDING"), failed])
    sleeps = []

    async def read(*a: Any) -> Any:
        assert gate.active == 1
        return next(results)

    async def sleep(seconds: float) -> None:
        assert gate.active == sessions["active"] == 0
        sleeps.append(seconds)

    monkeypatch.setattr(f15, "get_order_command", read)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    assert (
        await f15.wait_command(cast(AsyncEngine, None), uuid4(), failed, poll_gate=gate) is failed
    )
    assert sleeps == [0.25, 0.25] and sessions["entered"] == 3


async def test_projection_required_before_completion_and_gate_wait_in_latency(
    monkeypatch: pytest.MonkeyPatch, sessions: dict[str, Any]
) -> None:
    gate = ParentPollGate()
    counters = f15.Counters()
    latencies: list[float] = []
    projection = asyncio.Event()
    submitted = asyncio.Event()
    owner = SimpleNamespace(user_id=uuid4(), wallet=SimpleNamespace(wallet_id=uuid4()))
    intent = SimpleNamespace(order_id=uuid4())
    command = OrderCommand(uuid4(), "SUCCEEDED")

    async def submit(*a: Any, **kw: Any) -> OrderCommand:
        assert gate.active == 0
        submitted.set()
        return command

    async def get(*a: Any) -> OrderCommand:
        return command

    @asynccontextmanager
    async def session(*a: Any, **kw: Any) -> AsyncIterator[Any]:
        async def execute(*args: Any) -> Any:
            await projection.wait()
            return SimpleNamespace(scalar_one_or_none=lambda: "FILLED")

        yield SimpleNamespace(execute=execute)

    monkeypatch.setattr(f15, "submit_order", submit)
    monkeypatch.setattr(f15, "get_order_command", get)
    monkeypatch.setattr(f15, "user_session", session)
    for _ in range(4):
        await gate.semaphore.acquire()
    task = asyncio.create_task(
        f15.submit_new(
            cast(AsyncEngine, None),
            cast(f15.OwnerState, owner),
            cast(OrderIntent, intent),
            OrderStatus.FILLED,
            counters,
            latencies,
            poll_gate=gate,
        )
    )
    try:
        await submitted.wait()
        await asyncio.sleep(0.02)
        assert counters.admitted == 1 and counters.completed == 0
        for _ in range(4):
            gate.semaphore.release()
        await asyncio.sleep(0)
        assert counters.completed == 0
    finally:
        projection.set()
    await task
    assert counters.completed == 1 and latencies[0] >= 0.02 and gate.active == 0


async def test_gated_baseline_joins_siblings_before_propagating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    joined = []
    entered = asyncio.Event()
    original = ValueError("baseline failure")

    async def operation(value: int) -> None:
        if value == 0:
            await entered.wait()
            raise original
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            joined.append(value)

    with pytest.raises(ValueError) as caught:
        await f15.bounded_map(list(range(8)), operation, join_on_error=True)
    assert caught.value is original and set(joined) == set(range(1, 8))


async def test_limited_observer_preserves_original_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = options()
    args.output = tmp_path / "run"
    original = TimeoutError("cycle")

    async def workload(args: Any, **kw: Any) -> int:
        args.output.mkdir()
        assert kw["parent_runtime"].enabled
        raise original

    monkeypatch.setattr(f15, "_run", workload)
    with pytest.raises(TimeoutError) as caught:
        await f15.run(args)
    assert caught.value is original
    assert json.loads((args.output / "parent-runtime.json").read_text())["closed"]


async def test_real_rls_and_submission_read_coexistence(
    tmp_path: Path, engine_engine: AsyncEngine
) -> None:
    from tests.infra.execution_market.profile_checkpoint_fixture import prepare
    from tests.infra.execution_market.test_dispatch import intent
    from tiewtrade.infra.paper_orders.dispatch import get_order_command, submit_order

    await prepare(tmp_path / "fixture.json")
    doc = json.loads((tmp_path / "fixture.json").read_text())
    owner = UUID(doc["owner"])
    gate = ParentPollGate()
    gate.verify_pool(engine_engine)
    async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
        episode = (
            await session.execute("SELECT episode_id FROM paper_orders LIMIT 1")
        ).scalar_one()
    release = asyncio.Event()
    ready = asyncio.Event()
    tasks = []

    async def hold() -> None:
        async with f15.poll_session(engine_engine, owner, "wait_command", gate):
            if gate.active == 4:
                ready.set()
            await release.wait()

    try:
        tasks = [asyncio.create_task(hold()) for _ in range(8)]
        await ready.wait()
        async with asyncio.timeout(5):
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                command = await submit_order(
                    session, wallet_id=UUID(doc["wallet"]), intent=intent(owner, episode)
                )
        assert gate.active == 4
        async with user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE) as session:
            assert await get_order_command(session, command.command_id) is None
    finally:
        release.set()
        await asyncio.gather(*tasks)
        async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
            await session.execute(
                "UPDATE paper_order_dispatch SET state='TERMINAL',"
                "worker=NULL,claim_id=NULL,lease_until=NULL"
            )
    assert gate.active == 0 and gate.peak == 4


async def test_cycle_keeps_order_and_replay_cancel_identities(
    sessions: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = cast(
        f15.OwnerState,
        SimpleNamespace(
            user_id=uuid4(), wallet=SimpleNamespace(wallet_id=uuid4(), episode_id=uuid4())
        ),
    )
    run_id = uuid4()
    gate = ParentPollGate()
    commands = []
    statuses = []
    labels = []
    from tests.infra.risk_limits.profile_dispatch_timing import _CURRENT

    async def submit(session: Any, *, wallet_id: UUID, intent: OrderIntent) -> OrderCommand:
        commands.append(intent)
        labels.append((_CURRENT.get() or {}).get("phase"))
        return OrderCommand(intent.order_id, "SUCCEEDED")

    async def cancel(session: Any, **kw: Any) -> OrderCommand:
        labels.append((_CURRENT.get() or {}).get("phase"))
        assert kw["order_id"] == commands[1].order_id
        assert kw["idempotency_key"] == f15.identity(run_id, owner.user_id, 0, "cancel-key")
        return OrderCommand(uuid4(), "SUCCEEDED")

    async def wait(engine: Any, owner: Any, command: OrderCommand, **kw: Any) -> OrderCommand:
        assert kw["poll_gate"] is gate
        return command

    async def status(
        engine: Any, owner: Any, order: UUID, expected: OrderStatus, **kw: Any
    ) -> None:
        assert kw["poll_gate"] is gate
        statuses.append(expected)

    monkeypatch.setattr(f15, "submit_order", submit)
    monkeypatch.setattr(f15, "submit_cancel", cancel)
    monkeypatch.setattr(f15, "wait_command", wait)
    monkeypatch.setattr(f15, "wait_status", status)
    counters = f15.Counters()
    latencies: list[float] = []
    await f15.cycle(cast(AsyncEngine, None), owner, run_id, 0, counters, latencies, poll_gate=gate)
    assert commands[1] is commands[2]
    assert [x.order_id for x in commands] == [
        f15.market_buy(owner, run_id, 0).order_id,
        f15.limit_sell(owner, run_id, 0).order_id,
        f15.limit_sell(owner, run_id, 0).order_id,
        f15.market_sell(owner, run_id, 0).order_id,
    ]
    assert labels == ["submit_new", "submit_new", "submit_replay", "submit_cancel", "submit_new"]
    assert statuses == [
        OrderStatus.FILLED,
        OrderStatus.ACCEPTED,
        OrderStatus.CANCELED,
        OrderStatus.FILLED,
    ]
    assert (
        counters.offered == counters.completed == 5 and counters.cycles == 1 and len(latencies) == 5
    )


async def test_outer_cycle_deadline_cancels_waiting_gate(
    sessions: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = ParentPollGate()
    owner = cast(f15.OwnerState, SimpleNamespace(user_id=uuid4()))
    for _ in range(4):
        await gate.semaphore.acquire()
    original_timeout = asyncio.timeout
    monkeypatch.setattr(
        asyncio, "timeout", lambda seconds: original_timeout(0.02 if seconds == 60 else seconds)
    )

    async def cycle(engine: Any, owner: Any, *args: Any, **kw: Any) -> None:
        await f15.wait_command(
            engine,
            owner.user_id,
            OrderCommand(uuid4(), "PENDING"),
            timeout=100,
            poll_gate=kw["poll_gate"],
        )

    monkeypatch.setattr(f15, "cycle", cycle)
    try:
        with pytest.raises(TimeoutError):
            await f15.run_scheduled_cycles(
                cast(AsyncEngine, None), [owner], uuid4(), 1, 10, f15.Counters(), [], poll_gate=gate
            )
        assert (
            sessions["entered"] == 0
            and gate.active == 0
            and gate.rows[0]["outcome"] == "CancelledError"
        )
    finally:
        for _ in range(4):
            gate.semaphore.release()
