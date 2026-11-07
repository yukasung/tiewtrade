"""NC10: shared PostgreSQL selection, unchanged owner claims and parallel processing."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.infra.execution_market.commit_proxy import drop_commit_reply
from tests.infra.positions.conftest import create_production_wallet
from tiewtrade.core.orders import OrderConflictError
from tiewtrade.infra.db import (
    DatabaseRole,
    create_engine_for,
    scan_session_bypassing_rls,
    user_session,
)
from tiewtrade.infra.db.errors import InfraError
from tiewtrade.infra.paper_orders.dispatch import (
    ClaimedOrder,
    DueOrder,
    OrderClaimLostError,
    claim_order,
    due_orders,
    require_claim,
    submit_order,
    try_lock_order_selection,
)
from tiewtrade.infra.users import create_user
from tiewtrade.services.engine import paper_order


@pytest.fixture
async def queued_owners(
    api_engine: AsyncEngine, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> AsyncIterator[list[tuple[UUID, list[UUID]]]]:
    from tests.infra.execution_market.test_dispatch import intent

    owners: list[tuple[UUID, list[UUID]]] = []
    try:
        for _ in range(2):
            owner = uuid4()
            await create_user(api_engine, owner)
            wallet = await create_production_wallet(api_engine, engine_engine, scan_engine, owner)
            ids: list[UUID] = []
            owners.append((owner, ids))
            for _ in range(2):
                async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                    command = await submit_order(
                        session,
                        wallet_id=wallet.wallet_id,
                        intent=intent(owner, wallet.episode_id),
                    )
                ids.append(command.command_id)
        yield owners
    finally:
        for owner, _ in owners:
            async with user_session(engine_engine, owner, role=DatabaseRole.ENGINE) as session:
                # Retire only this test's dispatch hints; keep durable fixture history.
                await session.execute(
                    """UPDATE paper_order_dispatch SET state='TERMINAL',
                    worker=NULL,claim_id=NULL,lease_until=NULL"""
                )


async def run(engine: AsyncEngine, scan: AsyncEngine, **kwargs: Any) -> paper_order.PaperOrderRound:
    return await paper_order.run_paper_order_round(
        engine=engine,
        scan_engine=scan,
        worker="coordination-test",
        policy=None,
        claim_limit=1,
        **kwargs,
    )


@pytest.mark.parametrize(
    "options",
    [
        {"coordinate_claims": 1},
        {"coordinate_claims": True, "claim_limit": None},
        {"coordinate_claims": True, "claim_limit": True},
        {"coordinate_claims": True, "limit": 19},
        {"coordinate_claims": True, "limit": 20.0},
        {"coordinate_claims": True, "prefer_same_pair": True},
        {"coordinate_claims": True, "source_resumption": True},
        {"coordinate_claims": True, "prefer_same_pair": True, "admission_first": True},
    ],
)
async def test_invalid_mode_fails_before_sessions(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        paper_order, "scan_session_bypassing_rls", lambda *a, **k: pytest.fail("DB")
    )
    with pytest.raises(ValueError):
        await paper_order.run_paper_order_round(
            engine=object(),  # type: ignore[arg-type]
            scan_engine=object(),  # type: ignore[arg-type]
            worker="invalid",
            policy=None,
            **{"claim_limit": 1, **options},
        )


@pytest.mark.parametrize("coordinated", [False, True])
async def test_controlled_stale_hint_collision_and_parallel_processing(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
    coordinated: bool,
) -> None:
    scan_barrier = asyncio.Event()
    processing = asyncio.Event()
    release = asyncio.Event()
    scanned = 0
    processed: list[UUID] = []
    attempts: list[UUID] = []
    original_scan, original_claim = due_orders, claim_order

    async def scan(*args: Any, **kwargs: Any) -> tuple[DueOrder, ...]:
        nonlocal scanned
        result = await original_scan(*args, **kwargs)
        scanned += 1
        if not coordinated:
            if scanned == 2:
                scan_barrier.set()
            await scan_barrier.wait()  # Both legacy workers retain the same stale snapshot.
        return result

    async def claim(*args: Any, **kwargs: Any) -> ClaimedOrder | None:
        attempts.append(args[1].command_id)
        return await original_claim(*args, **kwargs)

    async def process(session: Any, value: ClaimedOrder, **kwargs: Any) -> None:
        processed.append(value.command_id)
        if len(processed) == 2:
            processing.set()
        await release.wait()

    monkeypatch.setattr(paper_order, "due_orders", scan)
    monkeypatch.setattr(paper_order, "claim_order", claim)
    monkeypatch.setattr(paper_order, "process_claimed_order", process)
    # Prewarm the scan pool and verify its actual isolation, not a mocked connection.
    async with scan_session_bypassing_rls(scan_engine) as session:
        assert (
            await session.execute("SHOW transaction_isolation")
        ).scalar_one() == "read committed"

    async def rounds() -> None:
        while True:
            result = await run(engine_engine, scan_engine, coordinate_claims=coordinated)
            if result.processed:
                return

    tasks = [asyncio.create_task(rounds()) for _ in range(2)]
    try:
        async with asyncio.timeout(5):
            await processing.wait()
        assert set(processed) == {ids[0] for _, ids in queued_owners}
        assert len(attempts) == (2 if coordinated else 3)
        # Both processors are alive: the coordinator is not held through processing.
        assert not any(task.done() for task in tasks)
    finally:
        release.set()
        await asyncio.gather(*tasks)
    assert (
        cast(Any, engine_engine.pool).checkedout() == cast(Any, scan_engine.pool).checkedout() == 0
    )


async def test_unclaimable_owner_does_not_block_next_candidate(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
) -> None:
    first, second = queued_owners
    processed = AsyncMock()
    monkeypatch.setattr(paper_order, "process_claimed_order", processed)
    async with user_session(engine_engine, first[0], role=DatabaseRole.ENGINE) as session:
        await session.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
            {"key": f"paper-wallet:{first[0]}"},
        )
        result = await run(engine_engine, scan_engine, coordinate_claims=True)
    assert result == paper_order.PaperOrderRound(processed=1, skipped=1)
    assert processed.call_args.args[1].command_id == second[1][0]


@pytest.mark.parametrize("waiting", [False, True])
@pytest.mark.parametrize("expire", [False, True])
async def test_cancellation_or_deadline_releases_gate_without_claim(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
    waiting: bool,
    expire: bool,
) -> None:
    entered = asyncio.Event()
    original_lock = try_lock_order_selection
    original_timeout = asyncio.timeout
    if expire:
        monkeypatch.setattr(
            asyncio, "timeout", lambda seconds: original_timeout(0.1 if seconds == 5 else seconds)
        )

    async def observe_lock(session: Any) -> bool:
        if not waiting:
            assert await original_lock(session)
        entered.set()
        # Hold at the acquisition call or after successful acquisition. V2 does
        # not wait on a busy PG gate; that explicit outcome has separate tests.
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(paper_order, "try_lock_order_selection", observe_lock)
    claim = AsyncMock(side_effect=AssertionError("claim reached"))
    monkeypatch.setattr(paper_order, "claim_order", claim)

    task = asyncio.create_task(run(engine_engine, scan_engine, coordinate_claims=True))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        if not expire:
            task.cancel()
        with pytest.raises(TimeoutError if expire else asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    claim.assert_not_awaited()
    async with asyncio.timeout(3), scan_session_bypassing_rls(scan_engine) as scan:
        assert await try_lock_order_selection(scan)
    assert (
        cast(Any, engine_engine.pool).checkedout() == cast(Any, scan_engine.pool).checkedout() == 0
    )


async def test_repeatable_read_rejected_before_scanning(scan_engine: AsyncEngine) -> None:
    repeatable = create_async_engine(scan_engine.url, isolation_level="REPEATABLE READ")
    try:
        async with scan_session_bypassing_rls(repeatable) as scan:
            with pytest.raises(OrderConflictError, match="read committed"):
                assert await try_lock_order_selection(scan)
    finally:
        await repeatable.dispose()


@pytest.mark.parametrize("cancel_backoff", [False, True])
async def test_busy_returns_connections_before_backoff_and_later_round_can_claim(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
    cancel_backoff: bool,
) -> None:
    holder = create_async_engine(scan_engine.url)
    backoff, release = asyncio.Event(), asyncio.Event()
    original_sleep = asyncio.sleep
    scan = AsyncMock(wraps=due_orders)
    claim = AsyncMock(wraps=claim_order)
    process = AsyncMock()
    maintenance = AsyncMock(wraps=vars(paper_order)["reconcile_maintenance_proofs"])

    async def sleep(seconds: float) -> None:
        if seconds != 0.250:
            await original_sleep(seconds)
            return
        assert cast(Any, scan_engine.pool).checkedout() == 0
        assert cast(Any, engine_engine.pool).checkedout() == 0
        scan.assert_not_awaited()
        claim.assert_not_awaited()
        process.assert_not_awaited()
        backoff.set()
        await release.wait()

    monkeypatch.setattr(paper_order, "due_orders", scan)
    monkeypatch.setattr(paper_order, "claim_order", claim)
    monkeypatch.setattr(paper_order, "process_claimed_order", process)
    monkeypatch.setattr(paper_order, "reconcile_maintenance_proofs", maintenance)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    try:
        async with scan_session_bypassing_rls(holder) as session:
            await session.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
                {"key": "paper-order-selection:v1"},
            )
            task = asyncio.create_task(run(engine_engine, scan_engine, coordinate_claims=True))
            try:
                await asyncio.wait_for(backoff.wait(), 3)
                if cancel_backoff:
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    maintenance.assert_not_awaited()
                else:
                    release.set()
                    assert await task == paper_order.PaperOrderRound()
                    maintenance.assert_awaited_once()
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        assert (await run(engine_engine, scan_engine, coordinate_claims=True)).processed == 1
        claim.assert_awaited_once()
        process.assert_awaited_once()
    finally:
        await holder.dispose()


async def test_busy_scan_commit_loss_propagates_without_backoff_or_claim(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
) -> None:
    armed, dropped = asyncio.Event(), asyncio.Event()
    claim = AsyncMock()
    original_sleep = asyncio.sleep

    async def gate(session: Any) -> bool:
        assert await try_lock_order_selection(session) is False
        armed.set()
        return False

    async def sleep(seconds: float) -> None:
        assert seconds != 0.250, "backoff after ambiguous scan commit"
        await original_sleep(seconds)

    monkeypatch.setattr(paper_order, "try_lock_order_selection", gate)
    monkeypatch.setattr(paper_order, "claim_order", claim)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    async with scan_session_bypassing_rls(scan_engine) as holder:
        assert await try_lock_order_selection(holder)
        async with drop_commit_reply("127.0.0.1", 55432, armed, dropped) as port:
            proxy = create_async_engine(scan_engine.url.set(port=port), connect_args={"ssl": False})
            try:
                with pytest.raises(InfraError):
                    await run(engine_engine, proxy, coordinate_claims=True)
                assert cast(Any, proxy.pool).checkedout() == 0
            finally:
                await proxy.dispose()
    assert dropped.is_set()
    claim.assert_not_awaited()


@pytest.mark.parametrize("lost_commit_role", ["owner", "scan"])
async def test_lost_claim_commit_reply_stops_and_existing_lease_recovers(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
    lost_commit_role: str,
) -> None:
    armed, dropped = asyncio.Event(), asyncio.Event()
    original = claim_order
    attempts: list[ClaimedOrder] = []

    async def claim(*args: Any, **kwargs: Any) -> ClaimedOrder | None:
        value = await original(*args, **kwargs)
        assert value is not None
        attempts.append(value)
        armed.set()
        return value

    monkeypatch.setattr(paper_order, "claim_order", claim)
    process = AsyncMock()
    monkeypatch.setattr(paper_order, "process_claimed_order", process)
    async with drop_commit_reply("127.0.0.1", 55432, armed, dropped) as port:
        target = engine_engine if lost_commit_role == "owner" else scan_engine
        proxy = create_async_engine(target.url.set(port=port), connect_args={"ssl": False})
        try:
            with pytest.raises(InfraError):
                await run(
                    proxy if lost_commit_role == "owner" else engine_engine,
                    proxy if lost_commit_role == "scan" else scan_engine,
                    coordinate_claims=True,
                )
        finally:
            await proxy.dispose()
    assert dropped.is_set() and len(attempts) == 1
    process.assert_not_awaited()
    assert (
        cast(Any, engine_engine.pool).checkedout() == cast(Any, scan_engine.pool).checkedout() == 0
    )
    previous = attempts[0]
    async with user_session(engine_engine, previous.user_id, role=DatabaseRole.ENGINE) as session:
        await require_claim(session, previous)  # Server committed despite missing reply.
        await session.execute(
            """UPDATE paper_order_dispatch SET lease_until=clock_timestamp()-interval '1s'
            WHERE command_id=:id""",
            {"id": previous.command_id},
        )
    async with scan_session_bypassing_rls(scan_engine) as scan:
        assert await try_lock_order_selection(scan)
        due = next(
            value for value in await due_orders(scan) if value.command_id == previous.command_id
        )
    async with user_session(engine_engine, previous.user_id, role=DatabaseRole.ENGINE) as session:
        recovered = await claim_order(session, due, worker="recovery")
    assert recovered is not None and recovered.claim_id != previous.claim_id
    async with user_session(engine_engine, previous.user_id, role=DatabaseRole.ENGINE) as session:
        with pytest.raises(OrderClaimLostError):
            await require_claim(session, previous)
        await require_claim(session, recovered)


async def _child(stage: str) -> None:
    """Independent-process test barrier; stdout contains markers/UUIDs only."""
    engine, scan = (
        create_engine_for(DatabaseRole.ENGINE),
        create_engine_for(DatabaseRole.ENGINE_SCAN),
    )
    try:
        if stage == "gate":
            async with scan_session_bypassing_rls(scan, cleanup_seconds=2) as session:
                # Preserve the V1 blocking holder to prove mixed-version exclusion.
                await session.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(:key,0))",
                    {"key": "paper-order-selection:v1"},
                )
                sys.stdout.write("GATE\n")
                sys.stdout.flush()
                await asyncio.to_thread(sys.stdin.readline)
        else:

            async def process(session: Any, claim: ClaimedOrder, **kwargs: Any) -> None:
                sys.stdout.write(f"PROCESS {claim.command_id}\n")
                sys.stdout.flush()
                await asyncio.to_thread(sys.stdin.readline)

            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(paper_order, "process_claimed_order", process)
                while not (await run(engine, scan, coordinate_claims=True)).processed:
                    sys.stdout.write("BUSY\n")
                    sys.stdout.flush()
    finally:
        await engine.dispose()
        await scan.dispose()


@pytest.mark.parametrize("stage", ["gate", "process"])
async def test_independent_process_gate_and_crash_recovery(
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
    stage: str,
) -> None:
    processes: list[asyncio.subprocess.Process] = []

    async def launch(mode: str) -> asyncio.subprocess.Process:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import asyncio,sys; "
            "from tests.infra.execution_market.test_claim_coordination import _child; "
            "asyncio.run(_child(sys.argv[1]))",
            mode,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=os.environ.copy(),
        )
        processes.append(process)
        return process

    async def line(process: asyncio.subprocess.Process) -> str:
        assert process.stdout is not None
        return (await asyncio.wait_for(process.stdout.readline(), 4)).decode().strip()

    try:
        first = await launch(stage)
        marker = await line(first)
        assert marker.startswith("GATE" if stage == "gate" else "PROCESS ")
        second = await launch("process")
        if stage == "gate":
            assert await line(second) == "BUSY"
            first.kill()
            await asyncio.wait_for(first.wait(), 3)
            async with asyncio.timeout(4):
                while (marker := await line(second)) == "BUSY":
                    pass
            assert marker.startswith("PROCESS ")
        else:
            other = await line(second)
            assert other.startswith("PROCESS ") and marker != other
            first.kill()  # One committed owner remains leased; another owner still progressed.
            await asyncio.wait_for(first.wait(), 3)
        assert second.stdin is not None
        second.stdin.write(b"release\n")
        await second.stdin.drain()
        assert await asyncio.wait_for(second.wait(), 3) == 0
        async with asyncio.timeout(3), scan_session_bypassing_rls(scan_engine) as scan:
            assert await try_lock_order_selection(scan)
    finally:
        for process in processes:
            if process.returncode is None:
                process.kill()
            await process.wait()
    assert cast(Any, scan_engine.pool).checkedout() == 0


@pytest.mark.parametrize("lost_role", ["scan", "owner"])
async def test_connection_loss_does_not_fallback_or_claim_again(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
    lost_role: str,
) -> None:
    attempts = 0
    process = AsyncMock()
    monkeypatch.setattr(paper_order, "process_claimed_order", process)

    async def broken_lock(session: Any) -> bool:
        assert await try_lock_order_selection(session)
        await session.execute("SELECT pg_terminate_backend(pg_backend_pid())")
        raise AssertionError("terminated connection returned")

    async def broken_claim(session: Any, due: DueOrder, **kwargs: Any) -> ClaimedOrder | None:
        nonlocal attempts
        attempts += 1
        result = await claim_order(session, due, **kwargs)
        await session.execute("SELECT pg_terminate_backend(pg_backend_pid())")
        return result

    monkeypatch.setattr(
        paper_order,
        "try_lock_order_selection",
        broken_lock if lost_role == "scan" else try_lock_order_selection,
    )
    monkeypatch.setattr(paper_order, "claim_order", broken_claim)
    with pytest.raises(InfraError):
        await run(engine_engine, scan_engine, coordinate_claims=True)
    assert attempts == (0 if lost_role == "scan" else 1)
    process.assert_not_awaited()
    async with scan_session_bypassing_rls(scan_engine) as scan:
        assert await try_lock_order_selection(scan)
        assert {row.user_id for row in await due_orders(scan)} == {
            owner for owner, _ in queued_owners
        }


async def test_legacy_worker_cannot_duplicate_a_gated_claim(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
) -> None:
    stale = asyncio.Event()
    proceed = asyncio.Event()
    processed_one = asyncio.Event()
    processed_two = asyncio.Event()
    release = asyncio.Event()
    processed: list[UUID] = []

    async def scan(*args: Any, **kwargs: Any) -> tuple[DueOrder, ...]:
        rows = await due_orders(*args, **kwargs)
        task = asyncio.current_task()
        if task is not None and task.get_name() == "legacy":
            stale.set()
            await proceed.wait()
        return rows

    async def process(session: Any, claim: ClaimedOrder, **kwargs: Any) -> None:
        processed.append(claim.command_id)
        processed_one.set()
        if len(processed) == 2:
            processed_two.set()
        await release.wait()

    monkeypatch.setattr(paper_order, "due_orders", scan)
    monkeypatch.setattr(paper_order, "process_claimed_order", process)
    tasks = [asyncio.create_task(run(engine_engine, scan_engine), name="legacy")]
    try:
        async with asyncio.timeout(5):
            await stale.wait()
            tasks.append(
                asyncio.create_task(run(engine_engine, scan_engine, coordinate_claims=True))
            )
            await processed_one.wait()
            proceed.set()
            await processed_two.wait()
        assert set(processed) == {ids[0] for _, ids in queued_owners}
    finally:
        proceed.set()
        release.set()
        await asyncio.gather(*tasks)


@pytest.mark.parametrize("kind", ["user", "scan"])
@pytest.mark.parametrize("bound", [0, -1, True, float("nan"), float("inf")])
async def test_invalid_cleanup_bound_rejected_before_checkout(kind: str, bound: Any) -> None:
    engine = cast(AsyncEngine, object())
    context = (
        user_session(engine, uuid4(), cleanup_seconds=bound)
        if kind == "user"
        else scan_session_bypassing_rls(engine, cleanup_seconds=bound)
    )
    with pytest.raises(ValueError, match="positive finite"):
        async with context:
            pytest.fail("session opened")


@pytest.mark.parametrize("kind", ["user", "scan"])
async def test_session_wrapper_forwards_bounded_cleanup_and_retains_primary_error(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    kind: str,
) -> None:
    from tiewtrade.infra.db import session as db

    original = db._begin
    seen: list[float | None] = []
    primary = RuntimeError("controlled body error")

    @asynccontextmanager
    async def begin(
        engine: AsyncEngine, *, cleanup_seconds: float | None = None
    ) -> AsyncIterator[Any]:
        seen.append(cleanup_seconds)
        async with original(engine, cleanup_seconds=cleanup_seconds) as connection:
            yield connection

    monkeypatch.setattr(db, "_begin", begin)
    context = (
        user_session(engine_engine, uuid4(), role=DatabaseRole.ENGINE, cleanup_seconds=2)
        if kind == "user"
        else scan_session_bypassing_rls(scan_engine, cleanup_seconds=2)
    )
    with pytest.raises(RuntimeError) as caught:
        async with context as session:
            await session.execute("SELECT 1")
            raise primary
    assert caught.value is primary and seen == [2]
    assert (
        cast(Any, engine_engine.pool).checkedout() == cast(Any, scan_engine.pool).checkedout() == 0
    )


async def test_deadline_includes_scan_pool_checkout(
    monkeypatch: pytest.MonkeyPatch, engine_engine: AsyncEngine, scan_engine: AsyncEngine
) -> None:
    bounded = create_async_engine(scan_engine.url, pool_size=1, max_overflow=0)
    original_timeout = asyncio.timeout
    monkeypatch.setattr(
        asyncio, "timeout", lambda seconds: original_timeout(0.1 if seconds == 5 else seconds)
    )
    gate = AsyncMock(side_effect=AssertionError("gate reached without connection"))
    monkeypatch.setattr(paper_order, "try_lock_order_selection", gate)
    try:
        async with bounded.connect():
            with pytest.raises(TimeoutError):
                await run(engine_engine, bounded, coordinate_claims=True)
        gate.assert_not_awaited()
        async with scan_session_bypassing_rls(bounded) as scan:
            assert await try_lock_order_selection(scan)
        assert cast(Any, bounded.pool).checkedout() == 0
    finally:
        await bounded.dispose()


async def test_processing_cancellation_keeps_claim_for_fenced_recovery(
    monkeypatch: pytest.MonkeyPatch,
    engine_engine: AsyncEngine,
    scan_engine: AsyncEngine,
    queued_owners: list[tuple[UUID, list[UUID]]],
) -> None:
    entered = asyncio.Event()
    claims: list[ClaimedOrder] = []

    async def process(session: Any, claim: ClaimedOrder, **kwargs: Any) -> None:
        await require_claim(session, claim)
        claims.append(claim)
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(paper_order, "process_claimed_order", process)
    task = asyncio.create_task(run(engine_engine, scan_engine, coordinate_claims=True))
    try:
        await asyncio.wait_for(entered.wait(), 3)
        async with asyncio.timeout(1), scan_session_bypassing_rls(scan_engine) as scan:
            assert await try_lock_order_selection(scan)  # Processing does not hold the coordinator.
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert len(claims) == 1
    async with user_session(engine_engine, claims[0].user_id, role=DatabaseRole.ENGINE) as session:
        await require_claim(session, claims[0])
        assert (
            await session.execute("SELECT count(*) FROM paper_order_command_results")
        ).scalar_one() == 0
    assert (
        cast(Any, engine_engine.pool).checkedout() == cast(Any, scan_engine.pool).checkedout() == 0
    )
