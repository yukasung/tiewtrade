"""Bounded failure context for the existing readonly fence sampler."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from time import monotonic
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from tests.infra.execution_market.profile_publisher_fence import FenceObservation
from tests.infra.execution_market.profile_publisher_lease import LeaseTrace
from tests.infra.execution_market.test_publisher_fence import QueryResult


@pytest.mark.parametrize(
    "fault,last_complete,activity_count,locks_count,error_class",
    [
        ("checkout", "statement_identity", None, None, TimeoutError),
        ("statement_timeout", "checkout", None, None, TimeoutError),
        ("lock_timeout", "statement_timeout", None, None, TimeoutError),
        ("db_clock", "lock_timeout", None, None, TimeoutError),
        ("activity", "db_clock", None, None, TimeoutError),
        ("locks", "activity", 1, None, TimeoutError),
        ("session_exit", "locks", 1, 1, TimeoutError),
        pytest.param("locks", "activity", 1, None, asyncio.CancelledError, id="cancelled-locks"),
    ],
)
@pytest.mark.parametrize("transition", ["none", "during", "different-current"])
@pytest.mark.usefixtures("internal_database")
async def test_failure_envelope_identifies_completed_steps_without_private_data(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
    last_complete: str,
    activity_count: int | None,
    locks_count: int | None,
    transition: str,
    error_class: type[BaseException],
) -> None:
    statement = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    trace = SimpleNamespace(statements=[statement], publication=SimpleNamespace(tick=42))
    observer = FenceObservation(lambda: cast(LeaseTrace, trace))
    original_engine = observer.engine
    primary = error_class("PRIVATE query=SECRET cookie=TOKEN")
    calls: list[str] = []

    def step(phase: str) -> None:
        calls.append(phase)
        if phase == fault:
            if transition == "during":
                statement.update(finished=monotonic(), backend_pid=999, stage="changed")
                trace.publication.tick = 99
            elif transition == "different-current":
                trace.statements = [{"stage": "following"}]
            raise primary

    class Connection:
        async def exec_driver_sql(self, sql: str) -> None:
            step("statement_timeout" if "statement_timeout" in sql else "lock_timeout")

        async def execute(self, sql: Any, *args: Any) -> QueryResult:
            if "pg_stat_activity" in str(sql):
                step("activity")
                return QueryResult([{"pid": 7, "blocking_pids": [8]}])
            if "pg_locks" in str(sql):
                step("locks")
                return QueryResult([{"pid": 7, "mode": "ExclusiveLock", "granted": False}])
            step("db_clock")
            return QueryResult()

    @asynccontextmanager
    async def connect() -> Any:
        step("checkout")
        yield Connection()
        step("session_exit")

    monkeypatch.setattr(observer, "engine", SimpleNamespace(connect=connect, dispose=AsyncMock()))
    try:
        with pytest.raises(error_class) as caught:
            await observer.sample(statement)
        assert caught.value is primary
        failure = observer.report()["failed_observation"]
        assert failure["capture_phase"] == fault
        assert failure["last_completed_phase"] == last_complete
        assert failure["activity_row_count"] == activity_count
        assert failure["locks_row_count"] == locks_count
        assert failure["publisher_pid"] == 7 and failure["stage"] == "price_renew"
        assert failure["publication_tick"] == 42
        expected = "ACTIVE_THROUGH_CAPTURE" if transition == "none" else "OVERLAPPED_OR_UNCONFIRMED"
        assert failure["statement_association"] == expected
        assert failure["capture_started"] <= failure["phase_started"] <= failure["observed_at"]
        assert datetime.fromisoformat(failure["failed_at"]).tzinfo is not None
        assert failure["error_type"] == error_class.__name__ and not failure["views_atomic"]
        assert len(failure["activity"]) == (activity_count or 0)
        assert len(failure["locks"]) == (locks_count or 0)
        assert observer.total == 0 and not observer.rows
        encoded = json.dumps(observer.report())
        assert all(private not in encoded for private in ("PRIVATE", "SECRET", "TOKEN", "SELECT"))
        assert calls[-1] == fault
        with pytest.raises(error_class):
            await observer.sample(statement)
        assert observer.report()["failed_observation"] is failure
    finally:
        await observer.close()
        await original_engine.dispose()


@pytest.mark.parametrize("overflow", ["activity", "locks"])
@pytest.mark.usefixtures("internal_database")
async def test_sampler_overflow_is_explicit_and_never_retains_unbounded_view(
    monkeypatch: pytest.MonkeyPatch, overflow: str
) -> None:
    statement = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    trace = SimpleNamespace(statements=[statement])
    observer = FenceObservation(lambda: cast(LeaseTrace, trace))
    original_engine = observer.engine

    class Connection:
        async def exec_driver_sql(self, sql: str) -> None:
            pass

        async def execute(self, sql: Any, *args: Any) -> QueryResult:
            if "pg_stat_activity" in str(sql):
                return QueryResult([{"pid": 7}] * (129 if overflow == "activity" else 1))
            if "pg_locks" in str(sql):
                return QueryResult([{"pid": 7}] * 8193)
            return QueryResult()

    @asynccontextmanager
    async def connect() -> Any:
        yield Connection()

    monkeypatch.setattr(observer, "engine", SimpleNamespace(connect=connect, dispose=AsyncMock()))
    try:
        with pytest.raises(ValueError, match="exceeds bound"):
            await observer.sample(statement)
        failure = observer.report()["failed_observation"]
        assert failure["capture_phase"] == overflow
        assert failure[f"{overflow}_row_count"] == (129 if overflow == "activity" else 8193)
        assert failure[overflow] == []
        assert len(failure["activity"]) <= 128 and len(failure["locks"]) <= 8192
    finally:
        await observer.close()
        await original_engine.dispose()


@pytest.mark.usefixtures("internal_database")
async def test_real_sampler_timeout_records_activity_phase_and_returns_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncConnection

    statement = {"backend_pid": 7, "stage": "price_renew", "started": monotonic() - 2}
    trace = SimpleNamespace(statements=[statement], publication=SimpleNamespace(tick=42))
    observer = FenceObservation(lambda: cast(LeaseTrace, trace))
    execute = AsyncConnection.execute
    injections = 0

    async def delayed_activity(connection: Any, sql: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal injections
        if "pg_stat_activity" in str(sql):
            injections += 1
            # Existing server500ms and overall1s deadlines remain active on real PG.
            await execute(connection, text("SELECT pg_sleep(0.6)"))
        return await execute(connection, sql, *args, **kwargs)

    monkeypatch.setattr(AsyncConnection, "execute", delayed_activity)
    observer.start()
    try:
        assert observer.task is not None
        await asyncio.wait_for(observer.task, 3)
        report = observer.report()
        assert injections == 1 and sum(report["errors"].values()) == 1
        assert report["total_samples"] == 0 and report["observations"] == []
        failure = report["failed_observation"]
        assert failure["capture_phase"] == "activity"
        assert failure["last_completed_phase"] == "db_clock"
        assert failure["activity_row_count"] is None and failure["activity"] == []
        assert failure["error_type"] in report["errors"]
        assert "pg_sleep" not in json.dumps(report) and "SELECT" not in json.dumps(report)
        assert observer.engine.pool.checkedout() == 0  # type: ignore[attr-defined]
        async with observer.engine.connect() as connection:
            assert (
                await connection.execute(text("SHOW transaction_read_only"))
            ).scalar_one() == "on"
            assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1
    finally:
        await observer.close()
    assert observer.report()["task_joined"]


@pytest.mark.usefixtures("internal_database")
async def test_missing_statement_identity_is_recorded_without_inventing_backend_pid() -> None:
    statement = {"stage": "price_renew", "started": monotonic() - 2}
    trace = SimpleNamespace(statements=[statement])
    observer = FenceObservation(lambda: cast(LeaseTrace, trace))
    observer.start()
    try:
        assert observer.task is not None
        await asyncio.wait_for(observer.task, 2)
        report = observer.report()
        assert report["errors"] == {"KeyError": 1} and report["total_samples"] == 0
        failure = report["failed_observation"]
        assert failure["publisher_pid"] is None and failure["publication_tick"] is None
        assert failure["capture_phase"] == "statement_identity"
        assert failure["last_completed_phase"] is None and failure["db_now"] is None
    finally:
        await observer.close()
