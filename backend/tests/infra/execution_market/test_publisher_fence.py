"""Real PG read-only blocker identity, bounded monitor and opt-in isolation."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.infra.execution_market.profile_owned_pools import parent_configuration
from tests.infra.execution_market.profile_publisher_fence import FenceObservation
from tests.infra.execution_market.profile_publisher_lease_load import validate_options
from tests.infra.execution_market.test_publisher_clock_recovery import (
    published_market as published_market,
)
from tiewtrade.infra.db import DatabaseRole, create_engine_for
from tiewtrade.infra.db.session import market_data_session, user_session


class QueryResult:
    """Existing query-result double shared by sampler transition and failure tests."""

    def __init__(self, rows: Any = None) -> None:
        self.rows = rows or []

    def scalar_one(self) -> Any:
        return datetime.now(UTC)

    def mappings(self) -> Any:
        return self.rows


@pytest.mark.parametrize(
    "option",
    [
        {"publisher_lease_observer": False},
        {"phase": "W3"},
        {"worker_only": True},
        {"publisher_clock_recovery": True},
        {"diagnostics": True},
        {"controlled_delay": True},
    ],
)
def test_fence_scope_rejected(option: dict[str, Any]) -> None:
    args = argparse.Namespace(
        **{
            "publisher_fence_observer": True,
            "publisher_lease_observer": True,
            "phase": "SMOKE",
            "acceptance_profile": "PAPER_INTERNAL20_V1",
            **option,
        }
    )
    with pytest.raises(ValueError):
        validate_options(args)


@pytest.mark.usefixtures("internal_database")
async def test_readonly_and_actual_shared_holder_exclusive_waiter() -> None:
    observer = FenceObservation(lambda: None)
    financial = create_engine_for(DatabaseRole.ENGINE)
    publisher = create_engine_for(DatabaseRole.MARKET_DATA)
    task = None
    entered = asyncio.Event()
    pid: list[int] = []
    try:
        async with observer.engine.connect() as connection:
            assert (
                await connection.execute(text("SHOW transaction_read_only"))
            ).scalar_one() == "on"
            with pytest.raises(DBAPIError) as caught:
                await connection.execute(
                    text("UPDATE risk_price_publication SET watermark=watermark")
                )
            assert getattr(caught.value.orig, "sqlstate", None) == "25006"
        async with user_session(financial, uuid4(), role=DatabaseRole.ENGINE) as session:
            holder = (await session.execute("SELECT pg_backend_pid()")).scalar_one()
            await session.execute("SELECT risk_financial_fence()")

            async def wait_for_fence() -> None:
                async with market_data_session(publisher) as current:
                    pid.append((await current.execute("SELECT pg_backend_pid()")).scalar_one())
                    entered.set()
                    await current.execute("SELECT risk_publication_fence()")

            task = asyncio.create_task(wait_for_fence())
            await asyncio.wait_for(entered.wait(), 2)
            snapshot = None
            for _ in range(10):
                snapshot = await observer.sample(
                    {"backend_pid": pid[0], "stage": "price_renew", "started": monotonic()}
                )
                waiter = next(row for row in snapshot["activity"] if row["pid"] == pid[0])
                if holder in waiter["blocking_pids"]:
                    break
                await asyncio.sleep(0.02)
            assert snapshot is not None and holder in waiter["blocking_pids"]
            assert waiter["wait_event_type"] == "Lock"
            assert any(row["pid"] == pid[0] and not row["granted"] for row in snapshot["locks"])
            assert all(
                "query" not in row and "query_text" not in row for row in snapshot["activity"]
            )
        await asyncio.wait_for(task, 2)
    finally:
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await observer.close()
        await financial.dispose()
        await publisher.dispose()


@pytest.mark.usefixtures("internal_database")
async def test_monitor_bounds_join_and_query_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    statement = {"backend_pid": 1, "stage": "price_renew", "started": monotonic() - 2}
    trace = type("Trace", (), {"statements": [statement]})()
    observer = FenceObservation(lambda: trace)
    counter = 0

    async def sample(_statement: Any) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        if counter == 70:
            raise OSError("PRIVATE_ERROR")
        return {"sequence": counter}

    monkeypatch.setattr(observer, "sample", sample)
    # Accelerate only idle monitor scheduling; no DB operation or lease is mocked here.
    original_wait = asyncio.wait_for

    async def immediate(awaitable: Any, timeout: float) -> Any:
        return await original_wait(awaitable, timeout=0.0001 if timeout == 0.25 else timeout)

    monkeypatch.setattr(asyncio, "wait_for", immediate)
    observer.start()
    assert observer.task is not None
    await original_wait(observer.task, 3)
    await observer.close()
    report = observer.report()
    assert report["total_samples"] == 69 and len(report["observations"]) == 64
    assert report["errors"] == {"OSError": 1} and report["task_joined"]
    assert "PRIVATE" not in json.dumps(report)


def test_fence_pool_inventory_is_additive_and_explicit() -> None:
    original = parent_configuration(publisher_lease_observer=True)
    both = parent_configuration(publisher_lease_observer=True, publisher_fence_observer=True)
    assert both == [*original, ("ADMIN_OBSERVER", 5, 10)]
    with pytest.raises(ValueError):
        parent_configuration(publisher_fence_observer=True)


@pytest.mark.usefixtures("internal_database")
async def test_sampler_error_keeps_partial_evidence_and_primary(tmp_path: Any) -> None:
    from unittest.mock import Mock

    from tests.infra.execution_market.profile_publisher_lease_load import LoadLeaseObserver

    observer = LoadLeaseObserver(tmp_path, {"write_failed": False}, fence_observer=True)
    report = {"errors": {"TimeoutError": 1}, "task_joined": True, "observations": []}
    observer.fence = Mock(errors=report["errors"], report=Mock(return_value=report))
    observer.outcomes["RETURNED"] = 1
    observer.guard_calls = 1
    (tmp_path / "publisher-readiness.json").write_text(
        json.dumps(
            {
                "scope": "parent publish_market readiness guards only",
                "checks": [{}],
                "total_checks": 1,
                "discarded_earlier_checks": 0,
                "flush_reason": "RuntimeError",
            }
        )
    )
    (tmp_path / "result.json").write_text(json.dumps({"status": "PASSED"}))
    error = RuntimeError("PRIVATE")
    with pytest.raises(RuntimeError) as caught, observer.observe():
        raise error
    assert caught.value is error and error.__notes__
    assert json.loads((tmp_path / "result.json").read_text())["status"] == "INCOMPLETE"
    saved = json.loads((tmp_path / "publisher-lease.json").read_text())
    assert saved["fence_observation"] == report and "PRIVATE" not in json.dumps(saved)


async def test_live_monitor_observes_wait_without_changing_publication(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    published_market: Any,
) -> None:
    from tests.infra.execution_market import profile_workload as workload
    from tests.infra.execution_market.profile_owned_pools import OwnedPools
    from tests.infra.execution_market.profile_publisher_lease_load import LoadLeaseObserver
    from tests.infra.execution_market.profile_publisher_readiness import observe_publisher_readiness

    engine, book, price = published_market

    async def publisher(*args: Any, **kwargs: Any) -> Any:
        return await workload.publish_market(
            engine,
            book,
            price,
            rebase=False,
            trade_id=2,
            update_price=False,
            heartbeat_per_book=True,
        )

    monkeypatch.setattr(workload, "market_publisher", publisher)
    status = {"write_failed": False}
    observer = LoadLeaseObserver(tmp_path, status, fence_observer=True)
    financial = create_engine_for(DatabaseRole.ENGINE)
    task = None
    try:
        with (
            OwnedPools(tmp_path / "pools.json", [("MARKET_DATA", 1, 0), ("ADMIN_OBSERVER", 5, 10)]),
            observer.observe(),
            observe_publisher_readiness(
                tmp_path / "publisher-readiness.json", evidence_status=status
            ),
        ):
            async with user_session(financial, uuid4(), role=DatabaseRole.ENGINE) as current:
                holder = (await current.execute("SELECT pg_backend_pid()")).scalar_one()
                await current.execute("SELECT risk_financial_fence()")
                task = asyncio.create_task(workload.market_publisher(engine, asyncio.Event(), {}))
                async with asyncio.timeout(3):
                    while observer.fence is None or not observer.fence.rows:
                        await asyncio.sleep(0.02)
                snapshot = observer.fence.rows[-1]
                assert snapshot["statement_association"] == "ACTIVE_THROUGH_CAPTURE"
                assert not snapshot["views_atomic"]
                waiter = next(
                    r for r in snapshot["activity"] if r["pid"] == snapshot["publisher_pid"]
                )
                assert holder in waiter["blocking_pids"]
            await asyncio.wait_for(task, 2)
        report = json.loads((tmp_path / "publisher-lease.json").read_text())
        assert report["counts"] == {"RETURNED": 1}
        assert (
            report["fence_observation"]["task_joined"] and not report["fence_observation"]["errors"]
        )
        assert json.loads((tmp_path / "pools.json").read_text())["passed"]
    finally:
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await financial.dispose()


@pytest.mark.parametrize(
    "repeat_cancel,dispose_error", [(False, False), (True, False), (True, True)]
)
@pytest.mark.usefixtures("internal_database")
async def test_cancelled_close_joins_before_disposal_and_preserves_cancellation(
    monkeypatch: pytest.MonkeyPatch,
    repeat_cancel: bool,
    dispose_error: bool,
) -> None:
    observer = FenceObservation(lambda: None)
    monitor_started, monitor_finishing, finish_monitor = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )
    dispose_started, finish_dispose = asyncio.Event(), asyncio.Event()
    original_dispose = observer.engine.dispose

    async def monitor() -> None:
        monitor_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            monitor_finishing.set()
            await finish_monitor.wait()

    async def dispose() -> None:
        assert observer.task is not None and observer.task.done()
        dispose_started.set()
        await finish_dispose.wait()
        await original_dispose()
        if dispose_error:
            raise OSError("PRIVATE_DISPOSE")

    monkeypatch.setattr(observer, "monitor", monitor)
    from types import SimpleNamespace

    monkeypatch.setattr(observer, "engine", SimpleNamespace(dispose=dispose))
    observer.start()
    await asyncio.wait_for(monitor_started.wait(), 1)
    closing = asyncio.create_task(observer.close())
    try:
        await asyncio.sleep(0)
        closing.cancel("ORIGINAL_CANCEL")
        await asyncio.wait_for(monitor_finishing.wait(), 1)
        assert not dispose_started.is_set() and not closing.done()
        if repeat_cancel:
            closing.cancel("LATER_CANCEL")
            await asyncio.sleep(0)
            assert not dispose_started.is_set()
        finish_monitor.set()
        await asyncio.wait_for(dispose_started.wait(), 1)
        if repeat_cancel:
            closing.cancel("DISPOSE_CANCEL")
            await asyncio.sleep(0)
            assert not closing.done()
        finish_dispose.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await asyncio.wait_for(closing, 1)
        assert caught.value.args == ("ORIGINAL_CANCEL",)
        assert observer.task is not None and observer.task.done()
        assert observer.cleanup_task is not None and observer.cleanup_task.done()
        if dispose_error:
            assert any("OSError" in note for note in caught.value.__notes__)
            assert all("PRIVATE" not in note for note in caught.value.__notes__)
    finally:
        finish_monitor.set()
        finish_dispose.set()
        if observer.task is not None and not observer.task.done():
            observer.task.cancel()
        await asyncio.gather(closing, return_exceptions=True)
        await original_dispose()


@pytest.mark.parametrize(
    "transition,expected_association",
    [
        ("none", "ACTIVE_THROUGH_CAPTURE"),
        ("activity", "OVERLAPPED_OR_UNCONFIRMED"),
        ("locks", "OVERLAPPED_OR_UNCONFIRMED"),
        ("already-finished", "COMPLETED_BEFORE_CAPTURE"),
        ("different-current", "OVERLAPPED_OR_UNCONFIRMED"),
    ],
)
@pytest.mark.usefixtures("internal_database")
async def test_snapshot_marks_statement_transition_without_losing_raw_views(
    monkeypatch: pytest.MonkeyPatch,
    transition: str,
    expected_association: str,
    tmp_path: Any,
) -> None:
    from contextlib import asynccontextmanager

    statement = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    if transition == "already-finished":
        statement["finished"] = monotonic() - 1
    from tests.infra.execution_market.profile_publisher_lease import LeaseTrace, Publication

    current = LeaseTrace(
        None, tmp_path / "unused", publication=Publication(2, False, True), sink=lambda row: None
    )
    current.statements.append(statement)
    observer = FenceObservation(lambda: current)
    original_engine = observer.engine

    class Connection:
        async def exec_driver_sql(self, _sql: str) -> None:
            pass

        async def execute(self, sql: Any, *_args: Any) -> QueryResult:
            activity = "pg_stat_activity" in str(sql)
            locks = "pg_locks" in str(sql)
            if (activity and transition == "activity") or (locks and transition == "locks"):
                statement["finished"] = monotonic()
                statement["stage"] = "different_stage"
                statement["backend_pid"] = 999
            if activity and transition == "different-current":
                current.statements = [{"stage": "following"}]
            if activity:
                return QueryResult([{"pid": 7, "blocking_pids": [8]}])
            if locks:
                return QueryResult([{"pid": 7, "mode": "ExclusiveLock", "granted": False}])
            return QueryResult()

    class Engine:
        @asynccontextmanager
        async def connect(self) -> Any:
            yield Connection()

    monkeypatch.setattr(observer, "engine", Engine())
    try:
        snapshot = await observer.sample(statement)
        assert snapshot["statement_association"] == expected_association
        assert snapshot["publisher_pid"] == 7 and snapshot["stage"] == "price_renew"
        assert snapshot["activity"][0]["blocking_pids"] == [8] and snapshot["locks"]
        assert not snapshot["views_atomic"]
        assert snapshot["capture_started"] <= snapshot["activity_interval"][0]
        assert snapshot["activity_interval"][1] <= snapshot["locks_interval"][0]
        assert snapshot["locks_interval"][1] <= snapshot["observed_at"]
        if transition in {"activity", "locks", "already-finished"}:
            assert snapshot["statement_finished_at_end"] is not None
    finally:
        await original_engine.dispose()


@pytest.mark.usefixtures("internal_database")
async def test_cancelled_close_returns_real_readonly_connection(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.infra.execution_market.profile_owned_pools import OwnedPools
    from tests.infra.execution_market.profile_publisher_lease import LeaseTrace, Publication

    entered = asyncio.Event()
    trace = LeaseTrace(
        None, tmp_path / "unused", publication=Publication(2, False, True), sink=lambda row: None
    )
    trace.statements.append({"backend_pid": 1, "stage": "test-read", "started": monotonic() - 2})
    with OwnedPools(tmp_path / "real-cleanup.json", [("ADMIN_OBSERVER", 5, 10)]) as tracker:
        observer = FenceObservation(lambda: trace)

        async def pending_read(_statement: Any) -> dict[str, Any]:
            async with observer.engine.connect() as connection:
                entered.set()
                await connection.execute(text("SELECT pg_sleep(1)"))
            return {}

        monkeypatch.setattr(observer, "sample", pending_read)
        observer.start()
        closing = None
        try:
            await asyncio.wait_for(entered.wait(), 1)
            tracker.begin_quiescence()
            closing = asyncio.create_task(observer.close())
            await asyncio.sleep(0)
            closing.cancel("CLOSE_CANCELLED")
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(closing, 2)
            assert observer.task is not None and observer.task.done()
            assert observer.cleanup_task is not None and observer.cleanup_task.done()
        finally:
            if closing is not None:
                await asyncio.gather(closing, return_exceptions=True)
            await observer.close()
    assert json.loads((tmp_path / "real-cleanup.json").read_text())["passed"]
